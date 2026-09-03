import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from 'react';

export type Lang = 'en' | 'te';

const STORAGE_KEY = 'echo.lang';

/** Substitute {name} placeholders. */
export function fmt(template: string, vars: Record<string, string | number> = {}): string {
  return Object.keys(vars).reduce((out, k) => out.split(`{${k}}`).join(String(vars[k])), template);
}

/** Telugu renderings of backend/app/questions.py, keyed by `ord`.
 *  Keep in sync when the question bank changes — unknown ords fall back to the English text. */
const QUESTIONS_TE: Record<number, string> = {
  1: 'మీ గురించి చెప్పండి — మీ పేరు, మీరు ఎక్కడి నుంచి, ఏం చేస్తుంటారు.',
  2: 'ఇప్పుడు మీ సాధారణ రోజు ఎలా గడుస్తుందో చెప్పండి.',
  3: 'మీరు బలంగా నమ్మే ఒక సూత్రం లేదా అభిప్రాయం ఏది, ఎందుకు?',
  4: 'మిమ్మల్ని తెలిసినవాళ్లు గుర్తుపట్టే మీ జీవితంలోని ఒక మరపురాని క్షణం లేదా కథ చెప్పండి.',
  5: 'మీకు ఎంతో ఇష్టమైన దాని గురించి — ఒక అభిరుచి, ఒక అంశం, ఏదైనా — సన్నిహిత స్నేహితుడికి చెబుతున్నట్టు వివరించండి.',
  6: 'ఒక నిమిషం పాటు స్వేచ్ఛగా మాట్లాడండి: మీకు ప్రపంచంలో అత్యంత ఇష్టమైన ప్రదేశం, అక్కడ ఉంటే ఎలా అనిపిస్తుందో వర్ణించండి. తొందర లేదు, సహజంగా మాట్లాడండి.',
};

/** Per-category label and the "why we ask" line shown under the question. */
const CATEGORIES: Record<string, { en: string; te: string; hintEn: string; hintTe: string }> = {
  biography: {
    en: 'BIOGRAPHY',
    te: 'జీవిత వివరాలు',
    hintEn: 'This anchors how your persona introduces you and answers everyday questions.',
    hintTe: 'మీ పర్సోనా మిమ్మల్ని ఎలా పరిచయం చేస్తుందో, రోజువారీ ప్రశ్నలకు ఎలా జవాబిస్తుందో దీనితో నిర్ణయమవుతుంది.',
  },
  values: {
    en: 'VALUES',
    te: 'విలువలు',
    hintEn: 'Convictions let your persona take positions the way you would.',
    hintTe: 'నమ్మకాలు మీ పర్సోనా మీలాగే నిలబడి మాట్లాడేలా చేస్తాయి.',
  },
  stories: {
    en: 'STORIES',
    te: 'కథలు',
    hintEn: 'Signature stories give your persona memorable, authentic material.',
    hintTe: 'మీవైన కథలు మీ పర్సోనాకు గుర్తుండిపోయే, నిజమైన సరుకును ఇస్తాయి.',
  },
  style: {
    en: 'STYLE',
    te: 'శైలి',
    hintEn: 'Verbal tics and phrasing make the clone feel like you, not a narrator.',
    hintTe: 'మాటల అలవాట్లే వాయిస్ క్లోన్‌ను మీలా అనిపించేలా చేస్తాయి.',
  },
  voice_sample: {
    en: 'VOICE SAMPLE',
    te: 'వాయిస్ శాంపిల్',
    hintEn: 'A longer, relaxed stretch of speech is what makes the voice clone sound natural.',
    hintTe: 'ప్రశాంతంగా ఎక్కువసేపు మాట్లాడితేనే వాయిస్ క్లోన్ సహజంగా వినిపిస్తుంది.',
  },
};

const EN = {
  tagline: 'Your digital self',
  steps: ['Interview', 'Voice', 'Knowledge', 'Live'],
  loading: 'Loading…',
  back: '← Back',

  // welcome
  welcomeTitle: 'Meet your digital self.',
  welcomeSub:
    'A short spoken interview teaches Echo how you sound and how you think. Add your documents, and your persona can answer for you — live, in your voice.',
  step1Tag: 'STEP 1',
  step2Tag: 'STEP 2',
  step3Tag: 'STEP 3',
  step1Title: 'Spoken interview',
  step1Desc: 'Answer {n} questions aloud. Your answers become your voice sample.',
  step2Title: 'Voice clone',
  step2Desc: 'An instant voice clone built from your recordings via ElevenLabs.',
  step3Title: 'Knowledge',
  step3Desc: 'Upload documents and notes so your persona answers with your facts.',
  namePh: 'Your name',
  beginBtn: 'Begin the interview',
  beginNote: 'Takes about 10 minutes · You can pause anytime',

  // interview
  echoAsks: 'ECHO ASKS',
  qOf: 'Question {n} of {t}',
  sampleCollected: 'Voice sample collected',
  sampleNeed: '{t} / 1:00 needed for instant clone',
  tapRecord: 'Tap to record your answer',
  speakNatural: 'Speak naturally, like you’re telling a friend. Aim for at least {n} seconds.',
  recording: 'RECORDING',
  stopRec: 'Stop recording',
  captured: 'Answer captured · {t}',
  reviewNote: 'Listen back before you keep it — these recordings also train your voice clone.',
  transcribedNote: 'Transcribed automatically · used for both voice and personality',
  transcribingNote: 'Transcribing your answer…',
  transcribeFailed: 'Transcription failed',
  reRecord: 'Re-record',
  useTake: 'Use this take',
  uploading: 'Uploading…',
  nextQ: 'Next question',
  finishQ: 'Finish — build my voice',
  prevQ: '← Previous',
  skipQ: 'Skip →',
  micFailed: 'Microphone access failed: {e}',

  // clone
  cloneIdleTitle: 'Ready to clone your voice.',
  cloneIdleSub: 'We’ll send your interview recordings to ElevenLabs and build an instant voice clone.',
  cloneActive: 'Cloning your voice…',
  cloneDoneTitle: 'Your voice is ready.',
  cloneSubActive: 'Usually under a minute. Your recordings never leave your account.',
  cloneSubDone: 'ElevenLabs Instant Voice · built from {t} of your answers',
  cloneNeedAudio: 'Record at least 60 seconds of interview audio first — you have {t}.',
  stages: [
    'Uploading voice samples',
    'Cleaning audio & removing noise',
    'Training instant voice clone',
    'Verifying voice similarity',
  ],
  doneWord: 'done',
  cloneBtn: 'Clone my voice',
  recloneBtn: 'Re-clone',
  previewBtn: 'Preview your voice',
  previewPlaying: 'Playing…',
  continueBtn: 'Continue — teach it what you know',

  // knowledge
  knowledgeTitle: 'Teach your persona what you know.',
  knowledgeSub:
    'Everything you add is chunked, embedded, and searched when someone asks your persona a question — so it answers with your facts, not guesses.',
  dropTitle: 'Drop documents here',
  dropSub: 'PDF, DOCX, TXT, Markdown · or click to browse',
  chunking: 'Chunking & embedding…',
  queued: 'Queued…',
  indexed: 'Indexed · searchable by your persona',
  ingestFailed: 'Failed',
  chunksTag: '{n} chunks',
  removeFile: 'Remove',
  pasteTitle: 'Or paste anything',
  pasteSub: 'Bio, FAQs, strong opinions, how you’d answer common questions.',
  pastePh:
    'e.g. I’m a product designer in Austin. I believe the best onboarding is no onboarding…',
  indexBtn: 'Index this text',
  indexing: 'Indexing…',
  statChunks: 'chunks indexed',
  statSources: 'sources',
  statReady: 'Ready',
  statVoice: 'voice clone',
  statPending: 'Pending',
  createBtn: 'Create my persona →',
  buildingProfile: 'Building…',

  // ready / dashboard
  readyTitle: 'Your Echo is live.',
  readySub: 'It sounds like you, and it knows what you told it.',
  notReadyTitle: 'Finish setting up your Echo.',
  notReadySub: 'A few steps left before it can speak for you.',
  statKChunks: 'knowledge chunks',
  statAnswers: 'interview answers',
  statAudio: 'of your voice',
  addMoreBtn: 'Add more knowledge',
  startCallBtn: 'Start a live call',
  textChatBtn: 'Text chat',
  comingNote: 'Share link, embed, and phone-number hookup coming later',
  setupInterview: 'Record the interview',
  setupInterviewSub: '{a}/{t} answered · {s}s of audio (need ≥60s)',
  setupProfile: 'Build the persona profile',
  setupProfileSub: 'Extracts your bio, values and speaking style from the interview transcripts.',
  setupVoice: 'Clone your voice',
  setupVoiceSub: 'Instant voice clone from your interview recordings.',
  setupKnowledge: 'Add your knowledge',
  setupAgent: 'Provision the live agent',
  setupAgentSubReady: 'Custom-LLM URL: {u}/v1',
  setupAgentSubMissing: 'Needs PUBLIC_BASE_URL in .env — start your tunnel first (ngrok http 8000).',
  open: 'Open',
  build: 'Build',
  rebuild: 'Rebuild',
  provision: 'Provision',
  resync: 'Re-sync',
  provisioning: 'Provisioning…',
  missingKeys: 'Missing in .env: {k} — some steps will fail until set.',

  // text chat
  chatTitle: 'Text chat',
  chatSub: 'Talk to the persona without spending voice minutes. English or Telugu.',
  chatPh: 'Ask me anything…',
  send: 'Send',
  sayHello: 'Say hello…',

  // live call
  liveLabel: 'LIVE · Echo of You',
  v2v: 'voice-to-voice',
  connectingLabel: 'Connecting…',
  connectBtn: 'Start the call',
  listening: 'Listening…',
  echoSpeaking: 'Echo is speaking',
  waitingLabel: 'Say something',
  mute: 'Mute',
  unmute: 'Unmute',
  youTag: 'YOU',
  echoTag: 'YOUR ECHO',
  callHint:
    'Just talk — Echo listens, thinks and answers in your cloned voice. Calls are in English; use text chat for Telugu.',
};

type Strings = typeof EN;

const TE: Strings = {
  tagline: 'మీ డిజిటల్ రూపం',
  steps: ['ఇంటర్వ్యూ', 'వాయిస్', 'జ్ఞానం', 'లైవ్'],
  loading: 'లోడ్ అవుతోంది…',
  back: '← వెనక్కి',

  welcomeTitle: 'మీ డిజిటల్ రూపాన్ని కలవండి.',
  welcomeSub:
    'ఒక చిన్న మాటల ఇంటర్వ్యూతో Echo మీ గొంతు, మీ ఆలోచనా విధానం నేర్చుకుంటుంది. మీ డాక్యుమెంట్లు జోడిస్తే — మీ పర్సోనా మీ తరఫున, మీ గొంతులోనే, లైవ్‌గా సమాధానం ఇస్తుంది.',
  step1Tag: 'దశ 1',
  step2Tag: 'దశ 2',
  step3Tag: 'దశ 3',
  step1Title: 'మాటల ఇంటర్వ్యూ',
  step1Desc: '{n} ప్రశ్నలకు మాటల్లో సమాధానం ఇవ్వండి. మీ సమాధానాలే మీ వాయిస్ శాంపిల్ అవుతాయి.',
  step2Title: 'వాయిస్ క్లోన్',
  step2Desc: 'మీ రికార్డింగ్‌ల నుంచి ElevenLabs ద్వారా ఇన్‌స్టంట్ వాయిస్ క్లోన్ తయారవుతుంది.',
  step3Title: 'జ్ఞానం',
  step3Desc: 'డాక్యుమెంట్లు, నోట్స్ అప్‌లోడ్ చేయండి — మీ పర్సోనా మీ వాస్తవాలతో సమాధానం ఇస్తుంది.',
  namePh: 'మీ పేరు',
  beginBtn: 'ఇంటర్వ్యూ ప్రారంభించండి',
  beginNote: 'సుమారు 10 నిమిషాలు · ఎప్పుడైనా విరామం తీసుకోవచ్చు',

  echoAsks: 'ECHO అడుగుతుంది',
  qOf: 'ప్రశ్న {n} / {t}',
  sampleCollected: 'సేకరించిన వాయిస్ శాంపిల్',
  sampleNeed: '{t} / ఇన్‌స్టంట్ క్లోన్‌కు 1:00 అవసరం',
  tapRecord: 'సమాధానం రికార్డ్ చేయడానికి నొక్కండి',
  speakNatural: 'స్నేహితుడితో మాట్లాడినట్టు సహజంగా మాట్లాడండి. కనీసం {n} సెకన్లు మాట్లాడండి.',
  recording: 'రికార్డింగ్',
  stopRec: 'రికార్డింగ్ ఆపండి',
  captured: 'సమాధానం సేవ్ అయింది · {t}',
  reviewNote: 'ఉంచుకునే ముందు ఒకసారి వినండి — ఈ రికార్డింగ్‌లే మీ వాయిస్ క్లోన్‌కు ఆధారం.',
  transcribedNote: 'ఆటోమేటిక్‌గా ట్రాన్స్‌క్రైబ్ అయింది · వాయిస్, వ్యక్తిత్వం రెండింటికీ ఉపయోగపడుతుంది',
  transcribingNote: 'మీ సమాధానం ట్రాన్స్‌క్రైబ్ అవుతోంది…',
  transcribeFailed: 'ట్రాన్స్‌క్రిప్షన్ విఫలమైంది',
  reRecord: 'మళ్లీ రికార్డ్',
  useTake: 'ఇదే ఉంచు',
  uploading: 'అప్‌లోడ్ అవుతోంది…',
  nextQ: 'తదుపరి ప్రశ్న',
  finishQ: 'పూర్తి — నా వాయిస్ తయారు చేయి',
  prevQ: '← మునుపటి',
  skipQ: 'దాటవేయి →',
  micFailed: 'మైక్రోఫోన్ అందుబాటులో లేదు: {e}',

  cloneIdleTitle: 'మీ వాయిస్ క్లోన్ చేయడానికి సిద్ధం.',
  cloneIdleSub: 'మీ ఇంటర్వ్యూ రికార్డింగ్‌లను ElevenLabs కు పంపి ఇన్‌స్టంట్ వాయిస్ క్లోన్ తయారు చేస్తాం.',
  cloneActive: 'మీ వాయిస్ క్లోన్ అవుతోంది…',
  cloneDoneTitle: 'మీ వాయిస్ సిద్ధం.',
  cloneSubActive: 'సాధారణంగా ఒక నిమిషం లోపే. మీ రికార్డింగ్‌లు మీ ఖాతా బయటకు వెళ్లవు.',
  cloneSubDone: 'ElevenLabs ఇన్‌స్టంట్ వాయిస్ · మీ {t} నిడివి సమాధానాల నుంచి తయారైంది',
  cloneNeedAudio: 'ముందు కనీసం 60 సెకన్ల ఇంటర్వ్యూ ఆడియో రికార్డ్ చేయండి — ప్రస్తుతం {t} ఉంది.',
  stages: [
    'వాయిస్ శాంపిల్స్ అప్‌లోడ్ అవుతున్నాయి',
    'ఆడియో శుభ్రం చేయడం, శబ్దం తొలగించడం',
    'ఇన్‌స్టంట్ వాయిస్ క్లోన్ ట్రైనింగ్',
    'వాయిస్ సారూప్యత తనిఖీ',
  ],
  doneWord: 'పూర్తి',
  cloneBtn: 'నా వాయిస్ క్లోన్ చేయి',
  recloneBtn: 'మళ్లీ క్లోన్ చేయి',
  previewBtn: 'మీ వాయిస్ వినండి',
  previewPlaying: 'ప్లే అవుతోంది…',
  continueBtn: 'కొనసాగించండి — మీకు తెలిసినవి నేర్పండి',

  knowledgeTitle: 'మీ పర్సోనాకు మీకు తెలిసినవి నేర్పండి.',
  knowledgeSub:
    'మీరు జోడించిన ప్రతిదీ చిన్న భాగాలుగా విడగొట్టి, ఎంబెడ్ చేసి, ఎవరైనా ప్రశ్న అడిగినప్పుడు వెతుకుతుంది — అంచనాలు కాదు, మీ వాస్తవాలతోనే సమాధానం ఇస్తుంది.',
  dropTitle: 'డాక్యుమెంట్లు ఇక్కడ వదలండి',
  dropSub: 'PDF, DOCX, TXT, Markdown · లేదా క్లిక్ చేసి ఎంచుకోండి',
  chunking: 'చంకింగ్ & ఎంబెడింగ్…',
  queued: 'క్యూలో ఉంది…',
  indexed: 'ఇండెక్స్ అయింది · మీ పర్సోనాకు అందుబాటులో',
  ingestFailed: 'విఫలమైంది',
  chunksTag: '{n} చంక్స్',
  removeFile: 'తొలగించు',
  pasteTitle: 'లేదా ఏదైనా పేస్ట్ చేయండి',
  pasteSub: 'బయో, తరచూ అడిగే ప్రశ్నలు, బలమైన అభిప్రాయాలు, మీరు ఎలా సమాధానం ఇస్తారో.',
  pastePh:
    'ఉదా: నేను ఆస్టిన్‌లో ప్రొడక్ట్ డిజైనర్‌ని. మంచి ఆన్‌బోర్డింగ్ అంటే అసలు ఆన్‌బోర్డింగ్ లేకపోవడమే అని నా నమ్మకం…',
  indexBtn: 'ఈ టెక్స్ట్ ఇండెక్స్ చేయి',
  indexing: 'ఇండెక్స్ అవుతోంది…',
  statChunks: 'ఇండెక్స్ అయిన చంక్స్',
  statSources: 'మూలాలు',
  statReady: 'సిద్ధం',
  statVoice: 'వాయిస్ క్లోన్',
  statPending: 'పెండింగ్',
  createBtn: 'నా పర్సోనా సృష్టించు →',
  buildingProfile: 'తయారవుతోంది…',

  readyTitle: 'మీ Echo లైవ్‌లో ఉంది.',
  readySub: 'ఇది మీలా వినిపిస్తుంది, మీరు చెప్పినవన్నీ తెలుసు.',
  notReadyTitle: 'మీ Echo సెటప్ పూర్తి చేయండి.',
  notReadySub: 'మీ తరఫున మాట్లాడటానికి ఇంకా కొన్ని దశలు మిగిలాయి.',
  statKChunks: 'జ్ఞాన చంక్స్',
  statAnswers: 'ఇంటర్వ్యూ సమాధానాలు',
  statAudio: 'మీ గొంతు నిడివి',
  addMoreBtn: 'మరింత జ్ఞానం జోడించు',
  startCallBtn: 'లైవ్ కాల్ ప్రారంభించు',
  textChatBtn: 'టెక్స్ట్ చాట్',
  comingNote: 'షేర్ లింక్, ఎంబెడ్, ఫోన్ నంబర్ అనుసంధానం త్వరలో',
  setupInterview: 'ఇంటర్వ్యూ రికార్డ్ చేయండి',
  setupInterviewSub: '{a}/{t} పూర్తి · {s} సెకన్ల ఆడియో (కనీసం 60 సెకన్లు)',
  setupProfile: 'పర్సోనా ప్రొఫైల్ తయారు చేయండి',
  setupProfileSub: 'ఇంటర్వ్యూ ట్రాన్స్‌క్రిప్ట్‌ల నుంచి మీ బయో, విలువలు, మాట తీరును తీసుకుంటుంది.',
  setupVoice: 'మీ వాయిస్ క్లోన్ చేయండి',
  setupVoiceSub: 'మీ ఇంటర్వ్యూ రికార్డింగ్‌ల నుంచి ఇన్‌స్టంట్ వాయిస్ క్లోన్.',
  setupKnowledge: 'మీ జ్ఞానం జోడించండి',
  setupAgent: 'లైవ్ ఏజెంట్ సిద్ధం చేయండి',
  setupAgentSubReady: 'Custom-LLM URL: {u}/v1',
  setupAgentSubMissing: '.env లో PUBLIC_BASE_URL కావాలి — ముందు టన్నెల్ ప్రారంభించండి (ngrok http 8000).',
  open: 'తెరవండి',
  build: 'తయారు చేయి',
  rebuild: 'మళ్లీ తయారు చేయి',
  provision: 'సిద్ధం చేయి',
  resync: 'మళ్లీ సింక్ చేయి',
  provisioning: 'సిద్ధమవుతోంది…',
  missingKeys: '.env లో లేనివి: {k} — ఇవి లేకుంటే కొన్ని దశలు విఫలమవుతాయి.',

  chatTitle: 'టెక్స్ట్ చాట్',
  chatSub: 'వాయిస్ నిమిషాలు ఖర్చు చేయకుండా పర్సోనాతో మాట్లాడండి. ఇంగ్లీష్ లేదా తెలుగు.',
  chatPh: 'ఏదైనా అడగండి…',
  send: 'పంపు',
  sayHello: 'హాయ్ చెప్పండి…',

  liveLabel: 'లైవ్ · మీ Echo',
  v2v: 'వాయిస్-టు-వాయిస్',
  connectingLabel: 'కనెక్ట్ అవుతోంది…',
  connectBtn: 'కాల్ ప్రారంభించు',
  listening: 'వింటోంది…',
  echoSpeaking: 'Echo మాట్లాడుతోంది',
  waitingLabel: 'ఏదైనా మాట్లాడండి',
  mute: 'మ్యూట్',
  unmute: 'అన్‌మ్యూట్',
  youTag: 'మీరు',
  echoTag: 'మీ ECHO',
  callHint:
    'మాట్లాడండి చాలు — Echo వింటుంది, ఆలోచించి మీ క్లోన్ గొంతులో సమాధానం ఇస్తుంది. కాల్స్ ఇంగ్లీష్‌లో మాత్రమే; తెలుగు కోసం టెక్స్ట్ చాట్ వాడండి.',
};

const DICT: Record<Lang, Strings> = { en: EN, te: TE };

interface LangCtx {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: Strings;
  /** Localized question text, falling back to the backend's English. */
  question: (ord: number, text: string) => string;
  category: (key: string) => string;
  /** Why this question is being asked. */
  hint: (key: string) => string;
}

const Ctx = createContext<LangCtx | null>(null);

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() =>
    localStorage.getItem(STORAGE_KEY) === 'te' ? 'te' : 'en',
  );

  const setLang = useCallback((l: Lang) => {
    localStorage.setItem(STORAGE_KEY, l);
    setLangState(l);
  }, []);

  const value = useMemo<LangCtx>(
    () => ({
      lang,
      setLang,
      t: DICT[lang],
      question: (ord, text) => (lang === 'te' ? QUESTIONS_TE[ord] ?? text : text),
      category: (key) => CATEGORIES[key]?.[lang] ?? key,
      hint: (key) => {
        const entry = CATEGORIES[key];
        if (!entry) return '';
        return lang === 'te' ? entry.hintTe : entry.hintEn;
      },
    }),
    [lang, setLang],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLang(): LangCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useLang must be used inside <LangProvider>');
  return ctx;
}

/** m:ss */
export function clock(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
