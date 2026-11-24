export type RecordingStream = { getTracks(): { stop(): void }[] }
export type RecorderInstance = {
  state: string; mimeType: string
  ondataavailable: ((event: { data: Blob }) => void) | null
  onstop: (() => void) | null; onerror: (() => void) | null
  start(timeslice?: number): void; stop(): void
}
export type RecorderConstructor = {
  new (stream: RecordingStream, options?: { mimeType?: string; audioBitsPerSecond?: number }): RecorderInstance
  isTypeSupported?(mime: string): boolean
}
export type RecorderEnvironment = {
  secure: boolean
  getUserMedia?: () => Promise<RecordingStream>
  Recorder?: RecorderConstructor
}
export type CaptureState = { phase: 'idle' | 'requesting' | 'recording' | 'stopping'; error: string }

export function browserRecorderEnvironment(): RecorderEnvironment {
  return {
    secure: window.isSecureContext,
    getUserMedia: navigator.mediaDevices?.getUserMedia ? () => navigator.mediaDevices.getUserMedia({ audio: true }) : undefined,
    Recorder: window.MediaRecorder as unknown as RecorderConstructor | undefined,
  }
}

export function createAudioRecorder(environment: RecorderEnvironment, callbacks: {
  onChange(state: CaptureState): void; onRecording(audio: Blob): void
}, limits = { seconds: 180, bytes: 15 * 1024 * 1024 }) {
  let phase: CaptureState['phase'] = 'idle'
  let recorder: RecorderInstance | null = null
  let stream: RecordingStream | null = null
  let disposed = false, generation = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  function update(next: CaptureState['phase'], error = '') {
    phase = next
    if (!disposed) callbacks.onChange({ phase, error })
  }
  function release() {
    if (timer !== undefined) clearTimeout(timer)
    timer = undefined
    if (recorder) { recorder.ondataavailable = null; recorder.onstop = null; recorder.onerror = null }
    if (stream) stream.getTracks().forEach(track => track.stop())
    stream = null; recorder = null
  }
  function cancel() {
    ++generation
    const current = recorder
    release()
    if (current && current.state !== 'inactive') { try { current.stop() } catch { /* Already stopped. */ } }
    update('idle')
  }
  function stop() {
    if (phase === 'requesting') { cancel(); return }
    if (!recorder || phase !== 'recording') return
    update('stopping')
    try { recorder.stop() } catch { release(); update('idle', 'The recording could not finish. Please try again or type your answer.') }
  }
  async function start() {
    if (disposed || phase !== 'idle') return
    if (!environment.secure || !environment.getUserMedia || !environment.Recorder) {
      update('idle', 'Audio recording is unavailable here. Open the app on localhost or HTTPS, or type your answer.'); return
    }
    const currentGeneration = ++generation
    update('requesting')
    try {
      const acquired = await environment.getUserMedia()
      if (disposed || generation !== currentGeneration) { acquired.getTracks().forEach(track => track.stop()); return }
      stream = acquired
      const Constructor = environment.Recorder
      const mimeType = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/webm', 'audio/ogg;codecs=opus'].find(mime => Constructor.isTypeSupported?.(mime))
      const instance = new Constructor(stream, { ...(mimeType ? { mimeType } : {}), audioBitsPerSecond: 64000 })
      recorder = instance
      const chunks: Blob[] = []
      let size = 0
      instance.ondataavailable = event => {
        if (recorder !== instance || disposed || !event.data.size) return
        chunks.push(event.data); size += event.data.size
        if (size > limits.bytes) { cancel(); update('idle', 'The recording is too large. Record a shorter answer.'); return }
      }
      instance.onerror = () => { if (recorder === instance) { cancel(); update('idle', 'The microphone recording failed. Check your input device and retry, or type your answer.') } }
      instance.onstop = () => {
        if (disposed || recorder !== instance || currentGeneration !== generation) return
        const blob = new Blob(chunks, { type: instance.mimeType || mimeType || 'application/octet-stream' })
        release(); update('idle')
        if (!blob.size) { update('idle', 'No audio was recorded. Check your microphone and try again.'); return }
        callbacks.onRecording(blob)
      }
      instance.start(1000)
      update('recording')
      timer = setTimeout(stop, limits.seconds * 1000)
    } catch (error) {
      if (disposed || generation !== currentGeneration) return
      release()
      const name = error instanceof Error ? error.name : ''
      update('idle', name === 'NotAllowedError' ? 'Microphone access was denied. Allow access for this site, or type your answer.' : name === 'NotFoundError' ? 'No microphone was found. Check your input device or type your answer.' : 'Could not start recording. Check microphone access and try again, or type your answer.')
    }
  }
  return { supported: Boolean(environment.secure && environment.getUserMedia && environment.Recorder), start, stop, cancel,
    dispose() { disposed = true; cancel() },
  }
}
