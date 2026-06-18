import type { Directive } from 'vue'

/**
 * `v-tooltip="'mi texto'"` — directive cross-device:
 *   - Desktop / non-touch: setea `title=` para tooltip nativo del browser.
 *   - Touch device: en `touchstart` muestra un popup propio cerca del elemento
 *     (porque `title` no se dispara con tap en iOS/Android).
 *
 * Singleton popup global — un solo div compartido, no DOM por elemento.
 * Auto-dismiss tras 2.5s o al tap fuera del anchor / scroll en cualquier
 * scrollable ancestor (no solo window).
 *
 * Usage:
 *   <button v-tooltip="'Recargar partidas'">↻</button>
 *
 * Reactividad: la directiva guarda el último texto en `el.__tooltipText`
 * dentro de mounted+updated. El handler de touchstart lee de ahí, no del
 * closure inicial — así un v-tooltip="streakAtRisk ? 'urgente' : 'normal'"
 * actualiza correctamente al cambiar el valor.
 */

let popupEl: HTMLDivElement | null = null
let hideTimer: number | null = null
let currentAnchor: HTMLElement | null = null

const supportsTouch =
  typeof window !== 'undefined' &&
  ('ontouchstart' in window || (navigator as any).maxTouchPoints > 0)

function ensurePopup(): HTMLDivElement {
  if (popupEl) return popupEl
  const el = document.createElement('div')
  el.style.cssText = [
    'position: fixed',
    'z-index: 999',
    'pointer-events: none',
    'background: rgba(0, 0, 0, 0.92)',
    'color: white',
    'font-family: ui-monospace, SFMono-Regular, Menlo, monospace',
    'font-size: 11px',
    'padding: 6px 10px',
    'border-radius: 6px',
    'border: 1px solid rgba(255, 255, 255, 0.2)',
    'box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4)',
    'max-width: 220px',
    'white-space: pre-wrap',
    'text-align: center',
    'opacity: 0',
    'transition: opacity 0.12s ease-out',
  ].join(';')
  document.body.appendChild(el)
  popupEl = el
  return el
}

function showTooltip(text: string, anchor: HTMLElement) {
  if (!text) return
  const el = ensurePopup()
  el.textContent = text
  el.style.left = '0px'
  el.style.top = '0px'
  // Forzar layout para conocer el tamaño real antes de posicionar.
  void el.offsetHeight
  const pr = el.getBoundingClientRect()
  const r = anchor.getBoundingClientRect()
  let x = r.left + r.width / 2 - pr.width / 2
  let y = r.top - pr.height - 8
  if (y < 8) y = r.bottom + 8
  const vw = window.innerWidth
  if (x < 8) x = 8
  if (x + pr.width > vw - 8) x = vw - 8 - pr.width
  el.style.left = `${x}px`
  el.style.top = `${y}px`
  el.style.opacity = '1'
  currentAnchor = anchor

  if (hideTimer != null) window.clearTimeout(hideTimer)
  hideTimer = window.setTimeout(hideTooltip, 2500)
}

export function hideTooltip() {
  if (!popupEl) return
  popupEl.style.opacity = '0'
  currentAnchor = null
  if (hideTimer != null) {
    window.clearTimeout(hideTimer)
    hideTimer = null
  }
}

let globalListenerInstalled = false
function installGlobalListener() {
  if (globalListenerInstalled) return
  globalListenerInstalled = true
  const handler = (e: Event) => {
    const target = e.target as HTMLElement | null
    if (!target) return
    if (!target.closest('[data-tooltip-anchor]')) hideTooltip()
  }
  document.addEventListener('touchstart', handler, { passive: true })
  document.addEventListener('click', handler)
  // capture:true para que oiga scroll en CUALQUIER ancestor scrollable
  // (modales con overflow-y-auto, dropdowns, etc.), no solo window.
  window.addEventListener('scroll', hideTooltip, { passive: true, capture: true })
}

// Estructura para asociar handler + último texto a cada elemento sin
// contaminar el tipo público de HTMLElement.
interface TooltipMeta {
  text: string
  handler?: (e: TouchEvent) => void
}
const metaMap = new WeakMap<HTMLElement, TooltipMeta>()

export const vTooltip: Directive<HTMLElement, string> = {
  mounted(el, binding) {
    const text = binding.value || ''
    if (!text) return
    el.setAttribute('title', text)
    el.setAttribute('data-tooltip-anchor', '')
    const meta: TooltipMeta = { text }
    metaMap.set(el, meta)
    if (!supportsTouch) return
    installGlobalListener()
    const handler = () => {
      const m = metaMap.get(el)
      if (m?.text) showTooltip(m.text, el)
    }
    meta.handler = handler
    el.addEventListener('touchstart', handler, { passive: true })
  },
  updated(el, binding) {
    if (binding.value === binding.oldValue) return
    const text = binding.value || ''
    if (text) el.setAttribute('title', text)
    else el.removeAttribute('title')
    // CRITICAL: sin esto el closure del handler de touchstart leía un valor
    // stale del mount inicial — bug HIGH cazado por la review adversaria.
    const m = metaMap.get(el)
    if (m) m.text = text
  },
  unmounted(el) {
    el.removeAttribute('data-tooltip-anchor')
    const m = metaMap.get(el)
    if (m?.handler) el.removeEventListener('touchstart', m.handler)
    metaMap.delete(el)
    // Si el tooltip activo estaba anclado a ESTE elemento (ej. el user
    // dismiss-ea el banner mientras está visible el tooltip), evita el
    // popup huérfano flotando en mitad de la pantalla.
    if (currentAnchor === el) hideTooltip()
  },
}
