import { useConversation } from '@elevenlabs/react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LangToggle } from '../App';
import { apiGet } from '../api';
import Orb from '../components/Orb';
import { clock, useLang } from '../i18n';

interface Caption {
  who: 'you' | 'echo';
  text: string;
}

export default function VoiceChat() {
  const { t, lang } = useLang();
  const navigate = useNavigate();

  const [captions, setCaptions] = useState<Caption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [muted, setMuted] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const timerRef = useRef<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const conversation = useConversation({
    micMuted: muted,
    onMessage: (message: { source: string; message: string }) =>
      setCaptions((cur) => [...cur, { who: message.source === 'user' ? 'you' : 'echo', text: message.message }]),
    onError: (message: string) => setError(String(message)),
    onDisconnect: () => setConnecting(false),
  });

  const connected = conversation.status === 'connected';

  useEffect(() => {
    if (!connected) {
      if (timerRef.current) window.clearInterval(timerRef.current);
      timerRef.current = null;
      return;
    }
    setSeconds(0);
    timerRef.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      timerRef.current = null;
    };
  }, [connected]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [captions.length]);

  async function start() {
    setError(null);
    setConnecting(true);
    setCaptions([]);
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      const session = await apiGet<{ token: string | null; signed_url: string | null }>('/api/agent/session');
      const overrides = { agent: { language: lang } };
      if (session.token) {
        await conversation.startSession({
          conversationToken: session.token,
          connectionType: 'webrtc',
          overrides,
        } as Parameters<typeof conversation.startSession>[0]);
      } else if (session.signed_url) {
        await conversation.startSession({
          signedUrl: session.signed_url,
          connectionType: 'websocket',
          overrides,
        } as Parameters<typeof conversation.startSession>[0]);
      } else {
        throw new Error('Backend returned no session token or signed URL');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setConnecting(false);
    }
  }

  async function end() {
    await conversation.endSession();
    navigate('/');
  }

  const speaking = connected && conversation.isSpeaking;
  const statusLabel = !connected
    ? connecting
      ? t.connectingLabel
      : t.connectBtn
    : speaking
      ? t.echoSpeaking
      : muted
        ? t.unmute
        : t.listening;

  return (
    <div className="call">
      <LangToggle night />

      <div className="call-top">
        <div className="call-live">
          {connected && <span className="dot" />}
          {connected ? t.liveLabel : 'ECHO'}
        </div>
        <div className="call-meta">
          {connected && <span className="call-pill">{t.v2v}</span>}
          <span>{clock(seconds)}</span>
        </div>
      </div>

      <div className="call-body">
        <Orb size={150} inset={22} rings={speaking ? 2 : 0} speed={1.4} night />

        {error && <div className="call-error">{error}</div>}

        {!connected && !error && (
          <p style={{ maxWidth: 460, textAlign: 'center', lineHeight: 1.65, opacity: 0.6, fontSize: 14.5 }}>
            {t.callHint}
          </p>
        )}

        {connected && (
          <div className="captions">
            {captions.map((caption, i) => (
              <div key={i} className={`caption-row${caption.who === 'you' ? ' you' : ''}`}>
                <div className="caption">
                  <div className="who">{caption.who === 'you' ? t.youTag : t.echoTag}</div>
                  {caption.text}
                </div>
              </div>
            ))}
            {speaking && captions.length === 0 && (
              <div className="thinking">
                <i />
                <i />
                <i />
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div className="call-controls">
        {connected ? (
          <>
            <button className={`call-btn${muted ? ' on' : ''}`} onClick={() => setMuted((m) => !m)}>
              {muted ? t.unmute : t.mute}
            </button>
            <button className="call-btn primary" disabled>
              {statusLabel}
            </button>
            <button className="call-btn end" onClick={end} aria-label={t.back}>
              <i />
            </button>
          </>
        ) : (
          <>
            <button className="call-btn" onClick={() => navigate('/')}>
              {t.back}
            </button>
            <button className="call-btn primary" onClick={start} disabled={connecting}>
              {connecting ? t.connectingLabel : t.connectBtn}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
