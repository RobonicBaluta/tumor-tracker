<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-[#0d0d1a] to-[#1a1a2e] overflow-y-auto">

    <!-- Search form -->
    <div v-if="!result" class="flex-1 flex justify-center items-center p-8">
      <div class="w-full max-w-2xl">
        <div class="bg-black/30 backdrop-blur-md p-10 rounded-2xl text-center shadow-2xl mb-6 animate-fade">
          <h1 class="text-white font-mono text-4xl mb-2">Modo Versus</h1>
          <div class="h-[2px] w-[50%] mx-auto my-4 bg-gradient-to-r from-transparent via-purple-500 to-transparent"></div>
          <p class="text-white/40 text-sm">¿Quién fue peor en las partidas que compartisteis?</p>
        </div>

        <div class="bg-black/30 backdrop-blur-md p-8 rounded-2xl shadow-2xl animate-fade space-y-6">
          <!-- #28: hasta 5 jugadores. Un solo input por slot ("Nombre#TAG").
               Mientras tecleas el nombre, autocompleta desde recent +
               saved + users + friends conocidos. El user puede aceptar una
               sugerencia (rellena el #TAG) o escribir manualmente. -->
          <div v-for="(p, i) in form.players" :key="i" class="relative">
            <div class="flex items-center justify-between mb-3">
              <p class="text-xs font-mono font-bold tracking-widest"
                :style="{ color: playerColor(i) }">JUGADOR {{ i + 1 }}</p>
              <button v-if="form.players.length > 2"
                @click="removePlayer(i)"
                class="text-white/30 hover:text-red-400 text-xs font-mono">✕ quitar</button>
            </div>
            <div class="relative">
              <input v-model="p.value"
                @input="onInput(i)"
                @focus="activeSlot = i"
                @blur="closeSuggestions(i)"
                @keydown.down="onArrow(i, 1, $event)"
                @keydown.up="onArrow(i, -1, $event)"
                @keydown.enter="onEnter(i, $event)"
                @keydown.escape="closeSuggestions(i)"
                type="text"
                placeholder="Nombre#TAG · ej. Faker#KR1"
                autocapitalize="off" autocorrect="off" autocomplete="off" spellcheck="false"
                role="combobox"
                :aria-expanded="activeSlot === i && suggestions[i]?.length > 0"
                :aria-controls="`compare-suggest-${i}`"
                :aria-activedescendant="(activeSlot === i && suggestions[i]?.length) ? `compare-suggest-${i}-${suggestionCursor[i] || 0}` : undefined"
                aria-autocomplete="list"
                class="w-full px-4 py-3 bg-white/5 border rounded-lg text-white placeholder-white/20 focus:outline-none transition font-mono"
                :style="{ borderColor: playerBorder(i) }" />

              <!-- Autocomplete dropdown — sólo cuando hay sugerencias
                   y el slot está activo (input enfocado). ARIA listbox
                   para que screen readers lo anuncien correctamente. -->
              <div v-if="activeSlot === i && suggestions[i]?.length"
                :id="`compare-suggest-${i}`"
                role="listbox"
                class="absolute z-20 left-0 right-0 mt-1 bg-[#0d0d1a] border border-white/15 rounded-lg shadow-2xl overflow-hidden">
                <button v-for="(s, idx) in suggestions[i]" :key="`${i}-${s}`"
                  :id="`compare-suggest-${i}-${idx}`"
                  type="button"
                  role="option"
                  :aria-selected="suggestionCursor[i] === idx"
                  @mousedown.prevent="pickSuggestion(i, s)"
                  :class="suggestionCursor[i] === idx ? 'bg-white/10' : 'hover:bg-white/5'"
                  class="w-full text-left px-3 py-2 text-sm text-white font-mono flex items-center justify-between transition">
                  <span class="truncate">{{ s.split('#')[0] }}</span>
                  <span class="text-white/40 text-[10px] shrink-0 ml-2">#{{ s.split('#')[1] }}</span>
                </button>
              </div>
            </div>
            <p v-if="p.value && !p.value.includes('#')" class="text-yellow-400/70 text-[10px] font-mono mt-1">
              Necesitas el TAG (después del #) — escríbelo o elige una sugerencia.
            </p>
          </div>

          <button v-if="form.players.length < MAX_PLAYERS"
            @click="addPlayer"
            class="w-full bg-white/5 hover:bg-white/10 border border-dashed border-white/20 text-white/60 font-mono text-sm py-2 rounded-lg transition">
            + Añadir jugador ({{ form.players.length }}/{{ MAX_PLAYERS }})
          </button>

          <button @click="search" :disabled="loading"
            class="w-full bg-purple-700 hover:bg-purple-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold py-3 rounded-lg transition font-mono tracking-wide">
            {{ loading ? 'Buscando partidas comunes...' : 'Comparar ⚔️' }}
          </button>

          <div v-if="error" class="bg-red-500/20 border border-red-500 text-red-300 px-4 py-3 rounded-lg text-sm font-mono">
            {{ error }}
          </div>
        </div>
      </div>
    </div>

    <!-- Results -->
    <div v-else class="p-6 max-w-6xl mx-auto w-full">

      <!-- Header scorecard: una columna por jugador + bloque central con
           total de partidas comunes. -->
      <div class="bg-black/30 rounded-2xl border border-white/10 p-6 mb-6 animate-fade">
        <p class="text-center text-white/20 text-[10px] font-mono tracking-widest mb-1">PARTIDAS COMUNES</p>
        <p class="text-center text-white font-black text-4xl font-mono mb-4">{{ result.common_matches }}</p>
        <div class="grid gap-3" :style="{ gridTemplateColumns: `repeat(${result.player_names.length}, minmax(0, 1fr))` }">
          <div v-for="(name, i) in result.player_names" :key="name" class="text-center">
            <p class="text-[10px] font-mono tracking-widest mb-1"
              :style="{ color: playerColor(i) }">JUGADOR {{ i + 1 }}</p>
            <p class="text-white font-bold text-sm truncate" :title="name">{{ name }}</p>
            <div :class="rankBadgeClass(i)"
              class="mt-2 inline-block border px-3 py-1 rounded-full text-xs font-mono font-bold">
              {{ rankLabel(i) }}
            </div>
            <p class="text-white/30 text-[10px] font-mono mt-1">{{ result.scores[i] }} veces peor</p>
          </div>
        </div>
      </div>

      <!-- No common matches -->
      <div v-if="result.common_matches === 0" class="text-center py-16 animate-fade">
        <p class="text-white/30 font-mono text-lg">No se encontraron partidas comunes</p>
        <p class="text-white/20 text-sm mt-2">Comprobando las últimas 30 rankeds de cada jugador</p>
      </div>

      <!-- Match list — cada match es una tarjeta con N rows. -->
      <div v-else class="space-y-3">
        <div v-for="match in result.matches" :key="match.match_id"
          class="bg-black/30 rounded-xl border border-white/10 overflow-hidden hover:border-white/20 transition animate-fade">
          <div class="px-4 pt-2 pb-1 flex items-center justify-between">
            <span :class="match.same_team ? 'text-green-400/60' : 'text-red-400/60'" class="text-[10px] font-mono">
              {{ match.same_team ? '🤝 Mismo equipo' : '⚔️ Equipos distintos' }} · {{ formatDuration(match.game_duration) }}
            </span>
            <span v-if="match.worst_index === -1" class="text-white/30 text-[10px] font-mono italic">empate KDA</span>
          </div>

          <div class="divide-y divide-white/5">
            <div v-for="(p, i) in match.players" :key="i"
              :class="match.worst_index === i ? 'bg-red-950/30' : ''"
              class="flex items-center gap-3 px-4 py-3">
              <div class="relative shrink-0">
                <img :src="championIconUrl(p.campeon, ddragonVersion)" @error="championIconFallback"
                  class="w-11 h-11 rounded-lg" />
                <span :class="p.win ? 'bg-blue-500' : 'bg-red-500'"
                  class="absolute -bottom-1 -right-1 text-white text-[9px] font-bold px-1 rounded font-mono">
                  {{ p.win ? 'W' : 'L' }}
                </span>
                <span v-if="match.worst_index === i" class="absolute -top-2 -left-2 text-sm animate-spin-slow">☢️</span>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-[10px] font-mono truncate" :style="{ color: playerColor(i) }">{{ result.player_names[i] }}</p>
                <p class="text-white text-sm font-bold">{{ p.kills }}/{{ p.deaths }}/{{ p.assists }}</p>
                <p :class="p.kda < 1 ? 'text-red-400' : p.kda < 2 ? 'text-yellow-400' : 'text-green-400'"
                  class="text-xs font-mono font-bold">{{ p.kda }} KDA</p>
              </div>
              <div class="text-right text-xs space-y-0.5">
                <p class="text-white/50 font-mono">{{ p.cs }} CS</p>
                <p class="text-white/50 font-mono">{{ formatGold(p.damage) }} DMG</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="pt-4 text-center">
        <button @click="resetSearch"
          class="px-6 py-2 text-white/40 hover:text-white border border-white/10 hover:border-white/30 rounded-lg transition font-mono text-sm">
          Nueva comparación
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { API_BASE } from '../composables/useApi'
import { championIconUrl, championIconFallback } from '../composables/overviewConstants'

interface ComparePlayer {
  campeon: string
  kills: number
  deaths: number
  assists: number
  kda: number
  cs: number
  damage: number
  win: boolean
  team_id?: number
}

interface CompareMatch {
  match_id: string
  game_duration: number
  same_team: boolean
  /** Índice 0-based del jugador con peor KDA; -1 si empate. */
  worst_index: number
  players: ComparePlayer[]
}

interface CompareResult {
  player_names: string[]
  scores: number[]
  common_matches: number
  matches: CompareMatch[]
}

const MAX_PLAYERS = 5
const ddragonVersion = ref('15.1.1')
fetch('https://ddragon.leagueoflegends.com/api/versions.json')
  .then(r => r.json()).then(v => { ddragonVersion.value = v[0] }).catch(() => {})

// Form: array de N players (default 2). Cada slot es un único string
// "Nombre#TAG" — el autocomplete sugiere completos desde el backend.
const form = ref<{ players: Array<{ value: string }> }>({
  players: [
    { value: '' },
    { value: '' },
  ],
})

// Autocomplete state — paralelo a form.players. suggestions[i] = string[]
// últimos resultados del search; suggestionCursor[i] = índice highlighted
// para keyboard nav. activeSlot = índice del input enfocado (para mostrar
// el dropdown sólo de UN slot a la vez). searchTimers[i] = debounce timer.
// reqIds[i] = contador monotónico para descartar respuestas viejas que
// volverían a sobrescribir el suggestions con datos stale (HIGH bug
// cazado por review: typing rápido + red lenta podía mostrar el resultado
// de "fa" tras el de "fak").
const suggestions = ref<string[][]>([[], []])
const suggestionCursor = ref<number[]>([0, 0])
const activeSlot = ref<number>(-1)
const searchTimers: Array<ReturnType<typeof setTimeout> | null> = [null, null]
const reqIds: number[] = [0, 0]

function onInput(i: number) {
  suggestionCursor.value[i] = 0
  // Bump request id INMEDIATAMENTE — cualquier fetch en vuelo será
  // descartado al volver porque su id local será menor que reqIds[i].
  reqIds[i] = (reqIds[i] || 0) + 1
  if (searchTimers[i]) clearTimeout(searchTimers[i] as any)
  searchTimers[i] = setTimeout(() => fetchSuggestions(i), 250)
}

async function fetchSuggestions(i: number) {
  const raw = form.value.players[i]?.value || ''
  if (raw.includes('#') && raw.split('#')[1].length > 0) {
    suggestions.value[i] = []
    return
  }
  const q = raw.trim()
  if (q.length < 2) {
    suggestions.value[i] = []
    return
  }
  const myReq = reqIds[i] = (reqIds[i] || 0) + 1
  try {
    const res = await fetch(`${API_BASE}/search/summoners?q=${encodeURIComponent(q)}&limit=5`)
    // Stale response — el user siguió tecleando antes de que volviéramos.
    if (myReq !== reqIds[i]) return
    if (!res.ok) { suggestions.value[i] = []; return }
    const data: string[] = await res.json()
    if (myReq !== reqIds[i]) return  // double-check tras await del json
    suggestions.value[i] = data
  } catch {
    if (myReq !== reqIds[i]) return
    suggestions.value[i] = []
  }
}

function moveSuggestion(i: number, dir: 1 | -1) {
  const list = suggestions.value[i] || []
  if (!list.length) return
  const cur = suggestionCursor.value[i] || 0
  const next = (cur + dir + list.length) % list.length
  suggestionCursor.value[i] = next
}

function acceptSuggestion(i: number) {
  const list = suggestions.value[i] || []
  if (!list.length) return
  pickSuggestion(i, list[suggestionCursor.value[i] || 0])
}

// Sólo prevent default cuando el dropdown está visible — sin esto las
// flechas se "comían" para usar input con caret normal y Enter no podía
// disparar la búsqueda cuando el user ya tenía Name#TAG completos.
function onArrow(i: number, dir: 1 | -1, e: KeyboardEvent) {
  const list = suggestions.value[i] || []
  if (!list.length) return  // sin dropdown, deja el browser mover el caret
  e.preventDefault()
  moveSuggestion(i, dir)
}

function onEnter(i: number, e: KeyboardEvent) {
  const list = suggestions.value[i] || []
  if (list.length) {
    e.preventDefault()
    acceptSuggestion(i)
  } else {
    // Sin sugerencias visibles → submit del form como atajo. Sólo si
    // todos los slots tienen Nombre#TAG ya escrito; si no, search() pinta
    // el error correspondiente.
    e.preventDefault()
    search()
  }
}

function pickSuggestion(i: number, full: string) {
  form.value.players[i].value = full
  suggestions.value[i] = []
  activeSlot.value = -1
}

function closeSuggestions(i: number) {
  // Pequeño delay para que el @mousedown del item dropdown gane la carrera
  // contra el @blur del input. Sin esto el blur cierra el dropdown ANTES
  // de que el click se procese y la selección no se aplica.
  setTimeout(() => {
    if (activeSlot.value === i) activeSlot.value = -1
  }, 150)
}
const result = ref<CompareResult | null>(null)
const loading = ref(false)
const error = ref('')

// Paleta determinista por slot — azul/rojo para 2 (como antes), expandida
// para 3-5. Mantiene la convención visual del juego (blue=p1, red=p2).
const PLAYER_COLORS = ['#60a5fa', '#f87171', '#facc15', '#a78bfa', '#34d399']
function playerColor(i: number) { return PLAYER_COLORS[i % PLAYER_COLORS.length] }
function playerBorder(i: number) { return `${playerColor(i)}55` }  // alpha 33%

function addPlayer() {
  if (form.value.players.length >= MAX_PLAYERS) return
  form.value.players.push({ value: '' })
  suggestions.value.push([])
  suggestionCursor.value.push(0)
  searchTimers.push(null)
  reqIds.push(0)
}
function removePlayer(i: number) {
  if (form.value.players.length <= 2) return
  // Limpia timer pendiente + bumpea reqId para que cualquier respuesta en
  // vuelo se descarte y no escriba en suggestions del slot equivocado.
  // Sin esto, splice desfasaba los índices y el timer del slot eliminado
  // fireaba luego sobre el slot adyacente (bug HIGH cazado por review).
  if (searchTimers[i]) {
    clearTimeout(searchTimers[i] as any)
    searchTimers[i] = null
  }
  reqIds[i] = (reqIds[i] || 0) + 1
  form.value.players.splice(i, 1)
  suggestions.value.splice(i, 1)
  suggestionCursor.value.splice(i, 1)
  searchTimers.splice(i, 1)
  reqIds.splice(i, 1)
}

// Ranking del jugador en función de su score (más score = más veces fue
// peor = peor jugador overall). El mejor del grupo es el de score mínimo.
const ranks = computed(() => {
  if (!result.value) return [] as number[]
  const s = result.value.scores
  const sorted = [...s].slice().sort((a, b) => a - b)
  // rank[i] = posición de s[i] en sorted (0 = mejor, n-1 = peor).
  return s.map(v => sorted.indexOf(v))
})

// Detecta scores uniformes (todos tied o todos 0). Sin este short-circuit
// sorted.indexOf devuelve 0 para todos y la UI mostraba 5 badges "MEJOR"
// con 0/0/0/0/0 worst-counts — bug MEDIUM cazado por review.
const allScoresEqual = computed(() => {
  if (!result.value || result.value.scores.length < 2) return false
  const first = result.value.scores[0]
  return result.value.scores.every(v => v === first)
})

function rankBadgeClass(i: number) {
  if (!result.value) return ''
  if (allScoresEqual.value) return 'bg-white/5 border-white/15 text-white/60'
  const r = ranks.value[i]
  const n = result.value.scores.length
  if (n === 0) return ''
  if (r === n - 1 && result.value.scores[i] > 0) return 'bg-red-900/40 border-red-500/40 text-red-400'
  if (r === 0) return 'bg-green-900/20 border-green-500/20 text-green-400'
  return 'bg-white/5 border-white/15 text-white/60'
}

function rankLabel(i: number) {
  if (!result.value) return ''
  if (allScoresEqual.value) return '= EMPATE'
  const score = result.value.scores[i]
  const r = ranks.value[i]
  const n = result.value.scores.length
  if (n === 0) return ''
  if (r === n - 1 && score > 0) return `☢ PEOR ${score}x`
  if (r === 0) return '✓ MEJOR'
  return `#${r + 1}`
}

function formatDuration(s: number) { return `${Math.floor(s / 60)}m ${(s % 60).toString().padStart(2, '0')}s` }
function formatGold(g: number) { return g >= 1000 ? `${(g / 1000).toFixed(1)}k` : String(g) }

async function search() {
  // Validación: cada slot debe ser "Nombre#TAG" no vacío en ambas partes.
  const bad = form.value.players.findIndex(p => {
    const v = p.value.trim()
    if (!v.includes('#')) return true
    const [name, tag] = v.split('#', 2)
    return !name.trim() || !tag?.trim()
  })
  if (bad >= 0) {
    error.value = `Jugador ${bad + 1}: usa formato Nombre#TAG`
    return
  }
  if (form.value.players.length < 2) {
    error.value = 'Mínimo 2 jugadores'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    for (const p of form.value.players) {
      params.append('p', p.value.trim())
    }
    const res = await fetch(`${API_BASE}/compare/multi?${params}`)
    const data = await res.json()
    if (!res.ok || data.error) throw new Error(data.error || 'Error al comparar')
    result.value = data
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Error desconocido'
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  result.value = null
  error.value = ''
}
</script>

<style scoped>
@keyframes fade {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade { animation: fade 0.4s ease forwards; }
@keyframes spin-slow { to { transform: rotate(360deg); } }
.animate-spin-slow { animation: spin-slow 3s linear infinite; }
</style>
