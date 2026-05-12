"""Stage 4 — embed.

BGE-M3 local embeddings (1024-dim). Returns chunks + memories paired with vectors.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np

from tvp.cache import stage
from tvp.config import TvpConfig
from tvp.models import AtomicMemory, Chunk

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _model(name: str):
    from sentence_transformers import SentenceTransformer  # type: ignore

    log.info("loading embedding model %s", name)
    return SentenceTransformer(name)


def encode(texts: list[str], model_name: str, *, batch_size: int = 32) -> np.ndarray:
    if not texts:
        return np.zeros((0, 1024), dtype=np.float32)
    m = _model(model_name)
    vecs = m.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return vecs.astype(np.float32)


@stage("embed", "v1")
def embed_chunks_and_memories(
    chunks: list[Chunk],
    memories: list[AtomicMemory],
    *,
    model_name: str,
) -> tuple[list[Chunk], np.ndarray, list[AtomicMemory], np.ndarray]:
    chunk_vecs = encode([c.text for c in chunks], model_name)
    mem_vecs = encode([m.claim for m in memories], model_name)
    log.info(
        "embedded %d chunks → %s, %d memories → %s",
        len(chunks),
        chunk_vecs.shape,
        len(memories),
        mem_vecs.shape,
    )
    return chunks, chunk_vecs, memories, mem_vecs


def run(
    cfg: TvpConfig,
    chunks: list[Chunk],
    memories: list[AtomicMemory],
    force: bool = False,
):
    return embed_chunks_and_memories(
        chunks, memories, model_name=cfg.ingest.embed_model, force=force
    )
