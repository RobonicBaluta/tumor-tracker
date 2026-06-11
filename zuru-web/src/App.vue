<script setup lang="ts">
import { ref, computed, provide, onMounted, defineAsyncComponent } from 'vue';
import Navbar from './components/Navbar.vue';
import OnboardingTour from './components/OnboardingTour.vue';
import ConfirmDialog from './components/ConfirmDialog.vue';
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

const initialPage = (() => {
  const h = window.location.hash || ''
  if (h.startsWith('#/summoner/') || h.startsWith('#/u/')) return 'overview'
  return 'overview'  // Top Tumores como default
})()
const currentPage = ref(initialPage);

window.addEventListener('hashchange', () => {
  const h = window.location.hash
  if (h.startsWith('#/summoner/') || h.startsWith('#/u/')) {
    currentPage.value = 'overview'
  }
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
    <Navbar :current-page="currentPage" @navigate="currentPage = $event" />

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
