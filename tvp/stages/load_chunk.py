"""Stage 1 — load_and_chunk.

Extract text from PDF/DOCX/MD/TXT, copy sources into the persona dir under their
sha256-named filenames, and chunk text (sentence-aware, 400 tokens / 50 overlap).
"""

from __future__ import annotations

import logging
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from tvp.cache import hash_file, stage
from tvp.config import TvpConfig
from tvp.models import Chunk, SourceFileHash

log = logging.getLogger(__name__)

TELUGU_RANGE = (0x0C00, 0x0C7F)
SUPPORTED_EXTS = {".pdf", ".docx", ".md", ".txt"}


# === Extraction ===


def _has_telugu(text: str, min_chars: int = 10) -> bool:
    count = sum(1 for c in text if TELUGU_RANGE[0] <= ord(c) <= TELUGU_RANGE[1])
    return count >= min_chars


def _extract_pdf(path: Path) -> str:
    """pymupdf primary, pdfplumber fallback, Tesseract OCR (Telugu) last resort."""
    text = ""
    try:
        import pymupdf  # type: ignore

        with pymupdf.open(path) as doc:
            text = "\n\n".join(page.get_text() for page in doc)
    except Exception as e:  # pragma: no cover
        log.warning("pymupdf failed on %s: %s", path, e)
        text = ""

    if text.strip() and _has_telugu_or_english(text):
        return text

    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(path) as pdf:
            text = "\n\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:  # pragma: no cover
        log.warning("pdfplumber failed on %s: %s", path, e)
        text = ""

    if text.strip() and _has_telugu_or_english(text):
        return text

    # OCR fallback. Needs Tesseract + tesseract-ocr-tel.
    log.info("falling back to OCR for %s", path)
    return _ocr_pdf(path)


def _has_telugu_or_english(text: str) -> bool:
    # Reject if the page came back as 99% rendering glyphs / mojibake; accept if
    # we see Telugu or a healthy run of ASCII letters.
    if _has_telugu(text):
        return True
    letters = sum(1 for c in text if c.isalpha() and c.isascii())
    return letters >= 50


def _ocr_pdf(path: Path) -> str:
    try:
        import pymupdf  # type: ignore
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        import io
    except Exception as e:
        log.error("OCR dependencies missing: %s", e)
        return ""

    out = []
    with pymupdf.open(path) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            try:
                out.append(pytesseract.image_to_string(img, lang="tel+eng"))
            except Exception as e:  # pragma: no cover
                log.warning("tesseract failed on page %d: %s", page.number, e)
    return "\n\n".join(out)


def _extract_docx(path: Path) -> str:
    from docx import Document  # type: ignore

    doc = Document(str(path))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".docx":
        return _extract_docx(path)
    if ext in {".md", ".txt"}:
        return _extract_text(path)
    raise ValueError(f"Unsupported file type: {ext} ({path})")


# === Chunking ===


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.\!\?。!?।])\s+|\n{2,}")


def _split_sentences_naive(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _approx_tokens(text: str) -> int:
    """Cheap token estimator: ~1 token per 3.5 chars (heuristic that works across
    Latin + Telugu for chunking purposes; the LLM uses its own tokenizer)."""
    return max(1, len(text) // 4)


@dataclass
class _Window:
    text: str
    source_offset: int
    token_count: int


def _chunk_text(
    text: str,
    source_file: str,
    *,
    chunk_size: int,
    overlap: int,
) -> list[Chunk]:
    sentences = _split_sentences_naive(text)
    if not sentences:
        return []

    # We need character offsets back into the source text. Walk both lists.
    windows: list[_Window] = []
    cursor = 0
    sentence_spans: list[tuple[str, int]] = []
    for s in sentences:
        idx = text.find(s, cursor)
        if idx == -1:
            idx = cursor
        sentence_spans.append((s, idx))
        cursor = idx + len(s)

    i = 0
    n = len(sentence_spans)
    while i < n:
        cur_text = ""
        cur_tokens = 0
        start_offset = sentence_spans[i][1]
        j = i
        while j < n and cur_tokens < chunk_size:
            s, _ = sentence_spans[j]
            t = _approx_tokens(s)
            if cur_tokens and cur_tokens + t > chunk_size:
                break
            cur_text = f"{cur_text} {s}".strip() if cur_text else s
            cur_tokens += t
            j += 1

        if cur_text:
            windows.append(
                _Window(text=cur_text, source_offset=start_offset, token_count=cur_tokens)
            )

        if j == i:
            j = i + 1  # single oversized sentence — emit alone

        if j >= n:
            break

        # Slide: roll back by overlap tokens.
        back = 0
        k = j
        while k > i and back < overlap:
            back += _approx_tokens(sentence_spans[k - 1][0])
            k -= 1
        i = max(k, i + 1)

    return [
        Chunk(
            id=str(uuid.uuid4()),
            text=w.text,
            source_file=source_file,
            source_offset=w.source_offset,
            token_count=w.token_count,
        )
        for w in windows
    ]


# === Public stage ===


def _archive_source(path: Path, persona_dir: Path) -> SourceFileHash:
    sha = hash_file(path)
    sources_dir = persona_dir / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    dest = sources_dir / f"{sha}{path.suffix.lower()}"
    if not dest.exists():
        shutil.copy2(path, dest)
    return SourceFileHash(
        relative_path=str(dest.relative_to(persona_dir)),
        sha256=sha,
        bytes=path.stat().st_size,
    )


@stage("load_chunk", "v1")
def load_and_chunk(
    doc_paths: list[str],
    persona_dir: str,
    *,
    chunk_size: int = 400,
    chunk_overlap: int = 50,
) -> tuple[list[Chunk], list[SourceFileHash]]:
    persona_path = Path(persona_dir)
    all_chunks: list[Chunk] = []
    archived: list[SourceFileHash] = []

    for p in doc_paths:
        src = Path(p)
        if not src.exists():
            log.warning("doc not found: %s — skipping", src)
            continue
        if src.suffix.lower() not in SUPPORTED_EXTS:
            log.warning(
                "unsupported file %s (only %s) — skipping",
                src,
                ", ".join(sorted(SUPPORTED_EXTS)),
            )
            continue

        hashed = _archive_source(src, persona_path)
        archived.append(hashed)

        text = extract(src)
        if not text.strip():
            log.warning("extracted no text from %s", src)
            continue

        chunks = _chunk_text(
            text,
            source_file=hashed.relative_path,
            chunk_size=chunk_size,
            overlap=chunk_overlap,
        )
        log.info("loaded %s — %d chunks", src.name, len(chunks))
        all_chunks.extend(chunks)

    return all_chunks, archived


def run(cfg: TvpConfig, persona_dir: Path, doc_paths: list[str], force: bool = False):
    return load_and_chunk(
        doc_paths,
        str(persona_dir),
        chunk_size=cfg.ingest.chunk_size,
        chunk_overlap=cfg.ingest.chunk_overlap,
        force=force,
    )
