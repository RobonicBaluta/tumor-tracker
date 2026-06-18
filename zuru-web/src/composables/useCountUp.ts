import { onBeforeUnmount, ref, watch } from 'vue'
import type { Ref } from 'vue'

interface CountUpOptions {
  /** Duración total de la animación en ms. Default 700. */
  duration?: number
  /** Easing aplicado al progreso lineal [0..1]. Default ease-out cubic. */
  easing?: (t: number) => number
  /** No animar al mount; solo al cambiar el target. Útil si la primera vez
   *  ya viene "desde 0" en data (eg cargas iniciales con valor real desde
   *  el primer render). Default false. */
  skipInitial?: boolean
}

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3)

/**
 * Anima un número desde su valor actual al `target`. Devuelve un ref con
 * el valor INTERMEDIO (redondeado). Re-anima cuando el target cambia.
 *
 * Pensado para stats prominentes (tumor scores, balances, win counts) —
 * no para tickers de animación continua. Usa requestAnimationFrame, se
 * cancela al unmount y al cambio de target.
 */
export function useCountUp(target: Ref<number | null | undefined>, options: CountUpOptions = {}) {
  const duration = options.duration ?? 700
  const easing = options.easing ?? easeOutCubic
  const skipInitial = options.skipInitial ?? false

  const display = ref(0)
  let rafId: number | null = null
  let startTs = 0
  let startVal = 0
  let endVal = 0
  let initial = true

  function cancel() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }

  function frame(now: number) {
    const elapsed = now - startTs
    const progress = Math.min(1, elapsed / duration)
    const eased = easing(progress)
    display.value = Math.round(startVal + (endVal - startVal) * eased)
    if (progress < 1) {
      rafId = requestAnimationFrame(frame)
    } else {
      rafId = null
    }
  }

  function animateTo(next: number) {
    cancel()
    startVal = display.value
    endVal = next
    // Si el delta es ínfimo o el browser no expone rAF (SSR), salto directo.
    if (startVal === endVal || typeof requestAnimationFrame === 'undefined') {
      display.value = endVal
      return
    }
    // performance.now() no se permite por sandboxing en algunos harnesses;
    // medimos elapsed contra el primer frame para evitar saltos visuales.
    startTs = 0
    rafId = requestAnimationFrame(t => {
      startTs = t
      frame(t)
    })
  }

  watch(
    target,
    (newVal) => {
      const next = typeof newVal === 'number' ? newVal : 0
      if (initial) {
        initial = false
        if (skipInitial) {
          display.value = next
          return
        }
      }
      animateTo(next)
    },
    { immediate: true },
  )

  onBeforeUnmount(cancel)

  return { display }
}
