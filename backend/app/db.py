import sqlite3
from pathlib import Path

import sqlite_vec

from .config import get_settings

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db() -> sqlite3.Connection:
    """New connection per request/task; cheap for SQLite and thread-safe this way."""
    settings = get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def init_db() -> None:
    settings = get_settings()
    settings.interview_audio_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    try:
        conn.executescript(SCHEMA_PATH.read_text())
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING "
            f"vec0(embedding float[{settings.embedding_dim}])"
        )
        _seed_questions(conn)
        conn.commit()
    finally:
        conn.close()


def _seed_questions(conn: sqlite3.Connection) -> None:
    from .questions import QUESTION_BANK

    existing = conn.execute("SELECT COUNT(*) FROM interview_questions").fetchone()[0]
    if existing:
        return
    conn.executemany(
        "INSERT INTO interview_questions (ord, category, text, min_seconds) VALUES (?, ?, ?, ?)",
        [(q["ord"], q["category"], q["text"], q["min_seconds"]) for q in QUESTION_BANK],
    )
