#!/usr/bin/env python3
"""ingest.py — one-shot pipeline that builds a persona artifact directory.

Usage:
    python ingest.py \\
      --persona srikar \\
      --voice path/to/voice.wav \\
      --docs path/to/doc1.pdf path/to/doc2.md path/to/profile.txt \\
      [--config config.toml] \\
      [--force]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from tvp.config import load_config
from tvp.models import PersonaManifest
from tvp.stages import (
    clone_voice,
    detect_language,
    embed,
    extract_memories,
    index,
    load_chunk,
    style_profile,
)


def _setup_logging(level: str):
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def _ensure_persona_dir(personas_root: Path, name: str) -> Path:
    d = personas_root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "sources").mkdir(exist_ok=True)
    return d


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a Telugu Voice Persona.")
    parser.add_argument("--persona", required=True, help="persona name (used as dir)")
    parser.add_argument("--voice", required=True, type=Path, help="voice sample audio")
    parser.add_argument(
        "--docs", required=True, nargs="+", type=str, help="document paths"
    )
    parser.add_argument("--config", default="config.toml", help="config.toml path")
    parser.add_argument(
        "--force",
        action="store_true",
        help="bypass stage cache; full rebuild",
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    _setup_logging(cfg.logging.level)
    log = logging.getLogger("ingest")

    persona_dir = _ensure_persona_dir(cfg.personas_root, args.persona)
    log.info("persona dir: %s", persona_dir)

    # Stage 1 — load + chunk
    log.info("=== Stage 1: load_and_chunk ===")
    chunks, source_files = load_chunk.run(cfg, persona_dir, args.docs, force=args.force)
    if not chunks:
        log.error("no chunks produced; aborting.")
        return 1

    # Stage 2 — language detection
    log.info("=== Stage 2: detect_language ===")
    chunks = detect_language.run(cfg, chunks, force=args.force)

    # Stage 3 — atomic memories
    log.info("=== Stage 3: extract_atomic_memories ===")
    memories = extract_memories.run(cfg, chunks, force=args.force)

    # Stage 4 — embed
    log.info("=== Stage 4: embed ===")
    chunks, chunk_vecs, memories, mem_vecs = embed.run(
        cfg, chunks, memories, force=args.force
    )

    # Stage 5 — index (Qdrant + SQLite). Always re-run; it touches external state.
    log.info("=== Stage 5: index ===")
    collection, sqlite_path, chunk_count, mem_count = index.run(
        cfg, args.persona, persona_dir, chunks, chunk_vecs, memories, mem_vecs
    )

    # Stage 6 — style profile
    log.info("=== Stage 6: extract_style_profile ===")
    style = style_profile.run(cfg, chunks, force=args.force)
    (persona_dir / "style.json").write_text(
        style.model_dump_json(indent=2), encoding="utf-8"
    )

    # Stage 7 — clone voice
    log.info("=== Stage 7: clone_voice ===")
    voice_id = clone_voice.run(cfg, args.persona, args.voice, persona_dir)

    # Stage 8 — write manifest
    log.info("=== Stage 8: write_manifest ===")
    manifest = PersonaManifest(
        name=args.persona,
        voice_id=voice_id,
        qdrant_collection=collection,
        sqlite_path=str(Path(sqlite_path).resolve()),
        style_profile=style,
        source_files=source_files,
        chunk_count=chunk_count,
        memory_count=mem_count,
        created_at=datetime.now(timezone.utc),
        ingest_config={
            "chunk_size": cfg.ingest.chunk_size,
            "chunk_overlap": cfg.ingest.chunk_overlap,
            "embed_model": cfg.ingest.embed_model,
            "extract_memories": cfg.ingest.extract_memories,
            "llm_model": cfg.generation.llm_model,
        },
    )
    manifest_path = persona_dir / "manifest.json"
    manifest_path.write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )

    # Summary.
    summary = {
        "persona": args.persona,
        "source_files": len(source_files),
        "chunks": chunk_count,
        "memories": mem_count,
        "voice_id": voice_id,
        "qdrant_collection": collection,
        "manifest": str(manifest_path),
    }
    print("\n=== INGEST COMPLETE ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
