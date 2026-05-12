#!/usr/bin/env python3
"""chat.py — interactive REPL for a built persona.

Usage:
    python chat.py --persona srikar [--config config.toml]

In-REPL commands:
    plain text          ask a question
    :sources            print citations for last turn
    :q / :quit / :exit  exit
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from tvp.config import TvpConfig, load_config
from tvp.models import (
    ChatTurn,
    LatencyBreakdown,
    PersonaManifest,
)
from tvp.stages import generate, log_turn, retrieve, synthesize


def _setup_logging(level: str):
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


# === Stage 1 — load_persona ===


def load_persona(cfg: TvpConfig, name: str) -> tuple[PersonaManifest, Path]:
    persona_dir = cfg.personas_root / name
    manifest_path = persona_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"manifest not found: {manifest_path}\n"
            f"Run `python ingest.py --persona {name} --voice ... --docs ...` first."
        )
    manifest = PersonaManifest.model_validate_json(manifest_path.read_text())

    # Verify Qdrant collection and SQLite db.
    try:
        from qdrant_client import QdrantClient  # type: ignore

        qc = QdrantClient(url=cfg.storage.qdrant_url)
        if not qc.collection_exists(manifest.qdrant_collection):
            raise RuntimeError(
                f"Qdrant collection missing: {manifest.qdrant_collection}. "
                f"Re-run ingest.py."
            )
    except Exception as e:
        raise RuntimeError(f"Qdrant not reachable at {cfg.storage.qdrant_url}: {e}")

    sqlite_path = Path(manifest.sqlite_path)
    if not sqlite_path.exists():
        raise RuntimeError(f"SQLite memories db missing: {sqlite_path}")

    return manifest, persona_dir


# === REPL helpers ===


def _print_sources(last_turn: ChatTurn | None):
    if last_turn is None:
        print("(no previous turn)")
        return
    if not last_turn.retrieved_memories and not last_turn.retrieved_chunks:
        print("(no retrieved sources)")
        return
    print()
    for r in last_turn.retrieved_memories:
        print(f"- memory {r.memory.id} (score={r.score:.2f}, {r.match_type}): {r.memory.claim}")
    for r in last_turn.retrieved_chunks:
        c = r.chunk
        snippet = c.text.strip().replace("\n", " ")
        if len(snippet) > 120:
            snippet = snippet[:120] + "…"
        print(
            f"- chunk {c.id} ({c.source_file}, offset {c.source_offset}, score={r.score:.2f}): {snippet}"
        )
    print()


def _new_session_id() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chat with a Telugu Voice Persona.")
    parser.add_argument("--persona", required=True)
    parser.add_argument("--config", default="config.toml")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    _setup_logging(cfg.logging.level)
    log = logging.getLogger("chat")

    manifest, persona_dir = load_persona(cfg, args.persona)
    print(
        f"persona: {manifest.name}  "
        f"sources={len(manifest.source_files)}  "
        f"chunks={manifest.chunk_count}  "
        f"memories={manifest.memory_count}  "
        f"ingested={manifest.created_at.isoformat()}"
    )

    session_id = _new_session_id()
    session_dir = cfg.runs_root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    log.info("session %s — audio dir %s", session_id, session_dir)

    turn_index = 0
    last_turn: ChatTurn | None = None

    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            continue
        if question in {":q", ":quit", ":exit"}:
            break
        if question == ":sources":
            _print_sources(last_turn)
            continue
        if question.startswith(":"):
            print(f"unknown command: {question}")
            continue

        turn_index += 1
        t_total = time.perf_counter()

        # Retrieve
        t0 = time.perf_counter()
        retrieval = retrieve.run(
            cfg, question, manifest.qdrant_collection, manifest.sqlite_path
        )
        retrieval_ms = int((time.perf_counter() - t0) * 1000)

        # Generate
        t0 = time.perf_counter()
        response = generate.run(
            cfg, manifest.name, question, manifest.style_profile, retrieval
        )
        generation_ms = int((time.perf_counter() - t0) * 1000)

        # Synthesize
        audio_path = ""
        tts_ms = 0
        try:
            t0 = time.perf_counter()
            audio_file = synthesize.run(
                cfg, response.text, manifest.voice_id, session_dir, turn_index
            )
            tts_ms = int((time.perf_counter() - t0) * 1000)
            audio_path = str(audio_file)
        except Exception as e:
            log.error("TTS failed: %s", e)

        total_ms = int((time.perf_counter() - t_total) * 1000)

        latency = LatencyBreakdown(
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
            tts_ms=tts_ms,
            total_ms=total_ms,
        )

        turn = ChatTurn(
            turn_id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=datetime.now(timezone.utc),
            question=question,
            retrieved_chunks=retrieval.chunks,
            retrieved_memories=retrieval.memories,
            generated_text=response.text,
            audio_path=audio_path,
            refused=response.refused,
            cited_memory_ids=response.cited_memory_ids,
            cited_chunk_ids=response.cited_chunk_ids,
            latency_ms=latency,
        )

        if cfg.logging.conversation_log:
            log_turn.run(turn, cfg.runs_root)

        print(
            f"[retrieve {retrieval_ms}ms] "
            f"[generate {generation_ms}ms] "
            f"[tts {tts_ms}ms] "
            f"[total {total_ms}ms]"
        )
        print(response.text)
        if audio_path:
            print(f"[audio: {audio_path}]")

        last_turn = turn

    print("bye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
