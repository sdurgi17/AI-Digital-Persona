"""Chat Stage 2 — retrieve.

Two-tier retrieval:
  Tier 1: Qdrant vector search over chunks (top 5).
  Tier 2: SQLite — both vector similarity over memories.embedding AND entity-LIKE
          filter on memories.entities. Entities are extracted from the question via
          a small LLM call (cached by question hash).
Thresholds: chunks ≥ 0.55, memories ≥ 0.60.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import re
import sqlite3
from pathlib import Path

import numpy as np

from tvp.config import TvpConfig
from tvp.llm import chat, load_prompt
from tvp.models import (
    AtomicMemory,
    Chunk,
    RetrievalResult,
    RetrievedChunk,
    RetrievedMemory,
)
from tvp.stages.embed import encode

log = logging.getLogger(__name__)


# === Qdrant ===


def _qdrant(url: str):
    from qdrant_client import QdrantClient  # type: ignore

    return QdrantClient(url=url)


def _chunk_from_payload(point) -> Chunk:
    p = point.payload or {}
    return Chunk(
        id=str(point.id),
        text=p.get("text", ""),
        source_file=p.get("source_file", ""),
        source_offset=int(p.get("source_offset") or 0),
        token_count=int(p.get("token_count") or 0),
        detected_lang=p.get("detected_lang"),
    )


def vector_search_chunks(
    cfg: TvpConfig,
    collection: str,
    qvec: np.ndarray,
    *,
    top_k: int,
    threshold: float,
) -> list[RetrievedChunk]:
    client = _qdrant(cfg.storage.qdrant_url)
    results = client.search(
        collection_name=collection,
        query_vector=qvec.tolist(),
        limit=top_k,
        with_payload=True,
        score_threshold=threshold,
    )
    return [
        RetrievedChunk(chunk=_chunk_from_payload(p), score=float(p.score))
        for p in results
    ]


# === SQLite memory retrieval ===


def _row_to_memory(row: sqlite3.Row) -> AtomicMemory:
    span_raw = row["source_span"]
    span: tuple[int, int] | None = None
    if span_raw:
        arr = json.loads(span_raw)
        span = (int(arr[0]), int(arr[1]))
    return AtomicMemory(
        id=row["id"],
        claim=row["claim"],
        type=row["type"],
        entities=json.loads(row["entities"]),
        date=row["date"],
        metric=row["metric"],
        source_chunk_id=row["source_chunk_id"],
        source_span=span,
    )


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(np.dot(a, b) / denom)


def vector_search_memories(
    sqlite_path: str,
    qvec: np.ndarray,
    *,
    top_k: int,
    threshold: float,
) -> list[RetrievedMemory]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, claim, type, entities, date, metric, source_chunk_id,"
            " source_span, embedding FROM memories"
        ).fetchall()
    finally:
        conn.close()

    scored: list[tuple[float, AtomicMemory]] = []
    for r in rows:
        vec = np.frombuffer(r["embedding"], dtype=np.float32)
        score = _cosine(qvec, vec)
        if score < threshold:
            continue
        scored.append((score, _row_to_memory(r)))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        RetrievedMemory(memory=m, score=s, match_type="vector")
        for s, m in scored[:top_k]
    ]


def entity_search_memories(
    sqlite_path: str,
    entities: list[str],
) -> list[RetrievedMemory]:
    if not entities:
        return []
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        clauses = " OR ".join(["entities LIKE ?"] * len(entities))
        params = [f"%{e}%" for e in entities]
        rows = conn.execute(
            f"SELECT id, claim, type, entities, date, metric, source_chunk_id,"
            f" source_span, embedding FROM memories WHERE {clauses}",
            params,
        ).fetchall()
    finally:
        conn.close()
    return [
        RetrievedMemory(memory=_row_to_memory(r), score=1.0, match_type="entity")
        for r in rows
    ]


# === Entity extraction ===


_JSON_ARRAY_RE = re.compile(r"\[.*?\]", re.DOTALL)


def _question_key(question: str, model: str) -> str:
    return hashlib.sha256(f"{model}::{question}".encode("utf-8")).hexdigest()


@functools.lru_cache(maxsize=256)
def _cached_entities(question: str, model: str) -> tuple[str, ...]:
    prompt = load_prompt("entity_extraction.txt").replace("{{question}}", question)
    try:
        raw = chat(
            model=model,
            system="You extract proper nouns and named entities. Output JSON only.",
            user=prompt,
            temperature=0.0,
            max_tokens=200,
        )
    except Exception as e:  # pragma: no cover
        log.warning("entity extraction failed: %s", e)
        return ()
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    m = _JSON_ARRAY_RE.search(s)
    s = m.group(0) if m else s
    try:
        arr = json.loads(s)
    except json.JSONDecodeError:
        return ()
    return tuple(str(x) for x in arr if isinstance(x, str))


def extract_entities(question: str, model: str) -> list[str]:
    return list(_cached_entities(question, model))


# === Orchestrator ===


def _dedupe_memories(items: list[RetrievedMemory]) -> list[RetrievedMemory]:
    seen: dict[str, RetrievedMemory] = {}
    for r in items:
        existing = seen.get(r.memory.id)
        if existing is None or r.score > existing.score:
            seen[r.memory.id] = r
    return sorted(seen.values(), key=lambda r: r.score, reverse=True)


def retrieve(
    cfg: TvpConfig,
    question: str,
    *,
    collection: str,
    sqlite_path: str,
) -> RetrievalResult:
    qvec = encode([question], cfg.ingest.embed_model)[0]

    chunks = vector_search_chunks(
        cfg,
        collection,
        qvec,
        top_k=5,
        threshold=cfg.generation.chunk_score_threshold,
    )

    mem_vec = vector_search_memories(
        sqlite_path,
        qvec,
        top_k=5,
        threshold=cfg.generation.memory_score_threshold,
    )
    entities = extract_entities(question, cfg.generation.entity_extraction_model)
    mem_ent = entity_search_memories(sqlite_path, entities)
    memories = _dedupe_memories(mem_vec + mem_ent)[:5]

    out_of_corpus = not chunks and not memories
    log.info(
        "retrieve: %d chunks, %d memories (entities=%s, OOC=%s)",
        len(chunks),
        len(memories),
        entities,
        out_of_corpus,
    )
    return RetrievalResult(
        chunks=chunks, memories=memories, out_of_corpus=out_of_corpus
    )


def run(
    cfg: TvpConfig,
    question: str,
    collection: str,
    sqlite_path: str,
) -> RetrievalResult:
    return retrieve(
        cfg, question, collection=collection, sqlite_path=sqlite_path
    )
