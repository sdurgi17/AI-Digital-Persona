"""Chat Stage 3 — generate.

Builds the persona prompt, calls the LLM via OpenRouter, parses out the citation
block. If out_of_corpus, short-circuit to the refusal phrase (no LLM call).
"""

from __future__ import annotations

import logging
import re

from tvp.config import TvpConfig
from tvp.llm import chat, load_prompt
from tvp.models import (
    GeneratedResponse,
    RetrievalResult,
    StyleProfile,
)

log = logging.getLogger(__name__)


_CITED_MEM_RE = re.compile(r"<cited_memories>(.*?)</cited_memories>", re.DOTALL)
_CITED_CHUNK_RE = re.compile(r"<cited_chunks>(.*?)</cited_chunks>", re.DOTALL)
_TAG_STRIP_RE = re.compile(r"<cited_(?:memories|chunks)>.*?</cited_(?:memories|chunks)>", re.DOTALL)


def _format_list(items: list[str], limit: int = 12) -> str:
    if not items:
        return "(none)"
    items = items[:limit]
    return "\n".join(f"- {x}" for x in items)


def _format_memories_block(result: RetrievalResult, top_n: int) -> str:
    if not result.memories:
        return "(none)"
    lines = []
    for r in result.memories[:top_n]:
        m = r.memory
        meta = []
        if m.date:
            meta.append(f"date={m.date}")
        if m.metric:
            meta.append(f"metric={m.metric}")
        if m.entities:
            meta.append(f"entities={','.join(m.entities)}")
        meta_str = f" [{'; '.join(meta)}]" if meta else ""
        lines.append(
            f"- id={m.id} type={m.type} score={r.score:.2f}{meta_str}\n    {m.claim}"
        )
    return "\n".join(lines)


def _format_chunks_block(result: RetrievalResult, top_n: int) -> str:
    if not result.chunks:
        return "(none)"
    lines = []
    for r in result.chunks[:top_n]:
        c = r.chunk
        snippet = c.text.strip().replace("\n", " ")
        if len(snippet) > 600:
            snippet = snippet[:600] + "…"
        lines.append(
            f"- id={c.id} source={c.source_file} offset={c.source_offset} score={r.score:.2f}\n    {snippet}"
        )
    return "\n".join(lines)


def _build_prompt(
    *,
    persona_name: str,
    question: str,
    style: StyleProfile,
    result: RetrievalResult,
    cfg: TvpConfig,
) -> str:
    template = load_prompt("generation.txt")
    return (
        template.replace("{{persona_name}}", persona_name)
        .replace("{{refusal_phrase}}", cfg.generation.refusal_phrase_telugu)
        .replace("{{register}}", style.register)
        .replace("{{characteristic_phrases}}", _format_list(style.characteristic_phrases))
        .replace("{{sentence_openers}}", _format_list(style.sentence_openers))
        .replace("{{preserved_vocabulary}}", _format_list(style.preserved_vocabulary, limit=40))
        .replace("{{code_mix_examples}}", _format_list(style.code_mix_examples, limit=7))
        .replace("{{memories_block}}", _format_memories_block(result, cfg.generation.top_memories))
        .replace("{{chunks_block}}", _format_chunks_block(result, cfg.generation.top_chunks))
        .replace("{{question}}", question)
    )


def _parse_citations(raw: str) -> tuple[str, list[str], list[str]]:
    mem_ids: list[str] = []
    chunk_ids: list[str] = []
    if (m := _CITED_MEM_RE.search(raw)):
        mem_ids = [x.strip() for x in m.group(1).split(",") if x.strip()]
    if (m := _CITED_CHUNK_RE.search(raw)):
        chunk_ids = [x.strip() for x in m.group(1).split(",") if x.strip()]
    clean = _TAG_STRIP_RE.sub("", raw).strip()
    return clean, mem_ids, chunk_ids


def generate(
    cfg: TvpConfig,
    persona_name: str,
    question: str,
    style: StyleProfile,
    result: RetrievalResult,
) -> GeneratedResponse:
    if result.out_of_corpus:
        log.info("out_of_corpus — short-circuit refusal")
        return GeneratedResponse(
            text=cfg.generation.refusal_phrase_telugu,
            refused=True,
        )

    prompt = _build_prompt(
        persona_name=persona_name,
        question=question,
        style=style,
        result=result,
        cfg=cfg,
    )
    raw = chat(
        model=cfg.generation.llm_model,
        system=None,
        user=prompt,
        temperature=cfg.generation.temperature,
        max_tokens=cfg.generation.max_tokens,
    )
    text, mem_ids, chunk_ids = _parse_citations(raw)

    refused = text.strip() == cfg.generation.refusal_phrase_telugu.strip()
    return GeneratedResponse(
        text=text,
        refused=refused,
        cited_memory_ids=mem_ids,
        cited_chunk_ids=chunk_ids,
    )


def run(
    cfg: TvpConfig,
    persona_name: str,
    question: str,
    style: StyleProfile,
    result: RetrievalResult,
) -> GeneratedResponse:
    return generate(cfg, persona_name, question, style, result)
