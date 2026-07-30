import json
import re
import sqlite3

from .llm.base import get_provider

PROFILE_INSTRUCTIONS = """\
You are building a persona profile from interview transcripts. The transcripts below are \
verbatim answers a person gave about themselves (question shown before each answer). \
Extract a profile as STRICT JSON matching exactly this shape (no markdown, no commentary):

{
  "identity": {"name": "...", "one_line_self_description": "..."},
  "biography_facts": ["..."],
  "speaking_style": {
    "tone": "...", "pace": "...", "vocabulary_quirks": ["..."],
    "typical_phrases": ["..."], "sentence_length": "...", "humor": "..."
  },
  "values_and_opinions": ["..."],
  "signature_stories": [{"title": "...", "gist": "..."}],
  "topics_confident": ["..."],
  "topics_avoid": ["..."]
}

Derive speaking_style from HOW the person actually talks in the transcripts (fillers, \
phrasing, rhythm), not from what they claim. typical_phrases must be verbatim snippets. \
If the transcripts are partly in Telugu or another language, keep quirks/phrases in the \
original language and note bilingualism in tone. Use empty arrays when there is no evidence.
"""

SYSTEM_PROMPT_TEMPLATE = """\
You are {name} — not an assistant playing {name}, but {name}'s digital persona, speaking \
in the first person at all times.

Who you are: {self_description}

Key facts about your life:
{facts}

Your values and opinions:
{values}

How you speak: {style_summary}
Typical phrases you use: {phrases}

Rules for speaking (this is a live voice conversation):
- Answer in 1–3 sentences unless the person asks for detail. No markdown, no lists, no URLs.
- Speak naturally, the way {name} does — same tone, same quirks.
- Reply in the language the person is speaking to you (you speak English and Telugu).
- When excerpts from your own documents or interviews are provided, prefer them over guessing.
- Never invent biographical facts. If you don't know something about your own life, say so \
the way {name} would.
"""


async def build_profile(conn: sqlite3.Connection) -> dict:
    answers = conn.execute(
        """
        SELECT q.text AS question, a.transcript
        FROM interview_answers a JOIN interview_questions q ON q.id = a.question_id
        WHERE a.status = 'transcribed' AND a.transcript IS NOT NULL
        ORDER BY q.ord
        """
    ).fetchall()
    if not answers:
        raise ValueError("No transcribed interview answers yet — finish the interview first.")

    transcript_block = "\n\n".join(f"Q: {a['question']}\nA: {a['transcript']}" for a in answers)
    provider = get_provider()
    raw = await provider.complete(
        [
            {"role": "system", "content": PROFILE_INSTRUCTIONS},
            {"role": "user", "content": transcript_block},
        ],
        max_tokens=2048,
    )
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Profile extraction did not return JSON: {raw[:200]}")
    return json.loads(match.group(0))


def render_system_prompt(profile: dict) -> str:
    identity = profile.get("identity", {})
    style = profile.get("speaking_style", {})
    name = identity.get("name") or "the persona"

    style_bits = [style.get("tone"), style.get("pace"), style.get("sentence_length"), style.get("humor")]
    style_summary = "; ".join(b for b in style_bits if b) or "natural and conversational"

    def bullets(items: list) -> str:
        return "\n".join(f"- {item}" for item in items) or "- (none recorded yet)"

    stories = [f"{s.get('title', '')}: {s.get('gist', '')}" for s in profile.get("signature_stories", [])]

    return SYSTEM_PROMPT_TEMPLATE.format(
        name=name,
        self_description=identity.get("one_line_self_description", ""),
        facts=bullets(profile.get("biography_facts", []) + stories),
        values=bullets(profile.get("values_and_opinions", [])),
        style_summary=style_summary,
        phrases=", ".join(style.get("typical_phrases", [])) or "(none recorded)",
    )
