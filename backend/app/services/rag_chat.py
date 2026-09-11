"""Shared RAG pipeline used by both /api/chat (text) and /v1/chat/completions (voice gateway)."""
import sqlite3
from typing import AsyncIterator

from .llm.base import get_provider
from .retrieval import format_context, retrieve


def get_persona(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM persona WHERE id = 1").fetchone()


def inject_rag_context(conn: sqlite3.Connection, messages: list[dict], persona_name: str) -> list[dict]:
    """Insert one system message with retrieved excerpts just before the last user turn.
    Per-turn injection: earlier turns never carry stale retrieval context."""
    last_user_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break
    if last_user_idx is None:
        return messages

    query = messages[last_user_idx].get("content") or ""
    if not isinstance(query, str):
        query = " ".join(
            p.get("text", "") for p in query if isinstance(p, dict) and p.get("type") == "text"
        )
    chunks = retrieve(conn, query)
    if not chunks:
        return messages

    context_msg = {"role": "system", "content": format_context(chunks, persona_name)}
    return messages[:last_user_idx] + [context_msg] + messages[last_user_idx:]


async def stream_persona_reply(
    conn: sqlite3.Connection, messages: list[dict], include_system_prompt: bool
) -> AsyncIterator[str]:
    """messages: OpenAI-shape conversation. include_system_prompt=True for /api/chat
    (client sends no system message); False for the gateway (ElevenLabs sends the
    agent's system prompt itself)."""
    persona = get_persona(conn)
    name = persona["name"] if persona else "the persona"

    if include_system_prompt:
        if persona and persona["system_prompt"]:
            messages = [{"role": "system", "content": persona["system_prompt"]}] + messages
        else:
            raise ValueError("Persona has not been built yet (POST /api/persona/build)")

    messages = inject_rag_context(conn, messages, name)
    async for delta in get_provider().stream_chat(messages):
        yield delta
