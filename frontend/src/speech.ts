// Question playback only. Audio transcription happens on the backend.
export function appendTranscript(base: string, transcript: string, limit = 4000) {
  const words = transcript.trim()
  const combined = words ? base + (base && !/\s$/.test(base) ? ' ' : '') + words : base
  return { text: combined.slice(0, limit), truncated: combined.length > limit }
}

type Utterance = { lang: string; rate: number; onend: (() => void) | null; onerror: (() => void) | null }
export type PlaybackEnvironment = {
  synthesis?: { speak(utterance: Utterance): void; cancel(): void }
  makeUtterance?: (text: string) => Utterance
}
export function browserPlaybackEnvironment(): PlaybackEnvironment {
  return {
    synthesis: window.speechSynthesis as unknown as PlaybackEnvironment['synthesis'],
    makeUtterance: typeof window.SpeechSynthesisUtterance === 'function' ? text => new SpeechSynthesisUtterance(text) as unknown as Utterance : undefined,
  }
}
export function createPlayback(environment: PlaybackEnvironment, onChange: (state: { speaking: boolean; error: string }) => void) {
  let utterance: Utterance | null = null
  let disposed = false
  function update(speaking: boolean, error = '') { if (!disposed) onChange({ speaking, error }) }
  function cancel() {
    if (!utterance) return
    utterance.onend = null; utterance.onerror = null; utterance = null
    environment.synthesis?.cancel(); update(false)
  }
  function speak(text: string) {
    if (disposed) return
    if (!environment.synthesis || !environment.makeUtterance) { update(false, 'Reading aloud is unavailable. Read the question on screen.'); return }
    cancel()
    try {
      const next = environment.makeUtterance(text)
      utterance = next; next.lang = 'en-IN'; next.rate = 0.95
      next.onend = () => { if (utterance === next) { utterance = null; update(false) } }
      next.onerror = () => { if (utterance === next) { utterance = null; update(false, 'Reading aloud failed. Read the question on screen or try again.') } }
      update(true); environment.synthesis.speak(next)
    } catch { utterance = null; update(false, 'Reading aloud could not start. Read the question on screen.') }
  }
  return { supported: Boolean(environment.synthesis && environment.makeUtterance), speak, cancel, dispose() { disposed = true; cancel() } }
}
