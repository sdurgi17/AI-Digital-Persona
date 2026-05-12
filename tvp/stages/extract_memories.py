"""Stage 3 — extract_atomic_memories.

One LLM call per chunk (parallel). Returns validated AtomicMemory list.
On parse/validation failure, retry once with a stricter variant, then skip.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import ValidationError

from tvp.cache import stage
from tvp.config import TvpConfig
from tvp.llm import chat, load_prompt
from tvp.models import AtomicMemory, Chunk

log = logging.getLogger(__name__)


_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _strip_to_json_array(text: str) -> str:
    # Models occasionally wrap output in prose or ```json fences. Pull out the array.
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    m = _JSON_ARRAY_RE.search(text)
    return m.group(0) if m else text


def _build_prompt(chunk: Chunk, strict: bool = False) -> str:
    base = load_prompt("memory_extraction.txt").replace("{{passage}}", chunk.text)
    if strict:
        base += (
            "\n\nREMINDER: Your previous response was not parseable as JSON. "
            "Return ONLY a valid JSON array, no prose, no markdown fences."
        )
    return base


def _parse_memories(raw: str, chunk: Chunk) -> list[AtomicMemory]:
    arr = json.loads(_strip_to_json_array(raw))
    if not isinstance(arr, list):
        raise ValueError("expected JSON array")
    out: list[AtomicMemory] = []
    for item in arr:
        span_raw = item.get("source_span")
        span: tuple[int, int] | None = None
        if isinstance(span_raw, (list, tuple)) and len(span_raw) == 2:
            try:
                span = (int(span_raw[0]), int(span_raw[1]))
            except (TypeError, ValueError):
                span = None
        try:
            mem = AtomicMemory(
                id=str(uuid.uuid4()),
                claim=item["claim"],
                type=item.get("type", "other"),
                entities=list(item.get("entities") or []),
                date=item.get("date"),
                metric=item.get("metric"),
                source_chunk_id=chunk.id,
                source_span=span,
            )
            out.append(mem)
        except (KeyError, ValidationError) as e:
            log.debug("dropping malformed memory item: %s — %s", item, e)
    return out


def _extract_one(chunk: Chunk, model: str) -> list[AtomicMemory]:
    for attempt in range(2):
        try:
            raw = chat(
                model=model,
                system="You extract structured biographical facts. Output JSON only.",
                user=_build_prompt(chunk, strict=attempt > 0),
                temperature=0.1,
                max_tokens=1200,
            )
            return _parse_memories(raw, chunk)
        except (json.JSONDecodeError, ValueError) as e:
            log.warning(
                "memory extraction parse failed for chunk %s (attempt %d): %s",
                chunk.id,
                attempt + 1,
                e,
            )
    log.warning("giving up on chunk %s memories", chunk.id)
    return []


@stage("extract_memories", "v1")
def extract_atomic_memories(
    chunks: list[Chunk],
    *,
    model: str,
    workers: int = 5,
) -> list[AtomicMemory]:
    if not chunks:
        return []
    out: list[AtomicMemory] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_extract_one, c, model): c for c in chunks}
        for fut in as_completed(futures):
            chunk = futures[fut]
            try:
                out.extend(fut.result())
            except Exception as e:  # pragma: no cover
                log.exception("memory extraction failed on chunk %s: %s", chunk.id, e)
    log.info("extracted %d memories from %d chunks", len(out), len(chunks))
    return out


def run(
    cfg: TvpConfig,
    chunks: list[Chunk],
    force: bool = False,
) -> list[AtomicMemory]:
    if not cfg.ingest.extract_memories:
        log.info("extract_memories disabled in config; returning []")
        return []
    return extract_atomic_memories(
        chunks,
        model=cfg.generation.llm_model,
        workers=cfg.ingest.memory_extraction_workers,
        force=force,
    )
