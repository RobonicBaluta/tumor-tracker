import { onBeforeUnmount, onMounted, ref } from 'vue'
import type { Ref } from 'vue'

interface UsePullToRefreshOptions {
  /** Pixeles a tirar antes de disparar refresh. Default 60. */
  threshold?: number
  /** Multiplicador de resistencia: 1=lineal, 0.5=mitad de lo que tiras se
   *  refleja en la barra. Default 0.55 — feels native iOS. */
  resistance?: number
  /** Tope visual de pull (incluso si resistencia es alta). Default
   *  threshold * 1.6. */
  maxPull?: number
  /** Si true, sólo arranca si scrollTop===0 al touchstart. Default true. */
  onlyOnScrollTop?: boolean
  /** Si true, ignora pulls cuando el ref `disabled` es true. */
  disabled?: Ref<boolean>
}

/**
 * Touch-only pull-to-refresh. NO instala listeners en desktop (no detecta
 * mouse drag a propósito — el pattern es solo mobile y queremos evitar
 * confusión accidental con scroll wheel + drag).
 *
 * Devuelve refs reactivos para que la UI pueda mostrar un indicador con
 * progreso continuo (`pullDistance` en px), estado de refresco (`isRefreshing`),
 * y un `progress` 0..1 (clamped) útil para opacity/rotación del spinner.
 *
 * El callback `onRefresh` puede ser async; mientras corre, `isRefreshing`
 * es true y nuevos pulls se ignoran (no se acumulan).
 */
export function usePullToRefresh(
  scrollEl: () => HTMLElement | null,
  onRefresh: () => unknown | Promise<unknown>,
  options: UsePullToRefreshOptions = {},
) {
  const threshold = options.threshold ?? 60
  const resistance = options.resistance ?? 0.55
  const maxPull = options.maxPull ?? threshold * 1.6
  const onlyOnScrollTop = options.onlyOnScrollTop ?? true

  const pullDistance = ref(0)
  const isPulling = ref(false)
  const isRefreshing = ref(false)
  const progress = ref(0)

  let startY = 0
  let startX = 0
  let tracking = false

  function isDisabled() {
    return isRefreshing.value || (options.disabled?.value ?? false)
  }

  function onTouchStart(e: TouchEvent) {
    if (isDisabled()) return
    const el = scrollEl()
    if (!el) return
    if (onlyOnScrollTop && el.scrollTop > 0) return
    const t = e.touches[0]
    if (!t) return
    startY = t.clientY
    startX = t.clientX
    tracking = true
    isPulling.value = false
    pullDistance.value = 0
    progress.value = 0
  }

  function onTouchMove(e: TouchEvent) {
    if (!tracking || isDisabled()) return
    const t = e.touches[0]
    if (!t) return
    const dy = t.clientY - startY
    const dx = t.clientX - startX
    // Gesto horizontal dominante: no es un pull-down; cancela.
    if (Math.abs(dx) > Math.abs(dy) * 0.8 && Math.abs(dx) > 12) {
      tracking = false
      return
    }
    if (dy <= 0) {
      pullDistance.value = 0
      progress.value = 0
      return
    }
    // El user todavía está cerca del top; si el scroll bajó del 0 mientras
    // tiraba (caso edge: scroll inercial), cancelamos.
    const el = scrollEl()
    if (onlyOnScrollTop && el && el.scrollTop > 0) {
      tracking = false
      pullDistance.value = 0
      progress.value = 0
      return
    }
    const resisted = dy * resistance
    pullDistance.value = Math.min(resisted, maxPull)
    progress.value = Math.min(1, pullDistance.value / threshold)
    isPulling.value = true
  }

  async function onTouchEnd() {
    if (!tracking) return
    tracking = false
    const trigger = pullDistance.value >= threshold
    isPulling.value = false
    if (trigger && !isRefreshing.value) {
      isRefreshing.value = true
      try {
        await onRefresh()
      } catch {
        // Errores los maneja el caller — refresh siempre cierra el indicador.
      } finally {
        isRefreshing.value = false
      }
    }
    pullDistance.value = 0
    progress.value = 0
  }

  function onTouchCancel() {
    tracking = false
    isPulling.value = false
    pullDistance.value = 0
    progress.value = 0
  }

  onMounted(() => {
    const el = scrollEl()
    if (!el) return
    // passive: true para no bloquear el scroll del browser; nuestro pattern
    // sólo lee deltaY y no llama preventDefault.
    el.addEventListener('touchstart', onTouchStart, { passive: true })
    el.addEventListener('touchmove', onTouchMove, { passive: true })
    el.addEventListener('touchend', onTouchEnd)
    el.addEventListener('touchcancel', onTouchCancel)
  })

  onBeforeUnmount(() => {
    const el = scrollEl()
    if (!el) return
    el.removeEventListener('touchstart', onTouchStart)
    el.removeEventListener('touchmove', onTouchMove)
    el.removeEventListener('touchend', onTouchEnd)
    el.removeEventListener('touchcancel', onTouchCancel)
  })

  return {
    pullDistance,
    isPulling,
    isRefreshing,
    progress,
  }
}
