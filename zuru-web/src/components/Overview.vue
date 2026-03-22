<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-[#0d1b2a] to-[#1b2838] overflow-y-auto relative">

    <!-- X-Ray scanning overlay -->
    <Transition name="xray">
      <div v-if="scanning" class="xray-overlay absolute inset-0 z-50 flex flex-col items-center justify-center overflow-hidden">
        <div class="scan-line"></div>
        <div class="scan-line-glow"></div>

        <div class="relative z-10 text-center select-none">
          <p class="xray-label text-xs font-mono mb-6 tracking-[0.4em] text-cyan-300/60">HOSPITAL ZURUWEB · ONCOLOGÍA</p>
          <p class="xray-title font-mono text-3xl font-bold tracking-widest text-white mb-2">ESCANEANDO</p>
          <p class="xray-name font-mono text-cyan-400 text-xl tracking-widest mb-8">
            {{ formData.gameName }}<span class="text-cyan-300/50">#{{ formData.tagLine }}</span>
          </p>
          <div class="flex gap-2 justify-center">
            <span v-for="i in 3" :key="i" class="xray-dot" :style="{ animationDelay: `${(i - 1) * 0.3}s` }"></span>
          </div>
          <p class="xray-label text-[10px] font-mono mt-8 tracking-[0.3em] text-cyan-300/40">DETECTANDO TEJIDOS CANCERÍGENOS...</p>
        </div>

        <!-- Corner marks (medical/film style) -->
        <div class="corner corner-tl"></div>
        <div class="corner corner-tr"></div>
        <div class="corner corner-bl"></div>
        <div class="corner corner-br"></div>
      </div>
    </Transition>

    <!-- Login screen -->
    <div v-if="!summoner" class="flex-1 flex justify-center items-center p-8">
      <div class="w-full max-w-md">
        <div class="bg-black/30 backdrop-blur-md p-12 rounded-2xl text-center shadow-2xl mb-6 animate-fade">
          <h1 class="text-white font-mono text-5xl mb-2">Top Tumores</h1>
          <div class="h-[3px] w-[60%] mx-auto my-5 bg-gradient-to-r from-transparent via-[#c89b3c] to-transparent"></div>
          <p class="text-white/50 text-base">Revisa el historial de tus peores compañeros</p>
        </div>

        <div class="bg-black/30 backdrop-blur-md p-8 rounded-2xl shadow-2xl animate-fade">
          <form @submit.prevent="login" class="space-y-5">
            <div>
              <label class="block text-[#c89b3c] text-sm font-semibold mb-2 font-mono">Nombre del Invocador</label>
              <input v-model="formData.gameName" type="text" placeholder="GameName"
                class="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-lg text-white placeholder-white/30 focus:outline-none focus:border-[#c89b3c] transition" required />
            </div>
            <div>
              <label class="block text-[#c89b3c] text-sm font-semibold mb-2 font-mono">Tag</label>
              <input v-model="formData.tagLine" type="text" placeholder="EUW"
                class="w-32 px-4 py-3 bg-white/5 border border-white/20 rounded-lg text-white placeholder-white/30 focus:outline-none focus:border-[#c89b3c] transition" required />
            </div>
            <button type="submit" :disabled="loading"
              class="w-full bg-[#c89b3c] hover:bg-[#e0b84e] disabled:opacity-40 disabled:cursor-not-allowed text-black font-bold py-3 rounded-lg transition transform hover:scale-105 font-mono">
              Escanear tumores ☢️
            </button>
            <div v-if="error" class="bg-red-500/20 border border-red-500 text-red-300 px-4 py-3 rounded-lg text-sm">
              {{ error }}
            </div>
          </form>
        </div>

        <!-- Recent searches -->
        <div v-if="recentSummoners.length" class="mt-4 animate-fade">
          <p class="text-white/30 text-[10px] font-mono tracking-widest mb-2 text-center">BÚSQUEDAS RECIENTES</p>
          <div class="flex flex-wrap gap-2 justify-center">
            <button v-for="entry in recentSummoners" :key="entry" @click="loadRecent(entry)"
              class="px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/15 hover:border-[#c89b3c]/50 text-white/70 hover:text-white text-xs font-mono rounded-lg transition">
              {{ entry }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Results screen -->
    <div v-else class="p-6 max-w-7xl mx-auto w-full">

      <!-- Header -->
      <div class="flex items-center justify-between mb-8 animate-fade">
        <div>
          <h1 class="text-white font-mono text-3xl font-bold">Top Tumores</h1>
          <div class="flex items-center gap-2 mt-1">
            <p class="text-[#c89b3c] font-mono">{{ summoner }}</p>
            <span v-if="tier" :class="tierColor[tier] ?? 'text-white/40'" class="font-mono font-bold text-sm border border-current/30 px-2 py-0.5 rounded">
              {{ tier }}{{ division ? ' ' + division : '' }}
            </span>
          </div>
        </div>
        <button @click="logout"
          class="px-4 py-2 text-sm text-white/60 hover:text-white border border-white/20 hover:border-white/40 rounded-lg transition font-mono">
          Cerrar sesión
        </button>
      </div>

      <!-- Personal stats panel -->
      <div v-if="personalStats" class="bg-black/30 rounded-xl border border-white/10 p-5 mb-6 animate-fade">
        <p class="text-white/30 text-[10px] font-mono tracking-widest mb-4">TUS ESTADÍSTICAS</p>
        <div class="grid grid-cols-9 gap-3 text-center">
          <div>
            <p class="text-white text-xl font-bold">{{ personalStats.total_matches }}</p>
            <p class="text-white/40 text-[10px] font-mono">PARTIDAS</p>
          </div>
          <div>
            <p class="text-blue-400 text-xl font-bold">{{ personalStats.wins }}</p>
            <p class="text-white/40 text-[10px] font-mono">VICTORIAS</p>
          </div>
          <div>
            <p class="text-red-400 text-xl font-bold">{{ personalStats.losses }}</p>
            <p class="text-white/40 text-[10px] font-mono">DERROTAS</p>
          </div>
          <div>
            <p :class="personalStats.win_rate >= 50 ? 'text-green-400' : 'text-red-400'" class="text-xl font-bold">{{ personalStats.win_rate }}%</p>
            <p class="text-white/40 text-[10px] font-mono">WIN RATE</p>
          </div>
          <div class="border-l border-white/10">
            <p :class="personalStats.avg_kda >= 3 ? 'text-green-400' : personalStats.avg_kda >= 2 ? 'text-yellow-400' : 'text-red-400'" class="text-xl font-bold">{{ personalStats.avg_kda }}</p>
            <p class="text-white/40 text-[10px] font-mono">KDA MEDIO</p>
          </div>
          <div>
            <p class="text-white/80 text-xl font-bold">{{ personalStats.avg_cs }}</p>
            <p class="text-white/40 text-[10px] font-mono">CS MEDIO</p>
          </div>
          <div>
            <p class="text-white/80 text-xl font-bold">{{ formatGold(personalStats.avg_damage) }}</p>
            <p class="text-white/40 text-[10px] font-mono">DMG MEDIO</p>
          </div>
          <div class="border-l border-white/10">
            <p class="text-red-400 text-xl font-bold">{{ personalStats.times_worst }}</p>
            <p class="text-white/40 text-[10px] font-mono">VECES TUMOR</p>
          </div>
          <div>
            <p class="text-orange-400 text-xl font-bold">{{ personalStats.times_best_and_lost }}</p>
            <p class="text-white/40 text-[10px] font-mono">MEJOR Y PERDIÓ</p>
          </div>
        </div>
      </div>

      <!-- Main content: match list + top tumor -->
      <div class="flex gap-6 items-start">

      <!-- Match list -->
      <div class="space-y-4 flex-1 min-w-0">
        <div v-for="match in matches" :key="match.match_id"
          class="relative bg-black/30 backdrop-blur-sm rounded-xl overflow-hidden border border-white/10 animate-fade hover:border-white/20 transition">

          <!-- Remake overlay -->
          <div v-if="match.game_duration < 300"
            class="absolute inset-0 z-10 bg-black/60 backdrop-grayscale flex items-center justify-center rounded-xl">
            <p class="text-white/80 font-mono font-black text-4xl tracking-[0.3em] select-none">REMAKE</p>
          </div>

          <div class="flex items-stretch">

            <!-- Win/Loss bar -->
            <div :class="match.win ? 'bg-blue-500' : 'bg-red-500'" class="w-1.5 shrink-0"></div>

            <!-- My stats -->
            <div class="flex items-center gap-4 px-4 py-4 border-r border-white/10 min-w-[200px]">
              <div class="relative">
                <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${match.my_champion}.png`"
                  class="w-12 h-12 rounded-lg" />
                <span :class="match.win ? 'bg-blue-500' : 'bg-red-500'"
                  class="absolute -bottom-1 -right-1 text-white text-[9px] font-bold px-1 rounded font-mono">
                  {{ match.win ? 'W' : 'L' }}
                </span>
                <span v-if="match.best_and_lost"
                  class="absolute -top-2 -left-2 text-[11px]"
                  title="Mejor de tu equipo y aun así perdiste">
                  🫀
                </span>
                <span v-if="match.worst_is_me"
                  class="absolute -top-2 -right-2 text-[13px] animate-spin-slow"
                  title="Fuiste el peor de tu equipo">
                  ☢️
                </span>
              </div>
              <div>
                <p class="text-white/50 text-[10px] font-mono mb-0.5">TÚ · {{ match.my_champion }}</p>
                <p class="text-white text-sm font-bold">
                  {{ match.my_kills }}/{{ match.my_deaths }}/{{ match.my_assists }}
                </p>
                <p class="text-[#c89b3c] text-xs font-mono">{{ match.my_kda }} KDA</p>
                <p v-if="match.best_and_lost" class="text-orange-400 text-[10px] font-mono mt-0.5">mejor del equipo</p>
              </div>
            </div>

            <!-- Arrow -->
            <div class="flex items-center px-3 text-white/20 text-lg">→</div>

            <!-- Worst player -->
            <div class="flex items-center gap-3 px-4 py-3 flex-1 min-w-0">
              <div class="relative shrink-0">
                <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${match.worst.campeon}.png`"
                  class="w-11 h-11 rounded-lg" />
                <span class="absolute -bottom-1 -right-1 bg-black/70 text-white text-[9px] font-bold px-1 rounded font-mono border border-white/20">
                  Lv{{ match.worst.champ_level }}
                </span>
              </div>

              <!-- Name + KDA -->
              <div class="min-w-0 w-28 shrink-0">
                <p class="text-white/50 text-[10px] font-mono truncate">{{ match.worst.campeon }}</p>
                <p class="text-white text-xs font-bold truncate">{{ match.worst.nombre }}</p>
                <p class="text-xs mt-0.5">
                  <span class="text-green-400">{{ match.worst.kills }}</span>
                  <span class="text-white/30">/</span>
                  <span class="text-red-400">{{ match.worst.deaths }}</span>
                  <span class="text-white/30">/</span>
                  <span class="text-blue-400">{{ match.worst.assists }}</span>
                  <span :class="match.worst.kda < 1 ? 'text-red-400' : match.worst.kda < 2 ? 'text-yellow-400' : 'text-green-400'"
                    class="ml-1 font-mono font-bold">{{ match.worst.kda.toFixed(2) }}</span>
                </p>
              </div>

              <!-- Extra stats grid with team avg deltas -->
              <div class="grid grid-cols-4 gap-x-3 gap-y-1 flex-1 min-w-0">
                <div class="text-center">
                  <p class="text-white/40 text-[9px] font-mono">CS</p>
                  <p :class="match.worst.cs < 80 ? 'text-red-400' : 'text-white/80'" class="text-xs font-bold">{{ match.worst.cs }}</p>
                  <p :class="delta(match.worst.cs, match.worst.team_avg.cs).better ? 'text-green-400/60' : 'text-red-400/60'" class="text-[9px] font-mono">{{ delta(match.worst.cs, match.worst.team_avg.cs).text }}</p>
                </div>
                <div class="text-center">
                  <p class="text-white/40 text-[9px] font-mono">DMG</p>
                  <p :class="match.worst.damage < 5000 ? 'text-red-400' : 'text-white/80'" class="text-xs font-bold">{{ formatGold(match.worst.damage) }}</p>
                  <p :class="delta(match.worst.damage, match.worst.team_avg.damage).better ? 'text-green-400/60' : 'text-red-400/60'" class="text-[9px] font-mono">{{ delta(match.worst.damage, match.worst.team_avg.damage).text }}</p>
                </div>
                <div class="text-center">
                  <p class="text-white/40 text-[9px] font-mono">ORO</p>
                  <p class="text-yellow-400/80 text-xs font-bold">{{ formatGold(match.worst.gold) }}</p>
                  <p :class="delta(match.worst.gold, match.worst.team_avg.gold).better ? 'text-green-400/60' : 'text-red-400/60'" class="text-[9px] font-mono">{{ delta(match.worst.gold, match.worst.team_avg.gold).text }}</p>
                </div>
                <div class="text-center">
                  <p class="text-white/40 text-[9px] font-mono">MUERTO</p>
                  <p :class="match.worst.time_dead > 180 ? 'text-red-400' : 'text-white/80'" class="text-xs font-bold">{{ formatDuration(match.worst.time_dead) }}</p>
                </div>
                <div class="text-center">
                  <p class="text-white/40 text-[9px] font-mono">VISIÓN</p>
                  <p :class="match.worst.vision_score < 10 ? 'text-red-400' : 'text-white/80'" class="text-xs font-bold">{{ match.worst.vision_score }}</p>
                  <p :class="delta(match.worst.vision_score, match.worst.team_avg.vision).better ? 'text-green-400/60' : 'text-red-400/60'" class="text-[9px] font-mono">{{ delta(match.worst.vision_score, match.worst.team_avg.vision).text }}</p>
                </div>
                <div class="text-center">
                  <p class="text-white/40 text-[9px] font-mono">WARDS</p>
                  <p :class="match.worst.wards_placed < 3 ? 'text-red-400' : 'text-white/80'" class="text-xs font-bold">{{ match.worst.wards_placed }}</p>
                </div>
                <div class="text-center col-span-2">
                  <p class="text-white/40 text-[9px] font-mono">DURACIÓN</p>
                  <p class="text-white/60 text-xs font-mono">{{ formatDuration(match.game_duration) }}</p>
                </div>
              </div>

              <!-- Tumor score -->
              <div class="shrink-0 flex flex-col items-center justify-center pl-3 border-l border-white/10 min-w-[64px]">
                <p :class="tumorColor(match.worst.tumor_score)" class="text-2xl font-black font-mono">{{ match.worst.tumor_score }}</p>
                <p :class="tumorColor(match.worst.tumor_score)" class="text-[9px] font-mono font-bold text-center leading-tight">{{ tumorLabel(match.worst.tumor_score) }}</p>
              </div>
            </div>
          </div>
        </div>

        <p v-if="matches.length === 0" class="text-white/40 text-center py-12 font-mono">
          No se encontraron partidas rankeds recientes.
        </p>

        <!-- Load more -->
        <div class="pt-2 pb-4 text-center">
          <button v-if="hasMore" @click="loadMore" :disabled="loadingMore"
            class="px-6 py-2.5 bg-white/5 hover:bg-white/10 border border-white/15 hover:border-[#c89b3c]/40 text-white/60 hover:text-white font-mono text-sm rounded-lg transition disabled:opacity-40">
            {{ loadingMore ? 'Cargando...' : `Cargar más (${currentStart} cargadas)` }}
          </button>
          <p v-else-if="matches.length > 0" class="text-white/20 text-xs font-mono">
            No hay más partidas
          </p>
        </div>
      </div>

      <!-- Top Tumor sidebar -->
      <div v-if="topTumor" class="w-64 shrink-0 sticky top-6 animate-fade">
        <div class="rounded-2xl overflow-hidden border border-red-500/30 shadow-2xl shadow-red-900/30">

          <!-- Loading screen portrait art -->
          <div class="relative">
            <img
              :src="`https://ddragon.leagueoflegends.com/cdn/img/champion/loading/${topTumor.campeon}_0.jpg`"
              class="w-full object-cover object-top"
              style="aspect-ratio: 308/560"
            />
            <div class="absolute inset-0 bg-gradient-to-t from-black via-black/20 to-transparent"></div>

            <!-- Badge -->
            <div class="absolute top-3 left-3 bg-red-600 text-white text-[10px] font-mono font-bold px-2 py-1 rounded tracking-widest">
              ☢ TOP TUMOR
            </div>

            <!-- Apparitions badge -->
            <div class="absolute top-3 right-3 bg-black/60 text-red-400 text-xs font-mono font-bold px-2 py-1 rounded border border-red-500/40">
              x{{ topTumor.apariciones }}
            </div>

            <!-- Name over art -->
            <div class="absolute bottom-0 left-0 right-0 p-4">
              <p class="text-white font-bold text-base leading-tight truncate">{{ topTumor.nombre }}</p>
              <p class="text-white/50 text-xs font-mono">{{ topTumor.campeon }}</p>
            </div>
          </div>

          <!-- Stats -->
          <div class="bg-[#0d1b2a] p-4 space-y-3">
            <p class="text-white/40 text-[10px] font-mono tracking-widest">ESTADÍSTICAS ACUMULADAS</p>

            <div class="grid grid-cols-3 gap-2 text-center">
              <div>
                <p class="text-green-400 text-lg font-bold">{{ topTumor.total_kills }}</p>
                <p class="text-white/40 text-[10px] font-mono">KILLS</p>
              </div>
              <div>
                <p class="text-red-400 text-lg font-bold">{{ topTumor.total_deaths }}</p>
                <p class="text-white/40 text-[10px] font-mono">DEATHS</p>
              </div>
              <div>
                <p class="text-blue-400 text-lg font-bold">{{ topTumor.total_assists }}</p>
                <p class="text-white/40 text-[10px] font-mono">ASSISTS</p>
              </div>
            </div>

            <div class="border-t border-white/10 pt-3 text-center">
              <p class="text-white/40 text-[10px] font-mono mb-1">KDA MEDIO</p>
              <p :class="topTumor.avg_kda < 1 ? 'text-red-400' : topTumor.avg_kda < 2 ? 'text-yellow-400' : 'text-green-400'"
                class="text-3xl font-bold font-mono">
                {{ topTumor.avg_kda.toFixed(2) }}
              </p>
            </div>

            <div class="border-t border-white/10 pt-3 text-center">
              <p class="text-white/40 text-[10px] font-mono mb-1">APARICIONES</p>
              <p class="text-white text-xl font-bold font-mono">{{ topTumor.apariciones }} <span class="text-white/30 text-sm">/ {{ matches.length }}</span></p>
            </div>
          </div>
        </div>
      </div>

      </div><!-- end flex -->
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface TeamAvg {
  kda: number
  cs: number
  damage: number
  vision: number
  gold: number
}

interface WorstPlayer {
  nombre: string
  campeon: string
  kills: number
  deaths: number
  assists: number
  kda: number
  cs: number
  damage: number
  vision_score: number
  gold: number
  time_dead: number
  champ_level: number
  wards_placed: number
  tumor_score: number
  team_avg: TeamAvg
}

interface PersonalStats {
  total_matches: number
  wins: number
  losses: number
  win_rate: number
  times_worst: number
  times_best_and_lost: number
  avg_kda: number
  avg_cs: number
  avg_damage: number
}

interface TopTumor {
  nombre: string
  apariciones: number
  campeon: string
  total_kills: number
  total_deaths: number
  total_assists: number
  avg_kda: number
}

interface MatchOverview {
  match_id: string
  game_duration: number
  win: boolean
  best_and_lost: boolean
  worst_is_me: boolean
  my_champion: string
  my_kills: number
  my_deaths: number
  my_assists: number
  my_kda: number
  my_cs: number
  my_damage: number
  worst: WorstPlayer
}

const ddragonVersion = ref('15.1.1') // fallback; overwritten on mount

fetch('https://ddragon.leagueoflegends.com/api/versions.json')
  .then(r => r.json())
  .then(versions => { ddragonVersion.value = versions[0] })
  .catch(() => {})

const formData = ref({ gameName: '', tagLine: '' })
const summoner = ref('')
const tier = ref('')
const division = ref('')
const matches = ref<MatchOverview[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const scanning = ref(false)
const hasMore = ref(false)
const currentStart = ref(0)
const error = ref('')
const recentSummoners = ref<string[]>([])

const validMatches = computed(() => matches.value.filter(m => m.game_duration >= 300))

const personalStats = computed<PersonalStats | null>(() => {
  const valid = validMatches.value
  const total = valid.length
  if (!total) return null
  const wins = valid.filter(m => m.win).length
  return {
    total_matches: total,
    wins,
    losses: total - wins,
    win_rate: Math.round(wins / total * 100),
    times_worst: valid.filter(m => m.worst_is_me).length,
    times_best_and_lost: valid.filter(m => m.best_and_lost).length,
    avg_kda: Math.round(valid.reduce((s, m) => s + m.my_kda, 0) / total * 100) / 100,
    avg_cs: Math.round(valid.reduce((s, m) => s + m.my_cs, 0) / total * 10) / 10,
    avg_damage: Math.round(valid.reduce((s, m) => s + m.my_damage, 0) / total),
  }
})

const topTumor = computed<TopTumor | null>(() => {
  const valid = validMatches.value
  if (!valid.length) return null

  const counts = new Map<string, { worst: WorstPlayer[] }>()
  for (const m of valid) {
    const n = m.worst.nombre
    if (!counts.has(n)) counts.set(n, { worst: [] })
    counts.get(n)!.worst.push(m.worst)
  }

  let best: { nombre: string; worst: WorstPlayer[] } | null = null
  for (const [nombre, entry] of counts)
    if (!best || entry.worst.length > best.worst.length) best = { nombre, ...entry }

  if (!best) return null

  const tk = best.worst.reduce((s, p) => s + p.kills, 0)
  const td = best.worst.reduce((s, p) => s + p.deaths, 0)
  const ta = best.worst.reduce((s, p) => s + p.assists, 0)
  const champMap = new Map<string, number>()
  for (const p of best.worst) champMap.set(p.campeon, (champMap.get(p.campeon) ?? 0) + 1)
  const campeon = [...champMap.entries()].sort((a, b) => b[1] - a[1])[0][0]

  return {
    nombre: best.nombre,
    apariciones: best.worst.length,
    campeon,
    total_kills: tk,
    total_deaths: td,
    total_assists: ta,
    avg_kda: Math.round((td === 0 ? tk + ta : (tk + ta) / td) * 100) / 100,
  }
})

const fetchRecent = async () => {
  try {
    const res = await fetch('http://localhost:5000/recentSummoners')
    recentSummoners.value = await res.json()
  } catch {}
}

const saveRecent = async (name: string) => {
  try {
    await fetch('http://localhost:5000/recentSummoners', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ summoner: name })
    })
    await fetchRecent()
  } catch {}
}

const loadRecent = (entry: string) => {
  const [gameName, tagLine] = entry.split('#')
  formData.value = { gameName, tagLine }
  login()
}

fetchRecent()


const formatDuration = (seconds: number) => {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s.toString().padStart(2, '0')}s`
}

const formatGold = (g: number) => g >= 1000 ? `${(g / 1000).toFixed(1)}k` : String(g)

const login = async () => {
  loading.value = true
  scanning.value = true
  error.value = ''

  try {
    const params = new URLSearchParams({
      game_name: formData.value.gameName,
      tag_line: formData.value.tagLine,
    })

    const res = await fetch(`http://localhost:5000/getOverview?${params}`)
    const data = await res.json()

    if (!res.ok || data.error) throw new Error(data.error || 'Error al cargar el overview')

    await new Promise(r => setTimeout(r, 2500))

    summoner.value = data.summoner
    tier.value = data.tier ?? ''
    division.value = data.division ?? ''
    matches.value = data.matches
    hasMore.value = data.has_more ?? false
    currentStart.value = data.matches.length
    saveRecent(data.summoner)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Error desconocido'
  } finally {
    loading.value = false
    scanning.value = false
  }
}

const loadMore = async () => {
  loadingMore.value = true
  try {
    const params = new URLSearchParams({
      game_name: summoner.value.split('#')[0],
      tag_line: summoner.value.split('#')[1],
      start: String(currentStart.value),
      tier: tier.value,
    })

    const res = await fetch(`http://localhost:5000/getOverview?${params}`)
    const data = await res.json()

    if (!res.ok || data.error) throw new Error(data.error)

    matches.value = [...matches.value, ...data.matches]
    hasMore.value = data.has_more ?? false
    currentStart.value += data.matches.length
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Error desconocido'
  } finally {
    loadingMore.value = false
  }
}

const logout = () => {
  summoner.value = ''
  tier.value = ''
  division.value = ''
  matches.value = []
  hasMore.value = false
  currentStart.value = 0
  formData.value = { gameName: '', tagLine: '' }
}

const tierColor: Record<string, string> = {
  IRON: 'text-[#8a7462]', BRONZE: 'text-[#a0522d]', SILVER: 'text-[#a0a9b0]',
  GOLD: 'text-[#c89b3c]', PLATINUM: 'text-[#4e9e8a]', EMERALD: 'text-[#2ecc71]',
  DIAMOND: 'text-[#7ec8e3]', MASTER: 'text-[#c45cff]', GRANDMASTER: 'text-[#ff4444]',
  CHALLENGER: 'text-[#f4c542]', UNRANKED: 'text-white/40',
}

const tumorColor = (score: number) => {
  if (score >= 75) return 'text-red-500'
  if (score >= 50) return 'text-orange-400'
  if (score >= 25) return 'text-yellow-400'
  return 'text-green-400'
}

const tumorLabel = (score: number) => {
  if (score >= 75) return '☢ NUCLEAR'
  if (score >= 50) return '☣ TUMOR'
  if (score >= 25) return '⚠ SUS'
  return '✓ DECENTE'
}

const delta = (val: number, avg: number, higherIsBetter = true) => {
  const d = val - avg
  const positive = d > 0
  const better = higherIsBetter ? positive : !positive
  const sign = positive ? '+' : ''
  return { text: `${sign}${Math.round(d)}`, better }
}
</script>

<style scoped>
@keyframes fade {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade {
  animation: fade 0.5s ease forwards;
}

/* X-Ray overlay */
.xray-overlay {
  background: rgba(0, 4, 10, 0.97);
  backdrop-filter: blur(2px);
}

/* Scanning beam */
@keyframes scan {
  0%   { top: -4px; }
  100% { top: 100%; }
}

.scan-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(0, 255, 255, 0.9), transparent);
  animation: scan 2s linear infinite;
  z-index: 1;
}

.scan-line-glow {
  position: absolute;
  left: 0;
  right: 0;
  height: 80px;
  background: linear-gradient(to bottom, transparent, rgba(0, 255, 255, 0.06), transparent);
  animation: scan 2s linear infinite;
  z-index: 1;
  margin-top: -40px;
}

/* Dots pulsing */
@keyframes dotPulse {
  0%, 100% { opacity: 0.2; transform: scale(0.8); }
  50%       { opacity: 1;   transform: scale(1.2); }
}
.xray-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(0, 255, 255, 0.8);
  animation: dotPulse 0.9s ease-in-out infinite;
}

/* Flicker effect on text */
@keyframes flicker {
  0%, 97%, 100% { opacity: 1; }
  98%           { opacity: 0.4; }
  99%           { opacity: 0.9; }
}
.xray-title {
  animation: flicker 4s infinite;
  text-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
}
.xray-name {
  text-shadow: 0 0 12px rgba(0, 200, 255, 0.4);
}
.xray-label {
  letter-spacing: 0.3em;
}

/* Corner marks */
.corner {
  position: absolute;
  width: 24px;
  height: 24px;
  border-color: rgba(0, 255, 255, 0.3);
  border-style: solid;
}
.corner-tl { top: 20px; left: 20px;  border-width: 2px 0 0 2px; }
.corner-tr { top: 20px; right: 20px; border-width: 2px 2px 0 0; }
.corner-bl { bottom: 20px; left: 20px;  border-width: 0 0 2px 2px; }
.corner-br { bottom: 20px; right: 20px; border-width: 0 2px 2px 0; }

@keyframes spinSlow {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
.animate-spin-slow {
  display: inline-block;
  animation: spinSlow 4s linear infinite;
}

/* Transition */
.xray-enter-active { transition: opacity 0.3s ease; }
.xray-leave-active { transition: opacity 0.6s ease; }
.xray-enter-from, .xray-leave-to { opacity: 0; }
</style>
