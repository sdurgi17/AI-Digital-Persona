import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiPost } from '../api';
import Orb from '../components/Orb';
import { clock, fmt, t } from '../strings';
import { useAppState } from '../state';

/** Where the creep stalls while we wait on ElevenLabs — the last stretch is the real response. */
const CREEP_CEILING = 92;

export default function VoiceClone() {
  const navigate = useNavigate();
  const { persona, progress, refresh, interviewDone, voiceDone } = useAppState();

  const [pct, setPct] = useState(voiceDone ? 100 : 0);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const creepRef = useRef<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (voiceDone && !running) setPct(100);
  }, [voiceDone, running]);

  useEffect(
    () => () => {
      if (creepRef.current) window.clearInterval(creepRef.current);
      audioRef.current?.pause();
    },
    [],
  );

  async function clone() {
    setError(null);
    setRunning(true);
    setPct(0);
    creepRef.current = window.setInterval(() => {
      setPct((cur) => (cur >= CREEP_CEILING ? cur : Math.min(CREEP_CEILING, cur + 1 + Math.random() * 2)));
    }, 400);
    try {
      await apiPost('/api/voice/clone');
      setPct(100);
      await refresh();
    } catch (e) {
      setPct(0);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (creepRef.current) window.clearInterval(creepRef.current);
      creepRef.current = null;
      setRunning(false);
    }
  }

  async function playPreview() {
    setError(null);
    setPreviewing(true);
    try {
      const res = await fetch('/api/voice/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'preview failed');
      const url = URL.createObjectURL(await res.blob());
      audioRef.current?.pause();
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        setPreviewing(false);
        URL.revokeObjectURL(url);
      };
      await audio.play();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPreviewing(false);
    }
  }

  const done = pct >= 100;
  const stageIndex = Math.min(3, Math.floor(pct / 25));
  const totalSeconds = progress?.total_seconds ?? 0;

  let title = t.cloneIdleTitle;
  let sub = t.cloneIdleSub;
  if (running) {
    title = t.cloneActive;
    sub = t.cloneSubActive;
  } else if (done) {
    title = t.cloneDoneTitle;
    sub = fmt(t.cloneSubDone, { t: clock(totalSeconds) });
  }

  return (
    <div className="stage-center" style={{ gap: 28, padding: '48px 24px' }}>
      <Orb size={120} inset={16} rings={running ? 2 : 1} speed={running ? 2.2 : 3.2} />

      <div>
        <h1 className="display">{title}</h1>
        <p className="sub" style={{ marginTop: 8 }}>{sub}</p>
      </div>

      {error && <div className="error-banner" style={{ maxWidth: 460 }}>{error}</div>}

      {!interviewDone && !voiceDone && (
        <p className="muted" style={{ maxWidth: 420 }}>
          {fmt(t.cloneNeedAudio, { t: clock(totalSeconds) })}
        </p>
      )}

      <div className="card tight" style={{ width: 400, maxWidth: '100%', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div className="clone-stages">
          {t.stages.map((label, i) => {
            const stageDone = done || (running && i < stageIndex);
            const active = running && !stageDone && i === stageIndex;
            return (
              <div key={label} className={`clone-stage${stageDone ? ' done' : ''}${active ? ' active' : ''}`}>
                <span className="icon">{stageDone ? '✓' : ''}</span>
                <span className="label">{label}</span>
                <span className="meta">{stageDone ? t.doneWord : active ? `${Math.min(99, Math.round(pct))}%` : ''}</span>
              </div>
            );
          })}
        </div>
        <div className="bar" style={{ marginTop: 4 }}>
          <i style={{ width: `${Math.min(100, pct)}%` }} />
        </div>
      </div>

      {done ? (
        <div className="col rise" style={{ alignItems: 'center', gap: 16 }}>
          <div className="row" style={{ justifyContent: 'center' }}>
            <button className="btn paper" onClick={playPreview} disabled={previewing}>
              <span className="btn-icon-play" style={{ borderLeftColor: 'var(--accent)' }} />
              {previewing ? t.previewPlaying : t.previewBtn}
            </button>
            <button className="btn ghost" onClick={clone} disabled={running || !interviewDone}>
              {t.recloneBtn}
            </button>
          </div>
          <button className="btn dark lg" onClick={() => navigate('/documents')}>
            {t.continueBtn}
          </button>
          {persona?.voice_id && <p className="tiny">voice_id: {persona.voice_id}</p>}
        </div>
      ) : (
        <button className="btn accent glow lg" onClick={clone} disabled={running || !interviewDone}>
          {running ? t.cloneActive : t.cloneBtn}
        </button>
      )}
    </div>
  );
}
