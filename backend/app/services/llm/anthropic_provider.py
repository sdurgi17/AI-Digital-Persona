from typing import AsyncIterator

from anthropic import AsyncAnthropic

from ...config import get_settings


def map_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """OpenAI-shape → Anthropic Messages API shape.

    - All system-role messages are hoisted into one system string (in order).
    - Consecutive same-role user/assistant turns are merged (Anthropic requires
      strict alternation).
    - A leading assistant turn gets a placeholder user turn before it
      (happens when ElevenLabs sends the agent's first_message as history).
    """
    system_parts: list[str] = []
    turns: list[dict] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content") or ""
        if not isinstance(content, str):
            # OpenAI content can be a list of parts; keep text parts only
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
            )
        if role == "system":
            system_parts.append(content)
            continue
        if role not in ("user", "assistant"):
            continue
        if not content.strip():
            continue
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n\n" + content
        else:
            turns.append({"role": role, "content": content})

    if turns and turns[0]["role"] == "assistant":
        turns.insert(0, {"role": "user", "content": "(conversation begins)"})
    if not turns:
        turns.append({"role": "user", "content": "(conversation begins)"})

    return "\n\n".join(system_parts), turns


class AnthropicProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        system, turns = map_messages(messages)
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system or "You are a helpful assistant.",
            messages=turns,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def complete(self, messages: list[dict], max_tokens: int | None = None) -> str:
        system, turns = map_messages(messages)
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=system or "You are a helpful assistant.",
            messages=turns,
        )
        return "".join(block.text for block in resp.content if block.type == "text")
