"""Provision/sync the ElevenLabs agent and mint browser session tokens.

Uses raw REST (httpx) for the convai surface to pin the exact documented payload
shapes for custom_llm / overrides / tokens; the SDK is used elsewhere (STT, IVC, TTS).
"""
import httpx
from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..db import get_db
from ..services.knowledge_base import sync_knowledge_base

router = APIRouter()

EL_BASE = "https://api.elevenlabs.io"
SECRET_NAME = "persona-custom-llm-secret"


def _headers() -> dict:
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise HTTPException(400, "ELEVENLABS_API_KEY is not set")
    return {"xi-api-key": settings.elevenlabs_api_key}


async def _ensure_secret(client: httpx.AsyncClient) -> str:
    """Store CUSTOM_LLM_SHARED_SECRET as a workspace secret; reuse if it exists."""
    settings = get_settings()
    resp = await client.get(f"{EL_BASE}/v1/convai/secrets", headers=_headers())
    resp.raise_for_status()
    for secret in resp.json().get("secrets", []):
        if secret.get("name") == SECRET_NAME:
            return secret["secret_id"]
    resp = await client.post(
        f"{EL_BASE}/v1/convai/secrets",
        headers=_headers(),
        json={"type": "new", "name": SECRET_NAME, "value": settings.custom_llm_shared_secret},
    )
    resp.raise_for_status()
    return resp.json()["secret_id"]


def _agent_payload(persona, secret_id: str | None, knowledge_base: list[dict]) -> dict:
    """Build the agent config for the configured LLM mode.

    builtin: an ElevenLabs-hosted model + their knowledge base. Required whenever
             the voice is an Instant Voice Clone — the API rejects a custom LLM
             on an IVC voice ("custom_llm_not_allowed_in_with_agent_with_ivc_voice").
    custom:  our own /v1 gateway (local sqlite-vec RAG). Needs a non-IVC voice.
    """
    settings = get_settings()

    prompt: dict = {"prompt": persona["system_prompt"], "tools": []}
    if settings.agent_llm_mode == "custom":
        prompt["llm"] = "custom-llm"
        prompt["custom_llm"] = {
            "url": settings.public_base_url.rstrip("/") + "/v1",
            "model_id": "persona-rag",
            "api_key": {"secret_id": secret_id},
        }
        # Our gateway injects its own retrieval, so drop any knowledge base left
        # attached by a previous builtin-mode provision rather than sending the
        # same material twice.
        prompt["knowledge_base"] = []
    else:
        prompt["llm"] = settings.agent_llm
        if knowledge_base:
            prompt["knowledge_base"] = knowledge_base

    return {
        "name": f"{persona['name']} (digital persona)",
        "conversation_config": {
            "agent": {
                "first_message": f"Hey, this is {persona['name']}. What's on your mind?",
                "language": "en",
                "prompt": prompt,
            },
            "tts": {
                "voice_id": persona["voice_id"],
                "model_id": settings.tts_model_id,
            },
        },
        "platform_settings": {
            "overrides": {"conversation_config_override": {"agent": {"language": True}}},
            "auth": {"enable_auth": True},
        },
    }


@router.post("/provision")
async def provision_agent() -> dict:
    settings = get_settings()
    conn = get_db()
    try:
        persona = conn.execute("SELECT * FROM persona WHERE id = 1").fetchone()
        if not persona or not persona["system_prompt"]:
            raise HTTPException(400, "Build the persona first (POST /api/persona/build)")
        if not persona["voice_id"]:
            raise HTTPException(400, "Clone the voice first (POST /api/voice/clone)")
        if settings.agent_llm_mode == "custom":
            if not settings.public_base_url:
                raise HTTPException(400, "PUBLIC_BASE_URL is not set — start your tunnel (e.g. ngrok http 8000) and put its URL in .env")
            if not settings.custom_llm_shared_secret:
                raise HTTPException(400, "CUSTOM_LLM_SHARED_SECRET is not set in .env")

        async with httpx.AsyncClient(timeout=60) as client:
            secret_id = None
            knowledge_base: list[dict] = []
            if settings.agent_llm_mode == "custom":
                secret_id = await _ensure_secret(client)
            else:
                knowledge_base = await sync_knowledge_base(conn, client, persona["name"])
            payload = _agent_payload(persona, secret_id, knowledge_base)
            if persona["agent_id"]:
                resp = await client.patch(
                    f"{EL_BASE}/v1/convai/agents/{persona['agent_id']}",
                    headers=_headers(),
                    json=payload,
                )
            else:
                resp = await client.post(
                    f"{EL_BASE}/v1/convai/agents/create", headers=_headers(), json=payload
                )
            if resp.status_code >= 400:
                raise HTTPException(502, f"ElevenLabs agent API error {resp.status_code}: {resp.text}")
            agent_id = resp.json().get("agent_id", persona["agent_id"])

        conn.execute(
            "UPDATE persona SET agent_id = ?, status = 'agent_ready', updated_at = datetime('now') WHERE id = 1",
            (agent_id,),
        )
        conn.commit()
        return {
            "agent_id": agent_id,
            "llm_mode": settings.agent_llm_mode,
            "llm": settings.agent_llm if settings.agent_llm_mode != "custom" else "custom-llm",
            "knowledge_base_documents": len(knowledge_base),
            "custom_llm_url": (
                settings.public_base_url.rstrip("/") + "/v1"
                if settings.agent_llm_mode == "custom"
                else None
            ),
        }
    finally:
        conn.close()


@router.post("/sync")
async def sync_agent() -> dict:
    """Re-push prompt/voice/tunnel URL to the existing agent."""
    return await provision_agent()


@router.get("/session")
async def get_session() -> dict:
    conn = get_db()
    try:
        persona = conn.execute("SELECT agent_id FROM persona WHERE id = 1").fetchone()
    finally:
        conn.close()
    if not persona or not persona["agent_id"]:
        raise HTTPException(400, "No agent provisioned yet (POST /api/agent/provision)")

    agent_id = persona["agent_id"]
    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.get(
            f"{EL_BASE}/v1/convai/conversation/token",
            headers=_headers(),
            params={"agent_id": agent_id},
        )
        signed_resp = await client.get(
            f"{EL_BASE}/v1/convai/conversation/get-signed-url",
            headers=_headers(),
            params={"agent_id": agent_id},
        )
    if token_resp.status_code >= 400 and signed_resp.status_code >= 400:
        raise HTTPException(502, f"Could not mint session: {token_resp.status_code} {token_resp.text}")
    return {
        "agent_id": agent_id,
        "token": token_resp.json().get("token") if token_resp.status_code < 400 else None,
        "signed_url": signed_resp.json().get("signed_url") if signed_resp.status_code < 400 else None,
    }
