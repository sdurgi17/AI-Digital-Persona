from fastapi import APIRouter

from ..config import get_settings

router = APIRouter()


@router.get("/config")
def config_status() -> dict:
    s = get_settings()
    return {
        "elevenlabs_api_key": bool(s.elevenlabs_api_key),
        "anthropic_api_key": bool(s.anthropic_api_key),
        "openai_api_key": bool(s.openai_api_key),
        "llm_provider": s.llm_provider,
        "llm_model": s.llm_model,
        "embedding_provider": s.embedding_provider,
        "custom_llm_shared_secret": bool(s.custom_llm_shared_secret),
        "public_base_url": s.public_base_url or None,
        "llm_key_ok": bool(
            s.anthropic_api_key if s.llm_provider == "anthropic" else s.openai_api_key
        ),
        "embedding_key_ok": s.embedding_provider != "openai" or bool(s.openai_api_key),
    }
