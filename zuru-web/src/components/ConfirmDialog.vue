<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show"
        class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        @click.self="onCancel">
        <div class="bg-[#0d1b2a]/95 border-2 rounded-xl p-5 max-w-sm w-full shadow-2xl"
          :style="{ borderColor: accentColor + 'aa', boxShadow: `0 0 30px -8px ${accentColor}` }"
          @click.stop>
          <p v-if="title"
            class="font-mono font-bold text-base mb-1.5"
            :style="{ color: accentColor }">
            {{ title }}
          </p>
          <p class="text-white/80 text-sm font-mono leading-relaxed mb-4 whitespace-pre-line">
            {{ message }}
          </p>
          <div class="flex gap-2 justify-end">
            <button @click="onCancel"
              class="text-xs font-mono px-3 py-2 border border-white/20 text-white/70 hover:text-white hover:bg-white/10 rounded transition">
              {{ cancelText || $t('common.cancel') }}
            </button>
            <button @click="onConfirm"
              class="text-xs font-mono font-bold px-4 py-2 rounded transition"
              :style="{
                background: accentColor,
                color: variant === 'danger' ? '#fff' : '#0d1b2a',
              }">
              {{ confirmText || $t('common.confirm') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'

// Defaults vacíos: el template los suple con $t('common.confirm'/'cancel')
// para que respeten el idioma activo al render-time.
const props = withDefaults(defineProps<{
  show: boolean
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  variant?: 'default' | 'danger' | 'warning'
}>(), {
  variant: 'default',
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const accentColor = computed(() => {
  if (props.variant === 'danger') return '#ef4444'   // red-500
  if (props.variant === 'warning') return '#facc15'  // yellow-400
  return '#22d3ee'                                    // cyan-400
})

function onConfirm() { emit('confirm') }
function onCancel() { emit('cancel') }
</script>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.15s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
