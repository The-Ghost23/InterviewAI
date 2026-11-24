import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { appendTranscript, browserPlaybackEnvironment, createPlayback } from './speech'
import { browserRecorderEnvironment, createAudioRecorder } from './recorder'
import type { CaptureState } from './recorder'

export function useVoice(key: string, answer: string, setAnswer: (value: string) => void) {
  const [capture, setCapture] = useState<CaptureState>({ phase: 'idle', error: '' })
  const [playback, setPlayback] = useState({ speaking: false, error: '' })
  const [supported, setSupported] = useState({ record: false, speak: false })
  const [server, setServer] = useState('checking')
  const [transcribing, setTranscribing] = useState(false)
  const [error, setError] = useState('')
  const [retryAvailable, setRetryAvailable] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const recordRef = useRef<ReturnType<typeof createAudioRecorder> | null>(null)
  const playbackRef = useRef<ReturnType<typeof createPlayback> | null>(null)
  const active = useRef<AbortController | null>(null)
  const recording = useRef<Blob | null>(null)
  const uploadRef = useRef<((audio: Blob) => void) | null>(null)
  const uploading = useRef(false)
  const answerRef = useRef(answer); answerRef.current = answer
  const setter = useRef(setAnswer); setter.current = setAnswer

  useEffect(() => {
    let alive = true
    const lifecycle = new AbortController()
    const speaker = createPlayback(browserPlaybackEnvironment(), state => { if (alive) setPlayback(state) })
    async function upload(audio: Blob) {
      if (!alive || uploading.current) return
      uploading.current = true
      recording.current = audio
      setTranscribing(true); setRetryAvailable(false); setError('')
      const abort = new AbortController(); active.current = abort
      try {
        const body = audio
        const result = await api<{ text: string }>('/api/speech/transcribe', { method: 'POST', headers: { 'Content-Type': audio.type || 'application/octet-stream' }, body, signal: abort.signal })
        if (!alive || abort.signal.aborted) return
        const appended = appendTranscript(answerRef.current, result.text)
        answerRef.current = appended.text; setter.current(appended.text)
        recording.current = null
        if (appended.truncated) setError('The transcript reached the 4,000-character limit. Review and shorten your answer if needed.')
      } catch (failure) {
        if (alive && !abort.signal.aborted) { setError(failure instanceof Error ? failure.message : 'Transcription failed. Retry or type your answer.'); setRetryAvailable(true) }
      } finally {
        if (active.current === abort) { uploading.current = false; active.current = null }
        if (alive) setTranscribing(false)
      }
    }
    uploadRef.current = audio => { void upload(audio) }
    const recorder = createAudioRecorder(browserRecorderEnvironment(), {
      onChange: state => { if (alive) setCapture(state) },
      onRecording: audio => { void upload(audio) },
    })
    recordRef.current = recorder; playbackRef.current = speaker
    setSupported({ record: recorder.supported, speak: speaker.supported })
    setCapture({ phase: 'idle', error: '' }); setPlayback({ speaking: false, error: '' })
    setTranscribing(false); setError(''); setRetryAvailable(false); setSeconds(0)
    recording.current = null; uploading.current = false
    async function check() {
      try {
        const result = await api<{ status: string }>('/api/speech/status', { signal: lifecycle.signal })
        if (alive) setServer(result.status)
      } catch { if (alive) setServer('unavailable') }
    }
    void check()
    const onHidden = () => { if (document.hidden) { recorder.cancel(); speaker.cancel() } }
    document.addEventListener('visibilitychange', onHidden)
    return () => {
      alive = false; lifecycle.abort(); active.current?.abort(); recorder.dispose(); speaker.dispose()
      document.removeEventListener('visibilitychange', onHidden)
      recording.current = null; uploadRef.current = null
    }
  }, [key])
  useEffect(() => {
    if (capture.phase !== 'recording') return
    const started = Date.now(); setSeconds(0)
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500)
    return () => clearInterval(timer)
  }, [capture.phase])
  return {
    phase: capture.phase, speaking: playback.speaking, transcribing, seconds,
    error: error || capture.error || playback.error,
    canSpeak: supported.speak, canRecord: supported.record, server, retryAvailable,
    startRecording() {
      if (uploading.current) return
      playbackRef.current?.cancel(); setError(''); setRetryAvailable(false); recording.current = null
      void recordRef.current?.start()
    },
    stopRecording: () => recordRef.current?.stop(),
    speak: (text: string) => playbackRef.current?.speak(text),
    cancelSpeech: () => playbackRef.current?.cancel(),
    retry() { if (recording.current) uploadRef.current?.(recording.current) },
    async checkServer() {
      setServer('checking')
      try { const result = await api<{ status: string }>('/api/speech/status'); setServer(result.status) } catch { setServer('unavailable') }
    },
    pause() { recordRef.current?.cancel(); playbackRef.current?.cancel() },
  }
}
