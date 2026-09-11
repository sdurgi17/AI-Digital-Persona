import uuid

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import get_settings
from ..db import get_db
from ..services.transcription import delete_answer_audio, transcribe_answer

router = APIRouter()


@router.get("/questions")
def list_questions() -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT q.id, q.ord, q.category, q.text, q.min_seconds,
                   a.id AS answer_id, a.status AS answer_status,
                   a.duration_seconds, a.transcript, a.language_code, a.error
            FROM interview_questions q
            LEFT JOIN interview_answers a ON a.question_id = q.id
            ORDER BY q.ord
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/answers/{question_id}")
async def submit_answer(
    question_id: int,
    audio: UploadFile,
    background: BackgroundTasks,
    duration_seconds: float = Form(0),
) -> dict:
    settings = get_settings()
    conn = get_db()
    try:
        question = conn.execute(
            "SELECT id FROM interview_questions WHERE id = ?", (question_id,)
        ).fetchone()
        if not question:
            raise HTTPException(404, "Question not found")

        # Re-recording replaces the previous answer
        old = conn.execute(
            "SELECT id, audio_path FROM interview_answers WHERE question_id = ?", (question_id,)
        ).fetchone()
        if old:
            delete_answer_audio(old["audio_path"])
            conn.execute("DELETE FROM interview_answers WHERE id = ?", (old["id"],))

        suffix = ".webm"
        if audio.filename and "." in audio.filename:
            suffix = "." + audio.filename.rsplit(".", 1)[1]
        path = settings.interview_audio_dir / f"q{question_id}_{uuid.uuid4().hex[:8]}{suffix}"
        path.write_bytes(await audio.read())

        cur = conn.execute(
            "INSERT INTO interview_answers (question_id, audio_path, duration_seconds) VALUES (?, ?, ?)",
            (question_id, str(path), duration_seconds),
        )
        conn.commit()
        answer_id = cur.lastrowid
    finally:
        conn.close()

    background.add_task(transcribe_answer, answer_id)
    return {"answer_id": answer_id, "status": "recorded"}


@router.get("/answers/{answer_id}/audio")
def get_answer_audio(answer_id: int) -> FileResponse:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT audio_path FROM interview_answers WHERE id = ?", (answer_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "Answer not found")
    return FileResponse(row["audio_path"])


@router.get("/progress")
def progress() -> dict:
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS answered,
                   COALESCE(SUM(duration_seconds), 0) AS total_seconds,
                   SUM(CASE WHEN status = 'transcribed' THEN 1 ELSE 0 END) AS transcribed
            FROM interview_answers
            """
        ).fetchone()
        total_questions = conn.execute("SELECT COUNT(*) FROM interview_questions").fetchone()[0]
        return {
            "answered": row["answered"],
            "transcribed": row["transcribed"] or 0,
            "total_questions": total_questions,
            "total_seconds": row["total_seconds"],
            "enough_audio_for_clone": row["total_seconds"] >= 60,
        }
    finally:
        conn.close()
