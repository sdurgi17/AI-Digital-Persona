"""Chat Stage 4 — synthesize.

ElevenLabs Multilingual v3 with cloned voice_id; fallback to v2 on failure or
when configured off. Writes MP3 to runs/<session_id>/turn_<N>.mp3.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tvp.config import TvpConfig

log = logging.getLogger(__name__)


def _strip_audio_tags(text: str) -> str:
    # Used as a safety fallback if ElevenLabs v3 is OFF and v2 doesn't understand
    # bracketed audio tags — we don't want them spoken out as "smiling smiling".
    import re

    return re.sub(r"\[(?:smiling|thoughtfully|sarcastic|laughs|whispers|softly|excited|chuckles|sighs|pauses)\]", "", text).strip()


def _client(cfg: TvpConfig):
    if not cfg.secrets.elevenlabs_api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not set.")
    from elevenlabs.client import ElevenLabs  # type: ignore

    return ElevenLabs(api_key=cfg.secrets.elevenlabs_api_key)


def _tts(cfg: TvpConfig, *, text: str, voice_id: str, model: str) -> bytes:
    client = _client(cfg)
    audio_iter = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id=model,
        output_format=cfg.tts.output_format,
    )
    if isinstance(audio_iter, (bytes, bytearray)):
        return bytes(audio_iter)
    return b"".join(audio_iter)


def synthesize(
    cfg: TvpConfig,
    *,
    text: str,
    voice_id: str,
    out_path: Path,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    primary = cfg.tts.model
    fallback = cfg.tts.fallback_model

    speak_text = text if cfg.tts.use_audio_tags else _strip_audio_tags(text)

    try:
        log.info("synthesizing with %s → %s", primary, out_path.name)
        audio = _tts(cfg, text=speak_text, voice_id=voice_id, model=primary)
    except Exception as e:
        log.warning("primary TTS model %s failed: %s — falling back to %s", primary, e, fallback)
        audio = _tts(
            cfg,
            text=_strip_audio_tags(speak_text),
            voice_id=voice_id,
            model=fallback,
        )

    out_path.write_bytes(audio)
    log.info("audio written: %s (%d bytes)", out_path, len(audio))
    return out_path


def run(
    cfg: TvpConfig,
    text: str,
    voice_id: str,
    session_dir: Path,
    turn_index: int,
) -> Path:
    out_path = session_dir / f"turn_{turn_index}.mp3"
    return synthesize(cfg, text=text, voice_id=voice_id, out_path=out_path)
