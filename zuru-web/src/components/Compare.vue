<template>
  <div class="flex-1 flex flex-col bg-gradient-to-br from-[#0d0d1a] to-[#1a1a2e] overflow-y-auto">

    <!-- Search form -->
    <div v-if="!result" class="flex-1 flex justify-center items-center p-8">
      <div class="w-full max-w-xl">
        <div class="bg-black/30 backdrop-blur-md p-10 rounded-2xl text-center shadow-2xl mb-6 animate-fade">
          <h1 class="text-white font-mono text-4xl mb-2">Modo Versus</h1>
          <div class="h-[2px] w-[50%] mx-auto my-4 bg-gradient-to-r from-transparent via-purple-500 to-transparent"></div>
          <p class="text-white/40 text-sm">¿Quién fue peor en las partidas que compartisteis?</p>
        </div>

        <div class="bg-black/30 backdrop-blur-md p-8 rounded-2xl shadow-2xl animate-fade space-y-6">
          <!-- Player 1 -->
          <div>
            <p class="text-blue-400 text-xs font-mono font-bold tracking-widest mb-3">JUGADOR 1</p>
            <div class="flex gap-3">
              <input v-model="form.gameName1" type="text" placeholder="GameName"
                class="flex-1 px-4 py-3 bg-white/5 border border-blue-500/30 rounded-lg text-white placeholder-white/20 focus:outline-none focus:border-blue-400 transition font-mono" />
              <input v-model="form.tagLine1" type="text" placeholder="EUW"
                class="w-28 px-4 py-3 bg-white/5 border border-blue-500/30 rounded-lg text-white placeholder-white/20 focus:outline-none focus:border-blue-400 transition font-mono" />
            </div>
          </div>

          <!-- VS divider -->
          <div class="flex items-center gap-3">
            <div class="flex-1 h-px bg-white/10"></div>
            <span class="text-white/20 font-mono font-black text-lg">VS</span>
            <div class="flex-1 h-px bg-white/10"></div>
          </div>

          <!-- Player 2 -->
          <div>
            <p class="text-red-400 text-xs font-mono font-bold tracking-widest mb-3">JUGADOR 2</p>
            <div class="flex gap-3">
              <input v-model="form.gameName2" type="text" placeholder="GameName"
                class="flex-1 px-4 py-3 bg-white/5 border border-red-500/30 rounded-lg text-white placeholder-white/20 focus:outline-none focus:border-red-400 transition font-mono" />
              <input v-model="form.tagLine2" type="text" placeholder="EUW"
                class="w-28 px-4 py-3 bg-white/5 border border-red-500/30 rounded-lg text-white placeholder-white/20 focus:outline-none focus:border-red-400 transition font-mono" />
            </div>
          </div>

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
    <div v-else class="p-6 max-w-5xl mx-auto w-full">

      <!-- Header scorecard -->
      <div class="bg-black/30 rounded-2xl border border-white/10 p-6 mb-6 animate-fade">
        <div class="grid grid-cols-3 gap-4 items-center">

          <!-- Player 1 -->
          <div class="text-center">
            <p class="text-blue-400 text-[10px] font-mono tracking-widest mb-1">JUGADOR 1</p>
            <p class="text-white font-bold text-lg truncate">{{ result.player1_name }}</p>
            <div :class="result.score1 > result.score2 ? 'bg-red-900/40 border-red-500/40 text-red-400' : 'bg-green-900/20 border-green-500/20 text-green-400'"
              class="mt-2 inline-block border px-3 py-1 rounded-full text-xs font-mono font-bold">
              {{ result.score1 > result.score2 ? `☢ PEOR ${result.score1}x` : result.score1 === result.score2 ? '= EMPATE' : `✓ MEJOR ${result.score1 < result.score2 ? result.score2 - result.score1 : 0}` }}
            </div>
          </div>

          <!-- Score -->
          <div class="text-center">
            <p class="text-white/20 text-[10px] font-mono tracking-widest mb-2">PARTIDAS COMUNES</p>
            <p class="text-white font-black text-4xl font-mono">{{ result.common_matches }}</p>
            <div class="flex justify-center gap-3 mt-2">
              <span class="text-blue-400 font-mono font-bold text-xl">{{ result.score1 }}</span>
              <span class="text-white/20 font-mono text-xl">-</span>
              <span class="text-red-400 font-mono font-bold text-xl">{{ result.score2 }}</span>
            </div>
            <p class="text-white/20 text-[9px] font-mono mt-1">veces peor</p>
          </div>

          <!-- Player 2 -->
          <div class="text-center">
            <p class="text-red-400 text-[10px] font-mono tracking-widest mb-1">JUGADOR 2</p>
            <p class="text-white font-bold text-lg truncate">{{ result.player2_name }}</p>
            <div :class="result.score2 > result.score1 ? 'bg-red-900/40 border-red-500/40 text-red-400' : 'bg-green-900/20 border-green-500/20 text-green-400'"
              class="mt-2 inline-block border px-3 py-1 rounded-full text-xs font-mono font-bold">
              {{ result.score2 > result.score1 ? `☢ PEOR ${result.score2}x` : result.score1 === result.score2 ? '= EMPATE' : `✓ MEJOR` }}
            </div>
          </div>
        </div>
      </div>

      <!-- No common matches -->
      <div v-if="result.common_matches === 0" class="text-center py-16 animate-fade">
        <p class="text-white/30 font-mono text-lg">No se encontraron partidas comunes</p>
        <p class="text-white/20 text-sm mt-2">Comprobando las últimas 30 rankeds de cada jugador</p>
      </div>

      <!-- Match list -->
      <div v-else class="space-y-3">
        <div v-for="match in result.matches" :key="match.match_id"
          class="bg-black/30 rounded-xl border border-white/10 overflow-hidden hover:border-white/20 transition animate-fade">

          <!-- Same/rival team indicator -->
          <div class="px-4 pt-2 pb-1">
            <span :class="match.same_team ? 'text-green-400/60' : 'text-red-400/60'" class="text-[10px] font-mono">
              {{ match.same_team ? '🤝 Mismo equipo' : '⚔️ Equipo rival' }} · {{ formatDuration(match.game_duration) }}
            </span>
          </div>

          <div class="flex items-stretch">
            <!-- Player 1 -->
            <div :class="[
              'flex-1 flex items-center gap-3 px-4 pb-4',
              match.worse_player === 1 ? 'bg-red-950/30' : match.worse_player === 2 ? 'bg-green-950/20' : ''
            ]">
              <div class="relative shrink-0">
                <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${match.player1.campeon}.png`"
                  class="w-12 h-12 rounded-lg" />
                <span :class="match.player1.win ? 'bg-blue-500' : 'bg-red-500'"
                  class="absolute -bottom-1 -right-1 text-white text-[9px] font-bold px-1 rounded font-mono">
                  {{ match.player1.win ? 'W' : 'L' }}
                </span>
                <span v-if="match.worse_player === 1" class="absolute -top-2 -left-2 text-sm animate-spin-slow">☢️</span>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-blue-400 text-[10px] font-mono truncate">{{ result.player1_name }}</p>
                <p class="text-white text-sm font-bold">{{ match.player1.kills }}/{{ match.player1.deaths }}/{{ match.player1.assists }}</p>
                <p :class="match.player1.kda < 1 ? 'text-red-400' : match.player1.kda < 2 ? 'text-yellow-400' : 'text-green-400'"
                  class="text-xs font-mono font-bold">{{ match.player1.kda }} KDA</p>
              </div>
              <div class="text-right text-xs space-y-0.5">
                <p class="text-white/50 font-mono">{{ match.player1.cs }} CS</p>
                <p class="text-white/50 font-mono">{{ formatGold(match.player1.damage) }} DMG</p>
              </div>
            </div>

            <!-- VS divider -->
            <div class="flex items-center px-4 shrink-0">
              <span class="text-white/20 font-black font-mono text-sm">VS</span>
            </div>

            <!-- Player 2 -->
            <div :class="[
              'flex-1 flex items-center gap-3 px-4 pb-4 flex-row-reverse',
              match.worse_player === 2 ? 'bg-red-950/30' : match.worse_player === 1 ? 'bg-green-950/20' : ''
            ]">
              <div class="relative shrink-0">
                <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${match.player2.campeon}.png`"
                  class="w-12 h-12 rounded-lg" />
                <span :class="match.player2.win ? 'bg-blue-500' : 'bg-red-500'"
                  class="absolute -bottom-1 -left-1 text-white text-[9px] font-bold px-1 rounded font-mono">
                  {{ match.player2.win ? 'W' : 'L' }}
                </span>
                <span v-if="match.worse_player === 2" class="absolute -top-2 -right-2 text-sm animate-spin-slow">☢️</span>
              </div>
              <div class="flex-1 min-w-0 text-right">
                <p class="text-red-400 text-[10px] font-mono truncate">{{ result.player2_name }}</p>
                <p class="text-white text-sm font-bold">{{ match.player2.kills }}/{{ match.player2.deaths }}/{{ match.player2.assists }}</p>
                <p :class="match.player2.kda < 1 ? 'text-red-400' : match.player2.kda < 2 ? 'text-yellow-400' : 'text-green-400'"
                  class="text-xs font-mono font-bold">{{ match.player2.kda }} KDA</p>
              </div>
              <div class="text-left text-xs space-y-0.5">
                <p class="text-white/50 font-mono">{{ match.player2.cs }} CS</p>
                <p class="text-white/50 font-mono">{{ formatGold(match.player2.damage) }} DMG</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="pt-4 text-center">
        <button @click="result = null; error = ''"
          class="px-6 py-2 text-white/40 hover:text-white border border-white/10 hover:border-white/30 rounded-lg transition font-mono text-sm">
          Nueva comparación
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface ComparePlayer {
  campeon: string
  kills: number
  deaths: number
  assists: number
  kda: number
  cs: number
  damage: number
  win: boolean
}

interface CompareMatch {
  match_id: string
  game_duration: number
  same_team: boolean
  worse_player: number
  player1: ComparePlayer
  player2: ComparePlayer
}

interface CompareResult {
  player1_name: string
  player2_name: string
  common_matches: number
  score1: number
  score2: number
  matches: CompareMatch[]
}

const ddragonVersion = ref('15.1.1')
fetch('https://ddragon.leagueoflegends.com/api/versions.json')
  .then(r => r.json()).then(v => { ddragonVersion.value = v[0] }).catch(() => {})

const form = ref({ gameName1: '', tagLine1: '', gameName2: '', tagLine2: '' })
const result = ref<CompareResult | null>(null)
const loading = ref(false)
const error = ref('')

const formatDuration = (s: number) => `${Math.floor(s / 60)}m ${(s % 60).toString().padStart(2, '0')}s`
const formatGold = (g: number) => g >= 1000 ? `${(g / 1000).toFixed(1)}k` : String(g)

const search = async () => {
  const { gameName1, tagLine1, gameName2, tagLine2 } = form.value
  if (!gameName1 || !tagLine1 || !gameName2 || !tagLine2) {
    error.value = 'Rellena ambos jugadores'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({ game_name1: gameName1, tag_line1: tagLine1, game_name2: gameName2, tag_line2: tagLine2 })
    const res = await fetch(`http://localhost:5000/compare?${params}`)
    const data = await res.json()
    if (!res.ok || data.error) throw new Error(data.error || 'Error al comparar')
    result.value = data
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Error desconocido'
  } finally {
    loading.value = false
  }
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
