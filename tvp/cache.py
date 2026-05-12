"""Stage cache: pickle-based hash-keyed caching for ingest stages.

Each stage takes inputs (any JSON-serializable / Pydantic-serializable structure) and
produces an output. The cache key is hash(stage_name + stage_version + canonical(inputs)).
A `--force` ingest run bypasses lookups but still writes the new result.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from tvp.config import get_config

log = logging.getLogger(__name__)


def _canonical(obj: Any) -> Any:
    """Recursively normalize for hashing. Pydantic → dict; sets → sorted list."""
    if isinstance(obj, BaseModel):
        return _canonical(obj.model_dump(mode="json"))
    if isinstance(obj, dict):
        return {k: _canonical(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    if isinstance(obj, set):
        return sorted(_canonical(v) for v in obj)
    if isinstance(obj, Path):
        return str(obj)
    return obj


def hash_inputs(*args, **kwargs) -> str:
    payload = {
        "args": _canonical(list(args)),
        "kwargs": _canonical(kwargs),
    }
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def hash_file(path: str | Path, chunk_bytes: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_bytes):
            h.update(chunk)
    return h.hexdigest()


def _cache_path(stage_name: str, version: str, key: str) -> Path:
    root = get_config().stage_cache_root / stage_name / version
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{key}.pkl"


def stage(name: str, version: str = "v1") -> Callable:
    """Decorator: cache a stage function by hash of its arguments.

    The wrapped function may receive a kwarg `force=True` (passed via the caller) to
    bypass the cache lookup. The result is always written to disk on completion.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, force: bool = False, **kwargs):
            key = hash_inputs(*args, **kwargs)
            cache_file = _cache_path(name, version, key)
            if cache_file.exists() and not force:
                log.info("stage[%s/%s] cache HIT key=%s", name, version, key)
                with cache_file.open("rb") as f:
                    return pickle.load(f)
            log.info("stage[%s/%s] cache MISS key=%s — running", name, version, key)
            result = fn(*args, **kwargs)
            with cache_file.open("wb") as f:
                pickle.dump(result, f)
            return result

        wrapper.stage_name = name  # type: ignore[attr-defined]
        wrapper.stage_version = version  # type: ignore[attr-defined]
        return wrapper

    return decorator
