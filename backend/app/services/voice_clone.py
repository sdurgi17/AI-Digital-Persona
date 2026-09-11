import logging
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from ..config import get_settings
from .el_client import get_el_client

logger = logging.getLogger(__name__)

MIN_TOTAL_SECONDS = 60
MAX_TOTAL_SECONDS = 180


class VoiceCloner(Protocol):
    def create(self, name: str, sample_paths: list[Path]) -> str:
        """Create a voice clone from audio samples; returns an ElevenLabs voice_id.
        PVCVoiceCloner implements the professional flow behind this same interface later."""
        ...


def select_samples(conn: sqlite3.Connection) -> list[Path]:
    """Prefer voice_sample answers, then longest others, until 60–180s total."""
    rows = conn.execute(
        """
        SELECT a.audio_path, a.duration_seconds, q.category
        FROM interview_answers a JOIN interview_questions q ON q.id = a.question_id
        WHERE a.status IN ('transcribed', 'recorded', 'transcribing')
        ORDER BY (q.category = 'voice_sample') DESC, a.duration_seconds DESC
        """
    ).fetchall()
    selected: list[Path] = []
    total = 0.0
    for row in rows:
        duration = row["duration_seconds"] or 0
        if total >= MAX_TOTAL_SECONDS:
            break
        selected.append(Path(row["audio_path"]))
        total += duration
    if total < MIN_TOTAL_SECONDS:
        raise ValueError(
            f"Only {total:.0f}s of recorded audio; need at least {MIN_TOTAL_SECONDS}s "
            "for a good clone. Record more (or longer) interview answers."
        )
    return selected


def _convert_to_mp3(paths: list[Path], tmpdir: Path) -> list[Path]:
    """webm/opus → mp3 via ffmpeg when available; otherwise upload webm as-is
    (ElevenLabs accepts most audio formats; mp3 is just the safest path)."""
    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg not found; uploading webm samples directly")
        return paths
    converted = []
    for path in paths:
        out = tmpdir / (path.stem + ".mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(path), "-b:a", "192k", str(out)],
            check=True,
            capture_output=True,
        )
        converted.append(out)
    return converted


class IVCVoiceCloner:
    def create(self, name: str, sample_paths: list[Path]) -> str:
        client = get_el_client()
        with tempfile.TemporaryDirectory() as tmp:
            files = _convert_to_mp3(sample_paths, Path(tmp))
            handles = [open(f, "rb") for f in files]
            try:
                voice = client.voices.ivc.create(
                    name=f"{name} (digital persona)",
                    files=handles,
                    remove_background_noise=True,
                )
            finally:
                for h in handles:
                    h.close()
        if getattr(voice, "requires_verification", False):
            logger.warning("Voice %s requires verification in the ElevenLabs dashboard", voice.voice_id)
        return voice.voice_id


def generate_preview(voice_id: str, text: str) -> bytes:
    settings = get_settings()
    client = get_el_client()
    audio = client.text_to_speech.convert(
        voice_id=voice_id, text=text, model_id=settings.tts_model_id
    )
    return b"".join(audio)
