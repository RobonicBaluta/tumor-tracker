<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, inject } from 'vue'
import { API_BASE } from '../composables/useApi'

interface Summary {
  ok: boolean
  has_data: boolean
  date?: string
  matches_predicted?: number
  resolved?: number
  correct?: number
  accuracy_pct?: number | null
}

const LS_KEY = 'dailySummary.lastSeen.v1'
const auth = inject<any>('auth')
const data = ref<Summary | null>(null)
const show = ref(false)
// Detect cuándo PwaInstallBanner está activo para apilar arriba en lugar
// de tapar. Mira el DOM directamente porque ambos banners están al mismo
// nivel en App.vue y no comparten composable.
const pwaVisible = ref(false)
function syncPwaVisibility() {
  if (typeof document === 'undefined') return
  pwaVisible.value = !!document.querySelector('[data-pwa-install-banner]')
}

function todayKey(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function tzHeader(): Record<string, string> {
  try { return { 'X-TZ-Offset': String(-new Date().getTimezoneOffset()) } } catch { return {} }
}

async function maybeShow() {
  if (!auth?.token?.value || !auth.user?.value) return
  // 1 vez por día por device. Si ya se mostró hoy, no re-fetch.
  let lastSeen = ''
  try { lastSeen = localStorage.getItem(LS_KEY) || '' } catch {}
  if (lastSeen === todayKey()) return
  try {
    const res = await fetch(`${API_BASE}/daily-summary`, {
      headers: { Authorization: `Bearer ${auth.token.value}`, ...tzHeader() },
    })
    if (!res.ok) return
    const body: Summary = await res.json()
    if (body.has_data) {
      data.value = body
      show.value = true
    }
    // Marca visto AHORA, no en dismiss — sin esto cada reload re-fetcheaba y
    // re-mostraba el banner. Bug MEDIUM cazado por review.
    try { localStorage.setItem(LS_KEY, todayKey()) } catch {}
  } catch {}
}

function dismiss() {
  show.value = false
  try { localStorage.setItem(LS_KEY, todayKey()) } catch {}
}

let bootTimer: ReturnType<typeof setTimeout> | null = null
onMounted(() => {
  // Pequeño delay para no chocar con la animación de login inicial.
  bootTimer = setTimeout(() => { maybeShow(); syncPwaVisibility() }, 1200)
})
onBeforeUnmount(() => { if (bootTimer) clearTimeout(bootTimer) })
</script>

<template>
  <!-- #30 — Banner del resumen de ayer. Se cierra con ✕ o automáticamente
       al cambiar de día. Posicionado encima del bottom-nav. -->
  <Teleport to="body">
    <Transition name="modal">
      <!-- Stack-aware bottom offset: si el PwaInstallBanner está visible
           (atributo `data-pwa-install` en body por el banner) subimos 6rem
           para no chocar. Sin coordinación cross-component, una mini
           convention. -->
      <div v-if="show && data?.has_data"
        class="fixed left-1/2 -translate-x-1/2 z-[100] max-w-md w-[calc(100%-2rem)]
               bg-theme-from/95 backdrop-blur-md border border-accent-40 rounded-xl shadow-2xl
               px-4 py-3 flex items-start gap-3"
        :style="{ bottom: pwaVisible
          ? 'calc(env(safe-area-inset-bottom, 0px) + 12.5rem)'
          : 'calc(env(safe-area-inset-bottom, 0px) + 6.5rem)' }">
        <span class="text-2xl shrink-0 leading-none">📊</span>
        <div class="flex-1 min-w-0">
          <p class="text-white font-mono text-sm font-bold leading-tight mb-0.5">
            Resumen de ayer
          </p>
          <p class="text-white/60 font-mono text-[11px] leading-snug">
            <span class="text-yellow-200 font-bold">{{ data.matches_predicted }}</span>
            {{ (data.matches_predicted ?? 0) === 1 ? 'partida' : 'partidas' }} con predicción
            <template v-if="data.resolved">
              · <span class="text-green-300 font-bold">{{ data.correct }}</span> de
              <span class="text-white/80">{{ data.resolved }}</span> aciertos
              <span v-if="data.accuracy_pct !== null" class="text-cyan-300">
                ({{ data.accuracy_pct }}%)
              </span>
            </template>
          </p>
        </div>
        <button @click="dismiss"
          class="text-white/30 hover:text-white/70 text-base leading-none shrink-0"
          v-tooltip="'Cerrar'">✕</button>
      </div>
    </Transition>
  </Teleport>
</template>
