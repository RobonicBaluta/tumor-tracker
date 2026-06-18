<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { championIconUrl, championIconFallback } from '../composables/overviewConstants'

// Custom dropdown que reemplaza al <select> nativo cuando queremos mostrar
// el icono del champion junto al nombre (native <option> no acepta <img>).
//
// IMPORTANTE: el popover se Teleporta a body y se posiciona absoluto sobre
// las coords del trigger button. Sin esto, el clipping por overflow-hidden
// de cualquier ancestor (cards con rounded-xl + overflow-hidden, modales,
// tabs con scroll) hacía que el dropdown quedase cortado o detrás. Con
// Teleport sale del DOM del parent y queda libre encima de TODO con su z.

const props = defineProps<{
  modelValue: string
  items: string[]                    // nombres de champion (orden ya sorted)
  ddragonVersion: string
  placeholder?: string               // texto cuando modelValue === ''
  allLabel?: string                  // label opcional para la opción "todos" (value '')
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const open = ref(false)
const triggerRef = ref<HTMLButtonElement | null>(null)
const popoverRef = ref<HTMLDivElement | null>(null)
const searchInputRef = ref<HTMLInputElement | null>(null)
const searchQuery = ref('')

// Coords + tamaño del popover (calculadas a partir del bounding del trigger).
const popoverStyle = ref<Record<string, string>>({})

const placeholderLabel = computed(() => props.placeholder || 'Selecciona…')

const filteredItems = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return props.items
  return props.items.filter(name => name.toLowerCase().includes(q))
})

function updatePosition() {
  const trig = triggerRef.value
  if (!trig) return
  const rect = trig.getBoundingClientRect()
  // Por defecto colgamos abajo; si no cabe (cerca del bottom del viewport),
  // pintamos arriba. Width mínimo = ancho del trigger, mínimo 220, clamped a
  // viewport para evitar que asome por el right edge en pantallas pequeñas.
  const vh = window.innerHeight
  const desiredW = Math.max(rect.width, 220)
  // Math.max(0, ...) evita left negativo en pantallas más estrechas que el
  // popover (320px en portrait extremo).
  const left = Math.max(0, Math.min(rect.left, window.innerWidth - desiredW - 8))
  const spaceBelow = vh - rect.bottom
  const popoverH = 320 // upper bound estimado (search input + max-h-72 + padding)
  const placeAbove = spaceBelow < popoverH && rect.top > popoverH
  popoverStyle.value = placeAbove
    ? {
        position: 'fixed',
        left: `${left}px`,
        bottom: `${vh - rect.top + 4}px`,
        width: `${desiredW}px`,
      }
    : {
        position: 'fixed',
        left: `${left}px`,
        top: `${rect.bottom + 4}px`,
        width: `${desiredW}px`,
      }
}

function select(value: string) {
  emit('update:modelValue', value)
  open.value = false
  searchQuery.value = ''
}

function toggle() {
  if (open.value) {
    open.value = false
    searchQuery.value = ''
    return
  }
  // Computamos position ANTES de poner open=true: el popover renderiza ya
  // con coords correctas en el primer paint. Antes el primer frame mostraba
  // el sheet en (0,0) durante un tick y saltaba a su sitio.
  updatePosition()
  open.value = true
  nextTick(() => requestAnimationFrame(() => searchInputRef.value?.focus()))
}

// Click outside cierra: como el popover vive en body via Teleport, tenemos
// que verificar el target contra trigger Y popover.
function onDocClick(e: MouseEvent) {
  if (!open.value) return
  const trig = triggerRef.value
  const pop = popoverRef.value
  if (!trig) return
  const target = e.target instanceof Node ? e.target : null
  if (!target) return
  if (trig.contains(target)) return
  if (pop && pop.contains(target)) return
  open.value = false
  searchQuery.value = ''
}
function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape' && open.value) {
    open.value = false
    searchQuery.value = ''
  }
}
// Re-posicionar en scroll/resize porque usamos position:fixed con coords
// absolutas — si el page hace scroll mientras el popover está abierto, queda
// "pegado" en pantalla pero desconectado del trigger.
function onScrollOrResize() {
  if (open.value) updatePosition()
}

onMounted(() => {
  document.addEventListener('click', onDocClick, true)
  document.addEventListener('keydown', onEsc)
  window.addEventListener('scroll', onScrollOrResize, true)
  window.addEventListener('resize', onScrollOrResize)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick, true)
  document.removeEventListener('keydown', onEsc)
  window.removeEventListener('scroll', onScrollOrResize, true)
  window.removeEventListener('resize', onScrollOrResize)
})

// Si modelValue cambia externamente (eg user borra el filtro vía otro botón),
// limpiamos search.
watch(() => props.modelValue, () => { searchQuery.value = '' })
</script>

<template>
  <div class="relative inline-block">
    <!-- Trigger -->
    <button ref="triggerRef" @click="toggle" type="button"
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

    <!-- Popover Teleported a body para que NUNCA quede clippeado por
         overflow-hidden de ningún ancestor. z-[70] queda por encima de
         modales (z-60) cuando se usa dentro de un modal. -->
    <Teleport to="body">
      <Transition name="cp-fade">
        <div v-if="open" ref="popoverRef"
          class="z-[70] bg-[#0d1b2a] border border-accent-40 rounded-lg shadow-2xl backdrop-blur overflow-hidden"
          :style="popoverStyle">
          <!-- Search -->
          <div class="p-2 border-b border-white/10">
            <input ref="searchInputRef" v-model="searchQuery" type="text" placeholder="Buscar champion…"
              class="w-full bg-black/40 border border-white/15 rounded px-2 py-1 text-white text-xs font-mono focus:outline-none focus:border-accent-60" />
          </div>
          <!-- All option -->
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
    </Teleport>
  </div>
</template>

<style scoped>
.cp-fade-enter-active, .cp-fade-leave-active { transition: opacity 0.15s, transform 0.15s; }
.cp-fade-enter-from, .cp-fade-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
