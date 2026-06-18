/**
 * Sound effects (#50): tonos cortos sintetizados con Web Audio.
 *
 * Decisión: sintetizar en lugar de bundlear mp3/wav. Coste: 0 KB en el
 * bundle. Latencia: 0 ms (la API decoded existe en cuanto creamos el
 * AudioContext). Limitación: solo tonos simples; no podemos reproducir
 * onepiece.mp3 desde aquí (eso lo gestiona el código que ya existía).
 *
 * Opt-in: por defecto SILENCIADO. El user activa los sfx en el toggle de
 * UserModal → settings. Estado persistido en localStorage para que cruce
 * sesiones sin pedir nada al backend.
 *
 * iOS Safari: AudioContext arranca en estado 'suspended' hasta el primer
 * gesto del usuario. La primera llamada a play() puede no sonar si aún no
 * hubo interacción. No es un bug del compose, es un policy del browser.
 */

const LS_ENABLED = 'sfx.enabled.v1'

let ctx: AudioContext | null = null
let enabled = ((): boolean => {
  try { return localStorage.getItem(LS_ENABLED) === '1' } catch { return false }
})()

function ensureCtx(): AudioContext | null {
  if (ctx) return ctx
  try {
    const AC = (window as any).AudioContext || (window as any).webkitAudioContext
    if (!AC) return null
    ctx = new AC() as AudioContext
    return ctx
  } catch {
    return null
  }
}

/**
 * Tono simple. `freq` (Hz), `duration` (s), `type` (oscillator wave),
 * `volume` (0-1 lineal), `attack`/`release` (envelope corto).
 */
function tone(freq: number, duration: number, type: OscillatorType = 'sine', volume = 0.15) {
  if (!enabled) return
  const ac = ensureCtx()
  if (!ac) return
  // Si Safari dejó el contexto suspended (autoplay policy), resúmelo al
  // vuelo. No await — si falla, no pasa nada audible.
  if (ac.state === 'suspended') {
    try { ac.resume() } catch {}
  }
  const now = ac.currentTime
  const osc = ac.createOscillator()
  osc.type = type
  osc.frequency.setValueAtTime(freq, now)
  const gain = ac.createGain()
  gain.gain.setValueAtTime(0, now)
  gain.gain.linearRampToValueAtTime(volume, now + 0.008)
  gain.gain.exponentialRampToValueAtTime(0.0001, now + duration)
  osc.connect(gain)
  gain.connect(ac.destination)
  osc.start(now)
  osc.stop(now + duration + 0.02)
}

export const sfx = {
  isEnabled(): boolean { return enabled },
  setEnabled(v: boolean) {
    enabled = v
    try { localStorage.setItem(LS_ENABLED, v ? '1' : '0') } catch {}
    if (v) {
      // Tono de prueba breve para que el user confirme que está activo.
      tone(660, 0.12, 'triangle', 0.12)
    }
  },
  /** Click ligero (UI buttons, dropdowns). */
  click() { tone(880, 0.06, 'square', 0.05) },
  /** Daily claim — campanita ascendente. */
  chime() {
    tone(659.25, 0.18, 'triangle', 0.12)
    setTimeout(() => tone(987.77, 0.22, 'triangle', 0.12), 80)
  },
  /** Prediction correct — acorde mayor breve. */
  success() {
    tone(523.25, 0.12, 'sine', 0.1)              // C5
    setTimeout(() => tone(659.25, 0.12, 'sine', 0.1), 60)  // E5
    setTimeout(() => tone(783.99, 0.18, 'sine', 0.12), 120) // G5
  },
  /** Error / acción rechazada. Tono grave decreciente. */
  fail() {
    tone(220, 0.16, 'sawtooth', 0.08)
    setTimeout(() => tone(165, 0.2, 'sawtooth', 0.08), 100)
  },
}
