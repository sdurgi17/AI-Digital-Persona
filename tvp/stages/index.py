"""Stage 5 — index.

- Qdrant: collection `persona_<name>_chunks`, cosine distance.
- SQLite: memories table with embedding BLOB.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

import numpy as np

from tvp.config import TvpConfig
from tvp.models import AtomicMemory, Chunk

log = logging.getLogger(__name__)

EMBED_DIM = 1024  # BGE-M3


# === Qdrant ===


def _qdrant(url: str):
    from qdrant_client import QdrantClient  # type: ignore

    return QdrantClient(url=url)


def index_chunks_qdrant(
    cfg: TvpConfig,
    persona_name: str,
    chunks: list[Chunk],
    vectors: np.ndarray,
) -> str:
    from qdrant_client.http import models as qm  # type: ignore

    client = _qdrant(cfg.storage.qdrant_url)
    collection = f"persona_{persona_name}_chunks"

    # Recreate cleanly each ingest run.
    if client.collection_exists(collection):
        client.delete_collection(collection)
    client.create_collection(
        collection_name=collection,
        vectors_config=qm.VectorParams(size=EMBED_DIM, distance=qm.Distance.COSINE),
    )

    if not chunks:
        log.warning("no chunks to index in Qdrant collection %s", collection)
        return collection

    points = [
        qm.PointStruct(
            id=c.id,
            vector=vectors[i].tolist(),
            payload={
                "text": c.text,
                "source_file": c.source_file,
                "source_offset": c.source_offset,
                "token_count": c.token_count,
                "detected_lang": c.detected_lang,
            },
        )
        for i, c in enumerate(chunks)
    ]
    client.upsert(collection_name=collection, points=points)
    log.info("upserted %d points to Qdrant collection %s", len(points), collection)
    return collection


# === SQLite ===


SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    claim TEXT NOT NULL,
    type TEXT NOT NULL,
    entities TEXT NOT NULL,
    date TEXT,
    metric TEXT,
    source_chunk_id TEXT NOT NULL,
    source_span TEXT,
    embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_type ON memories(type);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)
    return conn


def index_memories_sqlite(
    db_path: Path,
    memories: list[AtomicMemory],
    vectors: np.ndarray,
) -> int:
    conn = _connect(db_path)
    try:
        # Fresh table each ingest run — memories are derived; safe to rewrite.
        conn.execute("DELETE FROM memories;")
        rows = []
        for i, m in enumerate(memories):
            rows.append(
                (
                    m.id,
                    m.claim,
                    m.type,
                    json.dumps(m.entities, ensure_ascii=False),
                    m.date,
                    m.metric,
                    m.source_chunk_id,
                    json.dumps(list(m.source_span)) if m.source_span else None,
                    vectors[i].astype(np.float32).tobytes(),
                )
            )
        conn.executemany(
            """
            INSERT INTO memories
              (id, claim, type, entities, date, metric, source_chunk_id, source_span, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
        log.info("indexed %d memories into %s", len(rows), db_path)
        return len(rows)
    finally:
        conn.close()


def run(
    cfg: TvpConfig,
    persona_name: str,
    persona_dir: Path,
    chunks: list[Chunk],
    chunk_vecs: np.ndarray,
    memories: list[AtomicMemory],
    memory_vecs: np.ndarray,
) -> tuple[str, str, int, int]:
    collection = index_chunks_qdrant(cfg, persona_name, chunks, chunk_vecs)
    db_path = persona_dir / "memories.db"
    mem_count = index_memories_sqlite(db_path, memories, memory_vecs)
    return collection, str(db_path), len(chunks), mem_count
