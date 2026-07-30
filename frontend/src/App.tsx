import { BrowserRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { useLang } from './i18n';
import { useAppState } from './state';
import Dashboard from './pages/Dashboard';
import Documents from './pages/Documents';
import Interview from './pages/Interview';
import TextChat from './pages/TextChat';
import VoiceChat from './pages/VoiceChat';
import VoiceClone from './pages/VoiceClone';

/** Header step index per route; -1 keeps every dot inactive. */
const STEP_OF_ROUTE: Record<string, number> = {
  '/interview': 0,
  '/clone': 1,
  '/documents': 2,
  '/chat': 3,
  '/voice': 3,
};

const ROUTE_OF_STEP = ['/interview', '/clone', '/documents', '/chat'];

export function LangToggle({ night }: { night?: boolean }) {
  const { lang, setLang } = useLang();
  return (
    <div className={`lang-toggle${night ? ' on-night' : ''}`}>
      <button className={lang === 'en' ? 'active' : ''} onClick={() => setLang('en')}>
        EN
      </button>
      <button className={lang === 'te' ? 'active' : ''} onClick={() => setLang('te')}>
        తెలుగు
      </button>
    </div>
  );
}

function TopBar() {
  const { t } = useLang();
  const { interviewDone, profileDone, voiceDone, agentDone } = useAppState();
  const location = useLocation();
  const navigate = useNavigate();

  const current = STEP_OF_ROUTE[location.pathname] ?? -1;
  const completed = [interviewDone, voiceDone, profileDone, agentDone];

  return (
    <div className="topbar">
      <div className="brand">
        <div className="brand-mark" />
        <div className="brand-name">Echo</div>
        <div className="brand-tagline">{t.tagline}</div>
      </div>
      <div className="steps">
        {t.steps.map((label, i) => {
          const state = i === current ? 'active' : completed[i] ? 'done' : '';
          return (
            <button key={label} className={`step ${state}`} onClick={() => navigate(ROUTE_OF_STEP[i])}>
              <span className="step-dot" />
              <span className="step-label">{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Shell() {
  const { persona, loaded } = useAppState();
  const location = useLocation();

  // The design hides the chrome on the welcome screen and during a live call.
  const onWelcome = location.pathname === '/' && loaded && !persona?.exists;
  const onCall = location.pathname === '/voice';
  const showHeader = !onWelcome && !onCall;

  return (
    <div className="app">
      {!onCall && <LangToggle />}
      {showHeader && <TopBar />}
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/interview" element={<Interview />} />
        <Route path="/clone" element={<VoiceClone />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/chat" element={<TextChat />} />
        <Route path="/voice" element={<VoiceChat />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  );
}
