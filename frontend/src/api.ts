export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(await errText(res));
  return res.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await errText(res));
  return res.json();
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(path, { method: 'DELETE' });
  if (!res.ok) throw new Error(await errText(res));
  return res.json();
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(path, { method: 'POST', body: formData });
  if (!res.ok) throw new Error(await errText(res));
  return res.json();
}

async function errText(res: Response): Promise<string> {
  try {
    const data = await res.json();
    return data.detail || JSON.stringify(data);
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

/** POST an SSE endpoint and invoke onDelta per text delta. */
export async function streamSSE(
  path: string,
  body: unknown,
  onDelta: (delta: string) => void,
  onError: (message: string) => void,
): Promise<void> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    onError(await errText(res));
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';
    for (const event of events) {
      const line = event.trim();
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6);
      if (data === '[DONE]') return;
      try {
        const parsed = JSON.parse(data);
        if (parsed.error) onError(parsed.error);
        else if (parsed.delta) onDelta(parsed.delta);
      } catch {
        /* ignore malformed frames */
      }
    }
  }
}

export interface Question {
  id: number;
  ord: number;
  category: string;
  text: string;
  min_seconds: number;
  answer_id: number | null;
  answer_status: string | null;
  duration_seconds: number | null;
  transcript: string | null;
  language_code: string | null;
  error: string | null;
}

export interface Persona {
  exists: boolean;
  name?: string;
  status?: string;
  system_prompt?: string | null;
  voice_id?: string | null;
  agent_id?: string | null;
  profile_json?: Record<string, unknown> | null;
}

export interface Doc {
  id: number;
  filename: string;
  status: string;
  chunk_count: number;
  error: string | null;
}

export interface Progress {
  answered: number;
  transcribed: number;
  total_questions: number;
  total_seconds: number;
  enough_audio_for_clone: boolean;
}

export interface ConfigStatus {
  elevenlabs_api_key: boolean;
  llm_provider: string;
  llm_model: string;
  embedding_provider: string;
  custom_llm_shared_secret: boolean;
  public_base_url: string | null;
  llm_key_ok: boolean;
  embedding_key_ok: boolean;
}
