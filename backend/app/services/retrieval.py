import json
import sqlite3

from ..config import get_settings
from .embeddings import get_embedder

# vec0 distance is cosine distance in [0, 2]; keep chunks reasonably close.
MAX_DISTANCE = 1.0


def retrieve(conn: sqlite3.Connection, query: str, top_k: int | None = None) -> list[dict]:
    """Embed the query and return the nearest chunks: [{text, source_type, distance}]."""
    settings = get_settings()
    top_k = top_k or settings.rag_top_k
    has_chunks = conn.execute("SELECT 1 FROM chunks LIMIT 1").fetchone()
    if not has_chunks or not query.strip():
        return []

    embedding = get_embedder().embed([query])[0]
    rows = conn.execute(
        """
        SELECT c.text, c.source_type, v.distance
        FROM chunks_vec v
        JOIN chunks c ON c.id = v.rowid
        WHERE v.embedding MATCH ? AND k = ?
        ORDER BY v.distance
        """,
        (json.dumps(embedding), top_k),
    ).fetchall()
    return [
        {"text": r["text"], "source_type": r["source_type"], "distance": r["distance"]}
        for r in rows
        if r["distance"] <= MAX_DISTANCE
    ]


def format_context(chunks: list[dict], persona_name: str) -> str:
    numbered = "\n".join(f"[{i + 1}] {c['text']}" for i, c in enumerate(chunks))
    return (
        f"Relevant material from {persona_name}'s own documents and interview answers. "
        "Use it if helpful, stay in character, and never cite excerpt numbers aloud:\n" + numbered
    )
