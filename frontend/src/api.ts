import { supabase } from './auth'

const apiBase = (import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/$/, '')

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const { data, error } = supabase ? await supabase.auth.getSession() : { data: { session: null }, error: null }
  if (error) throw new Error('Please sign in again.')
  const headers = new Headers(init?.headers)
  if (data.session) headers.set('Authorization', `Bearer ${data.session.access_token}`)
  const response = await fetch(`${apiBase}${path}`, { ...init, headers, signal: init?.signal
    ? AbortSignal.any([init.signal, AbortSignal.timeout(240_000)]) : AbortSignal.timeout(240_000) })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}). Check your settings and try again.`)
  }
  return response.json() as Promise<T>
}
