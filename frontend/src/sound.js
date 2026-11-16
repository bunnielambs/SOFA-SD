// Sons sintetizados na hora (Web Audio), sem arquivos. So tocam depois que a pessoa ativa o som com um toque.
let ctx = null
export function unlock() {
  try { if (navigator.audioSession) navigator.audioSession.type = 'playback' } catch (e) {} // iPhone: tocar mesmo com a chave de silencio
  try { ctx = ctx || new (window.AudioContext || window.webkitAudioContext)(); if (ctx.state === 'suspended') ctx.resume(); return true } catch (e) { return false }
}
export const audioReady = () => !!ctx && ctx.state === 'running'

function env(g, t, a, peak, d) { g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(peak, t + a); g.gain.exponentialRampToValueAtTime(0.0001, t + a + d) }

function whistle(t, dur) {
  const o = ctx.createOscillator(), o2 = ctx.createOscillator(), lfo = ctx.createOscillator(), lg = ctx.createGain(), g = ctx.createGain()
  o.type = 'sine'; o.frequency.value = 2900; o2.type = 'sine'; o2.frequency.value = 3050
  lfo.frequency.value = 38; lg.gain.value = 120; lfo.connect(lg); lg.connect(o.frequency); lg.connect(o2.frequency)
  env(g, t, 0.02, 0.22, dur); o.connect(g); o2.connect(g); g.connect(ctx.destination)
  for (const n of [o, o2, lfo]) { n.start(t); n.stop(t + dur + 0.1) }
}
function thump(t, f = 85, peak = 0.9) {
  const o = ctx.createOscillator(), g = ctx.createGain(); o.type = 'sine'
  o.frequency.setValueAtTime(f * 1.8, t); o.frequency.exponentialRampToValueAtTime(f, t + 0.12)
  env(g, t, 0.005, peak, 0.22); o.connect(g); g.connect(ctx.destination); o.start(t); o.stop(t + 0.3)
}
function crowd(t, dur, peak = 0.35) {
  const n = ctx.sampleRate * dur, buf = ctx.createBuffer(1, n, ctx.sampleRate), d = buf.getChannelData(0)
  for (let i = 0; i < n; i++) d[i] = Math.random() * 2 - 1
  const s = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain()
  s.buffer = buf; f.type = 'bandpass'; f.frequency.setValueAtTime(500, t); f.frequency.linearRampToValueAtTime(1300, t + dur * 0.4); f.Q.value = 0.6
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(peak, t + 0.5); g.gain.setValueAtTime(peak, t + dur * 0.55); g.gain.exponentialRampToValueAtTime(0.0001, t + dur)
  s.connect(f); f.connect(g); g.connect(ctx.destination); s.start(t); s.stop(t + dur)
}
function horn(t, freqs, dur) {
  for (const fr of freqs) { const o = ctx.createOscillator(), g = ctx.createGain(), f = ctx.createBiquadFilter(); o.type = 'sawtooth'; o.frequency.value = fr
    f.type = 'lowpass'; f.frequency.value = 1400; env(g, t, 0.04, 0.09, dur); o.connect(f); f.connect(g); g.connect(ctx.destination); o.start(t); o.stop(t + dur + 0.1) }
}
const SOUNDS = {
  // rum, rum, rum, rum! + torcida + corneta
  goal: t => { [0, 0.26, 0.5, 0.7].forEach((d, i) => thump(t + d, 80 + i * 6)); thump(t + 0.9, 60, 1); crowd(t + 0.1, 3.2); horn(t + 0.9, [196, 247, 294], 0.5); horn(t + 1.45, [262, 330, 392], 0.9) },
  kickoff: t => whistle(t, 0.7),
  halftime: t => { whistle(t, 0.35); whistle(t + 0.5, 0.6) },
  fulltime: t => { whistle(t, 0.3); whistle(t + 0.42, 0.3); whistle(t + 0.84, 1.0) },
  red: t => { whistle(t, 0.25); const o = ctx.createOscillator(), g = ctx.createGain(); o.type = 'square'; o.frequency.setValueAtTime(180, t + 0.3); o.frequency.exponentialRampToValueAtTime(70, t + 1.0)
    env(g, t + 0.3, 0.02, 0.18, 0.7); o.connect(g); g.connect(ctx.destination); o.start(t + 0.3); o.stop(t + 1.2) },
}
const VIBES = { goal: [160, 90, 160, 90, 160, 90, 160, 120, 500], kickoff: [250], halftime: [150, 100, 250], fulltime: [120, 80, 120, 80, 450], red: [350, 120, 350] }

export function play(kind, { sound, vibrate }) {
  if (sound && audioReady() && SOUNDS[kind]) { try { SOUNDS[kind](ctx.currentTime + 0.03) } catch (e) {} }
  if (vibrate && navigator.vibrate) { try { navigator.vibrate(VIBES[kind] || 200) } catch (e) {} }
}
export const canVibrate = () => typeof navigator !== 'undefined' && !!navigator.vibrate
