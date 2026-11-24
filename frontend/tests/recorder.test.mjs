import test from 'node:test'
import assert from 'node:assert/strict'
import { createAudioRecorder } from '../src/recorder.ts'

function harness(options = {}) {
  const states = [], recordings = [], instances = []
  let trackStops = 0, permissionCalls = 0
  const stream = { getTracks: () => [{ stop: () => trackStops++ }] }
  class Recorder {
    static isTypeSupported(mime) { return mime === (options.mime || 'audio/webm;codecs=opus') }
    constructor(input, config) { this.state = 'inactive'; this.mimeType = config.mimeType || 'audio/webm'; this.config = config; instances.push(this) }
    start() { if (options.startThrows) throw new Error('failed'); this.state = 'recording' }
    stop() { this.state = 'inactive'; this.stops = (this.stops || 0) + 1 }
  }
  const controller = createAudioRecorder({ secure: true, Recorder,
    getUserMedia: async () => { permissionCalls++; if (options.denied) throw Object.assign(new Error('Denied'), { name: 'NotAllowedError' }); return options.permission || stream }, ...options.environment,
  }, { onChange: state => states.push(state), onRecording: blob => recordings.push(blob) }, options.limits)
  return { controller, states, recordings, instances, stream, trackStops: () => trackStops, permissionCalls: () => permissionCalls,
    chunk(text='audio') { instances.at(-1).ondataavailable?.({ data: new Blob([text]) }) },
    end() { instances.at(-1).onstop?.() },
  }
}

test('construction does not request the microphone', () => { const h=harness(); assert.equal(h.permissionCalls(),0); h.controller.dispose() })
test('unsupported recording retains a typed-answer fallback', async () => { const h=harness({environment:{Recorder:undefined}}); await h.controller.start(); assert.equal(h.controller.supported,false); assert.match(h.states.at(-1).error,/type/); assert.equal(h.permissionCalls(),0) })
test('permission failure explains how to recover', async () => { const h=harness({denied:true}); await h.controller.start(); assert.equal(h.states.at(-1).phase,'idle'); assert.match(h.states.at(-1).error,/denied/) })
test('the recorder remains active without speech-service events', async () => { const h=harness(); await h.controller.start(); assert.equal(h.states.at(-1).phase,'recording'); assert.equal(h.instances[0].state,'recording'); assert.equal(h.recordings.length,0); h.controller.dispose() })
test('rapid starts request microphone permission once', async () => { const h=harness(); const first=h.controller.start(); await h.controller.start(); await first; assert.equal(h.permissionCalls(),1); h.controller.dispose() })
test('stop waits for the final chunk before handing audio to transcription', async () => {
  const h=harness(); await h.controller.start(); h.chunk('first'); h.controller.stop(); assert.equal(h.states.at(-1).phase,'stopping'); assert.equal(h.recordings.length,0)
  h.chunk('last'); h.end(); assert.equal(await h.recordings[0].text(),'firstlast'); assert.equal(h.states.at(-1).phase,'idle'); assert.equal(h.trackStops(),1)
})
test('audio/mp4 is selected when webm is unsupported', async () => { const h=harness({mime:'audio/mp4'}); await h.controller.start(); assert.equal(h.instances[0].config.mimeType,'audio/mp4'); h.controller.dispose() })
test('stop and cancel release physical microphone tracks', async () => { const h=harness(); await h.controller.start(); h.controller.cancel(); assert.equal(h.trackStops(),1); assert.equal(h.recordings.length,0); assert.equal(h.states.at(-1).phase,'idle') })
test('cancelling pending permission releases the stream if approval arrives late', async () => {
  let resolve; const permission=new Promise(done=>{resolve=done}); const h=harness({permission}); const started=h.controller.start(); h.controller.stop(); resolve(h.stream); await started
  assert.equal(h.instances.length,0); assert.equal(h.trackStops(),1); assert.equal(h.states.at(-1).phase,'idle')
})
test('navigation during permission cannot start a recorder later', async () => {
  let resolve; const permission=new Promise(done=>{resolve=done}); const h=harness({permission}); const started=h.controller.start(); h.controller.dispose(); const count=h.states.length; resolve(h.stream); await started
  assert.equal(h.instances.length,0); assert.equal(h.trackStops(),1); assert.equal(h.states.length,count)
})
test('late recording callbacks cannot attach audio to another question', async () => {
  const h=harness(); await h.controller.start(); const end=h.instances[0].onstop, data=h.instances[0].ondataavailable; h.controller.dispose(); data({data:new Blob(['old'])}); end(); assert.equal(h.recordings.length,0)
})
test('empty recordings offer a retry rather than uploading', async () => { const h=harness(); await h.controller.start(); h.controller.stop(); h.end(); assert.equal(h.recordings.length,0); assert.match(h.states.at(-1).error,/No audio/) })
test('recorder failures clean up tracks', async () => { const h=harness(); await h.controller.start(); h.instances[0].onerror(); assert.equal(h.trackStops(),1); assert.match(h.states.at(-1).error,/failed/); assert.equal(h.recordings.length,0) })
test('start exceptions clean up tracks', async () => { const h=harness({startThrows:true}); await h.controller.start(); assert.equal(h.trackStops(),1); assert.equal(h.states.at(-1).phase,'idle') })
test('large recordings are rejected before upload', async () => { const h=harness({limits:{seconds:180,bytes:3}}); await h.controller.start(); h.chunk('large'); assert.match(h.states.at(-1).error,/too large/); assert.equal(h.trackStops(),1); assert.equal(h.recordings.length,0) })
test('the duration limit stops recording but preserves its final audio', async () => {
  const h=harness({limits:{seconds:0.01,bytes:100}}); await h.controller.start(); h.chunk(); await new Promise(done=>setTimeout(done,25)); assert.equal(h.instances[0].stops,1); h.end(); assert.equal(h.recordings.length,1); assert.equal(h.trackStops(),1)
})
