from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    elevenlabs_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Point the OpenAI-compatible client at a different gateway (e.g. OpenRouter:
    # https://openrouter.ai/api/v1). Empty means api.openai.com.
    openai_base_url: str = ""

    llm_provider: str = "anthropic"  # anthropic | openai
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_max_tokens: int = 1024

    embedding_provider: str = "openai"  # openai | fastembed
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    stt_model_id: str = "scribe_v2"
    tts_model_id: str = "eleven_flash_v2_5"

    # ElevenLabs refuses a custom LLM on an agent that uses an Instant Voice Clone,
    # so "builtin" runs the agent on an ElevenLabs-hosted model with our persona
    # prompt + their knowledge base. "custom" keeps the /v1 gateway (needs a
    # non-IVC voice). See backend/app/routers/agent.py.
    agent_llm_mode: str = "builtin"  # builtin | custom
    agent_llm: str = "claude-haiku-4-5"

    custom_llm_shared_secret: str = ""
    public_base_url: str = ""  # e.g. https://xxxx.ngrok-free.app

    data_dir: Path = BACKEND_DIR / "data"
    rag_top_k: int = 5

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def interview_audio_dir(self) -> Path:
        return self.data_dir / "audio" / "interview"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
