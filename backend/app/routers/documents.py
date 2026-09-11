import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from ..config import get_settings
from ..db import get_db
from ..services.ingestion import delete_document, ingest_document

router = APIRouter()

SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".markdown"}


@router.get("")
def list_documents() -> list[dict]:
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("")
async def upload_documents(files: list[UploadFile], background: BackgroundTasks) -> list[dict]:
    settings = get_settings()
    created = []
    conn = get_db()
    try:
        for file in files:
            name = file.filename or "upload"
            suffix = ("." + name.rsplit(".", 1)[1].lower()) if "." in name else ""
            if suffix not in SUPPORTED:
                raise HTTPException(400, f"Unsupported file type: {name} (pdf, docx, txt, md)")
            path = settings.uploads_dir / f"{uuid.uuid4().hex[:8]}__{name}"
            path.write_bytes(await file.read())
            cur = conn.execute(
                "INSERT INTO documents (filename, file_path, mime) VALUES (?, ?, ?)",
                (name, str(path), file.content_type),
            )
            created.append({"id": cur.lastrowid, "filename": name, "status": "uploaded"})
        conn.commit()
    finally:
        conn.close()

    for doc in created:
        background.add_task(ingest_document, doc["id"])
    return created


@router.delete("/{document_id}")
def remove_document(document_id: int) -> dict:
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Document not found")
        delete_document(conn, document_id)
        return {"deleted": document_id}
    finally:
        conn.close()
