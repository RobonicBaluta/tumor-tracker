<script setup lang="ts">
import { usePwaInstall } from '../composables/usePwaInstall'

const { canPrompt, isIos, triggerPrompt, dismiss } = usePwaInstall()
</script>

<template>
  <!-- #44: Custom install banner. Solo aparece tras 3+ visitas en días
       distintos (no spam en first visit), respeta cooldown de 14 días tras
       dismiss y desaparece para siempre si el user instala. -->
  <Transition name="modal">
    <div v-if="canPrompt"
      class="fixed left-1/2 -translate-x-1/2 z-[105] max-w-sm w-[calc(100%-2rem)]
             bg-theme-from/95 backdrop-blur-md border border-accent-40 rounded-xl shadow-2xl
             px-4 py-3 flex items-start gap-3"
      style="bottom: calc(env(safe-area-inset-bottom, 0px) + 6.5rem);">
      <span class="text-2xl shrink-0 leading-none">📲</span>
      <div class="flex-1 min-w-0">
        <p class="text-white font-mono text-sm font-bold leading-tight">
          Instala Tumor Tracker
        </p>
        <p v-if="isIos" class="text-white/60 font-mono text-[11px] leading-snug mt-1">
          Toca <span class="text-accent font-bold">Compartir</span> y luego
          <span class="text-accent font-bold">Añadir a pantalla de inicio</span>.
        </p>
        <p v-else class="text-white/60 font-mono text-[11px] leading-snug mt-1">
          Ábrela desde tu pantalla de inicio. Sin notificaciones, sin tracking.
        </p>
        <div class="flex gap-2 mt-2">
          <button v-if="!isIos" @click="triggerPrompt"
            class="text-[11px] font-mono font-bold px-3 py-1 rounded border border-accent-60 text-accent hover:bg-accent/10 transition">
            Instalar
          </button>
          <button @click="dismiss"
            class="text-[11px] font-mono px-3 py-1 rounded border border-white/15 text-white/50 hover:text-white/80 transition">
            Ahora no
          </button>
        </div>
      </div>
      <button @click="dismiss"
        class="text-white/30 hover:text-white/70 text-base leading-none shrink-0"
        v-tooltip="'Cerrar y no preguntar en 14 días'">✕</button>
    </div>
  </Transition>
</template>
