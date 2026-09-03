import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db
from ..services.ingestion import ingest_interview_answers
from ..services.persona_builder import build_profile, render_system_prompt

router = APIRouter()


class CreatePersona(BaseModel):
    name: str


class UpdatePrompt(BaseModel):
    system_prompt: str


class UpdateVoice(BaseModel):
    voice_id: str
    voice_kind: str = "pvc"  # ivc | pvc | library


@router.get("")
def get_persona_status() -> dict:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM persona WHERE id = 1").fetchone()
        if not row:
            return {"exists": False}
        data = dict(row)
        data["exists"] = True
        data["profile_json"] = json.loads(data["profile_json"]) if data["profile_json"] else None
        return data
    finally:
        conn.close()


@router.post("")
def create_persona(body: CreatePersona) -> dict:
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO persona (id, name, status) VALUES (1, ?, 'interviewing')
            ON CONFLICT(id) DO UPDATE SET name = excluded.name, updated_at = datetime('now')
            """,
            (body.name.strip(),),
        )
        conn.commit()
        return {"name": body.name.strip(), "status": "interviewing"}
    finally:
        conn.close()


@router.post("/build")
async def build_persona() -> dict:
    conn = get_db()
    try:
        persona = conn.execute("SELECT * FROM persona WHERE id = 1").fetchone()
        if not persona:
            raise HTTPException(400, "Create the persona first (POST /api/persona)")
        try:
            profile = await build_profile(conn)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        profile.setdefault("identity", {})["name"] = persona["name"]
        prompt = render_system_prompt(profile)
        interview_chunks = ingest_interview_answers(conn)
        new_status = persona["status"] if persona["status"] in ("voice_ready", "agent_ready") else "profile_ready"
        conn.execute(
            """
            UPDATE persona SET profile_json = ?, system_prompt = ?, status = ?,
                   updated_at = datetime('now') WHERE id = 1
            """,
            (json.dumps(profile, ensure_ascii=False), prompt, new_status),
        )
        conn.commit()
        return {"status": new_status, "profile": profile, "interview_chunks": interview_chunks}
    finally:
        conn.close()


@router.put("/voice")
def update_voice(body: UpdateVoice) -> dict:
    """Point the persona at an existing ElevenLabs voice (e.g. a Professional
    Voice Clone trained in their dashboard) instead of the interview-built IVC."""
    conn = get_db()
    try:
        persona = conn.execute("SELECT agent_id FROM persona WHERE id = 1").fetchone()
        if not persona:
            raise HTTPException(404, "Persona not created yet")
        conn.execute(
            """
            UPDATE persona SET voice_id = ?, voice_kind = ?, status = ?,
                   updated_at = datetime('now') WHERE id = 1
            """,
            (
                body.voice_id.strip(),
                body.voice_kind,
                "agent_ready" if persona["agent_id"] else "voice_ready",
            ),
        )
        conn.commit()
        return {"voice_id": body.voice_id.strip(), "voice_kind": body.voice_kind}
    finally:
        conn.close()


@router.put("/prompt")
def update_prompt(body: UpdatePrompt) -> dict:
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE persona SET system_prompt = ?, updated_at = datetime('now') WHERE id = 1",
            (body.system_prompt,),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Persona not created yet")
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
