import { onBeforeUnmount, onMounted } from 'vue'

type PollerCallback = () => void | Promise<void>

interface VisibilityPollerOptions {
  /** Llamar el callback inmediatamente al montar el componente (default: false). */
  immediate?: boolean
  /** Llamar el callback al hacer focus en la pestaña (default: true). Útil
   *  para re-hidratar UI tras un periodo largo en background. */
  fireOnVisible?: boolean
  /** Arrancar el setInterval automáticamente en onMounted (default: true).
   *  Pasa false si quieres llamar start() manualmente bajo condición
   *  (ej. sólo cuando el user está logged in). */
  autoStart?: boolean
}

/**
 * setInterval auto-pausable cuando document.visibilityState === 'hidden'.
 *
 * Para pollers de red (notifs, friends/live, predictionStats): evita quemar
 * battery y data en pestañas en background. Cuando la pestaña vuelve al
 * foreground, el intervalo se reanuda; si `fireOnVisible` está true (default),
 * dispara el callback inmediatamente para que la UI no muestre data stale.
 *
 * NO uses esto para animaciones de UI (60ms tick para barras de progreso,
 * dice roll, etc.): si el user re-focusea la pestaña le sorprenderá ver una
 * animación congelada. Esto es solo para "trabajo de red en background".
 *
 * Se auto-limpia en onBeforeUnmount.
 */
export function useVisibilityPoller(
  callback: PollerCallback,
  intervalMs: number,
  options: VisibilityPollerOptions = {},
) {
  const { immediate = false, fireOnVisible = true, autoStart = true } = options
  let pollerId: ReturnType<typeof setInterval> | null = null
  let lastVisibility = typeof document !== 'undefined'
    ? document.visibilityState
    : 'visible'

  const fire = () => {
    try {
      const r = callback()
      if (r && typeof (r as Promise<void>).catch === 'function') {
        (r as Promise<void>).catch(() => {})
      }
    } catch {
      // Silenciar errores del callback: un poller que tira no debe romper la app.
    }
  }

  const start = () => {
    if (pollerId !== null) return
    pollerId = setInterval(() => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      fire()
    }, intervalMs)
  }

  const stop = () => {
    if (pollerId !== null) {
      clearInterval(pollerId)
      pollerId = null
    }
  }

  const onVisibilityChange = () => {
    if (typeof document === 'undefined') return
    const now = document.visibilityState
    // Sólo refrescamos si el poller está activo. Si el caller usó
    // autoStart:false y aún no llamó start(), no queremos fire-on-visible
    // sorpresa — significaría ejecutar un callback que el caller pidió no
    // ejecutar todavía.
    if (now === 'visible' && lastVisibility === 'hidden' && fireOnVisible && pollerId !== null) {
      fire()
    }
    lastVisibility = now
  }

  onMounted(() => {
    if (autoStart) {
      if (immediate) fire()
      start()
    }
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibilityChange)
    }
  })

  onBeforeUnmount(() => {
    stop()
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  })

  return { start, stop, fire }
}
