import logging
from pathlib import Path

from ..config import get_settings
from ..db import get_db
from .el_client import get_el_client

logger = logging.getLogger(__name__)


def transcribe_answer(answer_id: int) -> None:
    """Background task: Scribe-transcribe one interview answer."""
    conn = get_db()
    try:
        row = conn.execute("SELECT audio_path FROM interview_answers WHERE id = ?", (answer_id,)).fetchone()
        if not row:
            return
        conn.execute("UPDATE interview_answers SET status = 'transcribing' WHERE id = ?", (answer_id,))
        conn.commit()
        try:
            settings = get_settings()
            client = get_el_client()
            with open(row["audio_path"], "rb") as f:
                result = client.speech_to_text.convert(file=f, model_id=settings.stt_model_id)
            conn.execute(
                "UPDATE interview_answers SET transcript = ?, language_code = ?, status = 'transcribed', error = NULL WHERE id = ?",
                (result.text, getattr(result, "language_code", None), answer_id),
            )
        except Exception as exc:
            logger.exception("Transcription failed for answer %s", answer_id)
            conn.execute(
                "UPDATE interview_answers SET status = 'error', error = ? WHERE id = ?",
                (str(exc), answer_id),
            )
        conn.commit()
    finally:
        conn.close()


def delete_answer_audio(audio_path: str) -> None:
    try:
        Path(audio_path).unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete audio file %s", audio_path)
