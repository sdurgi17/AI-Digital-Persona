"""OpenAI-compatible /v1/chat/completions endpoint that the ElevenLabs agent calls
each conversation turn. Contract (verified against ElevenLabs custom-LLM docs):
SSE chunks shaped like chat.completion.chunk, terminated by `data: [DONE]`.
Silent agent == broken framing here, so keep this exact."""
import json
import logging
import time
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..config import get_settings
from ..db import get_db
from ..services.rag_chat import stream_persona_reply

logger = logging.getLogger(__name__)
router = APIRouter()


def _check_auth(authorization: str | None) -> None:
    settings = get_settings()
    if not settings.custom_llm_shared_secret:
        raise HTTPException(500, "CUSTOM_LLM_SHARED_SECRET is not configured on the server")
    expected = f"Bearer {settings.custom_llm_shared_secret}"
    if authorization != expected:
        raise HTTPException(401, "Invalid or missing bearer token")


def _chunk(chunk_id: str, created: int, model: str, delta: dict, finish_reason: str | None = None) -> str:
    payload = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/completions")
async def chat_completions(request: Request, authorization: str | None = Header(None)):
    _check_auth(authorization)
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", "persona-rag")
    stream = body.get("stream", True)

    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    if not stream:
        conn = get_db()
        try:
            parts = [d async for d in stream_persona_reply(conn, messages, include_system_prompt=False)]
        finally:
            conn.close()
        return JSONResponse(
            {
                "id": chunk_id,
                "object": "chat.completion",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "".join(parts)},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
        )

    async def sse():
        conn = get_db()
        started = time.monotonic()
        try:
            yield _chunk(chunk_id, created, model, {"role": "assistant", "content": ""})
            first = True
            async for delta in stream_persona_reply(conn, messages, include_system_prompt=False):
                if first:
                    logger.info("gateway TTFT %.0f ms", (time.monotonic() - started) * 1000)
                    first = False
                yield _chunk(chunk_id, created, model, {"content": delta})
            yield _chunk(chunk_id, created, model, {}, finish_reason="stop")
        except Exception:
            logger.exception("gateway stream failed")
            yield _chunk(
                chunk_id, created, model,
                {"content": "Sorry, I lost my train of thought — say that again?"},
                finish_reason="stop",
            )
        finally:
            conn.close()
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
