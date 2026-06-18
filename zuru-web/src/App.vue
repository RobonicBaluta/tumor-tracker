<script setup lang="ts">
import { ref, computed, provide, onMounted, defineAsyncComponent } from 'vue';
import Navbar from './components/Navbar.vue';
import OnboardingTour from './components/OnboardingTour.vue';
import ConfirmDialog from './components/ConfirmDialog.vue';
import GlobalToast from './components/GlobalToast.vue';
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

const THEMES = {
  default: { from: '#0d1b2a', to: '#1b2838', label: 'Naval 🌊' },
  jungla:  { from: '#0a1f0a', to: '#162a16', label: 'Jungla 🌿' },
  support: { from: '#081c28', to: '#0c2535', label: 'Support 💎' },
  mid:     { from: '#1a1400', to: '#2a2000', label: 'Mid ⚡' },
  adc:     { from: '#200808', to: '#2e1010', label: 'ADC 🎯' },
  top:     { from: '#100a20', to: '#1a1032', label: 'Top 🗡️' },
}

const themeKey = ref(localStorage.getItem('zuruweb-theme') || 'default')
const theme = computed(() => THEMES[themeKey.value as keyof typeof THEMES] ?? THEMES.default)

const setTheme = (key: string) => {
  themeKey.value = key
  localStorage.setItem('zuruweb-theme', key)
}

provide('theme', theme)
provide('themeKey', themeKey)
provide('setTheme', setTheme)
provide('THEMES', THEMES)
</script>

<template>
  <div class="h-screen flex flex-col">
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
