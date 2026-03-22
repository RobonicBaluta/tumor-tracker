<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  currentPage: string;
}>();

const emit = defineEmits<{
  navigate: [page: string];
}>();

const navBgColor = computed(() => {
  const colors: Record<string, string> = {
    'oncologico': 'bg-[#143a32]',
    'mental': 'bg-[#2f0535]',
    'tinder': 'bg-[#762d79]'
  };
  return colors[props.currentPage] || 'bg-[#143a32]';
});
</script>

<template>
  <nav :class="[navBgColor, 'backdrop-blur-md border-b border-white/20 sticky top-0 z-50 shadow-lg']">
    <div class="max-w-6xl mx-auto px-6 py-4 flex justify-center gap-6">
      <button @click="emit('navigate', 'oncologico')" :class="[
        'px-6 py-3 rounded-lg font-bold transition duration-300 font-mono text-sm tracking-wide',
        'hover:-translate-y-1 active:translate-y-0',
        currentPage === 'oncologico'
          ? 'bg-[#54af8c] text-white shadow-lg shadow-[#54af8c]/50'
          : 'text-white bg-white/10 hover:bg-white/20 border border-white/20'
      ]">
        Oncológico
      </button>
      <button @click="emit('navigate', 'mental')" :class="[
        'px-6 py-3 rounded-lg font-bold transition duration-300 font-mono text-sm tracking-wide',
        'hover:-translate-y-1 active:translate-y-0',
        currentPage === 'mental'
          ? 'bg-[#f5e4f4] text-[#2f0535] shadow-lg shadow-[#54af8c]/50'
          : 'text-white bg-white/10 hover:bg-white/20 border border-white/20'
      ]">
        Mental
      </button>
      <button @click="emit('navigate', 'tinder')" :class="[
        'px-6 py-3 rounded-lg font-bold transition duration-300 font-mono text-sm tracking-wide',
        'hover:-translate-y-1 active:translate-y-0',
        currentPage === 'tinder'
          ? 'bg-white text-[#aa3059] shadow-lg shadow-[#54af8c]/50'
          : 'text-white bg-white/10 hover:bg-white/20 border border-white/20'
      ]">
        Tinder
      </button>
    </div>
  </nav>
</template>
