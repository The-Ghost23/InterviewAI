import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'
import { api } from './api'
import type { Preferences, Session, StorageStatus } from './types'
import { History } from './History'
import { InterviewRoom } from './InterviewRoom'

type AIStatus = { status: string; model: string }
const defaults: Preferences = { role: 'Software Engineer', topic: 'Data Structures', difficulty: 'Beginner', question_count: 5 }

function App() {
  const [storage, setStorage] = useState<StorageStatus>({ backend: 'unknown', persistent: false, ready: false })
  const [backend, setBackend] = useState('Checking')
  const [ai, setAI] = useState<AIStatus>({ status: 'checking', model: 'qwen3:4b' })
  const [preferences, setPreferences] = useState<Preferences>(defaults)
  const [session, setSession] = useState<Session | null>(null)
  const [route, setRoute] = useState(() => window.location.hash)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [checking, setChecking] = useState(false)
  const starting = useRef(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const inRoom = route.startsWith('#session/')
  const inHistory = route === '#history'

  async function checkStatus() {
    setChecking(true)
    await Promise.all([
      api<{ status: string }>('/api/health').then(data => setBackend(data.status === 'ok' ? 'Connected' : 'Unavailable')).catch(() => setBackend('Unavailable')),
      api<StorageStatus>('/api/storage/status').then(setStorage).catch(() => setStorage({ backend: 'unknown', persistent: false, ready: false })),
      api<AIStatus>('/api/ai/status').then(setAI).catch(() => setAI({ status: 'unknown', model: 'qwen3:4b' })),
    ])
    setChecking(false)
  }

  useEffect(() => {
    void checkStatus()
    const onRoute = () => setRoute(window.location.hash)
    window.addEventListener('hashchange', onRoute)
    return () => window.removeEventListener('hashchange', onRoute)
  }, [])

  useEffect(() => {
    setError('')
    if (!route.startsWith('#session/')) {
      setSession(null)
      setRestoring(false)
      return
    }
    const controller = new AbortController()
    const id = route.slice('#session/'.length)
    setRestoring(true)
    setSession(null)
    api<Session>(`/api/interviews/${encodeURIComponent(id)}`, { signal: controller.signal })
      .then(data => { setSession(data); setPreferences({ role: data.role, topic: data.topic, difficulty: data.difficulty, question_count: data.question_count }) })
      .catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to reopen this interview.') })
      .finally(() => { if (!controller.signal.aborted) setRestoring(false) })
    return () => controller.abort()
  }, [route])

  useEffect(() => { if (session) heading.current?.focus() }, [session?.id, session?.question_number])

  async function startInterview(event: FormEvent) {
    event.preventDefault()
    if (starting.current) return
    starting.current = true
    setBusy(true)
    setError('')
    try {
      const data = await api<Session>('/api/interviews', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(preferences),
      })
      window.location.hash = `session/${data.id}`
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to start your interview. Please retry.')
    } finally {
      starting.current = false
      setBusy(false)
      void checkStatus()
    }
  }

  function backToSetup() {
    setError('')
    window.location.hash = 'setup'
  }

  const ready = backend === 'Connected' && ai.status === 'ready' && storage.ready

  return (
    <main className="mx-auto max-w-6xl px-6 py-8 md:px-12 md:py-12">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-6">
        <a href="#setup" className="text-xl font-bold tracking-tight" aria-label="InterviewAI home">Interview<span className="text-violet-400">AI</span></a>
        <nav aria-label="Main navigation" className="flex items-center gap-4"><a href="#setup" aria-current={!inRoom && !inHistory ? 'page' : undefined} className="text-sm text-slate-300 hover:text-white">Practice</a><a href="#history" aria-current={inHistory ? 'page' : undefined} className="text-sm text-violet-200 hover:text-white">History</a></nav>
      </header>
      {inHistory ? <History storage={storage} /> : inRoom ? (
        <section className="py-10 md:py-14" aria-busy={restoring}>
          <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
            <div><p className="eyebrow">Interview room</p><h1 ref={heading} tabIndex={-1} className="text-3xl font-semibold tracking-tight md:text-4xl">Take a breath. You’ve got this.</h1></div>
            <button type="button" className="secondary" onClick={backToSetup}>Back to setup</button>
          </div>
          {restoring && <p role="status" className="panel">Opening your interview…</p>}
          {error && <div role="alert" className="panel border-red-400/30 text-red-200">{error}<p className="mt-3 text-slate-300">If the interview is no longer available, return to setup or check your history.</p></div>}
          {session && !restoring && <InterviewRoom session={session} onUpdate={setSession} persistent={storage.persistent && storage.ready} />}
        </section>
      ) : <>
        <section className="max-w-3xl py-10 md:py-14"><p className="mb-5 text-sm font-semibold uppercase tracking-widest text-violet-300">Make your next interview feel familiar</p><h1 className="text-4xl font-semibold leading-tight tracking-tight md:text-6xl">Your goal.<br /><span className="text-violet-300">Your practice session.</span></h1><p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-300">Choose the role you’re working toward and a topic to sharpen. Your AI interviewer will meet you there.</p></section>
        <div className="grid gap-6 md:grid-cols-[1.25fr_1fr]">
          <section className="panel"><p className="eyebrow">Interview setup</p><h2 className="mb-6 text-2xl font-semibold">Set your focus</h2>
            <form onSubmit={startInterview}>
              <fieldset disabled={busy} className="space-y-5">
                <label htmlFor="role" className="block">Target role<select id="role" value={preferences.role} onChange={e => setPreferences(p => ({ ...p, role: e.target.value }))}>{['Software Engineer', 'Backend Engineer', 'Frontend Engineer', 'Full Stack Engineer', 'Data Engineer'].map(role => <option key={role}>{role}</option>)}</select></label>
                <label htmlFor="topic" className="block">Interview topic<select id="topic" value={preferences.topic} onChange={e => setPreferences(p => ({ ...p, topic: e.target.value }))}>{['Data Structures', 'Algorithms', 'Python', 'JavaScript', 'DBMS', 'OOP', 'Operating Systems', 'Computer Networks'].map(topic => <option key={topic}>{topic}</option>)}</select></label>
                <label htmlFor="difficulty" className="block">Difficulty<select id="difficulty" value={preferences.difficulty} onChange={e => setPreferences(p => ({ ...p, difficulty: e.target.value }))}><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></label>
                <label htmlFor="question-count" className="block">Number of questions<select id="question-count" value={preferences.question_count} onChange={e => setPreferences(p => ({ ...p, question_count: Number(e.target.value) }))}><option value={3}>3 questions · Quick practice</option><option value={5}>5 questions · Focused session</option><option value={10}>10 questions · Deep practice</option></select></label>
                <p className="text-sm leading-relaxed text-slate-400">Answer each question in your own words, get coaching feedback, and review your results at the end.</p>
                <button className="primary w-full" disabled={busy || checking || !ready}>{busy ? 'Preparing your first question…' : 'Start interview'}</button>
              </fieldset>
            </form>
            <div aria-live="polite" className="mt-5">{busy && <p role="status" className="text-slate-300">Your interviewer is preparing. Loading the model for the first time may take a moment.</p>}{error && <p role="alert" className="rounded-xl bg-red-950/60 p-4 text-red-200">{error}</p>}</div>
          </section>
          <aside className="space-y-6"><section className="panel"><p className="eyebrow">Session preview</p><h2 className="mb-5 text-2xl font-semibold">A clear place to begin</h2><dl className="space-y-4"><div className="status-row"><dt>Your role</dt><dd>{preferences.role}</dd></div><div className="status-row"><dt>Your focus</dt><dd>{preferences.topic}</dd></div><div className="status-row"><dt>Your level</dt><dd>{preferences.difficulty}</dd></div><div className="status-row"><dt>Your plan</dt><dd>{preferences.question_count} questions</dd></div></dl></section>
            <section className="panel" aria-live="polite"><p className="eyebrow">Connection</p><h2 className="mb-5 text-xl font-semibold">Ready when you are</h2><dl className="space-y-4"><div className="status-row"><dt>Interview service</dt><dd>{backend}</dd></div><div className="status-row"><dt>Local AI</dt><dd className="capitalize">{ai.status}</dd></div><div className="status-row"><dt>Interview storage</dt><dd>{storage.ready ? storage.persistent ? 'Supabase connected' : 'Temporary memory' : 'Unavailable'}</dd></div></dl>
              {backend === 'Unavailable' ? <p className="mt-4 text-amber-200">The interview service is unavailable. Start the backend, then check again.</p> : ai.status === 'missing' ? <p className="mt-4 text-amber-200">The local model needs to be downloaded. See the README for setup.</p> : ai.status === 'unavailable' ? <p className="mt-4 text-amber-200">Ollama is unavailable. Start Ollama, then check again.</p> : null}
              {storage.backend === 'memory' && <p className="mt-4 text-sm leading-relaxed text-amber-200">Supabase is not connected yet. Interviews remain temporary until the backend database connection is configured.</p>}
              {!storage.ready && backend === 'Connected' && <p className="mt-4 text-sm text-amber-200">Interview storage is unavailable. Check the backend connection and migrations, then check again.</p>}
              <button type="button" onClick={() => void checkStatus()} disabled={checking || busy} className="secondary mt-6">{checking ? 'Checking…' : 'Check connection'}</button>
            </section>
          </aside>
        </div>
      </>}
      <footer className="mt-10 border-t border-white/10 pt-6 text-sm text-slate-400">Local AI feedback · Optional browser voice</footer>
    </main>
  )
}
export default App
