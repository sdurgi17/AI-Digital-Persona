"""Stage 2 — detect_language.

Per-chunk fastText lid.176 detection. Marks `te`, `en`, or `mixed` (both languages
present and neither dominant).
"""

from __future__ import annotations

import logging
import os
import urllib.request
from pathlib import Path

from tvp.cache import stage
from tvp.config import TvpConfig
from tvp.models import Chunk

log = logging.getLogger(__name__)

LID_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"


def _model_path(model_name: str) -> Path:
    # Resolve to project-root relative path; if missing, download.
    candidate = Path(model_name)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    if candidate.exists():
        return candidate.resolve()
    target = Path.cwd() / candidate.name
    if not target.exists():
        log.info("downloading fastText lid model to %s", target)
        urllib.request.urlretrieve(LID_URL, target)
    return target


_MODEL_CACHE = {}


def _load_model(model_name: str):
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]
    import fasttext  # type: ignore

    # fasttext is noisy on stderr; silence the deprecation warning.
    fasttext.FastText.eprint = lambda *_a, **_k: None
    path = _model_path(model_name)
    m = fasttext.load_model(str(path))
    _MODEL_CACHE[model_name] = m
    return m


def _classify_segment(model, text: str) -> tuple[str, float]:
    flat = text.replace("\n", " ").strip()
    if not flat:
        return "und", 0.0
    labels, probs = model.predict(flat, k=1)
    lang = labels[0].replace("__label__", "")
    return lang, float(probs[0])


def _classify_chunk(model, text: str) -> str:
    # Score the chunk overall, plus split lines to detect mix.
    overall, _ = _classify_segment(model, text)
    lines = [s for s in text.split("\n") if s.strip()]
    if len(lines) <= 1:
        if overall == "te":
            return "te"
        if overall == "en":
            return "en"
        return "mixed" if _looks_mixed(text) else "en"

    counts = {"te": 0, "en": 0, "other": 0}
    for line in lines:
        lang, _ = _classify_segment(model, line)
        if lang == "te":
            counts["te"] += 1
        elif lang == "en":
            counts["en"] += 1
        else:
            counts["other"] += 1

    total = sum(counts.values()) or 1
    te_frac = counts["te"] / total
    en_frac = counts["en"] / total

    if te_frac >= 0.7:
        return "te"
    if en_frac >= 0.7:
        return "en"
    if te_frac > 0 and en_frac > 0:
        return "mixed"
    return overall if overall in {"te", "en"} else "en"


def _looks_mixed(text: str) -> bool:
    has_telugu = any(0x0C00 <= ord(c) <= 0x0C7F for c in text)
    has_latin = any(c.isascii() and c.isalpha() for c in text)
    return has_telugu and has_latin


@stage("detect_language", "v1")
def detect_language(chunks: list[Chunk], *, model_name: str) -> list[Chunk]:
    if not chunks:
        return []
    model = _load_model(model_name)
    out: list[Chunk] = []
    for c in chunks:
        lang = _classify_chunk(model, c.text)
        out.append(c.model_copy(update={"detected_lang": lang}))  # type: ignore[arg-type]
    counts = {"te": 0, "en": 0, "mixed": 0}
    for c in out:
        counts[c.detected_lang or "en"] = counts.get(c.detected_lang or "en", 0) + 1
    log.info("language counts: %s", counts)
    return out


def run(cfg: TvpConfig, chunks: list[Chunk], force: bool = False) -> list[Chunk]:
    return detect_language(
        chunks, model_name=cfg.ingest.language_detection_model, force=force
    )
