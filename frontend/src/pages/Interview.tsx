import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet, apiUpload, Question } from '../api';
import Recorder from '../components/Recorder';
import { clock, fmt, useLang } from '../i18n';
import { useAppState } from '../state';

const CLONE_TARGET_SECONDS = 60;

export default function Interview() {
  const { t, question: localizedQuestion, category, hint } = useLang();
  const navigate = useNavigate();
  const { progress, refresh: refreshApp } = useAppState();

  const [questions, setQuestions] = useState<Question[]>([]);
  const [index, setIndex] = useState(0);
  const [retaking, setRetaking] = useState(false);
  const [liveSeconds, setLiveSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);
  const initializedRef = useRef(false);

  const refresh = useCallback(async () => {
    const qs = await apiGet<Question[]>('/api/interview/questions');
    setQuestions(qs);
    if (!initializedRef.current && qs.length > 0) {
      initializedRef.current = true;
      const firstUnanswered = qs.findIndex((q) => !q.answer_id);
      setIndex(firstUnanswered === -1 ? 0 : firstUnanswered);
    }
    return qs;
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError(String(e)));
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [refresh]);

  const ensurePolling = useCallback(() => {
    if (pollRef.current) return;
    pollRef.current = window.setInterval(async () => {
      try {
        const qs = await refresh();
        const pending = qs.some((q) => q.answer_status === 'recorded' || q.answer_status === 'transcribing');
        if (!pending && pollRef.current) {
          window.clearInterval(pollRef.current);
          pollRef.current = null;
          refreshApp();
        }
      } catch {
        /* transient */
      }
    }, 3000);
  }, [refresh, refreshApp]);

  if (questions.length === 0) {
    return (
      <div className="stage-center">
        <p className="muted">{t.loading}</p>
      </div>
    );
  }

  const q = questions[index];
  const isLast = index === questions.length - 1;
  const recordedSeconds = (progress?.total_seconds ?? 0) + liveSeconds;
  const samplePct = Math.min(100, Math.round((recordedSeconds / CLONE_TARGET_SECONDS) * 100));

  async function upload(blob: Blob, durationSeconds: number) {
    const form = new FormData();
    form.append('audio', blob, 'answer.webm');
    form.append('duration_seconds', String(durationSeconds));
    await apiUpload(`/api/interview/answers/${q.id}`, form);
    setLiveSeconds(0);
    setRetaking(false);
    ensurePolling();
    await refresh();
    await refreshApp();
  }

  function goto(next: number) {
    setIndex(next);
    setRetaking(false);
    setLiveSeconds(0);
  }

  return (
    <div className="interview">
      <div className="interview-prompt">
        <div className="row" style={{ gap: 10 }}>
          <span className="chip">{t.echoAsks}</span>
          <span className="muted" style={{ fontSize: 13 }}>
            {fmt(t.qOf, { n: index + 1, t: questions.length })}
          </span>
          <span className="tiny">{category(q.category)}</span>
        </div>

        <h1 className="display md rise" key={q.id}>
          {localizedQuestion(q.ord, q.text)}
        </h1>
        <p className="muted" style={{ lineHeight: 1.6, margin: 0 }}>{hint(q.category)}</p>

        {error && <div className="error-banner">{error}</div>}

        <div className="row" style={{ gap: 10 }}>
          <button className="btn ghost sm" disabled={index === 0} onClick={() => goto(index - 1)}>
            {t.prevQ}
          </button>
          {!isLast && (
            <button className="btn ghost sm" onClick={() => goto(index + 1)}>
              {t.skipQ}
            </button>
          )}
        </div>

        <div className="card soft" style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="row spread" style={{ fontSize: 12.5, color: 'var(--muted)' }}>
            <span style={{ fontWeight: 600, color: 'var(--ink)' }}>{t.sampleCollected}</span>
            <span className="tabular">{fmt(t.sampleNeed, { t: clock(recordedSeconds) })}</span>
          </div>
          <div className="bar">
            <i style={{ width: `${samplePct}%` }} />
          </div>
        </div>
      </div>

      <div className="interview-stage">
        {q.answer_id && !retaking ? (
          <Captured
            q={q}
            isLast={isLast}
            onRetake={() => setRetaking(true)}
            onNext={() => (isLast ? navigate('/clone') : goto(index + 1))}
          />
        ) : (
          <Recorder key={`${q.id}-${retaking}`} minSeconds={q.min_seconds} onAccept={upload} onTick={setLiveSeconds} />
        )}
      </div>
    </div>
  );
}

function Captured({
  q,
  isLast,
  onRetake,
  onNext,
}: {
  q: Question;
  isLast: boolean;
  onRetake: () => void;
  onNext: () => void;
}) {
  const { t } = useLang();
  const transcribing = q.answer_status === 'recorded' || q.answer_status === 'transcribing';
  const failed = q.answer_status === 'error';

  return (
    <div className="col rise" style={{ alignSelf: 'stretch', gap: 14 }}>
      <div className="done-line">
        <span className="tick">✓</span>
        {fmt(t.captured, { t: clock(q.duration_seconds ?? 0) })}
      </div>

      {q.transcript && <div className="transcript">“{q.transcript}”</div>}
      {transcribing && <p className="muted" style={{ margin: 0 }}>{t.transcribingNote}</p>}
      {failed && <div className="error-banner" style={{ marginBottom: 0 }}>{q.error ?? t.transcribeFailed}</div>}

      <audio controls src={`/api/interview/answers/${q.answer_id}/audio`} style={{ width: '100%' }} />

      {q.transcript && (
        <p className="tiny" style={{ margin: 0 }}>
          {t.transcribedNote}
          {q.language_code ? ` · ${q.language_code}` : ''}
        </p>
      )}

      <div className="row" style={{ marginTop: 6, flexWrap: 'nowrap' }}>
        <button className="btn ghost sm" onClick={onRetake}>
          {t.reRecord}
        </button>
        <button className="btn accent sm" style={{ flex: 1 }} onClick={onNext}>
          {isLast ? t.finishQ : t.nextQ}
        </button>
      </div>
    </div>
  );
}
