import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiDelete, apiGet, apiPost, apiUpload, Doc } from '../api';
import { fmt, t } from '../strings';
import { useAppState } from '../state';

const PASTE_PREFIX = 'Pasted note';

export default function Documents() {
  const navigate = useNavigate();
  const { progress, voiceDone, refresh: refreshApp } = useAppState();

  const [docs, setDocs] = useState<Doc[]>([]);
  const [drag, setDrag] = useState(false);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    const list = await apiGet<Doc[]>('/api/documents');
    setDocs(list);
    const anyBusy = list.some((d) => d.status === 'uploaded' || d.status === 'processing');
    if (anyBusy && !pollRef.current) {
      pollRef.current = window.setInterval(() => refresh().catch(() => {}), 2000);
    } else if (!anyBusy && pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError(String(e)));
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [refresh]);

  async function upload(files: File[]) {
    if (files.length === 0) return;
    setError(null);
    setBusy('upload');
    const form = new FormData();
    for (const f of files) form.append('files', f);
    try {
      await apiUpload('/api/documents', form);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function indexDraft() {
    const text = draft.trim();
    if (!text) return;
    const n = docs.filter((d) => d.filename.startsWith(PASTE_PREFIX)).length + 1;
    const file = new File([text], `${PASTE_PREFIX} ${n}.txt`, { type: 'text/plain' });
    setDraft('');
    await upload([file]);
  }

  async function remove(id: number) {
    setError(null);
    try {
      await apiDelete(`/api/documents/${id}`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function createPersona() {
    setBusy('build');
    setError(null);
    try {
      await apiPost('/api/persona/build');
      await refreshApp();
      navigate('/');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const chunks = docs.reduce((sum, d) => sum + d.chunk_count, 0);
  const canBuild = (progress?.transcribed ?? 0) >= 1;

  return (
    <div className="stage-page">
      <div>
        <h1 className="display">{t.knowledgeTitle}</h1>
        <p className="sub" style={{ marginTop: 8, maxWidth: 560 }}>{t.knowledgeSub}</p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="knowledge-cols">
        <div className="knowledge-left">
          <div
            className={`dropzone${drag ? ' drag' : ''}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              upload(Array.from(e.dataTransfer.files));
            }}
          >
            <div className="t">{t.dropTitle}</div>
            <div className="s">{t.dropSub}</div>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.md,.markdown"
              style={{ display: 'none' }}
              onChange={(e) => {
                if (e.target.files) upload(Array.from(e.target.files));
                e.target.value = '';
              }}
            />
          </div>

          {docs.map((doc) => (
            <FileRow key={doc.id} doc={doc} onRemove={() => remove(doc.id)} />
          ))}
        </div>

        <div className="knowledge-right">
          <div style={{ fontWeight: 600, fontSize: 15 }}>{t.pasteTitle}</div>
          <p className="muted" style={{ margin: 0, fontSize: 13, lineHeight: 1.55 }}>{t.pasteSub}</p>
          <textarea value={draft} placeholder={t.pastePh} onChange={(e) => setDraft(e.target.value)} />
          <button className="btn accent" disabled={!draft.trim() || busy !== null} onClick={indexDraft}>
            {busy === 'upload' ? t.indexing : t.indexBtn}
          </button>
        </div>
      </div>

      <div className="summary-bar">
        <div className="stats">
          <div>
            <div className="n">{chunks}</div>
            <div className="k">{t.statChunks}</div>
          </div>
          <div>
            <div className="n">{docs.length}</div>
            <div className="k">{t.statSources}</div>
          </div>
          <div>
            <div className="n">{voiceDone ? t.statReady : t.statPending}</div>
            <div className="k">{t.statVoice}</div>
          </div>
        </div>
        <button className="btn accent" disabled={!canBuild || busy !== null} onClick={createPersona}>
          {busy === 'build' ? t.buildingProfile : t.createBtn}
        </button>
      </div>
    </div>
  );
}

function FileRow({ doc, onRemove }: { doc: Doc; onRemove: () => void }) {
  const ext = (doc.filename.split('.').pop() ?? 'txt').toUpperCase().slice(0, 4);
  const pending = doc.status === 'uploaded' || doc.status === 'processing';
  const failed = doc.status === 'error';

  const status = failed
    ? doc.error || t.ingestFailed
    : doc.status === 'ingested'
      ? t.indexed
      : doc.status === 'processing'
        ? t.chunking
        : t.queued;

  return (
    <div className="file-row">
      <span className="ext">{ext}</span>
      <div className="meta">
        <div className="name" title={doc.filename}>{doc.filename}</div>
        <div className="status" title={status} style={failed ? { color: 'var(--warn)' } : undefined}>
          {status}
        </div>
      </div>
      {pending && (
        <div className="bar thin" style={{ width: 90 }}>
          <i style={{ width: '60%', animation: 'echoBlink 1.2s infinite' }} />
        </div>
      )}
      {doc.status === 'ingested' && <span className="count">{fmt(t.chunksTag, { n: doc.chunk_count })}</span>}
      <button className="remove" onClick={onRemove} title={t.removeFile} aria-label={t.removeFile}>
        ✕
      </button>
    </div>
  );
}
