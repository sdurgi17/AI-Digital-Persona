import json
import logging
import re
import sqlite3
from pathlib import Path

from .embeddings import check_embedding_consistency, get_embedder

logger = logging.getLogger(__name__)

CHUNK_TARGET = 1200
CHUNK_OVERLAP = 200


def parse_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        from docx import Document

        doc = Document(str(path))
        return "\n\n".join(p.text for p in doc.paragraphs)
    if suffix in (".txt", ".md", ".markdown"):
        return path.read_text(encoding="utf-8", errors="replace")
    raise ValueError(f"Unsupported file type: {suffix} (supported: pdf, docx, txt, md)")


def chunk_text(text: str) -> list[str]:
    """Paragraph-aware splitter targeting ~CHUNK_TARGET chars with overlap."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        while len(para) > CHUNK_TARGET:  # oversized paragraph: hard split
            if current:
                chunks.append(current)
                current = ""
            chunks.append(para[:CHUNK_TARGET])
            para = para[CHUNK_TARGET - CHUNK_OVERLAP :]
        if current and len(current) + len(para) + 2 > CHUNK_TARGET:
            chunks.append(current)
            current = current[-CHUNK_OVERLAP:] + "\n\n" + para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks


def store_chunks(
    conn: sqlite3.Connection,
    texts: list[str],
    source_type: str,
    document_id: int | None = None,
    answer_id: int | None = None,
) -> int:
    if not texts:
        return 0
    check_embedding_consistency(conn)
    embeddings = get_embedder().embed(texts)
    for ord_, (text, emb) in enumerate(zip(texts, embeddings)):
        cur = conn.execute(
            "INSERT INTO chunks (source_type, document_id, answer_id, ord, text) VALUES (?, ?, ?, ?, ?)",
            (source_type, document_id, answer_id, ord_, text),
        )
        conn.execute(
            "INSERT INTO chunks_vec (rowid, embedding) VALUES (?, ?)",
            (cur.lastrowid, json.dumps(emb)),
        )
    conn.commit()
    return len(texts)


def ingest_document(document_id: int) -> None:
    """Background task: parse → chunk → embed → store one uploaded document."""
    from ..db import get_db

    conn = get_db()
    try:
        row = conn.execute("SELECT file_path FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            return
        conn.execute("UPDATE documents SET status = 'processing' WHERE id = ?", (document_id,))
        conn.commit()
        try:
            text = parse_file(Path(row["file_path"]))
            chunks = chunk_text(text)
            if not chunks:
                raise ValueError("No text could be extracted from this file")
            count = store_chunks(conn, chunks, "document", document_id=document_id)
            conn.execute(
                "UPDATE documents SET status = 'ingested', chunk_count = ?, error = NULL WHERE id = ?",
                (count, document_id),
            )
        except Exception as exc:
            logger.exception("Ingestion failed for document %s", document_id)
            conn.execute(
                "UPDATE documents SET status = 'error', error = ? WHERE id = ?",
                (str(exc), document_id),
            )
        conn.commit()
    finally:
        conn.close()


def ingest_interview_answers(conn: sqlite3.Connection) -> int:
    """(Re)ingest all transcribed interview answers as RAG chunks."""
    old = conn.execute("SELECT id FROM chunks WHERE source_type = 'interview'").fetchall()
    for row in old:
        conn.execute("DELETE FROM chunks_vec WHERE rowid = ?", (row["id"],))
        conn.execute("DELETE FROM chunks WHERE id = ?", (row["id"],))
    conn.commit()

    answers = conn.execute(
        """
        SELECT a.id, a.transcript, q.text AS question
        FROM interview_answers a JOIN interview_questions q ON q.id = a.question_id
        WHERE a.status = 'transcribed' AND a.transcript IS NOT NULL
        """
    ).fetchall()
    total = 0
    for answer in answers:
        qa_text = f"Q: {answer['question']}\nA: {answer['transcript']}"
        total += store_chunks(conn, chunk_text(qa_text), "interview", answer_id=answer["id"])
    return total


def delete_document(conn: sqlite3.Connection, document_id: int) -> None:
    rows = conn.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,)).fetchall()
    for row in rows:
        conn.execute("DELETE FROM chunks_vec WHERE rowid = ?", (row["id"],))
    file_row = conn.execute("SELECT file_path FROM documents WHERE id = ?", (document_id,)).fetchone()
    conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))  # cascades chunks
    conn.commit()
    if file_row:
        Path(file_row["file_path"]).unlink(missing_ok=True)
