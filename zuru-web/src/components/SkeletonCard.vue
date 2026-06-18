<script setup lang="ts">
import { computed } from 'vue'

// Skeleton loader con shimmer dorado-sobre-oscuro. La variant determina la
// estructura que imita — la idea es que el user reconozca de qué tipo de
// data viene mientras se carga, no solo "algo se está cargando".

interface Props {
  /** Qué layout imitar:
   *   - 'match-detail': dos equipos de 5 jugadores (modal de detalle de partida)
   *   - 'match-row':    una fila tipo participante (icon + 2 lines + score)
   */
  variant?: 'match-detail' | 'match-row'
  /** Para 'match-row': cuántas instancias renderizar. */
  count?: number
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'match-row',
  count: 1,
})

const rows = computed(() => Array.from({ length: Math.max(1, props.count) }))
</script>

<template>
  <!-- Variante match-detail: 2 paneles azul/rojo, 5 filas cada uno -->
  <div v-if="variant === 'match-detail'" class="grid grid-cols-1 md:grid-cols-2 gap-3">
    <div v-for="side in ['blue', 'red']" :key="side"
      class="bg-black/20 border border-white/10 rounded-xl p-3 space-y-2">
      <div class="flex items-center gap-2 mb-2">
        <div :class="side === 'blue' ? 'bg-blue-500/30' : 'bg-red-500/30'"
          class="w-2 h-2 rounded-full"></div>
        <div :class="side === 'blue' ? 'bg-blue-500/20' : 'bg-red-500/20'"
          class="h-3 w-24 rounded shimmer"></div>
      </div>
      <div v-for="n in 5" :key="n"
        class="flex items-center gap-2.5 bg-white/3 rounded-lg p-2">
        <div class="w-9 h-9 rounded-lg bg-white/10 shimmer"></div>
        <div class="flex-1 space-y-1.5">
          <div class="h-2.5 bg-white/10 rounded shimmer"
            :style="{ width: `${55 + (n * 7) % 35}%` }"></div>
          <div class="h-2 bg-white/5 rounded shimmer"
            :style="{ width: `${30 + (n * 11) % 30}%` }"></div>
        </div>
        <div class="w-12 h-6 bg-white/10 rounded shimmer"></div>
      </div>
    </div>
  </div>

  <!-- Variante match-row: filas estilo participante -->
  <div v-else class="space-y-2">
    <div v-for="(_, i) in rows" :key="i"
      class="flex items-center gap-3 bg-white/5 rounded-lg p-3">
      <div class="w-9 h-9 rounded-lg bg-white/10 shimmer"></div>
      <div class="flex-1 space-y-1.5">
        <div class="h-2.5 bg-white/10 rounded shimmer"
          :style="{ width: `${55 + (i * 7) % 35}%` }"></div>
        <div class="h-2 bg-white/5 rounded shimmer"
          :style="{ width: `${30 + (i * 11) % 30}%` }"></div>
      </div>
      <div class="w-10 h-6 bg-white/10 rounded shimmer"></div>
    </div>
  </div>
</template>

<style scoped>
/* Mismo shimmer que el resto del codebase ya define en Overview.vue/global,
   pero scoped aquí para que SkeletonCard.vue sea autocontenido y
   re-utilizable sin depender de styles externos. */
@keyframes shimmer-bg {
  0%   { background-position: -200% 0; }
  100% { background-position:  200% 0; }
}
.shimmer {
  background-image: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.04) 0%,
    rgba(255, 255, 255, 0.12) 50%,
    rgba(255, 255, 255, 0.04) 100%
  );
  background-size: 200% 100%;
  animation: shimmer-bg 1.6s ease-in-out infinite;
}
</style>
