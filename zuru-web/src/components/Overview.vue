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
          <p class="text-[#c89b3c] font-mono mt-1">{{ summoner }}</p>
        </div>
        <button @click="logout"
          class="px-4 py-2 text-sm text-white/60 hover:text-white border border-white/20 hover:border-white/40 rounded-lg transition font-mono">
          Cerrar sesión
        </button>
      </div>

      <!-- Stats summary -->
      <div class="grid grid-cols-3 gap-4 mb-8 animate-fade">
        <div class="bg-black/30 rounded-xl p-4 text-center border border-white/10">
          <p class="text-white/50 text-xs font-mono mb-1">PARTIDAS</p>
          <p class="text-white text-2xl font-bold">{{ matches.length }}</p>
        </div>
        <div class="bg-black/30 rounded-xl p-4 text-center border border-white/10">
          <p class="text-white/50 text-xs font-mono mb-1">VICTORIAS</p>
          <p class="text-green-400 text-2xl font-bold">{{ wins }}</p>
        </div>
        <div class="bg-black/30 rounded-xl p-4 text-center border border-white/10">
          <p class="text-white/50 text-xs font-mono mb-1">DERROTAS</p>
          <p class="text-red-400 text-2xl font-bold">{{ losses }}</p>
        </div>
      </div>

      <!-- Main content: match list + top tumor -->
      <div class="flex gap-6 items-start">

      <!-- Match list -->
      <div class="space-y-4 flex-1 min-w-0">
        <div v-for="match in matches" :key="match.match_id"
          class="bg-black/30 backdrop-blur-sm rounded-xl overflow-hidden border border-white/10 animate-fade hover:border-white/20 transition">

          <div class="flex items-stretch">

            <!-- Win/Loss bar -->
            <div :class="match.win ? 'bg-blue-500' : 'bg-red-500'" class="w-1.5 shrink-0"></div>

            <!-- My stats -->
            <div class="flex items-center gap-4 px-4 py-4 border-r border-white/10 min-w-[200px]">
              <div class="relative">
                <img :src="`https://ddragon.leagueoflegends.com/cdn/13.24.1/img/champion/${match.my_champion}.png`"
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
            <div class="flex items-center gap-4 px-4 py-4 flex-1">
              <img :src="`https://ddragon.leagueoflegends.com/cdn/13.24.1/img/champion/${match.worst.campeon}.png`"
                class="w-12 h-12 rounded-lg shrink-0" />
              <div class="flex-1 min-w-0">
                <p class="text-white/50 text-[10px] font-mono mb-0.5">PEOR ALIADO · {{ match.worst.campeon }}</p>
                <p class="text-white text-sm font-bold truncate">{{ match.worst.nombre }}</p>
                <p class="text-sm">
                  <span class="text-green-400">{{ match.worst.kills }}</span>
                  <span class="text-white/40">/</span>
                  <span class="text-red-400">{{ match.worst.deaths }}</span>
                  <span class="text-white/40">/</span>
                  <span class="text-blue-400">{{ match.worst.assists }}</span>
                </p>
              </div>

              <!-- KDA badge -->
              <div class="text-right shrink-0">
                <p class="text-white/40 text-[10px] font-mono">KDA</p>
                <p :class="match.worst.kda < 1 ? 'text-red-400' : match.worst.kda < 2 ? 'text-yellow-400' : 'text-green-400'"
                  class="text-xl font-bold font-mono">
                  {{ match.worst.kda.toFixed(2) }}
                </p>
              </div>

              <!-- Duration -->
              <div class="text-right shrink-0 pl-4 border-l border-white/10">
                <p class="text-white/40 text-[10px] font-mono">DURACIÓN</p>
                <p class="text-white/70 text-sm font-mono">{{ formatDuration(match.game_duration) }}</p>
              </div>
            </div>
          </div>
        </div>

        <p v-if="matches.length === 0" class="text-white/40 text-center py-12 font-mono">
          No se encontraron partidas rankeds recientes.
        </p>
      </div>

      <!-- Top Tumor sidebar -->
      <div v-if="topTumor" class="w-72 shrink-0 sticky top-6 animate-fade">
        <div class="rounded-2xl overflow-hidden border border-red-500/30 shadow-2xl shadow-red-900/30">

          <!-- Splash art -->
          <div class="relative h-80"
            :style="{ backgroundImage: `url(https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${topTumor.campeon}_0.jpg)`, backgroundSize: 'cover', backgroundPosition: 'center top' }">
            <div class="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent"></div>

            <!-- Badge -->
            <div class="absolute top-3 left-3 bg-red-600 text-white text-[10px] font-mono font-bold px-2 py-1 rounded tracking-widest">
              ☢ TOP TUMOR
            </div>

            <!-- Apparitions badge -->
            <div class="absolute top-3 right-3 bg-black/60 text-red-400 text-xs font-mono font-bold px-2 py-1 rounded border border-red-500/40">
              x{{ topTumor.apariciones }}
            </div>

            <!-- Name over splash -->
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

interface WorstPlayer {
  nombre: string
  campeon: string
  kills: number
  deaths: number
  assists: number
  kda: number
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
  worst: WorstPlayer
}

const RECENT_KEY = 'tt_recent_summoners'
const MAX_RECENT = 5

const formData = ref({ gameName: '', tagLine: '' })
const summoner = ref('')
const matches = ref<MatchOverview[]>([])
const topTumor = ref<TopTumor | null>(null)
const loading = ref(false)
const scanning = ref(false)
const error = ref('')
const recentSummoners = ref<string[]>(JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]'))

const saveRecent = (name: string) => {
  const list = [name, ...recentSummoners.value.filter(s => s !== name)].slice(0, MAX_RECENT)
  recentSummoners.value = list
  localStorage.setItem(RECENT_KEY, JSON.stringify(list))
}

const loadRecent = (entry: string) => {
  const [gameName, tagLine] = entry.split('#')
  formData.value = { gameName, tagLine }
  login()
}

const wins = computed(() => matches.value.filter(m => m.win).length)
const losses = computed(() => matches.value.filter(m => !m.win).length)

const formatDuration = (seconds: number) => {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s.toString().padStart(2, '0')}s`
}

const login = async () => {
  loading.value = true
  scanning.value = true
  error.value = ''

  try {
    const params = new URLSearchParams({
      game_name: formData.value.gameName,
      tag_line: formData.value.tagLine
    })

    const res = await fetch(`http://localhost:5000/getOverview?${params}`)
    const data = await res.json()

    if (!res.ok || data.error) {
      throw new Error(data.error || 'Error al cargar el overview')
    }

    // Hold the scan for at least 2.5s so the animation is visible
    await new Promise(r => setTimeout(r, 2500))

    summoner.value = data.summoner
    matches.value = data.matches
    topTumor.value = data.top_tumor ?? null
    saveRecent(data.summoner)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Error desconocido'
  } finally {
    loading.value = false
    scanning.value = false
  }
}

const logout = () => {
  summoner.value = ''
  matches.value = []
  topTumor.value = null
  formData.value = { gameName: '', tagLine: '' }
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
