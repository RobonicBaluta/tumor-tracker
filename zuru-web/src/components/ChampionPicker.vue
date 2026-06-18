<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { championIconUrl, championIconFallback } from '../composables/overviewConstants'

// Custom dropdown que reemplaza al <select> nativo cuando queremos mostrar
// el icono del champion junto al nombre (native <option> no acepta <img>).
// Mantiene la API de v-model como un select normal.

const props = defineProps<{
  modelValue: string
  items: string[]                    // nombres de champion (orden ya sorted)
  ddragonVersion: string
  placeholder?: string               // texto cuando modelValue === ''
  allLabel?: string                  // label para la opción "todos" (value '')
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const open = ref(false)
const wrapperRef = ref<HTMLDivElement | null>(null)
const searchInputRef = ref<HTMLInputElement | null>(null)
const searchQuery = ref('')

const placeholderLabel = computed(() => props.placeholder || 'Selecciona…')

const filteredItems = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return props.items
  return props.items.filter(name => name.toLowerCase().includes(q))
})

function select(value: string) {
  emit('update:modelValue', value)
  open.value = false
  searchQuery.value = ''
}

function toggle() {
  open.value = !open.value
  if (open.value) {
    // Focus el search input al abrir — el user puede empezar a teclear el champ
    requestAnimationFrame(() => searchInputRef.value?.focus())
  } else {
    searchQuery.value = ''
  }
}

// Click outside + Escape cierran el dropdown. Usamos capture phase para
// distinguir del click en el trigger (evita el toggle+close inmediato).
function onDocClick(e: MouseEvent) {
  if (!open.value) return
  const el = wrapperRef.value
  if (!el) return
  if (e.target instanceof Node && !el.contains(e.target)) {
    open.value = false
    searchQuery.value = ''
  }
}
function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape' && open.value) {
    open.value = false
    searchQuery.value = ''
  }
}
onMounted(() => {
  document.addEventListener('click', onDocClick, true)
  document.addEventListener('keydown', onEsc)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick, true)
  document.removeEventListener('keydown', onEsc)
})
</script>

<template>
  <div ref="wrapperRef" class="relative inline-block">
    <!-- Trigger: caja estilo select con icono + nombre (o placeholder) -->
    <button @click="toggle" type="button"
      class="flex items-center gap-2 bg-white/5 border border-white/15 hover:border-accent-50 rounded-lg px-3 py-1.5 text-white/80 text-xs font-mono transition min-w-[160px]"
      :aria-expanded="open">
      <img v-if="modelValue"
        :src="championIconUrl(modelValue, ddragonVersion)" @error="championIconFallback"
        class="w-5 h-5 rounded shrink-0" />
      <span v-else class="w-5 h-5 rounded bg-white/10 shrink-0 flex items-center justify-center text-[10px]">★</span>
      <span class="flex-1 text-left truncate">
        {{ modelValue || placeholderLabel }}
      </span>
      <span class="text-white/40 text-[10px]">{{ open ? '▲' : '▼' }}</span>
    </button>

    <!-- Popover: search input + lista de items. Z-50 para sobrepasar contenido
         pero por debajo de modales (z-60+). -->
    <Transition name="cp-fade">
      <div v-if="open"
        class="absolute z-50 mt-1 left-0 min-w-full w-72 max-w-[90vw] bg-[#0d1b2a] border border-accent-30 rounded-lg shadow-2xl backdrop-blur overflow-hidden">
        <!-- Search -->
        <div class="p-2 border-b border-white/10">
          <input ref="searchInputRef" v-model="searchQuery" type="text" placeholder="Buscar champion…"
            class="w-full bg-black/40 border border-white/15 rounded px-2 py-1 text-white text-xs font-mono focus:outline-none focus:border-accent-60" />
        </div>
        <!-- All option (empty string) — solo si el caller pasó allLabel explícito.
             Sin esta opción el picker no permite seleccionar "ninguno" → forzaría
             elegir siempre un champion específico. -->
        <button v-if="allLabel" @click="select('')"
          :class="modelValue === '' ? 'bg-accent-15 text-accent' : 'text-white/70 hover:bg-white/5 hover:text-white'"
          class="w-full text-left px-3 py-2 text-xs font-mono flex items-center gap-2 border-b border-white/5 transition">
          <span class="w-5 h-5 rounded bg-white/10 flex items-center justify-center text-[10px] shrink-0">★</span>
          <span class="flex-1 truncate">{{ allLabel }}</span>
          <span v-if="modelValue === ''" class="text-[10px]">✓</span>
        </button>
        <!-- Items list -->
        <div class="max-h-72 overflow-y-auto">
          <button v-for="name in filteredItems" :key="name" @click="select(name)"
            :class="modelValue === name ? 'bg-accent-15 text-accent' : 'text-white/70 hover:bg-white/5 hover:text-white'"
            class="w-full text-left px-3 py-1.5 text-xs font-mono flex items-center gap-2 transition">
            <img :src="championIconUrl(name, ddragonVersion)" @error="championIconFallback"
              class="w-5 h-5 rounded shrink-0" />
            <span class="flex-1 truncate">{{ name }}</span>
            <span v-if="modelValue === name" class="text-[10px]">✓</span>
          </button>
          <p v-if="!filteredItems.length" class="text-white/30 text-xs font-mono text-center py-4 italic">
            Sin resultados
          </p>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.cp-fade-enter-active, .cp-fade-leave-active { transition: opacity 0.15s, transform 0.15s; }
.cp-fade-enter-from, .cp-fade-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
