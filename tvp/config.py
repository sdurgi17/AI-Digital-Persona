"""Config loader. Reads config.toml + .env. Returns a frozen Pydantic model."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


class IngestConfig(BaseModel):
    chunk_size: int = 400
    chunk_overlap: int = 50
    embed_model: str = "BAAI/bge-m3"
    extract_memories: bool = True
    memory_extraction_workers: int = 5
    language_detection_model: str = "lid.176.bin"


class GenerationConfig(BaseModel):
    llm_provider: str = "openrouter"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "anthropic/claude-sonnet-4.5"
    entity_extraction_model: str = "anthropic/claude-haiku-4.5"
    temperature: float = 0.3
    max_tokens: int = 800
    chunk_score_threshold: float = 0.55
    memory_score_threshold: float = 0.60
    top_chunks: int = 3
    top_memories: int = 5
    refusal_phrase_telugu: str = "నాకు దీని గురించి తెలియదు"


class TTSConfig(BaseModel):
    provider: str = "elevenlabs"
    model: str = "eleven_v3"
    fallback_model: str = "eleven_multilingual_v2"
    use_audio_tags: bool = True
    output_format: str = "mp3_44100_128"


class StorageConfig(BaseModel):
    qdrant_url: str = "http://localhost:6333"
    personas_root: str = "./personas"
    runs_root: str = "./runs"
    stage_cache_root: str = "./stage_cache"


class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    conversation_log: bool = True


class Secrets(BaseModel):
    openrouter_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    cohere_api_key: str | None = None
    sarvam_api_key: str | None = None


class TvpConfig(BaseModel):
    ingest: IngestConfig = Field(default_factory=IngestConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    secrets: Secrets = Field(default_factory=Secrets)

    @property
    def personas_root(self) -> Path:
        return Path(self.storage.personas_root).resolve()

    @property
    def runs_root(self) -> Path:
        return Path(self.storage.runs_root).resolve()

    @property
    def stage_cache_root(self) -> Path:
        return Path(self.storage.stage_cache_root).resolve()


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def load_config(config_path: str | Path | None = None) -> TvpConfig:
    """Load config.toml (if present) and .env, return a TvpConfig."""
    load_dotenv()
    path = Path(config_path) if config_path else Path("config.toml")
    data = _load_toml(path)
    cfg = TvpConfig(**data)
    cfg.secrets = Secrets(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY"),
        cohere_api_key=os.getenv("COHERE_API_KEY"),
        sarvam_api_key=os.getenv("SARVAM_API_KEY"),
    )
    # Ensure runtime dirs exist.
    cfg.personas_root.mkdir(parents=True, exist_ok=True)
    cfg.runs_root.mkdir(parents=True, exist_ok=True)
    cfg.stage_cache_root.mkdir(parents=True, exist_ok=True)
    return cfg


@lru_cache(maxsize=1)
def get_config() -> TvpConfig:
    return load_config()
