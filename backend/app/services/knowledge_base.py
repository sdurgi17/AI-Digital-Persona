"""Sync persona knowledge into the ElevenLabs knowledge base.

Needed for the built-in-LLM agent mode: ElevenLabs refuses a custom LLM on an
agent that uses an Instant Voice Clone, so when we keep the IVC voice the RAG
has to live on their side instead of in our sqlite-vec index.

Documents are re-parsed from the original upload rather than reassembled from
`chunks`, whose overlap would duplicate text across the seams.
"""
import json
import logging
import sqlite3
from pathlib import Path

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)

EL_BASE = "https://api.elevenlabs.io"
SETTINGS_KEY = "el_kb_docs"  # {source_key: knowledge_base_id}


def _headers() -> dict:
    return {"xi-api-key": get_settings().elevenlabs_api_key}


def collect_sources(conn: sqlite3.Connection) -> dict[str, str]:
    """Map a stable source key -> the text ElevenLabs should index."""
    from .ingestion import parse_file

    sources: dict[str, str] = {}

    for row in conn.execute(
        "SELECT id, filename, file_path FROM documents WHERE status = 'ingested'"
    ):
        try:
            text = parse_file(Path(row["file_path"])).strip()
        except Exception:
            logger.exception("knowledge base: could not parse %s", row["filename"])
            continue
        if text:
            sources[f"doc:{row['id']}"] = text

    answers = conn.execute(
        """
        SELECT q.text AS question, a.transcript
        FROM interview_answers a
        JOIN interview_questions q ON q.id = a.question_id
        WHERE a.transcript IS NOT NULL AND TRIM(a.transcript) != ''
        ORDER BY q.ord
        """
    ).fetchall()
    if answers:
        sources["interview"] = "\n\n".join(
            f"Q: {r['question']}\nA: {r['transcript'].strip()}" for r in answers
        )

    return sources


def _load_map(conn: sqlite3.Connection) -> dict[str, str]:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (SETTINGS_KEY,)).fetchone()
    return json.loads(row["value"]) if row and row["value"] else {}


def _save_map(conn: sqlite3.Connection, mapping: dict[str, str]) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (SETTINGS_KEY, json.dumps(mapping)),
    )
    conn.commit()


async def sync_knowledge_base(
    conn: sqlite3.Connection, client: httpx.AsyncClient, persona_name: str
) -> list[dict]:
    """Upload any not-yet-uploaded sources; return agent `knowledge_base` entries.

    Uploads are keyed by source so re-provisioning does not duplicate documents.
    A source whose upload fails is skipped rather than failing the whole sync —
    a partial knowledge base still beats an agent that will not provision.
    """
    sources = collect_sources(conn)
    mapping = _load_map(conn)

    for key, text in sources.items():
        if key in mapping:
            continue
        name = f"{persona_name} — {'interview' if key == 'interview' else key}"
        resp = await client.post(
            f"{EL_BASE}/v1/convai/knowledge-base/text",
            headers=_headers(),
            json={"name": name, "text": text},
        )
        if resp.status_code >= 400:
            logger.error("knowledge base upload failed for %s: %s %s", key, resp.status_code, resp.text)
            continue
        mapping[key] = resp.json()["id"]

    # Drop entries whose source no longer exists locally.
    mapping = {k: v for k, v in mapping.items() if k in sources}
    _save_map(conn, mapping)

    return [
        {"type": "text", "name": f"{persona_name} — {k}", "id": doc_id}
        for k, doc_id in mapping.items()
    ]
