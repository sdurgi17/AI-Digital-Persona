import { ReactNode, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet, apiPost, Doc } from '../api';
import Orb from '../components/Orb';
import { clock, fmt, useLang } from '../i18n';
import { useAppState } from '../state';

export default function Dashboard() {
  const { t } = useLang();
  const navigate = useNavigate();
  const { persona, progress, loaded, refresh, missingKeys, profileDone, voiceDone, agentDone } = useAppState();

  const [name, setName] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chunks, setChunks] = useState(0);

  useEffect(() => {
    if (!persona?.exists) return;
    apiGet<Doc[]>('/api/documents')
      .then((docs) => setChunks(docs.reduce((sum, d) => sum + d.chunk_count, 0)))
      .catch(() => setChunks(0));
  }, [persona?.exists]);

  async function run(label: string, fn: () => Promise<unknown>) {
    setBusy(label);
    setError(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  if (!loaded) {
    return (
      <div className="stage-center">
        <p className="muted">{t.loading}</p>
      </div>
    );
  }

  if (!persona?.exists) {
    return (
      <Welcome
        name={name}
        setName={setName}
        busy={busy !== null}
        error={error}
        onBegin={() =>
          run('create', async () => {
            await apiPost('/api/persona', { name: name.trim() });
            navigate('/interview');
          })
        }
        questionCount={progress?.total_questions ?? 6}
      />
    );
  }

  const live = profileDone && voiceDone && agentDone;

  return (
    <div className="stage-center" style={{ gap: 30 }}>
      {missingKeys.length > 0 && (
        <div className="error-banner" style={{ maxWidth: 620 }}>
          {fmt(t.missingKeys, { k: missingKeys.join(', ') })}
        </div>
      )}
      {error && <div className="error-banner" style={{ maxWidth: 620 }}>{error}</div>}

      <div className="card hero rise" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22, maxWidth: 640 }}>
        <Orb size={108} inset={12} rings={live ? 1 : 0} speed={3} />
        <div>
          <h1 className="display lg">{live ? t.readyTitle : t.notReadyTitle}</h1>
          <p className="sub" style={{ marginTop: 8 }}>{live ? t.readySub : t.notReadySub}</p>
        </div>

        <div className="ready-stats">
          <div className="s">
            <div className="n">{chunks}</div>
            <div className="k">{t.statKChunks}</div>
          </div>
          <div className="s">
            <div className="n">
              {progress?.transcribed ?? 0}/{progress?.total_questions ?? 0}
            </div>
            <div className="k">{t.statAnswers}</div>
          </div>
          <div className="s">
            <div className="n">{clock(progress?.total_seconds ?? 0)}</div>
            <div className="k">{t.statAudio}</div>
          </div>
        </div>

        {!live && (
          <SetupList
            busy={busy}
            run={run}
            chunks={chunks}
            onNavigate={navigate}
          />
        )}

        <div className="row" style={{ justifyContent: 'center', marginTop: 4 }}>
          <button className="btn ghost" onClick={() => navigate('/documents')}>
            {t.addMoreBtn}
          </button>
          <button className="btn ghost" disabled={!profileDone} onClick={() => navigate('/chat')}>
            {t.textChatBtn}
          </button>
          <button className="btn accent glow" disabled={!agentDone} onClick={() => navigate('/voice')}>
            <span className="call-live-dot" style={{ width: 9, height: 9, borderRadius: '50%', background: '#fff', animation: 'echoBlink 1.4s infinite' }} />
            {t.startCallBtn}
          </button>
        </div>
      </div>
      <p className="tiny">{t.comingNote}</p>
    </div>
  );
}

function SetupList({
  busy,
  run,
  chunks,
  onNavigate,
}: {
  busy: string | null;
  run: (label: string, fn: () => Promise<unknown>) => Promise<void>;
  chunks: number;
  onNavigate: (to: string) => void;
}) {
  const { t } = useLang();
  const { progress, config, persona, interviewDone, profileDone, voiceDone, agentDone } = useAppState();

  return (
    <div className="setup-list">
      <Item
        done={interviewDone}
        num={1}
        title={t.setupInterview}
        sub={fmt(t.setupInterviewSub, {
          a: progress?.answered ?? 0,
          t: progress?.total_questions ?? 0,
          s: Math.round(progress?.total_seconds ?? 0),
        })}
        action={
          <button className="btn ghost sm" onClick={() => onNavigate('/interview')}>
            {t.open}
          </button>
        }
      />
      <Item
        done={profileDone}
        num={2}
        title={t.setupProfile}
        sub={t.setupProfileSub}
        action={
          <button
            className="btn accent sm"
            disabled={busy !== null || (progress?.transcribed ?? 0) < 1}
            onClick={() => run('build', () => apiPost('/api/persona/build'))}
          >
            {busy === 'build' ? t.buildingProfile : profileDone ? t.rebuild : t.build}
          </button>
        }
      />
      <Item
        done={voiceDone}
        num={3}
        title={t.setupVoice}
        sub={voiceDone ? `voice_id: ${persona?.voice_id}` : t.setupVoiceSub}
        action={
          <button className="btn ghost sm" onClick={() => onNavigate('/clone')}>
            {t.open}
          </button>
        }
      />
      <Item
        done={agentDone}
        num={4}
        title={t.setupAgent}
        sub={
          config?.public_base_url
            ? fmt(t.setupAgentSubReady, { u: config.public_base_url })
            : t.setupAgentSubMissing
        }
        action={
          <button
            className="btn accent sm"
            disabled={
              busy !== null ||
              !profileDone ||
              !voiceDone ||
              !config?.public_base_url ||
              !config?.custom_llm_shared_secret
            }
            onClick={() => run('provision', () => apiPost('/api/agent/provision'))}
          >
            {busy === 'provision' ? t.provisioning : agentDone ? t.resync : t.provision}
          </button>
        }
      />
      {chunks === 0 && (
        <Item
          done={false}
          num={5}
          title={t.setupKnowledge}
          sub={t.step3Desc}
          action={
            <button className="btn ghost sm" onClick={() => onNavigate('/documents')}>
              {t.open}
            </button>
          }
        />
      )}
    </div>
  );
}

function Item({
  done,
  num,
  title,
  sub,
  action,
}: {
  done: boolean;
  num: number;
  title: string;
  sub: string;
  action: ReactNode;
}) {
  return (
    <div className={`setup-item${done ? ' done' : ''}`}>
      <span className="num">{done ? '✓' : num}</span>
      <div className="body" style={{ textAlign: 'left' }}>
        <div className="t">{title}</div>
        <div className="s">{sub}</div>
      </div>
      {action}
    </div>
  );
}

function Welcome({
  name,
  setName,
  busy,
  error,
  onBegin,
  questionCount,
}: {
  name: string;
  setName: (v: string) => void;
  busy: boolean;
  error: string | null;
  onBegin: () => void;
  questionCount: number;
}) {
  const { t } = useLang();
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="stage-center">
      <div style={{ marginBottom: 36 }}>
        <Orb size={96} inset={14} rings={2} speed={2.6} />
      </div>
      <h1 className="display xl">{t.welcomeTitle}</h1>
      <p className="lede" style={{ marginTop: 20 }}>{t.welcomeSub}</p>

      <div className="welcome-steps">
        <div className="welcome-step">
          <div className="eyebrow">{t.step1Tag}</div>
          <div className="t">{t.step1Title}</div>
          <div className="d">{fmt(t.step1Desc, { n: questionCount })}</div>
        </div>
        <div className="welcome-step">
          <div className="eyebrow">{t.step2Tag}</div>
          <div className="t">{t.step2Title}</div>
          <div className="d">{t.step2Desc}</div>
        </div>
        <div className="welcome-step">
          <div className="eyebrow">{t.step3Tag}</div>
          <div className="t">{t.step3Title}</div>
          <div className="d">{t.step3Desc}</div>
        </div>
      </div>

      {error && <div className="error-banner" style={{ maxWidth: 460 }}>{error}</div>}

      <div className="row" style={{ justifyContent: 'center', gap: 10 }}>
        <input
          ref={inputRef}
          type="text"
          value={name}
          placeholder={t.namePh}
          style={{ maxWidth: 220 }}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && name.trim() && !busy) onBegin();
          }}
        />
        <button className="btn dark lg" disabled={!name.trim() || busy} onClick={onBegin}>
          {t.beginBtn}
        </button>
      </div>
      <p className="tiny" style={{ marginTop: 14 }}>{t.beginNote}</p>
    </div>
  );
}
