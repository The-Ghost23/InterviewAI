export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, signal: init?.signal
    ? AbortSignal.any([init.signal, AbortSignal.timeout(130_000)]) : AbortSignal.timeout(130_000) })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}). Check your settings and try again.`)
  }
  return response.json() as Promise<T>
}
