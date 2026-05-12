"""OpenRouter-backed LLM client (OpenAI-compatible)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from tvp.config import TvpConfig, get_config

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    cfg = get_config()
    if not cfg.secrets.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY not set. Add it to .env or your environment."
        )
    return OpenAI(
        base_url=cfg.generation.llm_base_url,
        api_key=cfg.secrets.openrouter_api_key,
    )


def load_prompt(name: str) -> str:
    """Load a prompt template by file name (with or without .txt)."""
    if not name.endswith(".txt"):
        name = f"{name}.txt"
    path = PROMPTS_DIR / name
    return path.read_text(encoding="utf-8")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def chat(
    *,
    model: str,
    system: str | None,
    user: str,
    temperature: float = 0.3,
    max_tokens: int = 800,
    cfg: TvpConfig | None = None,
) -> str:
    """Single-turn chat completion. Returns assistant text."""
    cfg = cfg or get_config()
    client = get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""
