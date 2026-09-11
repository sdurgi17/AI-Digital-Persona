# AI Digital Persona

Create an AI digital persona of yourself: the app interviews you (recording your voice),
clones your voice with ElevenLabs Instant Voice Clone, ingests your documents for RAG,
and then lets you hold a **real-time voice conversation** with your persona — in English
or Telugu.

## Architecture

- **Frontend**: Vite + React (TS) — the "Echo" flow: welcome → spoken interview → voice clone →
  knowledge → live call, plus text chat, all bilingual (English/తెలుగు). Live voice goes through
  `@elevenlabs/react` (WebRTC).
- **Backend**: FastAPI — SQLite (+ `sqlite-vec` for vectors in the same DB file), Scribe STT
  for interview transcription, IVC voice cloning, document ingestion/chunking/embedding,
  persona-profile extraction, and an **OpenAI-compatible `/v1/chat/completions` gateway**.
- **Real-time voice**: an ElevenLabs Agent handles STT, turn-taking, interruptions and
  streaming TTS in your cloned voice. Its "Custom LLM" points at our gateway, which does
  per-turn RAG over your documents + interview answers and streams from Claude or OpenAI.

```
you speak ⇄ ElevenLabs Agent (STT · turn-taking · TTS in your voice)
                     ⇅ custom-LLM webhook (tunnel)
        FastAPI gateway → RAG (sqlite-vec) → Claude / OpenAI (streamed)
```

## Prerequisites

- Python 3.11+, Node 18+
- ElevenLabs account (IVC requires a **paid** plan; Agents minutes are billed per-minute)
- An Anthropic or OpenAI API key (LLM), and an OpenAI key for embeddings (default)
- Optional: `ffmpeg` (better voice-clone audio conversion; webm is uploaded as-is without it)
- Only for live voice: a tunnel — `ngrok` (free static domain) or `cloudflared`

## Setup

```bash
cp .env.example .env       # fill in keys

# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# frontend (new terminal)
cd frontend
npm install
npm run dev                # http://localhost:5173
```

## Usage flow

The welcome screen walks you straight through steps 1–4; the dashboard is where you come back to
for anything still outstanding. Use the EN/తెలుగు toggle (top right) at any point — it switches the
whole interface, including the interview questions and the language the live agent speaks.

1. **Welcome** → enter your name to create the persona, then "Begin the interview".
2. **Interview** → answer 6 short questions (~3 min total). Recordings are transcribed with
   Scribe automatically; they also become the voice-clone samples, so: quiet room, close mic.
   The meter on the left tracks the 60 s of audio an instant clone needs.
3. **Voice** → clones your voice with ElevenLabs IVC and lets you audition the result.
4. **Knowledge** (optional) → drop in PDFs/DOCX/TXT/MD or paste raw text; the persona cites them.
   "Create my persona" then extracts your bio/values/speaking style into the system prompt and
   indexes the transcripts for RAG.
5. **Text chat** → test the persona brain for free (works in English and Telugu).
6. **Live voice**:
   ```bash
   ngrok http 8000                     # note the https URL
   # .env → PUBLIC_BASE_URL=https://... and CUSTOM_LLM_SHARED_SECRET=<random 32+ chars>
   # restart uvicorn, then hit "Provision" on the dashboard
   ```
   Open **Live** and start the call.

## Testing the gateway without ElevenLabs (M4 check)

```python
from openai import OpenAI
client = OpenAI(base_url="https://YOUR-TUNNEL/v1", api_key="YOUR_CUSTOM_LLM_SHARED_SECRET")
stream = client.chat.completions.create(
    model="persona-rag",
    messages=[{"role": "user", "content": "who are you?"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")
```

A wrong api_key must return 401. If this streams correctly, the voice agent will work.

## Gotchas

- **A cloned voice restricts which brain the agent can use.** ElevenLabs rejects a
  custom LLM on an agent whose voice is an **Instant** Voice Clone
  (`custom_llm_not_allowed_in_with_agent_with_ivc_voice`) — undocumented, enforced
  only at the API. So `AGENT_LLM_MODE=builtin` (their model + their knowledge base)
  is the only option with an IVC. A **Professional** Voice Clone lifts the
  restriction, which is what makes `AGENT_LLM_MODE=custom` — your own gateway and
  sqlite-vec RAG — possible. Point the persona at a PVC trained in their dashboard
  with `PUT /api/persona/voice`.
- **Editing `.env` alone changes nothing.** `get_settings()` is cached and `--reload`
  watches `backend/`, not the repo-root `.env` — restart uvicorn after every edit.
- **Telugu live calls are not possible.** ElevenLabs Agents supports `hi` and `ta` but
  not `te`, so calls are English-only; text chat still handles Telugu.
- **Silent agent in voice chat** ⇒ the tunnel is down or `PUBLIC_BASE_URL` changed
  (only matters in `custom` mode). Restart the tunnel, update `.env`, restart uvicorn,
  hit "Re-sync" on the dashboard.
- **Voice quality** is capped by recording quality: quiet room, consistent tone.
  ElevenLabs may flag the voice `requires_verification` (check their dashboard).
- **Changing `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`** after ingesting refuses to mix vectors:
  delete documents and rebuild the persona (or delete `backend/data/app.db`) to re-embed.
- Swap in a longer interview later by editing `backend/app/questions.py` and deleting
  `backend/data/app.db` (or the `interview_questions` rows).

## Tests

```bash
cd backend && source .venv/bin/activate && pytest
```
