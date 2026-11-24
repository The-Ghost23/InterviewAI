import { useEffect, useState } from 'react'
import { api } from './api'
import type { StorageStatus } from './types'

type HistoryItem = {
  id: string; created_at: string; role: string; topic: string; difficulty: string
  question_count: number; question_number: number; answered: number
  status: 'awaiting_answer' | 'feedback' | 'completed'; score: number | null
}

export function History({ storage }: { storage: StorageStatus }) {
  const [items, setItems] = useState<HistoryItem[]>([])
  const [offset, setOffset] = useState(0)
  const [refresh, setRefresh] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    const abort = new AbortController()
    setLoading(true); setError('')
    api<{ items: HistoryItem[]; has_more: boolean }>(`/api/interviews?limit=10&offset=${offset}`, { signal: abort.signal })
      .then(data => { if (!abort.signal.aborted) { setItems(data.items); setHasMore(data.has_more) } })
      .catch(err => { if (!abort.signal.aborted) setError(err instanceof Error ? err.message : 'Could not load your interviews.') })
      .finally(() => { if (!abort.signal.aborted) setLoading(false) })
    return () => abort.abort()
  }, [offset, refresh])
  return <section className="py-10 md:py-14">
    <div className="mb-8 flex flex-wrap items-center justify-between gap-4"><div><p className="eyebrow">Interview history</p><h1 className="text-3xl font-semibold tracking-tight md:text-4xl">See how far you’ve come.</h1></div><a href="#setup" className="primary">New interview</a></div>
    <p className="mb-6 max-w-2xl leading-relaxed text-slate-300">{storage.persistent && storage.ready ? 'Your interviews are saved in Supabase. Revisit a report or pick up where you left off.' : storage.backend === 'memory' ? 'This workspace currently uses temporary storage. These interviews disappear when the backend restarts. Connect Supabase to keep them.' : 'Storage is being checked or is unavailable. Refresh the connection before relying on saved history.'}</p>
    <div className="mb-5 flex items-center justify-between gap-3"><p className="text-sm text-slate-400">{items.length ? `Interviews ${offset + 1}–${offset + items.length}` : 'Your practice sessions'}</p><button type="button" className="secondary" disabled={loading} onClick={() => setRefresh(value => value + 1)}>Refresh history</button></div>
    {loading ? <p role="status" className="panel">Loading interviews…</p> : error ? <p role="alert" className="panel text-red-200">{error}</p> : items.length === 0 ? <div className="panel"><h2 className="text-xl font-semibold">Your next interview is your first step.</h2><p className="mt-3 text-slate-300">Start a practice session, and it will appear here.</p><a href="#setup" className="secondary mt-5 inline-block">Set up an interview</a></div> : <div className="space-y-4">{items.map(item => <article key={item.id} className="panel flex flex-wrap items-center justify-between gap-5">
      <div className="min-w-0"><p className="mb-2 text-sm text-violet-200">{item.status === 'completed' ? 'Completed' : 'In progress'} · {item.difficulty}</p><h2 className="text-xl font-semibold">{item.role}</h2><p className="mt-2 text-slate-300">{item.topic} · {item.answered} of {item.question_count} answers submitted</p><p className="mt-2 text-sm text-slate-400">{new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(item.created_at))}</p></div>
      <div className="flex flex-wrap items-center gap-5">{item.score !== null && <p className="text-2xl font-semibold text-violet-200">{item.score}<span className="text-sm text-slate-400"> / 10</span></p>}<a href={`#session/${item.id}`} className="secondary">{item.status === 'completed' ? 'View report' : 'Resume interview'}</a></div>
    </article>)}</div>}
    <nav aria-label="History pages" className="mt-6 flex flex-wrap items-center justify-between gap-3"><button type="button" className="secondary" disabled={loading || offset === 0} onClick={() => setOffset(value => Math.max(0, value - 10))}>Previous page</button><button type="button" className="secondary" disabled={loading || !!error || !hasMore} onClick={() => setOffset(value => value + 10)}>Next page</button></nav>
  </section>
}
