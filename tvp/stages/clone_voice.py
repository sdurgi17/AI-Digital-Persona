"""Stage 7 — clone_voice.

Calls ElevenLabs Instant Voice Cloning, archives the audio sample under
`personas/<name>/source_audio.<ext>`, and writes `voice_id.txt`.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from tvp.config import TvpConfig

log = logging.getLogger(__name__)


def _eleven_client(cfg: TvpConfig):
    if not cfg.secrets.elevenlabs_api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY not set. Add it to .env or your environment."
        )
    from elevenlabs.client import ElevenLabs  # type: ignore

    return ElevenLabs(api_key=cfg.secrets.elevenlabs_api_key)


def clone_voice(
    cfg: TvpConfig,
    persona_name: str,
    voice_audio: Path,
    persona_dir: Path,
) -> str:
    """Submit the audio sample for cloning. Returns the ElevenLabs voice_id."""
    if not voice_audio.exists():
        raise FileNotFoundError(f"voice audio not found: {voice_audio}")

    archived = persona_dir / f"source_audio{voice_audio.suffix.lower()}"
    if not archived.exists():
        shutil.copy2(voice_audio, archived)

    voice_id_file = persona_dir / "voice_id.txt"
    if voice_id_file.exists() and voice_id_file.read_text().strip():
        existing = voice_id_file.read_text().strip()
        log.info("voice_id already cloned for %s: %s", persona_name, existing)
        return existing

    client = _eleven_client(cfg)
    log.info("cloning voice for %s from %s", persona_name, archived.name)
    with archived.open("rb") as f:
        # SDK API: client.voices.ivc.create(...) on newer SDKs;
        # client.clone(name=..., files=[...]) on older. Try the newer path first.
        try:
            voice = client.voices.ivc.create(  # type: ignore[attr-defined]
                name=f"tvp_{persona_name}",
                description=f"Telugu Voice Persona for {persona_name}",
                files=[f],
            )
        except AttributeError:
            f.seek(0)
            voice = client.clone(  # type: ignore[attr-defined]
                name=f"tvp_{persona_name}",
                description=f"Telugu Voice Persona for {persona_name}",
                files=[f],
            )

    voice_id = getattr(voice, "voice_id", None) or voice.get("voice_id")  # type: ignore[union-attr]
    if not voice_id:
        raise RuntimeError(f"ElevenLabs response missing voice_id: {voice!r}")

    voice_id_file.write_text(voice_id)
    log.info("voice_id=%s saved to %s", voice_id, voice_id_file)
    return voice_id


def run(
    cfg: TvpConfig,
    persona_name: str,
    voice_audio: Path,
    persona_dir: Path,
) -> str:
    return clone_voice(cfg, persona_name, voice_audio, persona_dir)
