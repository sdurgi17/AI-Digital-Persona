"""Pydantic contracts for every stage boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# === Core types ===


class Chunk(BaseModel):
    id: str
    text: str
    source_file: str
    source_offset: int
    token_count: int
    detected_lang: Literal["te", "en", "mixed"] | None = None


class AtomicMemory(BaseModel):
    id: str
    claim: str
    type: Literal[
        "professional_event",
        "achievement",
        "leadership",
        "relationship",
        "belief",
        "preference",
        "personal_fact",
        "skill",
        "education",
        "other",
    ]
    entities: list[str]
    date: str | None = None
    metric: str | None = None
    source_chunk_id: str
    source_span: tuple[int, int] | None = None


class StyleProfile(BaseModel):
    characteristic_phrases: list[str] = Field(default_factory=list)
    sentence_openers: list[str] = Field(default_factory=list)
    register: Literal["formal", "casual", "mixed", "technical", "spiritual"] = "mixed"
    preserved_vocabulary: list[str] = Field(default_factory=list)
    code_mix_examples: list[str] = Field(default_factory=list)


class SourceFileHash(BaseModel):
    relative_path: str
    sha256: str
    bytes: int


class PersonaManifest(BaseModel):
    name: str
    voice_id: str
    qdrant_collection: str
    sqlite_path: str
    style_profile: StyleProfile
    source_files: list[SourceFileHash]
    chunk_count: int
    memory_count: int
    created_at: datetime
    ingest_config: dict


# === Chat-time types ===


class RetrievedChunk(BaseModel):
    chunk: Chunk
    score: float


class RetrievedMemory(BaseModel):
    memory: AtomicMemory
    score: float
    match_type: Literal["vector", "entity"]


class RetrievalResult(BaseModel):
    chunks: list[RetrievedChunk]
    memories: list[RetrievedMemory]
    out_of_corpus: bool


class GeneratedResponse(BaseModel):
    text: str
    refused: bool
    cited_memory_ids: list[str] = Field(default_factory=list)
    cited_chunk_ids: list[str] = Field(default_factory=list)


class LatencyBreakdown(BaseModel):
    retrieval_ms: int
    generation_ms: int
    tts_ms: int
    total_ms: int


class ChatTurn(BaseModel):
    turn_id: str
    session_id: str
    timestamp: datetime
    question: str
    retrieved_chunks: list[RetrievedChunk]
    retrieved_memories: list[RetrievedMemory]
    generated_text: str
    audio_path: str
    refused: bool
    cited_memory_ids: list[str]
    cited_chunk_ids: list[str]
    latency_ms: LatencyBreakdown
