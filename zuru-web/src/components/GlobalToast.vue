<template>
  <Teleport to="body">
    <div class="fixed bottom-6 right-6 z-[120] flex flex-col gap-2 max-w-sm w-[calc(100%-2rem)] sm:w-auto pointer-events-none">
      <TransitionGroup name="toast">
        <div v-for="entry in state.entries" :key="entry.id"
          :style="{ borderColor: accentColor(entry.kind) + '88', background: bgColor(entry.kind) }"
          class="pointer-events-auto backdrop-blur-md border-2 rounded-xl shadow-2xl
                 px-4 py-3 flex items-start gap-3 min-w-[280px]">
          <span class="text-xl shrink-0 leading-none">{{ icon(entry.kind) }}</span>
          <p class="flex-1 text-sm font-mono leading-snug whitespace-pre-line"
            :style="{ color: textColor(entry.kind) }">
            {{ entry.message }}
          </p>
          <button @click="dismiss(entry.id)"
            class="text-lg leading-none shrink-0 opacity-60 hover:opacity-100 transition"
            :style="{ color: textColor(entry.kind) }">✕</button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useToast } from '../composables/useToast'

const { state, dismiss } = useToast()

function icon(kind: string): string {
  if (kind === 'error')   return '🚫'
  if (kind === 'success') return '✓'
  if (kind === 'warning') return '⚠'
  return 'ℹ'
}

function accentColor(kind: string): string {
  if (kind === 'error')   return '#ef4444'  // red-500
  if (kind === 'success') return '#22c55e'  // green-500
  if (kind === 'warning') return '#facc15'  // yellow-400
  return '#22d3ee'                           // cyan-400
}

function bgColor(kind: string): string {
  if (kind === 'error')   return 'rgba(69, 10, 10, 0.92)'    // red-950/92
  if (kind === 'success') return 'rgba(5, 46, 22, 0.92)'      // green-950/92
  if (kind === 'warning') return 'rgba(66, 32, 6, 0.92)'      // yellow-950/92
  return 'rgba(8, 47, 73, 0.92)'                              // cyan-950/92
}

function textColor(kind: string): string {
  if (kind === 'error')   return '#fecaca'  // red-200
  if (kind === 'success') return '#bbf7d0'  // green-200
  if (kind === 'warning') return '#fef3c7'  // amber-100
  return '#a5f3fc'                           // cyan-200
}
</script>

<style scoped>
.toast-enter-active, .toast-leave-active {
  transition: opacity 0.2s, transform 0.25s;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(40px);
}
.toast-move {
  transition: transform 0.25s;
}
</style>
