"""Stage 6 — extract_style_profile.

(1) Telugu LLM pass for phrases/openers/register/code-mix examples.
(2) Frequency-based extraction of preserved English vocabulary (≥3 occurrences),
    stopwords filtered.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter

from tvp.cache import stage
from tvp.config import TvpConfig
from tvp.llm import chat, load_prompt
from tvp.models import Chunk, StyleProfile

log = logging.getLogger(__name__)


_ENGLISH_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9\-]{1,}\b")

# Minimal English stopwords + words that aren't worth preserving as "vocab".
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on", "for",
    "with", "by", "at", "from", "as", "is", "was", "were", "be", "been", "being",
    "are", "am", "do", "does", "did", "have", "has", "had", "having", "i", "you",
    "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "this",
    "that", "these", "those", "my", "your", "his", "its", "our", "their", "not",
    "no", "yes", "so", "than", "then", "there", "here", "what", "which", "who",
    "whom", "whose", "when", "where", "why", "how", "all", "any", "both", "each",
    "few", "more", "most", "some", "such", "only", "own", "same", "too", "very",
    "can", "will", "just", "also", "into", "out", "up", "down", "over", "under",
    "again", "about", "after", "before", "between", "while", "during", "because",
    "would", "could", "should", "may", "might",
}

_MIN_VOCAB_OCCURRENCES = 3
_MAX_LLM_SAMPLE_CHARS = 12_000


def _telugu_sample(chunks: list[Chunk]) -> str:
    pieces: list[str] = []
    used = 0
    for c in chunks:
        if c.detected_lang not in {"te", "mixed"}:
            continue
        if used + len(c.text) > _MAX_LLM_SAMPLE_CHARS:
            break
        pieces.append(c.text)
        used += len(c.text)
    return "\n\n---\n\n".join(pieces)


def _llm_style(sample: str, model: str) -> dict:
    prompt = load_prompt("style_extraction.txt").replace("{{sample}}", sample)
    raw = chat(
        model=model,
        system="You are a careful linguistic-style analyst. Output JSON only.",
        user=prompt,
        temperature=0.2,
        max_tokens=1500,
    )
    # Strip code fences if present.
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return json.loads(s)


def _preserved_vocab(chunks: list[Chunk]) -> list[str]:
    counter: Counter[str] = Counter()
    for c in chunks:
        if c.detected_lang not in {"en", "mixed"}:
            continue
        for tok in _ENGLISH_TOKEN_RE.findall(c.text):
            low = tok.lower()
            if low in _STOPWORDS:
                continue
            if len(low) < 2:
                continue
            counter[tok] += 1
    out = [
        word
        for word, count in counter.most_common()
        if count >= _MIN_VOCAB_OCCURRENCES
    ]
    return out[:200]


@stage("style_profile", "v1")
def extract_style_profile(chunks: list[Chunk], *, model: str) -> StyleProfile:
    telugu_sample = _telugu_sample(chunks)
    llm_fields: dict = {}
    if telugu_sample:
        try:
            llm_fields = _llm_style(telugu_sample, model)
        except (json.JSONDecodeError, Exception) as e:  # noqa: BLE001
            log.warning("style LLM call failed: %s — using empty fields", e)
    else:
        log.warning(
            "no Telugu / mixed chunks found — style profile will be generic"
        )

    preserved = _preserved_vocab(chunks)

    profile = StyleProfile(
        characteristic_phrases=list(llm_fields.get("characteristic_phrases") or []),
        sentence_openers=list(llm_fields.get("sentence_openers") or []),
        register=llm_fields.get("register") or "mixed",
        preserved_vocabulary=preserved,
        code_mix_examples=list(llm_fields.get("code_mix_examples") or []),
    )
    log.info(
        "style profile: %d phrases, %d openers, register=%s, %d preserved vocab",
        len(profile.characteristic_phrases),
        len(profile.sentence_openers),
        profile.register,
        len(profile.preserved_vocabulary),
    )
    return profile


def run(cfg: TvpConfig, chunks: list[Chunk], force: bool = False) -> StyleProfile:
    return extract_style_profile(chunks, model=cfg.generation.llm_model, force=force)
