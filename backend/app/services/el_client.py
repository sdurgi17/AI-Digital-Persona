from functools import lru_cache

from elevenlabs.client import ElevenLabs

from ..config import get_settings


@lru_cache
def get_el_client() -> ElevenLabs:
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set (see .env.example)")
    return ElevenLabs(api_key=settings.elevenlabs_api_key)
