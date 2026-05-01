<script setup lang="ts">
import { ref, computed, provide } from 'vue';
import Navbar from './components/Navbar.vue';
import DiagnosisForm from './components/DiagnosisForm.vue';
import Mental from './components/Mental.vue';
import Tinder from './components/Tinder.vue';
import Overview from './components/Overview.vue';
import Compare from './components/Compare.vue';

const initialPage = (() => {
  const h = window.location.hash || ''
  if (h.startsWith('#/summoner/')) return 'overview'
  return 'overview'  // Top Tumores como default
})()
const currentPage = ref(initialPage);

window.addEventListener('hashchange', () => {
  if (window.location.hash.startsWith('#/summoner/')) {
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
  </div>
</template>
