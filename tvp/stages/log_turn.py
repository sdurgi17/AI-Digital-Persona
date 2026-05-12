"""Chat Stage 5 — log_turn.

Append a ChatTurn as a single JSONL line to runs/<session_id>.jsonl.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from tvp.models import ChatTurn

log = logging.getLogger(__name__)


def log_turn(turn: ChatTurn, runs_root: Path) -> Path:
    runs_root.mkdir(parents=True, exist_ok=True)
    out = runs_root / f"{turn.session_id}.jsonl"
    line = turn.model_dump_json()
    with out.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    log.debug("turn logged: %s", out)
    return out


def run(turn: ChatTurn, runs_root: Path) -> Path:
    return log_turn(turn, runs_root)
