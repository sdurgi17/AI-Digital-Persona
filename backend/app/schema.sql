CREATE TABLE IF NOT EXISTS persona (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  profile_json TEXT,
  system_prompt TEXT,
  voice_id TEXT,
  voice_kind TEXT DEFAULT 'ivc',
  agent_id TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS interview_questions (
  id INTEGER PRIMARY KEY,
  ord INTEGER NOT NULL,
  category TEXT NOT NULL,
  text TEXT NOT NULL,
  min_seconds INTEGER DEFAULT 15
);

CREATE TABLE IF NOT EXISTS interview_answers (
  id INTEGER PRIMARY KEY,
  question_id INTEGER NOT NULL UNIQUE REFERENCES interview_questions(id),
  audio_path TEXT NOT NULL,
  duration_seconds REAL,
  transcript TEXT,
  language_code TEXT,
  status TEXT NOT NULL DEFAULT 'recorded',
  error TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  filename TEXT NOT NULL,
  file_path TEXT NOT NULL,
  mime TEXT,
  status TEXT NOT NULL DEFAULT 'uploaded',
  error TEXT,
  chunk_count INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY,
  source_type TEXT NOT NULL,
  document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
  answer_id INTEGER REFERENCES interview_answers(id),
  ord INTEGER,
  text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
