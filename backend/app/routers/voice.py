from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..db import get_db
from ..services.voice_clone import IVCVoiceCloner, generate_preview, select_samples

router = APIRouter()


class PreviewRequest(BaseModel):
    text: str = "Hello! This is my digital persona speaking. Pretty close, right?"


@router.post("/clone")
def clone_voice() -> dict:
    conn = get_db()
    try:
        persona = conn.execute("SELECT * FROM persona WHERE id = 1").fetchone()
        if not persona:
            raise HTTPException(400, "Create the persona first")
        try:
            samples = select_samples(conn)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        try:
            voice_id = IVCVoiceCloner().create(persona["name"], samples)
        except Exception as exc:
            raise HTTPException(502, f"Voice clone failed: {exc}")
        new_status = "agent_ready" if persona["agent_id"] else "voice_ready"
        conn.execute(
            """
            UPDATE persona SET voice_id = ?, voice_kind = 'ivc', status = ?,
                   updated_at = datetime('now') WHERE id = 1
            """,
            (voice_id, new_status),
        )
        conn.commit()
        return {"voice_id": voice_id, "samples_used": len(samples), "status": new_status}
    finally:
        conn.close()


@router.post("/preview")
def preview_voice(body: PreviewRequest) -> Response:
    conn = get_db()
    try:
        persona = conn.execute("SELECT voice_id FROM persona WHERE id = 1").fetchone()
    finally:
        conn.close()
    if not persona or not persona["voice_id"]:
        raise HTTPException(400, "No cloned voice yet (POST /api/voice/clone)")
    try:
        audio = generate_preview(persona["voice_id"], body.text)
    except Exception as exc:
        raise HTTPException(502, f"TTS preview failed: {exc}")
    return Response(content=audio, media_type="audio/mpeg")
