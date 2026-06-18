<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

defineProps<{
  isPublicView: boolean
  liveLoading: boolean
  analyticsLoading: boolean
  exportingImage: boolean
  loading: boolean
  shareCopied: boolean
  isSaved: boolean
  unreadNotifCount: number
}>()

const emit = defineEmits<{
  live: []
  stats: []
  card: []
  refresh: []
  share: []
  save: []
  excuse: []
  notif: []
  logout: []
}>()

// Drawer state: el botón "Más" abre un sheet vertical desde abajo con el
// resto de acciones secundarias (Refrescar, Compartir, Guardar, Excusa,
// Notif, Salir). Click fuera o sobre cualquier item lo cierra.
const drawerOpen = ref(false)
const drawerRef = ref<HTMLDivElement | null>(null)

function openDrawer() {
  drawerOpen.value = true
}
function closeDrawer() {
  drawerOpen.value = false
}

// Click outside del drawer lo cierra. Mounted en document para capturar
// taps en el backdrop translúcido y en otras zonas del viewport.
function onDocumentClick(e: MouseEvent) {
  if (!drawerOpen.value) return
  const el = drawerRef.value
  if (!el) return
  if (e.target instanceof Node && !el.contains(e.target)) {
    closeDrawer()
  }
}
function onEscape(e: KeyboardEvent) {
  if (e.key === 'Escape' && drawerOpen.value) closeDrawer()
}
onMounted(() => {
  document.addEventListener('click', onDocumentClick, true)
  document.addEventListener('keydown', onEscape)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick, true)
  document.removeEventListener('keydown', onEscape)
})
</script>

<template>
  <Teleport to="body">
    <!-- Container fijo abajo, solo en mobile (sm:hidden). Padding inferior con
         env(safe-area-inset-bottom) para escapar del home indicator en iOS. -->
    <div
      class="fixed bottom-0 left-0 right-0 z-40 sm:hidden pointer-events-none"
      style="padding-bottom: env(safe-area-inset-bottom);"
      ref="drawerRef"
    >
      <!-- Más drawer: sheet vertical encima de la barra. Z-index relativo al
           container para quedar siempre sobre los 4 slots. -->
      <Transition name="bn-drawer">
        <div v-if="drawerOpen"
          class="pointer-events-auto bg-theme-from/95 backdrop-blur-md border-t border-accent-40 shadow-2xl mb-px">
          <div class="px-3 py-2 grid grid-cols-2 gap-1.5">
            <button @click="emit('refresh'); closeDrawer()" :disabled="loading"
              class="flex items-center gap-2 h-11 px-3 text-xs text-white/80 border border-white/15 rounded-lg disabled:opacity-30 font-mono">
              <span :class="loading ? 'animate-spin inline-block' : ''">↻</span>
              <span>Refrescar</span>
            </button>
            <button @click="emit('share'); closeDrawer()"
              class="flex items-center gap-2 h-11 px-3 text-xs text-white/80 border border-white/15 rounded-lg font-mono">
              <span>{{ shareCopied ? '✓' : '🔗' }}</span>
              <span>{{ shareCopied ? 'Copiado' : 'Compartir' }}</span>
            </button>

            <template v-if="!isPublicView">
              <button @click="emit('save'); closeDrawer()"
                :class="isSaved ? 'bg-accent-15 border-accent-50 text-accent' : 'border-white/15 text-white/80'"
                class="flex items-center gap-2 h-11 px-3 text-xs border rounded-lg font-mono">
                <span>{{ isSaved ? '⭐' : '☆' }}</span>
                <span>{{ isSaved ? 'Guardado' : 'Guardar' }}</span>
              </button>
              <button @click="emit('excuse'); closeDrawer()"
                class="flex items-center gap-2 h-11 px-3 text-xs text-yellow-200 bg-yellow-900/20 border border-yellow-500/40 rounded-lg font-mono">
                <span>🎲</span>
                <span>Excusa</span>
              </button>
              <button @click="emit('notif'); closeDrawer()"
                class="relative flex items-center gap-2 h-11 px-3 text-xs text-white/80 border border-white/15 rounded-lg font-mono">
                <span>🔔</span>
                <span>Notif</span>
                <span v-if="unreadNotifCount > 0"
                  class="absolute -top-1 -right-1 bg-red-500 text-white text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center">{{ unreadNotifCount }}</span>
              </button>
              <button @click="emit('logout'); closeDrawer()"
                class="col-span-2 flex items-center justify-center gap-2 h-11 px-3 text-xs text-red-300 border border-red-500/30 rounded-lg font-mono">
                <span>⎋</span>
                <span>Cerrar sesión</span>
              </button>
            </template>
          </div>
        </div>
      </Transition>

      <!-- 4 slots primarios. Cada uno full-height (~58px) para targets táctiles
           cómodos (~50px efectivos sin contar borders). -->
      <nav
        class="pointer-events-auto bg-theme-from/95 backdrop-blur-md border-t border-accent-30 grid grid-cols-4">
        <button @click="emit('live'); closeDrawer()" :disabled="liveLoading"
          class="flex flex-col items-center justify-center py-2 gap-0.5 text-red-300 hover:bg-red-950/30 active:bg-red-950/50 disabled:opacity-30 transition">
          <span class="relative">
            <span class="inline-block w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
          </span>
          <span class="text-[10px] font-mono uppercase tracking-wide">{{ liveLoading ? '...' : 'Live' }}</span>
        </button>
        <button @click="emit('stats'); closeDrawer()" :disabled="analyticsLoading"
          class="flex flex-col items-center justify-center py-2 gap-0.5 text-purple-300 hover:bg-purple-950/30 active:bg-purple-950/50 disabled:opacity-30 transition">
          <span class="text-lg leading-none">📊</span>
          <span class="text-[10px] font-mono uppercase tracking-wide">Stats</span>
        </button>
        <button @click="emit('card'); closeDrawer()" :disabled="exportingImage"
          class="flex flex-col items-center justify-center py-2 gap-0.5 text-accent hover:bg-accent-15 active:bg-accent-20 disabled:opacity-30 transition">
          <span class="text-lg leading-none">🖼</span>
          <span class="text-[10px] font-mono uppercase tracking-wide">Card</span>
        </button>
        <button @click="drawerOpen ? closeDrawer() : openDrawer()"
          :class="drawerOpen ? 'text-accent bg-white/5' : 'text-white/70'"
          class="relative flex flex-col items-center justify-center py-2 gap-0.5 hover:bg-white/5 active:bg-white/10 transition">
          <span class="text-lg leading-none">{{ drawerOpen ? '✕' : '⋯' }}</span>
          <span class="text-[10px] font-mono uppercase tracking-wide">{{ drawerOpen ? 'Cerrar' : 'Más' }}</span>
          <!-- Badge agregado sobre "Más" si hay notifs pendientes para que el
               user no tenga que abrir el drawer para enterarse. -->
          <span v-if="!isPublicView && unreadNotifCount > 0 && !drawerOpen"
            class="absolute top-1 right-3 bg-red-500 text-white text-[9px] font-bold rounded-full w-4 h-4 flex items-center justify-center">{{ unreadNotifCount }}</span>
        </button>
      </nav>
    </div>
  </Teleport>
</template>

<style scoped>
.bn-drawer-enter-active,
.bn-drawer-leave-active {
  transition: transform 0.18s ease, opacity 0.18s ease;
}
.bn-drawer-enter-from,
.bn-drawer-leave-to {
  transform: translateY(12px);
  opacity: 0;
}
</style>
