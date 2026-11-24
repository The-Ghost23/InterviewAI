import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './api'
import { useVoice } from './useVoice'
import type { Feedback, Session } from './types'

const categories = [
  ['technical_accuracy', 'Technical accuracy'], ['completeness', 'Completeness'],
  ['clarity', 'Clarity'], ['reasoning', 'Reasoning'],
] as const

function Notes({ title, notes, empty }: { title: string; notes: string[]; empty?: string }) {
  return <section className="mt-5"><h4 className="font-semibold text-violet-200">{title}</h4>{notes.length ? <ul className="mt-2 list-disc space-y-2 pl-5 text-slate-300">{notes.map((note, i) => <li key={i}>{note}</li>)}</ul> : <p className="mt-2 text-slate-400">{empty}</p>}</section>
}

function FeedbackCard({ feedback }: { feedback: Feedback }) {
  return <div className="mt-6 rounded-xl border border-violet-400/30 bg-violet-400/5 p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-xl font-semibold">Your feedback</h3><p className="text-2xl font-semibold text-violet-200">{feedback.score}<span className="text-base text-slate-400"> / 10</span></p></div>
    <dl className="mt-5 grid grid-cols-2 gap-3">{categories.map(([key, label]) => <div key={key} className="rounded-lg bg-white/5 p-3"><dt className="text-sm text-slate-300">{label}</dt><dd className="mt-1 text-lg font-semibold">{feedback[key]} / 10</dd></div>)}</dl>
    <Notes title="What went well" notes={feedback.strengths} empty="No specific strengths identified in this answer." />
    <Notes title="Missing concepts" notes={feedback.missing_concepts} empty="No missing concepts identified." />
    <Notes title="Try this next time" notes={feedback.suggestions} />
    <p className="mt-5 text-sm text-slate-400">AI coaching feedback can be imperfect. Scores are practice guidance.</p>
  </div>
}

export function InterviewRoom({ session, onUpdate, persistent }: { session: Session; onUpdate: (session: Session) => void; persistent: boolean }) {
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState<'answer' | 'next' | null>(null)
  const [error, setError] = useState('')
  const pending = useRef(false)
  const controller = useRef<AbortController | null>(null)
  const resultHeading = useRef<HTMLHeadingElement>(null)
  const current = session.history.find(turn => turn.question_number === session.question_number)
  const complete = session.status === 'completed'
  const voice = useVoice(`${session.id}:${session.question_number}:${session.status}`, answer, setAnswer)
  const dictating = voice.phase !== 'idle' || voice.transcribing

  useEffect(() => { setAnswer(''); setError('') }, [session.id, session.question_number])
  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => { if (current || complete) resultHeading.current?.focus() }, [current, complete])

  async function perform(action: 'answer' | 'next') {
    if (pending.current || dictating) return
    voice.pause()
    pending.current = true
    setBusy(action)
    setError('')
    const abort = new AbortController()
    controller.current = abort
    try {
      const updated = await api<Session>(`/api/interviews/${session.id}/${action === 'answer' ? 'answers' : 'next'}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: abort.signal,
        body: JSON.stringify({ question_number: session.question_number, ...(action === 'answer' ? { answer: answer.trim() } : {}) }),
      })
      if (!abort.signal.aborted) onUpdate(updated)
    } catch (err) {
      if (!abort.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to complete this request. Please retry.')
    } finally {
      pending.current = false
      if (!abort.signal.aborted) setBusy(null)
    }
  }

  function submit(event: FormEvent) { event.preventDefault(); void perform('answer') }

  return <div className="grid gap-6 md:grid-cols-[1.5fr_1fr]">
    <section className="panel" aria-busy={busy !== null}>
      {complete && session.summary ? <>
        <p className="eyebrow">Interview complete</p><h2 ref={resultHeading} tabIndex={-1} className="text-3xl font-semibold">Your practice, in perspective.</h2>
        <p className="mt-6 text-4xl font-semibold text-violet-200">{session.summary.overall_score}<span className="text-lg text-slate-400"> / 10 overall</span></p>
        <p className="mt-3 text-slate-300">You answered {session.summary.answered} of {session.question_count} questions.</p>
        <dl className="mt-6 grid grid-cols-2 gap-3">{categories.map(([key, label]) => <div key={key} className="rounded-lg bg-white/5 p-3"><dt className="text-sm text-slate-300">Average {label.toLowerCase()}</dt><dd className="mt-1 font-semibold">{session.summary!.category_scores[key]} / 10</dd></div>)}</dl>
        <Notes title="Your next practice steps" notes={session.summary.suggestions} />
        <p className="mt-5 text-sm leading-relaxed text-slate-400">Scores are equal-weight averages of AI coaching ratings, not a validated assessment. Review the feedback alongside each answer.</p>
        <h3 className="mb-4 mt-8 text-xl font-semibold">Review your interview</h3>
        {session.history.map(turn => <details key={turn.question_number} className="review-turn"><summary>Question {turn.question_number} · {turn.feedback.score} / 10</summary><p className="mt-4 text-lg font-medium">{turn.question}</p><h4 className="mb-2 mt-4 font-semibold text-violet-200">Your answer</h4><p className="whitespace-pre-wrap break-words text-slate-300">{turn.answer}</p><FeedbackCard feedback={turn.feedback} /></details>)}
      </> : <>
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3"><p className="text-sm font-semibold text-violet-200">Question {session.question_number} of {session.question_count}</p><span className="tag">{session.difficulty}</span></div>
        <div className="mb-8 h-1.5 overflow-hidden rounded-full bg-white/10" role="progressbar" aria-label="Answers submitted" aria-valuemin={0} aria-valuemax={session.question_count} aria-valuenow={session.history.length}><div className="h-full rounded-full bg-violet-400" style={{ width: `${session.history.length / session.question_count * 100}%` }} /></div>
        <h2 className="text-2xl font-medium leading-relaxed md:text-3xl">{session.question}</h2>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button type="button" className="secondary" disabled={!voice.canSpeak || dictating || busy !== null} onClick={() => voice.speaking ? voice.cancelSpeech() : voice.speak(session.question)}>{voice.speaking ? 'Stop reading' : 'Read question aloud'}</button>
          {!voice.canSpeak && <p className="text-sm text-slate-400">Reading aloud is unavailable in this browser.</p>}
        </div>
        {current ? <>
          <h3 ref={resultHeading} tabIndex={-1} className="mb-2 mt-8 font-semibold text-violet-200">Your submitted answer</h3><p className="whitespace-pre-wrap break-words text-slate-300">{current.answer}</p>
          <FeedbackCard feedback={current.feedback} />
          <button type="button" className="primary mt-6 w-full" disabled={busy !== null} onClick={() => void perform('next')}>{busy === 'next' ? 'Preparing your next question…' : 'Next question'}</button>
        </> : <form onSubmit={submit} className="mt-8">
          <label htmlFor="answer" className="block font-semibold">Your answer</label><p id="answer-help" className="mb-3 mt-2 text-sm text-slate-400">Explain the core idea, your reasoning, and an example if helpful. Up to 4,000 characters.</p>
          <div className="voice-panel mb-4">
            <div className="flex flex-wrap items-center gap-3">
              <button type="button" className="secondary" disabled={!voice.canRecord || busy !== null || voice.transcribing || voice.phase === 'stopping' || (voice.phase === 'idle' && voice.server !== 'ready')} onClick={() => voice.phase === 'idle' ? voice.startRecording() : voice.stopRecording()}>{voice.phase === 'requesting' ? 'Cancel recording' : voice.phase === 'recording' ? 'Stop and transcribe' : voice.phase === 'stopping' ? 'Finishing recording…' : voice.transcribing ? 'Transcribing…' : 'Record answer'}</button>
              <span role="status" className="text-sm text-violet-200">{voice.phase === 'requesting' ? 'Waiting for microphone permission…' : voice.phase === 'recording' ? `Recording · ${voice.seconds}s / 180s` : voice.phase === 'stopping' ? 'Saving the last audio…' : voice.transcribing ? 'Microphone off · Converting audio to text…' : 'Microphone off'}</span>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-slate-400">Record up to 3 minutes, then stop to transcribe on the InterviewAI server. At the time limit, recording stops and transcribes automatically. No speech-model download or browser speech service is needed. Review and edit the text before submitting.</p>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">Your recording is sent to this app’s backend for transcription. Audio is processed in memory, not saved as a recording. Leaving this page or hiding the tab discards an unfinished recording.</p>
            {!voice.canRecord && <p className="mt-3 text-sm text-amber-200">Recording is unavailable here. Use localhost or HTTPS with microphone access, or type below.</p>}
            {voice.server !== 'ready' && <div className="mt-3"><p className="text-sm text-amber-200">{voice.server === 'checking' ? 'Checking voice connection…' : 'Voice transcription is unavailable on the server. You can still type your answer.'}</p><button type="button" className="secondary mt-2" disabled={voice.server === 'checking'} onClick={() => void voice.checkServer()}>Check voice connection</button></div>}
            {voice.retryAvailable && <button type="button" className="secondary mt-3" disabled={dictating || busy !== null} onClick={() => voice.retry()}>Retry transcription</button>}
          </div>
          <textarea id="answer" value={answer} onChange={e => setAnswer(e.target.value)} required minLength={2} maxLength={4000} rows={8} disabled={busy !== null || dictating} aria-describedby="answer-help answer-count" placeholder="Walk your interviewer through your thinking…" />
          <p id="answer-count" className="mt-2 text-right text-sm text-slate-400">{answer.length} / 4,000</p>
          <button className="primary mt-4 w-full" disabled={busy !== null || dictating || answer.trim().length < 2}>{busy === 'answer' ? 'Reviewing your answer…' : 'Submit answer'}</button>
        </form>}
      </>}
      {voice.error && <p role="alert" className="mt-4 rounded-xl border border-amber-400/30 bg-amber-400/5 p-4 text-amber-200">{voice.error}</p>}
      <div aria-live="polite">{busy && <p role="status" className="mt-4 text-slate-300">{busy === 'answer' ? 'Your AI interviewer is reviewing your answer. This may take a moment.' : 'Your interviewer is preparing a different question.'}</p>}{error && <p role="alert" className="mt-4 rounded-xl bg-red-950/60 p-4 text-red-200">{error} Retry this action, or refresh to check the latest session. Repeating the same submission will not create a second answer.</p>}</div>
    </section>
    <aside className="panel h-fit"><p className="eyebrow">Your interview</p><h2 className="mb-6 text-xl font-semibold">Practice with purpose</h2><dl className="space-y-4"><div className="status-row"><dt>Role</dt><dd>{session.role}</dd></div><div className="status-row"><dt>Topic</dt><dd>{session.topic}</dd></div><div className="status-row"><dt>Difficulty</dt><dd>{session.difficulty}</dd></div><div className="status-row"><dt>Answers submitted</dt><dd>{session.history.length} / {session.question_count}</dd></div><div className="status-row"><dt>Session</dt><dd>{complete ? 'Complete' : 'In progress'}</dd></div></dl><p className="mt-6 break-all text-sm text-slate-400">Session ID: {session.id}</p><p className="mt-4 text-sm leading-relaxed text-slate-400">{persistent ? 'Your interview is saved to Supabase. It remains available after a backend restart; reopen it from History.' : 'Temporary storage: submitted progress survives refresh, but clears after a backend restart or four hours.'}</p></aside>
  </div>
}
