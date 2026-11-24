// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
const auth = vi.hoisted(() => ({ getSession: vi.fn() }))
vi.mock('../src/auth', () => ({ supabase: { auth } }))
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.resetModules(); vi.clearAllMocks() })
it('sends authentication and audio directly to the configured backend, preserving content type', async () => {
  vi.stubEnv('VITE_API_BASE_URL','https://api.example.test/')
  auth.getSession.mockResolvedValue({ data: { session: { access_token: 'test-access-token' } }, error: null })
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ text: 'Answer' }) })
  vi.stubGlobal('fetch',fetch)
  const { api } = await import('../src/api')
  const audio = new Blob(['test audio'],{type:'audio/webm'})
  await api('/api/speech/transcribe',{method:'POST',headers:{'Content-Type':'audio/webm'},body:audio})
  expect(fetch.mock.calls[0][0]).toBe('https://api.example.test/api/speech/transcribe')
  const request=fetch.mock.calls[0][1]
  expect(request.headers.get('Authorization')).toBe('Bearer test-access-token')
  expect(request.headers.get('Content-Type')).toBe('audio/webm')
  expect(request.body).toBe(audio)
})
it('keeps relative API paths for local development without sending an empty bearer header',async () => {
  vi.stubEnv('VITE_API_BASE_URL','')
  auth.getSession.mockResolvedValue({data:{session:null},error:null})
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({status:'ok'})})
  vi.stubGlobal('fetch',fetch)
  const {api}=await import('../src/api')
  await api('/api/health')
  expect(fetch.mock.calls[0][0]).toBe('/api/health')
  expect(fetch.mock.calls[0][1].headers.has('Authorization')).toBe(false)
})
