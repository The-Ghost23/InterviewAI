// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, act } from '@testing-library/react'
import { AuthGate } from '../src/AuthGate'
const mock = vi.hoisted(() => ({
  listener: null as null | ((event: string, session: unknown) => void),
  getSession: vi.fn(), signUp: vi.fn(), signInWithPassword: vi.fn(), signInWithOAuth: vi.fn(),
  signOut: vi.fn(), resetPasswordForEmail: vi.fn(), updateUser: vi.fn(),
}))
vi.mock('../src/auth', () => ({ supabase: { auth: {
  ...mock,
  initialize: () => Promise.resolve({ error: null }),
  onAuthStateChange: (listener: typeof mock.listener) => { mock.listener = listener; return { data: { subscription: { unsubscribe: vi.fn() } } } },
} } }))
const session = { user: { id: 'user-a', email: 'fixture@example.test', user_metadata: { display_name: 'Practice user' } } }
async function open() {
  render(<AuthGate>{() => <p>Private interview history</p>}</AuthGate>)
  await screen.findByRole('button', { name: 'Sign in' })
}
beforeEach(() => {
  vi.clearAllMocks()
  mock.getSession.mockResolvedValue({ data: { session: null }, error: null })
  mock.signUp.mockResolvedValue({ data: { session: null }, error: null })
  mock.signInWithPassword.mockResolvedValue({ error: null })
  mock.signInWithOAuth.mockResolvedValue({ error: null })
  mock.signOut.mockResolvedValue({ error: null })
  mock.resetPasswordForEmail.mockResolvedValue({ error: null })
  mock.updateUser.mockResolvedValue({ error: null })
  window.history.replaceState({}, '', '/')
})
afterEach(cleanup)
describe('Account access', () => {
  it('keeps private content hidden until the auth SDK reports a session, and hides it on sign-out', async () => {
    await open()
    expect(screen.queryByText('Private interview history')).toBeNull()
    act(() => mock.listener?.('SIGNED_IN', session))
    expect(screen.getByText('Private interview history')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    await screen.findByRole('button', { name: 'Sign in' })
    expect(screen.queryByText('Private interview history')).toBeNull()
    expect(mock.signOut).toHaveBeenCalledWith({ scope: 'local' })
  })
  it('uses email and password sign-in and surfaces a rejected login', async () => {
    mock.signInWithPassword.mockResolvedValue({ error: new Error('Invalid login credentials') })
    await open()
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'fixture@example.test' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'test-only-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await screen.findByRole('alert')
    expect(screen.getByRole('alert').textContent).toContain('Invalid login credentials')
    expect(screen.queryByText('Private interview history')).toBeNull()
  })
  it('stores the display name as metadata and requires confirmation when no session is returned', async () => {
    await open()
    fireEvent.click(screen.getByRole('button', { name: 'Create an account' }))
    fireEvent.change(screen.getByLabelText('Display username'), { target: { value: 'Learner' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'fixture@example.test' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'test-only-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }))
    await screen.findByRole('status')
    expect(mock.signUp.mock.calls[0][0].options.data).toEqual({ display_name: 'Learner' })
    expect(screen.queryByText('Private interview history')).toBeNull()
  })
  it('requests Google OAuth with the current origin as the callback', async () => {
    await open()
    fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }))
    await waitFor(() => expect(mock.signInWithOAuth).toHaveBeenCalledWith({ provider: 'google', options: { redirectTo: window.location.origin + '/' } }))
  })
  it('offers email recovery and uses the recovery session to update a password', async () => {
    await open()
    fireEvent.click(screen.getByRole('button', { name: 'Forgot password?' }))
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'fixture@example.test' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send reset link' }))
    await screen.findByRole('status')
    expect(mock.resetPasswordForEmail.mock.calls[0][0]).toBe('fixture@example.test')
    act(() => mock.listener?.('PASSWORD_RECOVERY', session))
    expect(screen.queryByText('Private interview history')).toBeNull()
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'new-test-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Update password' }))
    await screen.findByText('Private interview history')
    expect(mock.updateUser).toHaveBeenCalledWith({ password: 'new-test-password' })
  })
})
