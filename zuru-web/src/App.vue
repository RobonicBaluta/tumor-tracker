<script setup lang="ts">
import { ref, computed, provide, onMounted, watchEffect, defineAsyncComponent } from 'vue';
import Navbar from './components/Navbar.vue';
import OnboardingTour from './components/OnboardingTour.vue';
import ConfirmDialog from './components/ConfirmDialog.vue';
import GlobalToast from './components/GlobalToast.vue';
import PwaInstallBanner from './components/PwaInstallBanner.vue';
import DailySummaryBanner from './components/DailySummaryBanner.vue';
import { useAuth } from './composables/useAuth';
import { useConfirm } from './composables/useConfirm';

const { state: confirmState, accept: confirmAccept, cancel: confirmCancel } = useConfirm();

// Lazy imports — el bundle inicial solo trae Navbar.
// Cada componente pesado se carga bajo demanda al navegar.
const DiagnosisForm = defineAsyncComponent(() => import('./components/DiagnosisForm.vue'));
const Mental = defineAsyncComponent(() => import('./components/Mental.vue'));
const Tinder = defineAsyncComponent(() => import('./components/Tinder.vue'));
const Overview = defineAsyncComponent(() => import('./components/Overview.vue'));
const Compare = defineAsyncComponent(() => import('./components/Compare.vue'));

const auth = useAuth();
onMounted(() => {
  auth.handleAuthRedirect();
});
provide('auth', auth);

// Páginas top-level con hash routing — #/<page>. 'overview' es el default
// (hash vacío o cualquier ruta de summoner/u). Otras: compare, tinder, mental,
// oncologico.
type PageKey = 'overview' | 'compare' | 'tinder' | 'mental' | 'oncologico'
const PAGE_HASHES: Record<Exclude<PageKey, 'overview'>, string> = {
  compare:    '#/compare',
  tinder:     '#/tinder',
  mental:     '#/mental',
  oncologico: '#/oncologico',
}

function pageFromHash(hash: string): PageKey {
  if (hash.startsWith('#/summoner/') || hash.startsWith('#/u/')) return 'overview'
  if (hash === '#/compare')    return 'compare'
  if (hash === '#/tinder')     return 'tinder'
  if (hash === '#/mental')     return 'mental'
  if (hash === '#/oncologico') return 'oncologico'
  return 'overview'  // Top Tumores como default
}

const currentPage = ref<PageKey>(pageFromHash(window.location.hash || ''))

// Escribe el hash sin push (replaceState) cuando el user navega por el navbar.
// El listener de hashchange abajo sincroniza el state en ambas direcciones.
function navigateTo(page: PageKey) {
  const desired = page === 'overview' ? '' : PAGE_HASHES[page]
  if (page === 'overview') {
    // Para volver a Top Tumores, limpia el hash (no la URL completa).
    if (window.location.hash) {
      history.replaceState(null, '', window.location.pathname + window.location.search)
    }
  } else if (window.location.hash !== desired) {
    history.replaceState(null, '', desired)
  }
  currentPage.value = page
}

window.addEventListener('hashchange', () => {
  // Cuando el hash cambia (back/forward del navegador o programáticamente),
  // sincroniza currentPage. Overview maneja su propio sub-routing (slug + queue).
  currentPage.value = pageFromHash(window.location.hash || '')
})

// THEMES re-revisión 2026-06-18: salimos del role-based (Naval/Jungla/Mid/etc.)
// y vamos a algo "más especial" pedido por el user. Cada theme ahora tiene
// un identidad propia inspirada en lore/eventos de LoL: from/to definen el
// gradiente del fondo, accent es el color de realce que se propaga via
// CSS var --theme-accent (focus rings, hover borders sutiles).
// Default cambia a 'royal' (azul demaciano profundo + dorado) — sigue
// siendo azul para no romper la identidad visual de la app pero ya no es
// la "Naval" plana original.
const THEMES = {
  royal:    { from: '#0a1a3a', to: '#142a52', accent: '#d4af37', label: 'Demacia Royal 🏰' },
  void:     { from: '#1a0d2e', to: '#2d1b4e', accent: '#b08cff', label: 'Void Sovereign 🔮' },
  kda:      { from: '#190a1f', to: '#2a0f3a', accent: '#ff2e88', label: 'K/DA Neon 💫' },
  worlds:   { from: '#2a1f0a', to: '#3d2f14', accent: '#ffd700', label: 'Worlds Gold 🏆' },
  inferno:  { from: '#330000', to: '#5c1a1a', accent: '#ff6b3a', label: 'Inferno Ascent 🔥' },
  pentakill:{ from: '#0a0a0a', to: '#1f1815', accent: '#c9102e', label: 'Pentakill Metal 🎸' },
  guardian: { from: '#1f0f2e', to: '#341a4f', accent: '#ff8fc7', label: 'Star Guardian ✨' },
  shadow:   { from: '#050505', to: '#1a1a2e', accent: '#00ff88', label: 'Shadow Assassin ⚔️' },
}

// localStorage migration: cualquier key que no esté en THEMES (legacy
// 'default'/'jungla'/..., typos, residuos de otros deploys, valores
// inyectados via XSS) se reescribe a 'royal' on-boot para no dejar el
// storage sucio acumulando keys desconocidas en cada sesión.
const storedKey = localStorage.getItem('zuruweb-theme') || ''
const isValidKey = storedKey && Object.prototype.hasOwnProperty.call(THEMES, storedKey)
const initialKey = isValidKey ? storedKey : 'royal'
if (storedKey && !isValidKey) {
  localStorage.setItem('zuruweb-theme', 'royal')
}
const themeKey = ref(initialKey)
const theme = computed(() => THEMES[themeKey.value as keyof typeof THEMES] ?? THEMES.royal)

const setTheme = (key: string) => {
  themeKey.value = key
  localStorage.setItem('zuruweb-theme', key)
}

// Propagar las CSS vars del theme a document.documentElement (:root) para
// que TODOS los elementos las hereden — incluso los Teleported a body
// (modales, dropdowns, BottomNav, ChampionPicker). El style inline en App.vue
// y Overview.vue NO alcanza a los Teleported (DOM parent es body, no App).
// :root sí los cubre por inheritance natural de CSS custom properties.
watchEffect(() => {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  const t = theme.value as any
  root.style.setProperty('--theme-accent', t.accent || '#c89b3c')
  root.style.setProperty('--theme-from', t.from || '#0d1b2a')
  root.style.setProperty('--theme-to', t.to || '#1b2838')
})

provide('theme', theme)
provide('themeKey', themeKey)
provide('setTheme', setTheme)
provide('THEMES', THEMES)
</script>

<template>
  <!-- CSS var --theme-accent expuesta a TODA la app desde el root. Componentes
       que quieran realce temático lo pintan con var(--theme-accent). Si el
       theme no define accent (themes legacy), fallback al gold de marca. -->
  <div class="h-screen flex flex-col"
    :style="{ ['--theme-accent' as any]: theme.accent || '#c89b3c' }">
    <Navbar :current-page="currentPage" @navigate="navigateTo($event as PageKey)" />

    <DiagnosisForm v-if="currentPage === 'oncologico'" />
    <Mental v-else-if="currentPage === 'mental'" />
    <Tinder v-else-if="currentPage === 'tinder'" />
    <Overview v-else-if="currentPage === 'overview'" />
    <Compare v-else-if="currentPage === 'compare'" />

    <OnboardingTour />

    <!-- Toast global de error de auth (rate-limited, discord_too_new, etc.) -->
    <Transition name="modal">
      <div v-if="auth.authError.value"
        class="fixed bottom-6 left-1/2 -translate-x-1/2 z-[110] max-w-sm w-[calc(100%-2rem)]
               bg-red-950/90 backdrop-blur-md border-2 border-red-500/60 rounded-xl shadow-2xl
               px-4 py-3 flex items-start gap-3">
        <span class="text-xl shrink-0">🚫</span>
        <p class="flex-1 text-red-200 text-sm font-mono leading-snug">{{ auth.authError.value }}</p>
        <button @click="auth.authError.value = null"
          class="text-red-300/60 hover:text-red-200 text-lg leading-none">✕</button>
      </div>
    </Transition>

    <!-- Toasts globales: lanzados desde cualquier componente con useToast() -->
    <GlobalToast />

    <!-- PWA install banner (#44). Self-gated: solo aparece tras 3 visitas en
         días distintos y respeta cooldown de dismiss. -->
    <PwaInstallBanner />

    <!-- Daily summary banner (#30). Self-gated: solo 1 vez por día. -->
    <DailySummaryBanner />

    <!-- Confirm dialog global: cualquier componente puede dispararlo con useConfirm() -->
    <ConfirmDialog
      :show="confirmState.show"
      :title="confirmState.title"
      :message="confirmState.message"
      :confirm-text="confirmState.confirmText"
      :cancel-text="confirmState.cancelText"
      :variant="confirmState.variant"
      @confirm="confirmAccept"
      @cancel="confirmCancel" />
  </div>
</template>
