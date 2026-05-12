# SPEC.md — Telugu Voice Persona System (v1)

## Project name
`tvp` (Telugu Voice Persona)

## Goal
A script-based pipeline that:
1. Ingests a person's voice audio + documents describing them
2. Builds a queryable, voice-enabled digital persona
3. Answers typed questions in their cloned voice using only their own captured material

Persona is data, not code. The same scripts work for any persona; each persona is a `personas/<name>/` directory.

## Non-goals (v1)
- Web UI (deferred to v2)
- Voice/microphone input — text questions only
- Multi-turn conversation memory (single-turn only)
- Real-time streaming TTS or audio playback inside the script (audio saved to disk)
- Professional Voice Cloning (Instant Voice Cloning only; PVC is a config swap later)
- DOC (legacy binary) support — DOCX, PDF, MD, TXT only
- BM25 / hybrid retrieval (dense-only via BGE-M3)
- Code-switching at conversation level (English retained only for technical / professional vocabulary per Translation Policy)
- Eval harness (specified at end as next deliverable; not built in v1)

## Architecture

Two scripts. Persona artifact directory is the boundary between them.

```
┌──────────────────┐     ┌──────────────────┐
│ voice audio file │────▶│                  │
│ document files   │────▶│   ingest.py      │
└──────────────────┘     │  (one-shot)      │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ personas/<name>/ │
                         │  manifest.json   │
                         │  voice_id.txt    │
                         │  style.json      │
                         │  memories.db     │ ◀── SQLite (Tier 2)
                         │  sources/        │ ◀── archived source docs
                         │  source_audio    │ ◀── archived voice clone audio
                         └────────┬─────────┘
                                  │
                                  ▼ (+ Qdrant collection: persona_<name>_chunks)
                         ┌──────────────────┐
   text question  ────▶  │   chat.py        │  ────▶ audio file (MP3)
                         │   (REPL)         │  ────▶ printed text
                         │                  │  ────▶ JSONL conversation log
                         └──────────────────┘
```

Synchronous Python throughout. No async. Stage caching with hash-based invalidation. Pydantic contracts at every stage boundary.

## Translation policy (output language)

Output is **Telugu-primary**. The following are retained in original English (Latin script):
- Proper nouns: AWS, Lambda, Snowflake, Django, TOCA Football, etc.
- Technical vocabulary: migration, deployment, pipeline, database, retrieval, query, model, server, cache, latency, function, etc.
- Business/professional terms: meeting, client, deadline, sprint, manager, report, etc.
- Modern concepts without natural Telugu equivalent: startup, consultancy, dashboard, framework
- Numbers and units in technical context: 400GB, 95%, sub-2s

Translated to Telugu:
- Everyday verbs, nouns
- Family/relationships, emotions, sensory descriptions
- Connective tissue (prepositions, conjunctions, pronouns)
- Traditional or cultural concepts

**Decision rule when ambiguous:** if the word appears in English anywhere in the source corpus, keep English. Otherwise translate.

**Refusal phrase:** `నాకు దీని గురించి తెలియదు`

**Emotion / prosody:** insert ElevenLabs v3 audio tags inline where natural — `[smiling]`, `[thoughtfully]`, `[sarcastic]`, `[laughs]`, `[whispers]`. Tags stay in English brackets even when surrounding text is Telugu (ElevenLabs v3 expects English tag tokens).

## Pydantic contracts

```python
# === Core types ===

class Chunk(BaseModel):
    id: str                                    # uuid4
    text: str
    source_file: str                           # relative path under sources/
    source_offset: int                         # char offset in source
    token_count: int
    detected_lang: Literal["te", "en", "mixed"] | None = None

class AtomicMemory(BaseModel):
    id: str
    claim: str
    type: Literal[
        "professional_event", "achievement", "leadership",
        "relationship", "belief", "preference", "personal_fact",
        "skill", "education", "other"
    ]
    entities: list[str]
    date: str | None                           # ISO date or freeform ("Q2 2024")
    metric: str | None                         # "$200K/year", "60% reduction"
    source_chunk_id: str
    source_span: tuple[int, int] | None        # char offsets within chunk

class StyleProfile(BaseModel):
    characteristic_phrases: list[str]          # 10-20 phrases from corpus
    sentence_openers: list[str]                # 5-10 common openers
    register: Literal["formal", "casual", "mixed", "technical", "spiritual"]
    preserved_vocabulary: list[str]            # English terms speaker uses (≥3 occurrences)
    code_mix_examples: list[str]               # 5-7 exemplar sentences from corpus

class SourceFileHash(BaseModel):
    relative_path: str
    sha256: str
    bytes: int

class PersonaManifest(BaseModel):
    name: str
    voice_id: str                              # ElevenLabs ID
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
    out_of_corpus: bool                        # True if both tiers empty above threshold

class GeneratedResponse(BaseModel):
    text: str                                  # Telugu + retained English + inline audio tags
    refused: bool
    cited_memory_ids: list[str]
    cited_chunk_ids: list[str]

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
```

## Ingest stages (`ingest.py`)

All stages cached by hash of inputs + stage version.

### Stage 1 — `load_and_chunk`
- **In:** list of document paths
- **Out:** `list[Chunk]`
- Extractors:
  - PDF: `pymupdf` primary, `pdfplumber` fallback, Tesseract OCR (Telugu) as last resort if extracted text fails a Telugu-Unicode-presence validation
  - DOCX: `python-docx`
  - MD / TXT: read as UTF-8
- Chunk size: 400 tokens, 50-token overlap, sentence-boundary aware
- Sentence boundary detection: IndicNLP `sentence_tokenize` for Telugu chunks, NLTK punkt for English chunks (route by language detection done in Stage 2; first pass uses naive split, second pass re-chunks based on language)
- Source files copied to `personas/<name>/sources/<sha256>.<ext>` and referenced by relative path

### Stage 2 — `detect_language`
- **In:** `list[Chunk]`
- **Out:** same chunks, `detected_lang` populated
- fastText `lid.176.bin` per chunk
- Tag: `te`, `en`, or `mixed` (both languages present, neither dominant)

### Stage 3 — `extract_atomic_memories` (Tier 2)
- **In:** `list[Chunk]`
- **Out:** `list[AtomicMemory]`
- One LLM call per chunk via OpenRouter (default: `anthropic/claude-sonnet-4.5`), prompt at `tvp/prompts/memory_extraction.txt`
- Prompt instructs extraction of discrete factual claims with the schema above
- Output validated against Pydantic; on failure, retry once with a stricter prompt variant; on second failure, log warning and skip that chunk's memories (chunk is still indexed in Tier 1)
- Parallelize with `ThreadPoolExecutor`, default 5 workers (configurable)
- Memories never duplicate; each gets a uuid4

### Stage 4 — `embed`
- **In:** `list[Chunk]` + `list[AtomicMemory]`
- **Out:** chunks and memories with attached embeddings
- Model: `BAAI/bge-m3` (sentence-transformers), local, 1024-dim
- Embed `chunk.text` for chunks
- Embed `memory.claim` for memories

### Stage 5 — `index`
- **In:** embedded chunks and memories
- **Out:** Qdrant collection populated; SQLite memories table populated
- Qdrant collection name: `persona_<name>_chunks`, distance metric cosine
- SQLite schema:

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    claim TEXT NOT NULL,
    type TEXT NOT NULL,
    entities TEXT NOT NULL,        -- JSON array
    date TEXT,
    metric TEXT,
    source_chunk_id TEXT NOT NULL,
    source_span TEXT,              -- JSON [start, end]
    embedding BLOB NOT NULL        -- float32 numpy bytes
);
CREATE INDEX idx_type ON memories(type);
-- entities filtered via JSON1 LIKE; no dedicated index in v1
```

### Stage 6 — `extract_style_profile`
- **In:** `list[Chunk]`
- **Out:** `StyleProfile`
- Two sub-passes:
  1. **Telugu style extraction:** single LLM call via OpenRouter (default: `anthropic/claude-sonnet-4.5`) with a sample of Telugu-only chunks; returns characteristic phrases, sentence openers, register, code_mix_examples (prompt at `tvp/prompts/style_extraction.txt`)
  2. **Preserved vocabulary:** frequency analysis over English-tagged tokens (`detected_lang == "en"` chunks + English tokens from `mixed` chunks); threshold ≥3 occurrences; filter out stopwords

If the corpus has no Telugu chunks, leave Telugu-specific fields empty and log a warning — the persona will sound generically Telugu rather than reflecting a unique style.

### Stage 7 — `clone_voice`
- **In:** voice audio file path
- **Out:** ElevenLabs voice ID written to `voice_id.txt`
- ElevenLabs Instant Voice Cloning API
- Audio: 1-5 minutes of clean mono audio, 16kHz+ sample rate, single speaker
- Audio file archived as `personas/<name>/source_audio.<ext>`

### Stage 8 — `write_manifest`
- Assemble `PersonaManifest` from prior stage outputs
- Write `manifest.json` (pretty-printed)
- Print ingest summary: chunk count, memory count, source file count, voice_id

## Chat stages (`chat.py`)

### Stage 1 — `load_persona`
- **In:** persona name
- **Out:** loaded `PersonaManifest`, Qdrant client, SQLite connection, ElevenLabs voice ID
- Verify Qdrant collection exists and SQLite memories table is populated; abort with clear error if not
- Print: persona name, source count, memory count, last-ingested timestamp

### Stage 2 — `retrieve`
- **In:** question text
- **Out:** `RetrievalResult`
- Embed question with BGE-M3
- **Tier 1:** Qdrant vector search, top 5 chunks
- **Tier 2:** SQLite — both:
  - Vector similarity over `memories.embedding` (top 5 by cosine)
  - Entity match: extract candidate entities from question via a small Haiku-class LLM call via OpenRouter (default: `anthropic/claude-haiku-4.5`), cached by question hash; SQL filter `entities LIKE '%<entity>%'`
- Score thresholds: 0.55 for chunks, 0.60 for memory vector matches
- `out_of_corpus = True` if both lists empty after threshold filtering AND entity match returns nothing

### Stage 3 — `generate`
- **In:** question, `RetrievalResult`, `StyleProfile`
- **Out:** `GeneratedResponse`
- If `out_of_corpus`: return refusal phrase immediately, skip LLM call, `refused=True`
- Otherwise LLM call via OpenRouter (default: `anthropic/claude-sonnet-4.5`), temperature 0.3, max_tokens 800
- Prompt (template at `tvp/prompts/generation.txt`) includes:
  - Persona identity (name from manifest)
  - Translation policy (verbatim)
  - Style profile (phrases, openers, register, preserved_vocabulary)
  - 3-5 few-shot exemplars from `code_mix_examples`
  - Top 3 retrieved chunks (with source labels)
  - Top 5 retrieved memories (with ids)
  - Strict refusal instruction: "If memories are insufficient, respond ONLY with: నాకు దీని గురించి తెలియదు"
  - ElevenLabs v3 audio-tag instruction with examples
- Response parser extracts cited memory/chunk ids if the LLM was asked to list them (instruction in prompt requests `<cited_memories>...</cited_memories>` block at end, stripped before TTS)

### Stage 4 — `synthesize`
- **In:** generated text (with audio tags)
- **Out:** path to MP3
- ElevenLabs Multilingual v3 with cloned voice_id
- Fallback to Multilingual v2 if v3 fails or is configured off (single config flag)
- Output: `runs/<session_id>/turn_<N>.mp3`
- If `refused`: still synthesize the refusal phrase (the cloned voice saying "I don't know about this" is part of the persona)

### Stage 5 — `log_turn`
- Append `ChatTurn` as a single JSONL line to `runs/<session_id>.jsonl`
- Print to console: generated text, audio file path, latency summary

## Persona artifact layout

```
personas/<name>/
├── manifest.json
├── voice_id.txt
├── style.json
├── memories.db          (SQLite)
├── sources/
│   ├── <sha256>.pdf
│   ├── <sha256>.docx
│   └── ...
└── source_audio.<ext>
```

Qdrant collections live in the Qdrant server (external), named `persona_<name>_chunks`. Manifest records the collection name for portability.

## CLI surface

```bash
# Ingest (one-shot)
python ingest.py \
  --persona srikar \
  --voice path/to/voice.wav \
  --docs path/to/doc1.pdf path/to/doc2.md path/to/profile.txt \
  [--config config.toml] \
  [--force]                  # bypass stage cache, full rebuild

# Chat (interactive REPL)
python chat.py --persona srikar

# Example session
> What did you do at TOCA?
[retrieve 142ms] [generate 1820ms] [tts 2410ms] [total 4372ms]
మీరు TOCA లో analytics stack ని Redshift నుండి Snowflake కి migrate చేశారు. [thoughtfully]
ఇది approximately $200K annually save చేసింది, మరియు query latency 60% తగ్గింది.
[audio: runs/2026-05-12_14-32-01/turn_1.mp3]

> :sources
- memory mem_003: Migration saved ~$200K annually
- memory mem_004: Migration reduced query latency by 60%
- chunk c_47 (project-report.pdf, offset 1240)

> :q
```

In-REPL commands:
- plain text → question
- `:sources` → print citations for last turn
- `:q` / `:quit` → exit

## Configuration

`config.toml` at project root:

```toml
[ingest]
chunk_size = 400
chunk_overlap = 50
embed_model = "BAAI/bge-m3"
extract_memories = true        # set false to skip Tier 2
memory_extraction_workers = 5
language_detection_model = "lid.176.bin"

[generation]
llm_provider = "openrouter"
llm_base_url = "https://openrouter.ai/api/v1"
llm_model = "anthropic/claude-sonnet-4.5"
entity_extraction_model = "anthropic/claude-haiku-4.5"
temperature = 0.3
max_tokens = 800
chunk_score_threshold = 0.55
memory_score_threshold = 0.60
top_chunks = 3
top_memories = 5
refusal_phrase_telugu = "నాకు దీని గురించి తెలియదు"

[tts]
provider = "elevenlabs"
model = "eleven_v3"
fallback_model = "eleven_multilingual_v2"
use_audio_tags = true
output_format = "mp3_44100_128"

[storage]
qdrant_url = "http://localhost:6333"
personas_root = "./personas"
runs_root = "./runs"

[logging]
level = "INFO"
conversation_log = true
```

Secrets in `.env`:
```
OPENROUTER_API_KEY=...
ELEVENLABS_API_KEY=...
COHERE_API_KEY=...             # reserved for v2 reranker
SARVAM_API_KEY=...             # reserved for v2 voice input ASR
```

OpenRouter exposes an OpenAI-compatible API. Use the `openai` Python SDK with `base_url=https://openrouter.ai/api/v1` and `api_key=$OPENROUTER_API_KEY`. Model swaps (Claude → GPT → Llama → Gemini) are config-only — no code changes. Useful for cost/quality A/B tests when the eval harness lands.

## Project layout

```
project_root/
├── ingest.py
├── chat.py
├── tvp/
│   ├── __init__.py
│   ├── models.py              # Pydantic types
│   ├── config.py              # config loader (pydantic-settings)
│   ├── cache.py               # stage() decorator + hash logic
│   ├── stages/
│   │   ├── load_chunk.py
│   │   ├── detect_language.py
│   │   ├── extract_memories.py
│   │   ├── embed.py
│   │   ├── index.py
│   │   ├── style_profile.py
│   │   ├── clone_voice.py
│   │   ├── retrieve.py
│   │   ├── generate.py
│   │   ├── synthesize.py
│   │   └── log_turn.py
│   └── prompts/
│       ├── memory_extraction.txt
│       ├── style_extraction.txt
│       ├── generation.txt
│       └── entity_extraction.txt
├── personas/                  # persona artifacts
├── runs/                      # session logs + audio
├── stage_cache/               # cached stage outputs by hash
├── config.toml
├── .env
└── requirements.txt
```

## Environment
- Python 3.11+
- Qdrant running locally (Docker: `qdrant/qdrant:latest` on port 6333)
- System deps: `libportaudio2` (placeholder; not strictly needed in v1 since no mic), Tesseract with Telugu data (`tesseract-ocr-tel`) for PDF OCR fallback

## Open decisions (resolved during implementation, not blocking)

- Token counter for chunking: IndicNLP for Telugu-accurate chunk sizing, tiktoken for LLM budgeting. Recommend dual approach.
- Memory entity extraction at ingest: rely on the LLM extraction call's output (entities field on AtomicMemory) rather than a separate NER pass. Re-evaluate if entity match quality is poor.
- ElevenLabs v3 vs v2 for Telugu quality: smoke test (see Validation below). Config has both with a fallback flag.
- IVC adequacy for Telugu cloning: smoke test required before full corpus ingest. If IVC quality is unacceptable, jump straight to PVC.

## Validation gates (before declaring v1 complete)

1. **Voice clone smoke test.** Record 5-10 min of clean Telugu audio. Run Stage 7 only. Generate 5 test sentences (mix of pure Telugu, technical-English-retained Telugu, pure English). Native-speaker rate naturalness 1-5. **Kill criterion:** mean < 3.5/5.
2. **Memory extraction sample review.** Run Stage 3 on 5 representative chunks. Manually inspect 25-30 extracted memories. Reject if >15% have wrong type, false claims, or missing entities.
3. **Retrieval sanity check.** Hand-label 20 question→expected-memory pairs. Measure recall@5. **Kill criterion:** recall@5 < 0.6.
4. **End-to-end refusal check.** Run 10 obviously out-of-corpus questions through chat.py. **Kill criterion:** any hallucinated answer (refusal phrase must trigger ≥9/10).

Pass all four → v1 is shippable.

## Next deliverable: eval harness (`eval.py`)

Not built in v1. Spec'd here so the data plumbing (JSONL conversation logging) is built to support it.

A standalone script that runs a labeled question set through `chat.py` programmatically and computes:

1. **Faithfulness benchmark.** 100 hand-crafted questions across in-corpus / partially-answerable / out-of-corpus buckets. Report: correct / correct refusal / hallucination.
2. **Refusal calibration.** Out-of-corpus refusal rate vs hallucination rate.
3. **Retrieval quality.** Recall@5, MRR on labeled question→memory mappings.
4. **Persona consistency.** Same 30 questions × 5 runs; pairwise semantic similarity of responses (BGE-M3 cosine).
5. **Voice naturalness MOS.** Recruited Telugu speakers blind-rate; eval script aggregates their inputs.
6. **Latency.** p50/p95 of stages, aggregated from JSONL logs.

This is the artifact that turns the project from "RAG chatbot" into something a hiring manager actually reads twice.

## Handoff notes for Claude Code

Implementation order:
1. `tvp/models.py`, `tvp/config.py`, `tvp/cache.py` — foundation
2. `tvp/stages/load_chunk.py` + `detect_language.py` — verify on a small (3-5 doc) corpus
3. `tvp/stages/clone_voice.py` — independent; run smoke test in isolation before continuing
4. `tvp/stages/extract_memories.py` — iterate on the prompt against a 5-chunk sample until output is clean
5. `tvp/stages/embed.py` + `index.py`
6. `tvp/stages/style_profile.py`
7. `ingest.py` orchestration + manifest writer (Stage 8)
8. `tvp/stages/retrieve.py` + `generate.py`
9. `tvp/stages/synthesize.py` + `log_turn.py`
10. `chat.py` REPL

Smoke test after each stage; do not build everything then test.

Highest-risk areas, in order:
1. ElevenLabs IVC quality on Telugu — existential. Validate first.
2. Telugu PDF text extraction — build the pymupdf → pdfplumber → OCR fallback chain explicitly.
3. Atomic memory extraction prompt — needs iteration, not single-pass.
4. Refusal calibration — under-tested in most RAG systems; verify aggressively.