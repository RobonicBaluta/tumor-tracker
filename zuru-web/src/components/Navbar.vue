<script setup lang="ts">
import { computed, inject, ref } from 'vue';

const props = defineProps<{
  currentPage: string;
}>();

const emit = defineEmits<{
  navigate: [page: string];
}>();

const themeKey = inject<ReturnType<typeof ref>>('themeKey')!
const setTheme = inject<(k: string) => void>('setTheme')!
const THEMES = inject<Record<string, { from: string; to: string; label: string }>>('THEMES')!

const showThemes = ref(false)

const navBgColor = computed(() => {
  const colors: Record<string, string> = {
    'oncologico': 'bg-[#143a32]',
    'mental': 'bg-[#2f0535]',
    'tinder': 'bg-[#762d79]',
    'overview': 'bg-[#0d1b2a]',
    'compare': 'bg-[#1a0d2e]',
  };
  return colors[props.currentPage] || 'bg-[#143a32]';
});
</script>

<template>
  <nav :class="[navBgColor, 'backdrop-blur-md border-b border-white/20 sticky top-0 z-50 shadow-lg']">
    <div class="max-w-6xl mx-auto px-6 py-3 flex justify-center items-center gap-6">
      <button @click="emit('navigate', 'oncologico')" :class="[
        'px-6 py-2.5 rounded-lg font-bold transition duration-300 font-mono text-sm tracking-wide',
        'hover:-translate-y-1 active:translate-y-0',
        currentPage === 'oncologico'
          ? 'bg-[#54af8c] text-white shadow-lg shadow-[#54af8c]/50'
          : 'text-white bg-white/10 hover:bg-white/20 border border-white/20'
      ]">
        Oncológico
      </button>
      <button @click="emit('navigate', 'mental')" :class="[
        'px-6 py-2.5 rounded-lg font-bold transition duration-300 font-mono text-sm tracking-wide',
        'hover:-translate-y-1 active:translate-y-0',
        currentPage === 'mental'
          ? 'bg-[#f5e4f4] text-[#2f0535] shadow-lg shadow-[#54af8c]/50'
          : 'text-white bg-white/10 hover:bg-white/20 border border-white/20'
      ]">
        Mental
      </button>
      <button @click="emit('navigate', 'tinder')" :class="[
        'px-6 py-2.5 rounded-lg font-bold transition duration-300 font-mono text-sm tracking-wide',
        'hover:-translate-y-1 active:translate-y-0',
        currentPage === 'tinder'
          ? 'bg-white text-[#aa3059] shadow-lg shadow-[#54af8c]/50'
          : 'text-white bg-white/10 hover:bg-white/20 border border-white/20'
      ]">
        Tinder
      </button>
      <button @click="emit('navigate', 'overview')" :class="[
        'px-6 py-2.5 rounded-lg font-bold transition duration-300 font-mono text-sm tracking-wide',
        'hover:-translate-y-1 active:translate-y-0',
        currentPage === 'overview'
          ? 'bg-[#c89b3c] text-black shadow-lg shadow-[#c89b3c]/50'
          : 'text-white bg-white/10 hover:bg-white/20 border border-white/20'
      ]">
        Top Tumores
      </button>
      <button @click="emit('navigate', 'compare')" :class="[
        'px-6 py-2.5 rounded-lg font-bold transition duration-300 font-mono text-sm tracking-wide',
        'hover:-translate-y-1 active:translate-y-0',
        currentPage === 'compare'
          ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/50'
          : 'text-white bg-white/10 hover:bg-white/20 border border-white/20'
      ]">
        Versus ⚔️
      </button>

      <!-- Theme picker -->
      <div class="relative ml-2">
        <button @click="showThemes = !showThemes"
          class="w-8 h-8 rounded-full border border-white/20 bg-white/10 hover:bg-white/20 transition flex items-center justify-center text-sm"
          title="Cambiar tema">
          🎨
        </button>
        <Transition name="dropdown">
          <div v-if="showThemes" class="absolute right-0 top-10 bg-[#0d1b2a] border border-white/20 rounded-xl shadow-2xl p-2 min-w-[140px] z-50">
            <p class="text-white/30 text-[9px] font-mono tracking-widest px-2 pb-2">TEMA</p>
            <button v-for="(t, key) in THEMES" :key="key"
              @click="setTheme(key); showThemes = false"
              :class="themeKey === key ? 'bg-white/15 text-white' : 'text-white/60 hover:bg-white/10 hover:text-white'"
              class="w-full text-left px-3 py-1.5 rounded-lg text-xs font-mono transition flex items-center justify-between">
              {{ t.label }}
              <span v-if="themeKey === key" class="text-[10px]">✓</span>
            </button>
          </div>
        </Transition>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.dropdown-enter-active, .dropdown-leave-active { transition: opacity 0.15s, transform 0.15s; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
