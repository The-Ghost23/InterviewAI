import test from 'node:test'
import assert from 'node:assert/strict'
import { createPlayback, appendTranscript } from '../src/speech.ts'
function harness() {
  const states=[], spoken=[]; let cancels=0
  const controller=createPlayback({synthesis:{speak:u=>spoken.push(u),cancel:()=>cancels++},makeUtterance:text=>({text})},state=>states.push(state))
  return {controller,states,spoken,cancels:()=>cancels}
}
test('playback never starts automatically',()=>{const h=harness();assert.equal(h.spoken.length,0)})
test('playback uses the question and reports completion',()=>{const h=harness();h.controller.speak('Question?');assert.equal(h.spoken[0].text,'Question?');assert.equal(h.states.at(-1).speaking,true);h.spoken[0].onend();assert.equal(h.states.at(-1).speaking,false)})
test('playback cancellation suppresses stale callbacks',()=>{const h=harness();h.controller.speak('First?');const end=h.spoken[0].onend;h.controller.cancel();h.controller.speak('Second?');end();assert.equal(h.states.at(-1).speaking,true);h.controller.dispose();assert.equal(h.cancels(),2)})
test('playback failure restores the control',()=>{const h=harness();h.controller.speak('Question?');h.spoken[0].onerror();assert.equal(h.states.at(-1).speaking,false);assert.match(h.states.at(-1).error,/failed/)})
test('unsupported playback preserves the question on screen',()=>{const states=[];const controller=createPlayback({},state=>states.push(state));controller.speak('Question?');assert.match(states[0].error,/on screen/)})
test('transcribed text appends to existing edited answers without exceeding 4000 characters',()=>{assert.deepEqual(appendTranscript('Typed.',' New words. '),{text:'Typed. New words.',truncated:false});assert.deepEqual(appendTranscript('1234','56',6),{text:'1234 5',truncated:true})})
