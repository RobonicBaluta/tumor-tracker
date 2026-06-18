<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue'
import {
  championIconUrl,
  championSplashUrl,
  championIconFallback,
  tumorColor,
  tumorLabel,
} from '../composables/overviewConstants'

// Modal de stats por champion: input es el nombre del champion + 2 arrays
// (champion_pool del backend con games/wins/winrate/avg_tumor agregados, y
// matches del viewer para filtrar las últimas N partidas con ese champ).
// Todo client-side desde data ya cargada — sin nuevo endpoint backend en v1.

interface ChampionPoolEntry {
  champion: string
  games: number
  wins: number
  winrate: number
  avg_tumor: number
}

interface MatchLite {
  match_id: string
  my_champion: string
  my_kills: number
  my_deaths: number
  my_assists: number
  my_kda: number
  win: boolean
  worst_is_me?: boolean
  game_duration?: number
  queue_name?: string
}

const props = defineProps<{
  show: boolean
  championName: string | null
  ddragonVersion: string
  championPool: ChampionPoolEntry[]
  matches: MatchLite[]
}>()

const emit = defineEmits<{ close: [] }>()

// Stats agregados del champion_pool (top 10 by volume del analytics endpoint).
// Si el champion no está en el pool — porque el user lo jugó pocas veces y
// no entró en el top 10 — caemos a un derive on-the-fly desde matches.
const poolEntry = computed(() => {
  if (!props.championName) return null
  return props.championPool.find(c => c.champion === props.championName) || null
})

// Matches del viewer con este champion, más reciente primero.
// Ordenamos por game_date DESC explícito: el viewer puede haber paginado con
// "Load more" antes de abrir el modal y el array combina chunks de fetches
// distintos cuyo orden inter-chunk no está garantizado por el backend.
const recentMatches = computed(() => {
  if (!props.championName) return []
  return props.matches
    .filter(m => m.my_champion === props.championName)
    .slice() // copia para no mutar props
    .sort((a, b) => ((b as any).game_date || 0) - ((a as any).game_date || 0))
    .slice(0, 10)
})

// Si NO está en pool pero sí en matches, computamos agregados básicos local.
const derivedStats = computed(() => {
  if (poolEntry.value) return poolEntry.value
  if (!recentMatches.value.length) return null
  const list = recentMatches.value
  const wins = list.filter(m => m.win).length
  return {
    champion: props.championName!,
    games: list.length,
    wins,
    winrate: Math.round((wins / list.length) * 100),
    avg_tumor: 0, // no tenemos tumor por-match del viewer en data local
  } as ChampionPoolEntry
})

const stats = computed(() => poolEntry.value || derivedStats.value)

const avgKda = computed(() => {
  if (!recentMatches.value.length) return null
  const sum = recentMatches.value.reduce((s, m) => s + (m.my_kda || 0), 0)
  return (sum / recentMatches.value.length).toFixed(2)
})

const winrateColor = computed(() => {
  const wr = stats.value?.winrate ?? 0
  if (wr >= 55) return 'text-green-400'
  if (wr < 45) return 'text-red-400'
  return 'text-yellow-300'
})

const kdaColor = computed(() => {
  const k = Number(avgKda.value) || 0
  if (k >= 3) return 'text-green-400'
  if (k < 1.5) return 'text-red-400'
  return 'text-yellow-300'
})

// Cierre con Escape — mounteo/desmonteo dinámico vía watch para no instalar
// el listener si el modal nunca se abre en la sesión.
function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
watch(() => props.show, (open) => {
  if (typeof document === 'undefined') return
  if (open) document.addEventListener('keydown', onEsc)
  else document.removeEventListener('keydown', onEsc)
})
onBeforeUnmount(() => {
  if (typeof document !== 'undefined') document.removeEventListener('keydown', onEsc)
})

function timeFmt(s?: number) {
  if (!s) return ''
  const m = Math.floor(s / 60)
  const ss = Math.floor(s % 60).toString().padStart(2, '0')
  return `${m}:${ss}`
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show && championName"
        class="fixed inset-0 z-[60] bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4 overflow-y-auto"
        @click.self="emit('close')">
        <div
          class="bg-[#0d1b2a] border border-yellow-500/30 shadow-2xl w-full max-w-xl max-h-[88vh] flex flex-col
                 rounded-t-2xl rounded-b-none sm:rounded-2xl"
          style="padding-bottom: env(safe-area-inset-bottom);">
          <!-- Drag handle mobile -->
          <div class="sm:hidden flex justify-center pt-2 pb-1">
            <span class="block w-10 h-1 bg-white/20 rounded-full"></span>
          </div>

          <!-- Header con splash blureado de fondo + icono + nombre + ✕ -->
          <div class="relative overflow-hidden rounded-t-2xl sm:rounded-t-xl">
            <img :src="championSplashUrl(championName)" @error="championIconFallback"
              class="absolute inset-0 w-full h-full object-cover opacity-25" />
            <div class="absolute inset-0 bg-gradient-to-b from-black/40 via-[#0d1b2a]/60 to-[#0d1b2a]"></div>
            <div class="relative flex items-center justify-between px-5 py-4">
              <div class="flex items-center gap-3 min-w-0">
                <img :src="championIconUrl(championName, ddragonVersion)" @error="championIconFallback"
                  class="w-14 h-14 rounded-lg border border-yellow-500/40 shadow-lg shrink-0" />
                <div class="min-w-0">
                  <p class="text-yellow-200 font-mono font-bold text-lg truncate">{{ championName }}</p>
                  <p class="text-white/50 font-mono text-[10px] uppercase tracking-widest">Stats con este campeón</p>
                </div>
              </div>
              <button @click="emit('close')"
                class="text-white/40 hover:text-white text-xl transition shrink-0"
                aria-label="Cerrar">✕</button>
            </div>
          </div>

          <!-- Stat grid: games / WR / KDA / Tumor -->
          <div v-if="stats" class="grid grid-cols-2 sm:grid-cols-4 gap-2 px-5 py-3">
            <div class="bg-black/30 border border-white/10 rounded-lg p-2.5 text-center">
              <p class="text-white/40 text-[9px] font-mono tracking-widest mb-1">PARTIDAS</p>
              <p class="text-white text-2xl font-mono font-bold leading-none">{{ stats.games }}</p>
              <p class="text-white/30 text-[10px] font-mono mt-0.5">{{ stats.wins }}W / {{ stats.games - stats.wins }}L</p>
            </div>
            <div class="bg-black/30 border border-white/10 rounded-lg p-2.5 text-center">
              <p class="text-white/40 text-[9px] font-mono tracking-widest mb-1">WIN RATE</p>
              <p :class="winrateColor" class="text-2xl font-mono font-bold leading-none">{{ stats.winrate }}%</p>
            </div>
            <div class="bg-black/30 border border-white/10 rounded-lg p-2.5 text-center">
              <p class="text-white/40 text-[9px] font-mono tracking-widest mb-1">KDA medio</p>
              <p v-if="avgKda" :class="kdaColor" class="text-2xl font-mono font-bold leading-none">{{ avgKda }}</p>
              <p v-else class="text-white/30 text-2xl font-mono font-bold leading-none">—</p>
              <p class="text-white/30 text-[10px] font-mono mt-0.5">últimas {{ recentMatches.length }}</p>
            </div>
            <div class="bg-black/30 border border-white/10 rounded-lg p-2.5 text-center">
              <p class="text-white/40 text-[9px] font-mono tracking-widest mb-1">TUMOR avg</p>
              <p v-if="stats.avg_tumor > 0" :class="tumorColor(stats.avg_tumor)" class="text-2xl font-mono font-bold leading-none">
                {{ stats.avg_tumor }}
              </p>
              <p v-else class="text-white/30 text-2xl font-mono font-bold leading-none">—</p>
              <p v-if="stats.avg_tumor > 0" :class="tumorColor(stats.avg_tumor)" class="text-[10px] font-mono mt-0.5 font-bold">
                {{ tumorLabel(stats.avg_tumor) }}
              </p>
            </div>
          </div>

          <!-- Empty state -->
          <div v-if="!stats || stats.games === 0"
            class="flex-1 flex flex-col items-center justify-center px-6 py-10 text-center">
            <span class="text-5xl mb-4">🎮</span>
            <p class="text-white font-mono font-bold mb-1">Aún no has jugado {{ championName }}</p>
            <p class="text-white/40 text-sm font-mono">
              No hay partidas con este campeón en tu historial cargado.
            </p>
          </div>

          <!-- Recent matches strip -->
          <div v-if="recentMatches.length" class="px-5 py-3 border-t border-white/10 overflow-y-auto">
            <p class="text-white/40 text-[10px] font-mono tracking-widest mb-2">
              ÚLTIMAS {{ recentMatches.length }} PARTIDAS
            </p>
            <div class="flex gap-2 overflow-x-auto pb-1">
              <div v-for="m in recentMatches" :key="m.match_id"
                class="shrink-0 flex flex-col items-center gap-1 p-2 rounded-lg border min-w-[64px]"
                :class="m.win
                  ? 'bg-blue-950/30 border-blue-500/30'
                  : 'bg-red-950/30 border-red-500/30'">
                <span :class="m.win ? 'bg-blue-500' : 'bg-red-500'"
                  class="w-7 h-7 rounded-full flex items-center justify-center text-white font-mono text-xs font-bold">
                  {{ m.win ? 'W' : 'L' }}
                </span>
                <p class="text-white text-[10px] font-mono font-bold">
                  {{ m.my_kills }}/{{ m.my_deaths }}/{{ m.my_assists }}
                </p>
                <p class="text-white/40 text-[9px] font-mono">{{ m.my_kda }} KDA</p>
                <p v-if="m.worst_is_me" class="text-red-300 text-[10px]" title="Fuiste el peor de tu equipo">☢️</p>
                <p v-if="m.game_duration" class="text-white/30 text-[9px] font-mono">{{ timeFmt(m.game_duration) }}</p>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="px-5 py-3 border-t border-white/10 flex items-center justify-end">
            <button @click="emit('close')"
              class="text-[10px] font-mono text-white/40 hover:text-white/70">
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Transición "modal": fade del backdrop. Sin esto el Transition con
   name="modal" no tendría reglas y el sheet aparecería/desaparecería sin
   animación. Mismo timing que UserModal/MyBetsModal/SocialModal para
   consistencia. */
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
