import { FormEvent, useEffect, useRef, useState } from 'react';
import { streamSSE } from '../api';
import { useLang } from '../i18n';

interface Msg {
  role: 'user' | 'assistant';
  content: string;
}

export default function TextChat() {
  const { t } = useLang();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function send(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setError(null);
    setInput('');
    const history = [...messages, { role: 'user' as const, content: text }];
    setMessages([...history, { role: 'assistant', content: '' }]);
    setBusy(true);
    try {
      await streamSSE(
        '/api/chat',
        { messages: history },
        (delta) =>
          setMessages((cur) => {
            const next = [...cur];
            next[next.length - 1] = {
              ...next[next.length - 1],
              content: next[next.length - 1].content + delta,
            };
            return next;
          }),
        (message) => setError(message),
      );
    } finally {
      setBusy(false);
      setMessages((cur) => (cur[cur.length - 1]?.content === '' ? cur.slice(0, -1) : cur));
    }
  }

  return (
    <div className="chat-shell">
      <div>
        <h1 className="display">{t.chatTitle}</h1>
        <p className="sub" style={{ marginTop: 8 }}>{t.chatSub}</p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="chat-box">
        {messages.length === 0 && <p className="muted">{t.sayHello}</p>}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.content || '…'}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form className="chat-form" onSubmit={send}>
        <input
          type="text"
          value={input}
          placeholder={t.chatPh}
          onChange={(e) => setInput(e.target.value)}
          style={{ flex: 1 }}
        />
        <button className="btn accent" disabled={busy || !input.trim()}>
          {busy ? '…' : t.send}
        </button>
      </form>
    </div>
  );
}
