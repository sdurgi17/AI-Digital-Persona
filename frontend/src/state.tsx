import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { apiGet, ConfigStatus, Persona, Progress } from './api';

interface AppState {
  persona: Persona | null;
  progress: Progress | null;
  config: ConfigStatus | null;
  loaded: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  /** Names of .env values the backend reports as missing. */
  missingKeys: string[];
  /** Milestones, derived once so every screen agrees. */
  interviewDone: boolean;
  profileDone: boolean;
  voiceDone: boolean;
  agentDone: boolean;
}

const Ctx = createContext<AppState | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [persona, setPersona] = useState<Persona | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [config, setConfig] = useState<ConfigStatus | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [p, pr, c] = await Promise.all([
        apiGet<Persona>('/api/persona'),
        apiGet<Progress>('/api/interview/progress'),
        apiGet<ConfigStatus>('/api/health/config'),
      ]);
      setPersona(p);
      setProgress(pr);
      setConfig(c);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const value = useMemo<AppState>(() => {
    const missingKeys: string[] = [];
    if (config) {
      if (!config.elevenlabs_api_key) missingKeys.push('ELEVENLABS_API_KEY');
      if (!config.llm_key_ok) {
        missingKeys.push(config.llm_provider === 'anthropic' ? 'ANTHROPIC_API_KEY' : 'OPENAI_API_KEY');
      }
      if (!config.embedding_key_ok) missingKeys.push('OPENAI_API_KEY (embeddings)');
    }
    return {
      persona,
      progress,
      config,
      loaded,
      error,
      refresh,
      missingKeys,
      interviewDone: (progress?.transcribed ?? 0) >= 1 && Boolean(progress?.enough_audio_for_clone),
      profileDone: Boolean(persona?.system_prompt),
      voiceDone: Boolean(persona?.voice_id),
      agentDone: Boolean(persona?.agent_id),
    };
  }, [persona, progress, config, loaded, error, refresh]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppState(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAppState must be used inside <AppStateProvider>');
  return ctx;
}
