import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'
import { supabase } from './auth'

type Mode = 'login' | 'signup' | 'reset' | 'recovery'
export function AuthGate({ children }: { children: (session: Session) => ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(Boolean(supabase))
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [username, setUsername] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  useEffect(() => {
    if (!supabase) return
    let active = true
    const { data } = supabase.auth.onAuthStateChange((event, next) => {
      if (!active) return
      setSession(next); setLoading(false)
      if (event === 'PASSWORD_RECOVERY') setMode('recovery')
      if (event === 'SIGNED_OUT') { setPassword(''); setMode('login') }
    })
    supabase.auth.getSession().then(({ data, error }) => {
      if (active) { setSession(data.session); setLoading(false); if (error) setError('Could not restore your session. Please sign in again.') }
    }).catch(() => { if (active) { setLoading(false); setError('Could not connect to authentication. Please reload.') } })
    const params = new URLSearchParams(window.location.search)
    if (params.has('error')) setError('Sign-in was cancelled or could not finish. Please try again.')
    // Remove OAuth query parameters after the SDK finishes exchanging the PKCE code.
    supabase.auth.initialize().then(() => {
      if (active && (params.has('code') || params.has('error'))) window.history.replaceState({}, '', window.location.pathname + window.location.hash)
    }).catch(() => { if (active) { setLoading(false); setError('Could not finish sign-in. Please try again.') } })
    return () => { active = false; data.subscription.unsubscribe() }
  }, [])
  function changeMode(next: Mode) { setMode(next); setError(''); setMessage(''); setPassword('') }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!supabase || busy) return
    setBusy(true); setError(''); setMessage('')
    const redirect = window.location.origin + '/'
    try {
      if (mode === 'signup') {
        const { data, error } = await supabase.auth.signUp({ email: email.trim(), password, options: { data: { display_name: username.trim() }, emailRedirectTo: redirect } })
        if (error) throw error
        if (!data.session) setMessage('Check your email to confirm your account, then sign in. If you already have an account, use Sign in.')
      } else if (mode === 'reset') {
        const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), { redirectTo: redirect })
        if (error) throw error
        setMessage('If this email has an account, a password reset link will arrive shortly.')
      } else if (mode === 'recovery') {
        const { error } = await supabase.auth.updateUser({ password })
        if (error) throw error
        setMode('login'); setMessage('Password updated.');
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password })
        if (error) throw error
      }
      setPassword('')
    } catch (err) { setError(err instanceof Error ? err.message : 'Authentication failed. Please retry.') }
    finally { setBusy(false) }
  }
  async function google() {
    if (!supabase || busy) return
    setBusy(true); setError('')
    try {
      const { error } = await supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin + '/' } })
      if (error) throw error
    } catch (err) { setError(err instanceof Error ? err.message : 'Google sign-in failed.') }
    finally { setBusy(false) }
  }
  async function logout() {
    if (!supabase) return
    setBusy(true); setError('')
    try {
      const { error } = await supabase.auth.signOut({ scope: 'local' })
      if (error) throw error
      window.location.hash = 'setup'; setSession(null)
    } catch { setError('Could not sign out. Please retry.') }
    finally { setBusy(false) }
  }
  if (loading) return <main className="mx-auto max-w-xl px-6 py-16"><p role="status">Restoring your account…</p></main>
  if (session && mode !== 'recovery') return <><div className="mx-auto flex max-w-6xl flex-wrap items-center justify-end gap-4 px-6 pt-6 text-sm"><span>Signed in as {session.user.user_metadata?.display_name || session.user.email}</span><button className="secondary" disabled={busy} onClick={() => void logout()}>Sign out</button>{error && <p role="alert">{error}</p>}</div>{children(session)}</>
  return <main className="mx-auto max-w-lg px-6 py-16"><a href="#setup" className="text-xl font-bold">Interview<span className="text-violet-400">AI</span></a><section className="panel mt-8"><p className="eyebrow">Your space to practice</p><h1 className="mb-4 text-3xl font-semibold">{mode === 'signup' ? 'Create your account' : mode === 'reset' ? 'Reset your password' : mode === 'recovery' ? 'Choose a new password' : 'Welcome back'}</h1><p className="mb-6 text-slate-300">Save your progress and keep your interview history private.</p>
    {!supabase ? <p role="alert">Authentication setup is needed. Add your Supabase Project URL and publishable key to frontend/.env, then restart Vite.</p> : <>
      {(mode === 'login' || mode === 'signup') && <><button type="button" className="secondary mb-6 w-full" disabled={busy} onClick={() => void google()}>Continue with Google</button><p className="mb-5 text-center text-sm text-slate-400">or continue with email</p></>}
      <form onSubmit={submit}><fieldset disabled={busy} className="space-y-5">
        {mode === 'signup' && <label className="block">Display username<input className="mt-2 w-full rounded-lg border border-white/20 bg-slate-900 p-3" autoComplete="nickname" value={username} onChange={e => setUsername(e.target.value)} minLength={2} maxLength={50} required /></label>}
        {mode !== 'recovery' && <label className="block">Email<input className="mt-2 w-full rounded-lg border border-white/20 bg-slate-900 p-3" type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} required /></label>}
        {mode !== 'reset' && <label className="block">Password<input className="mt-2 w-full rounded-lg border border-white/20 bg-slate-900 p-3" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password} onChange={e => setPassword(e.target.value)} minLength={mode === 'login' ? 1 : 8} maxLength={128} required /></label>}
        <button className="primary w-full">{busy ? 'Please wait…' : mode === 'signup' ? 'Create account' : mode === 'reset' ? 'Send reset link' : mode === 'recovery' ? 'Update password' : 'Sign in'}</button>
      </fieldset></form>
      <div className="mt-6 flex flex-wrap gap-4 text-sm">{mode === 'login' ? <><button disabled={busy} onClick={() => changeMode('signup')}>Create an account</button><button disabled={busy} onClick={() => changeMode('reset')}>Forgot password?</button></> : mode !== 'recovery' && <button disabled={busy} onClick={() => changeMode('login')}>Back to sign in</button>}</div>
    </>}
    {error && <p role="alert" className="mt-5 text-red-200">{error}</p>}{message && <p role="status" className="mt-5 text-emerald-200">{message}</p>}
  </section></main>
}
