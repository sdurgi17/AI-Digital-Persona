/** Substitute {name} placeholders. */
export function fmt(template: string, vars: Record<string, string | number> = {}): string {
  return Object.keys(vars).reduce((out, k) => out.split(`{${k}}`).join(String(vars[k])), template);
}

/** Per-category label and the "why we ask" line shown under the question. */
const CATEGORIES: Record<string, { label: string; hint: string }> = {
  biography: {
    label: 'BIOGRAPHY',
    hint: 'This anchors how your persona introduces you and answers everyday questions.',
  },
  values: {
    label: 'VALUES',
    hint: 'Convictions let your persona take positions the way you would.',
  },
  stories: {
    label: 'STORIES',
    hint: 'Signature stories give your persona memorable, authentic material.',
  },
  style: {
    label: 'STYLE',
    hint: 'Verbal tics and phrasing make the clone feel like you, not a narrator.',
  },
  voice_sample: {
    label: 'VOICE SAMPLE',
    hint: 'A longer, relaxed stretch of speech is what makes the voice clone sound natural.',
  },
};

export function categoryLabel(key: string): string {
  return CATEGORIES[key]?.label ?? key;
}

/** Why this question is being asked. */
export function categoryHint(key: string): string {
  return CATEGORIES[key]?.hint ?? '';
}

export const t = {
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
  chatSub: 'Talk to the persona without spending voice minutes.',
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
    'Just talk — Echo listens, thinks and answers in your cloned voice.',
};

/** m:ss */
export function clock(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}
