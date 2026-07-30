import { useEffect, useRef, useState } from 'react';
import { clock, fmt, useLang } from '../i18n';
import Waveform from './Waveform';

interface Props {
  minSeconds: number;
  onAccept: (blob: Blob, durationSeconds: number) => Promise<void>;
  /** Live total across the interview, so the sample meter can tick while recording. */
  onTick?: (seconds: number) => void;
}

type Phase = 'idle' | 'recording' | 'review' | 'uploading';

export default function Recorder({ minSeconds, onAccept, onTick }: Props) {
  const { t } = useLang();
  const [phase, setPhase] = useState<Phase>('idle');
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const blobRef = useRef<Blob | null>(null);
  const timerRef = useRef<number | null>(null);
  const secondsRef = useRef(0);
  const blobUrlRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      recorderRef.current?.stream.getTracks().forEach((track) => track.stop());
      if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
    };
  }, []);

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm';
      const recorder = new MediaRecorder(stream, { mimeType: mime });
      chunksRef.current = [];
      recorder.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunksRef.current, { type: mime });
        blobRef.current = blob;
        if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
        blobUrlRef.current = URL.createObjectURL(blob);
        setBlobUrl(blobUrlRef.current);
        setPhase('review');
      };
      recorderRef.current = recorder;
      recorder.start();
      secondsRef.current = 0;
      setSeconds(0);
      setPhase('recording');
      timerRef.current = window.setInterval(() => {
        secondsRef.current += 1;
        setSeconds(secondsRef.current);
        onTick?.(secondsRef.current);
      }, 1000);
    } catch (e) {
      setError(fmt(t.micFailed, { e: e instanceof Error ? e.message : String(e) }));
    }
  }

  function stop() {
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
    recorderRef.current?.stop();
  }

  function discard() {
    blobRef.current = null;
    if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
    blobUrlRef.current = null;
    setBlobUrl(null);
    setSeconds(0);
    secondsRef.current = 0;
    onTick?.(0);
    setPhase('idle');
  }

  async function accept() {
    if (!blobRef.current) return;
    setPhase('uploading');
    setError(null);
    try {
      await onAccept(blobRef.current, secondsRef.current);
      discard();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase('review');
    }
  }

  return (
    <>
      {error && <div className="error-banner" style={{ alignSelf: 'stretch' }}>{error}</div>}

      {phase === 'idle' && (
        <>
          <button className="rec-button" onClick={start} aria-label={t.tapRecord}>
            <span className="glyph">
              <i />
            </span>
          </button>
          <div style={{ fontWeight: 600, fontSize: 16 }}>{t.tapRecord}</div>
          <p className="muted" style={{ textAlign: 'center', maxWidth: 280, lineHeight: 1.55, margin: 0, fontSize: 13 }}>
            {fmt(t.speakNatural, { n: minSeconds })}
          </p>
        </>
      )}

      {phase === 'recording' && (
        <>
          <div className="rec-live">
            <span className="dot" />
            {t.recording}
          </div>
          <Waveform />
          <div className="timer">{clock(seconds)}</div>
          <button className="btn dark sm" onClick={stop}>
            {t.stopRec}
          </button>
        </>
      )}

      {(phase === 'review' || phase === 'uploading') && blobUrl && (
        <div className="col rise" style={{ alignSelf: 'stretch', gap: 14 }}>
          <div className="done-line">
            <span className="tick">✓</span>
            {fmt(t.captured, { t: clock(secondsRef.current) })}
          </div>
          <audio controls src={blobUrl} style={{ width: '100%' }} />
          <p className="tiny" style={{ margin: 0 }}>{t.reviewNote}</p>
          <div className="row" style={{ marginTop: 6, flexWrap: 'nowrap' }}>
            <button className="btn ghost sm" onClick={discard} disabled={phase === 'uploading'}>
              {t.reRecord}
            </button>
            <button className="btn accent sm" style={{ flex: 1 }} onClick={accept} disabled={phase === 'uploading'}>
              {phase === 'uploading' ? t.uploading : t.useTake}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
