from typing import AsyncIterator, Protocol


class LLMProvider(Protocol):
    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        """Stream completion text deltas for OpenAI-shape messages
        [{"role": "system"|"user"|"assistant", "content": str}, ...]."""
        ...

    async def complete(self, messages: list[dict], max_tokens: int | None = None) -> str:
        """Non-streaming completion; used for persona profile extraction."""
        ...


def get_provider():
    from ...config import get_settings

    settings = get_settings()
    if settings.llm_provider == "openai":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider()
    if settings.llm_provider == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r} (expected 'anthropic' or 'openai')")
