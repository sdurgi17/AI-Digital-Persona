import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..db import get_db
from ..services.rag_chat import stream_persona_reply

router = APIRouter()


class ChatRequest(BaseModel):
    messages: list[dict]  # [{role: user|assistant, content: str}, ...]


@router.post("")
async def chat(body: ChatRequest) -> StreamingResponse:
    """Text chat with the persona; SSE stream of {"delta": "..."} events."""

    async def event_stream():
        conn = get_db()
        try:
            try:
                async for delta in stream_persona_reply(conn, body.messages, include_system_prompt=True):
                    yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
            except ValueError as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'error': f'LLM error: {exc}'})}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            conn.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
