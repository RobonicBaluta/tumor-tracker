import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Custom PWA install prompt (#44).
 *
 * Por defecto, los browsers chromium-based reservan la decisión de cuándo
 * disparar el prompt automático: a veces nunca lo muestran, otras esperan
 * a engagement signals. Nosotros queremos mostrarlo deliberadamente tras
 * que el user demuestre interés real (3 visitas en días distintos), no en
 * la primera carga (donde es spam y suele rechazarse).
 *
 * Flujo:
 *   1. Captura `beforeinstallprompt` (Chrome/Edge/Samsung) y lo guarda.
 *   2. Cuenta visitas en localStorage, una por día.
 *   3. Si >= UMBRAL y no instalado, expone `canPrompt = true` para que la
 *      UI muestre un banner custom. Click → llama `triggerPrompt()`.
 *   4. Si el user dismissea, guardamos timestamp en LS y no volvemos a
 *      preguntar en 14 días. Si acepta, ocultamos para siempre.
 *
 * iOS Safari no soporta beforeinstallprompt — para esos UAs detectamos
 * iOS y mostramos un banner con instrucciones manuales ("Share → Añadir a
 * pantalla de inicio") en lugar del prompt nativo.
 */

const LS_VISIT_DAYS = 'pwa.visitDays.v1'   // array de YYYY-MM-DD
const LS_DISMISSED_AT = 'pwa.dismissedAt.v1' // ms timestamp
const LS_INSTALLED = 'pwa.installed.v1'    // '1' una vez instalado
const VISIT_THRESHOLD = 3
const DISMISS_COOLDOWN_MS = 14 * 24 * 3600 * 1000

// Fallback in-memory para private-mode browsers donde localStorage tira
// SecurityError. Sin esto, el banner NUNCA se mostraría en Safari private
// (que es precisamente el caso de uso del branch iOS-instructions).
let memVisitDays: string[] | null = null
let memDismissedAt: number | null = null

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

let deferredEvt: BeforeInstallPromptEvent | null = null

// CRITICAL: capturar beforeinstallprompt a NIVEL MÓDULO, no en onMounted.
// Chrome dispara el evento en cuanto el engagement criteria se cumple, lo
// que para un user returning ocurre durante parse/early-load — antes de
// que el composable se monte. Si esperáramos a onMounted perderíamos el
// evento (no se repite) y el banner no podría disparar el prompt nativo.
// Bug HIGH cazado por review adversaria.
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e: Event) => {
    e.preventDefault()
    deferredEvt = e as BeforeInstallPromptEvent
  })
}

function todayKey(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

function readVisitDays(): string[] {
  try {
    const raw = localStorage.getItem(LS_VISIT_DAYS)
    if (raw) return JSON.parse(raw) as string[]
  } catch {}
  return memVisitDays ? [...memVisitDays] : []
}

function writeVisitDays(arr: string[]) {
  try {
    localStorage.setItem(LS_VISIT_DAYS, JSON.stringify(arr))
  } catch {
    memVisitDays = arr
  }
}

function recordVisit() {
  const arr = readVisitDays()
  const today = todayKey()
  if (!arr.includes(today)) {
    arr.push(today)
    // Cap a últimos 30 días para no crecer indefinidamente.
    writeVisitDays(arr.slice(-30))
  }
}

function visitCount(): number {
  return readVisitDays().length
}

function isDismissedInCooldown(): boolean {
  let ts: number | null = null
  try {
    const raw = localStorage.getItem(LS_DISMISSED_AT)
    if (raw) ts = parseInt(raw, 10)
  } catch {
    ts = memDismissedAt
  }
  if (ts == null || !isFinite(ts)) return false
  return Date.now() - ts < DISMISS_COOLDOWN_MS
}

function isInstalledOrStandalone(): boolean {
  try {
    if (localStorage.getItem(LS_INSTALLED) === '1') return true
  } catch {}
  // matchMedia detecta si la app corre como PWA instalada (display-mode).
  if (typeof window !== 'undefined' && window.matchMedia('(display-mode: standalone)').matches) {
    return true
  }
  // iOS-only flag.
  if (typeof navigator !== 'undefined' && (navigator as any).standalone === true) return true
  return false
}

function isIOSSafari(): boolean {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent
  const isIOS = /iPad|iPhone|iPod/.test(ua) && !(window as any).MSStream
  // Chrome on iOS reporta también iPhone pero usa CriOS en UA.
  const isSafari = isIOS && !/CriOS|FxiOS|EdgiOS/.test(ua)
  return isSafari
}

export function usePwaInstall() {
  const canPrompt = ref(false)
  const isIos = ref(false)

  const evaluate = () => {
    if (isInstalledOrStandalone()) {
      canPrompt.value = false
      return
    }
    if (isDismissedInCooldown()) {
      canPrompt.value = false
      return
    }
    if (visitCount() < VISIT_THRESHOLD) {
      canPrompt.value = false
      return
    }
    // Caso A: Chrome-like — tenemos deferredEvt.
    if (deferredEvt) {
      canPrompt.value = true
      return
    }
    // Caso B: iOS Safari — no hay evento, pero podemos enseñar instrucciones.
    if (isIOSSafari()) {
      canPrompt.value = true
      isIos.value = true
      return
    }
    canPrompt.value = false
  }

  const onBeforeInstall = (e: Event) => {
    // Coexistencia con el listener módulo-load: ambos preventDefault y
    // setean deferredEvt; el evento solo dispara una vez así que el segundo
    // setter no hace daño (mismo evento, mismo objeto).
    e.preventDefault()
    deferredEvt = e as BeforeInstallPromptEvent
    evaluate()
  }

  const onInstalled = () => {
    try {
      localStorage.setItem(LS_INSTALLED, '1')
    } catch {}
    canPrompt.value = false
    deferredEvt = null
  }

  const dismiss = () => {
    const now = Date.now()
    try {
      localStorage.setItem(LS_DISMISSED_AT, String(now))
    } catch {
      memDismissedAt = now
    }
    canPrompt.value = false
  }

  const triggerPrompt = async (): Promise<'accepted' | 'dismissed' | 'unavailable'> => {
    if (!deferredEvt) return 'unavailable'
    try {
      await deferredEvt.prompt()
      const choice = await deferredEvt.userChoice
      deferredEvt = null
      canPrompt.value = false
      if (choice.outcome === 'accepted') {
        try {
          localStorage.setItem(LS_INSTALLED, '1')
        } catch {}
      } else {
        dismiss()
      }
      return choice.outcome
    } catch {
      return 'dismissed'
    }
  }

  onMounted(() => {
    if (!isInstalledOrStandalone()) recordVisit()
    evaluate()
    window.addEventListener('beforeinstallprompt', onBeforeInstall)
    window.addEventListener('appinstalled', onInstalled)
  })

  onUnmounted(() => {
    window.removeEventListener('beforeinstallprompt', onBeforeInstall)
    window.removeEventListener('appinstalled', onInstalled)
  })

  return { canPrompt, isIos, triggerPrompt, dismiss }
}
