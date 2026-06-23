<script setup lang="ts">
// Extraído de Overview.vue para code-split (#16). Componente PURO de
// rendering — todo el state y handlers viven en Overview, este recibe
// props y emite events. Estrategia: no mover state ni timers, sólo el
// template. Lazy-loaded vía defineAsyncComponent así que el ~16KB de
// código JSX no entra al bundle inicial.

import {
  championIconUrl,
  championIconFallback,
  tumorColor,
  tumorLabel,
  ROLE_LABEL,
  RUNE_STYLES,
  SUMMONER_SPELLS,
  TIER_COLORS,
} from '../composables/overviewConstants'
import TumorScoreCounter from './TumorScoreCounter.vue'

// Alias del map de tier colors usado en el template original.
const tierColor = TIER_COLORS

// El padre (Overview) tiene una interface LivePlayer con MUCHOS más campos
// (role, champion_pct, recent_losses, etc.) — los tipamos como any aquí
// porque este componente sólo renderiza scalars del player y no
// estructura la lógica que valida esos campos. Si tipamos estrictos,
// TS no acepta el LivePlayer del padre como subtype del nuestro.
type LivePlayer = Record<string, any>

interface Ban { team_id: number; champion_id: number; champion_name: string }

interface LiveGame {
  match_id?: string
  game_id?: number
  queue_id?: number
  bans?: Ban[]
  players: LivePlayer[]
  prediction?: unknown
}

defineProps<{
  show: boolean
  liveGame: LiveGame | null
  liveLoading: boolean
  liveError: string
  liveProgress: { step: string; progress: number; total: number }
  predictionStats: {
    total: number
    correct: number
    accuracy: number
    pending: number
    current_streak?: number
    max_streak?: number
    scope?: 'user' | 'global'
  } | null
  livePrediction: {
    blueTumor: number
    redTumor: number
    winner: 'blue' | 'red' | 'tie'
    confidence: number
  }
  hasPrediction: boolean
  isArena: boolean
  isLiveQueueBettable: boolean
  blacklistedInTeam: LivePlayer[]
  arenaSortedPlayers: LivePlayer[]
  laneMatchups: Array<{
    role: string
    blue: LivePlayer
    red: LivePlayer
    edge: 'blue' | 'red' | 'tie'
  }>
  championBlacklist: string[]
  champData: Record<string, string>
  ddragonVersion: string
  resolving: boolean
  resolveResult: { predicted: string; actual: string; correct: boolean } | null
  existingPlayerBet: { target_puuid?: string } | null
  /** Devuelve true si se puede apostar contra este player (función del padre
   *  que conoce currency, existingPlayerBet, queue, etc). */
  canBetPlayer: (p: LivePlayer) => boolean
  /** Slug-ify del riot_id para hash-link al perfil del player. */
  profileUrl: (nombre: string) => string
}>()

const emit = defineEmits<{
  close: []
  openCreateBet: []
  openPlayerBet: [player: LivePlayer]
  toggleBlacklist: [championName: string]
  resolveLivePrediction: []
  retryRefresh: []
}>()

// Spell icon URL se construye inline en el template usando SUMMONER_SPELLS
// + la prop ddragonVersion, así que no hace falta helper aquí.

// SIDES const: extraído del template para que la referencia de array no se
// recree en cada render (verify cazó que `v-for="side in [{...}, {...}]"`
// inline mata la estabilidad de keys del v-for outer).
const SIDES = [
  { id: 100, label: 'EQUIPO AZUL', color: 'text-blue-400' },
  { id: 200, label: 'EQUIPO ROJO', color: 'text-red-400' },
] as const
</script>

<template>
  <!-- `appear` necesario: el modal está en un chunk lazy y se monta con
       `show=true` ya activo en la primera apertura, lo que Vue trata como
       render inicial (sin enter animation). Mismo bug detectado en
       AnalyticsModal — extiendo el fix por paridad. -->
  <Transition name="modal" appear>
    <div v-if="show" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start sm:items-center justify-center overflow-y-auto p-4 pt-[6vh] sm:pt-4"
      @click.self="emit('close')">
      <div class="bg-theme-from border border-red-500/30 rounded-2xl shadow-2xl shadow-red-900/30 w-full max-w-5xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div class="flex items-center gap-3">
            <span class="inline-block w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse"></span>
            <p class="text-white font-mono font-bold">Partida en directo · Predicción de tumor</p>
            <div v-if="predictionStats && predictionStats.total > 0"
              class="flex items-center gap-1.5 bg-accent-10 border border-accent-30 px-2.5 py-1 rounded-lg">
              <span class="text-[9px] font-mono text-white/50 tracking-widest">
                {{ predictionStats.scope === 'user' ? 'TU ACIERTO' : 'ACIERTO GLOBAL' }}
              </span>
              <span :class="predictionStats.accuracy >= 60 ? 'text-green-400' : predictionStats.accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'"
                class="text-xs font-mono font-bold">{{ predictionStats.accuracy }}%</span>
              <span class="text-white/30 text-[9px] font-mono">({{ predictionStats.correct }}/{{ predictionStats.total }})</span>
            </div>
            <div v-if="predictionStats && predictionStats.scope === 'user' && (predictionStats.current_streak ?? 0) >= 2"
              class="flex items-center gap-1.5 bg-green-900/30 border border-green-500/50 px-2.5 py-1 rounded-lg"
              :class="(predictionStats.current_streak ?? 0) >= 5 ? 'animate-pulse shadow-lg shadow-green-900/40' : ''"
              :title="`Racha actual de aciertos: ${predictionStats.current_streak}. Máxima: ${predictionStats.max_streak || 0}`">
              <span class="text-sm">{{ (predictionStats.current_streak ?? 0) >= 5 ? '🔥' : (predictionStats.current_streak ?? 0) >= 3 ? '⚡' : '✨' }}</span>
              <span class="text-green-400 text-xs font-mono font-bold">{{ predictionStats.current_streak }}</span>
              <span class="text-white/30 text-[9px] font-mono">aciertos</span>
            </div>
          </div>
          <button @click="emit('close')" class="text-white/40 hover:text-white text-xl transition">✕</button>
        </div>

        <div v-if="liveLoading" class="flex flex-col items-center justify-center py-12 gap-4 px-8">
          <p class="text-white/70 font-mono text-sm">{{ liveProgress.step || 'Iniciando...' }}</p>
          <div class="w-full max-w-md bg-white/5 border border-white/10 rounded-full h-2 overflow-hidden">
            <div class="h-full bg-gradient-to-r from-red-500 to-orange-400 transition-all duration-500"
              :style="{ width: `${Math.min(100, (liveProgress.progress / Math.max(1, liveProgress.total)) * 100)}%` }"></div>
          </div>
          <p class="text-white/30 font-mono text-[10px]">{{ liveProgress.progress }}/{{ liveProgress.total }}</p>
        </div>

        <div v-else-if="liveError" class="py-16 text-center">
          <p class="text-red-400 font-mono text-sm">{{ liveError }}</p>
        </div>

        <div v-else-if="liveGame" class="p-4 sm:p-6">
          <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">
            Tumor score promedio basado en últimas rankeds de cada jugador
          </p>

          <!-- Bans -->
          <div v-if="liveGame.bans && liveGame.bans.length" class="mb-3 flex items-center gap-3 bg-black/30 border border-white/10 rounded-xl px-3 py-2 flex-wrap">
            <span class="text-white/30 text-[10px] font-mono tracking-widest">BANS</span>
            <div class="flex gap-1.5 flex-wrap">
              <img v-for="b in liveGame.bans" :key="`${b.team_id}-${b.champion_id}`"
                :src="championIconUrl(b.champion_name, ddragonVersion)"
                @error="championIconFallback"
                :alt="b.champion_name"
                :title="b.champion_name"
                class="w-7 h-7 rounded border border-white/10 grayscale opacity-70" />
            </div>
          </div>

          <!-- Blacklist warning -->
          <div v-if="blacklistedInTeam.length"
            class="mb-3 flex items-center gap-3 bg-red-950/40 border border-red-500/40 rounded-xl px-4 py-2.5 animate-pulse">
            <span class="text-2xl">🚫</span>
            <div class="flex-1">
              <p class="text-red-300 font-mono text-sm font-bold">Champ en blacklist en tu equipo</p>
              <p class="text-red-400/70 text-[11px] font-mono">
                {{ blacklistedInTeam.map(p => p.champion_display_name || p.champion_name).join(', ') }} — históricamente pierdes con estos picks
              </p>
            </div>
          </div>

          <!-- Arena (1700): lista plana ordenada por tumor prior. -->
          <div v-if="isArena" class="mb-4">
            <p class="text-white/30 text-[10px] font-mono tracking-widest mb-2">⚔ ARENA · 16 JUGADORES (peor prior arriba)</p>
            <p class="text-white/40 text-[10px] font-mono italic mb-3">
              Riot no expone los duos en partida en directo (solo tras acabar). Aquí van los 16 ordenados por su tumor prior individual — fíjate en los de arriba.
            </p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              <div v-for="(p, idx) in arenaSortedPlayers" :key="p.puuid"
                class="bg-black/30 border rounded-lg px-2.5 py-1.5 flex items-center gap-2"
                :class="p.is_me ? 'border-yellow-500/50 bg-yellow-900/10' : 'border-white/10'">
                <span class="text-white/30 text-[9px] font-mono w-5 text-center">#{{ idx + 1 }}</span>
                <img v-if="p.champion_name"
                  :src="championIconUrl(p.champion_name, ddragonVersion)"
                  @error="championIconFallback"
                  class="w-7 h-7 rounded shrink-0" />
                <div class="flex-1 min-w-0">
                  <p class="text-[11px] font-mono truncate"
                    :class="p.is_me ? 'text-yellow-300 font-bold' : 'text-white/80'">
                    {{ p.nombre.split('#')[0] }}
                  </p>
                  <p class="text-white/40 text-[9px] font-mono truncate">{{ p.champion_display_name || p.champion_name }} · {{ p.tier || '?' }}</p>
                </div>
                <div class="flex items-center gap-1 shrink-0">
                  <span v-if="p.is_tilted" title="Tilteado">🌋</span>
                  <span v-if="p.is_hotstreak" title="Hot streak">🔥</span>
                  <span v-if="p.streamer_mode" class="text-white/30 text-[9px]" title="Streamer mode">📺</span>
                  <span v-if="p.avg_tumor_score !== null && p.avg_tumor_score !== undefined" :class="tumorColor(p.avg_tumor_score)"
                    class="font-bold font-mono text-sm w-7 text-right">{{ p.avg_tumor_score }}</span>
                  <span v-else class="text-white/20 text-xs w-7 text-right">?</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Win prediction · solo 5v5 -->
          <div v-else-if="hasPrediction" class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4 items-center">
            <div class="bg-blue-950/40 border rounded-xl px-4 py-3 text-center"
              :class="livePrediction.winner === 'blue' ? 'border-blue-400/70 shadow-lg shadow-blue-500/20' : 'border-blue-500/20'">
              <p class="text-blue-400 text-[10px] font-mono tracking-widest">EQUIPO AZUL</p>
              <p :class="tumorColor(livePrediction.blueTumor)" class="text-3xl font-mono font-black mt-1">{{ livePrediction.blueTumor }}</p>
              <p class="text-blue-300/60 text-[9px] font-mono">tumor de equipo</p>
            </div>
            <div class="text-center">
              <p class="text-white/40 text-[9px] font-mono tracking-widest mb-1">PREDICCIÓN</p>
              <p class="text-2xl">{{ livePrediction.winner === 'blue' ? '🔵' : livePrediction.winner === 'red' ? '🔴' : '⚖️' }}</p>
              <p :class="livePrediction.winner === 'blue' ? 'text-blue-300' : livePrediction.winner === 'red' ? 'text-red-300' : 'text-white/50'"
                class="text-[10px] font-mono font-bold mt-1">
                {{ livePrediction.winner === 'blue' ? 'GANA AZUL' : livePrediction.winner === 'red' ? 'GANA ROJO' : 'IGUALADO' }}
              </p>
              <p class="text-white/30 text-[9px] font-mono mt-0.5">{{ livePrediction.confidence }}% conf.</p>
            </div>
            <div class="bg-red-950/40 border rounded-xl px-4 py-3 text-center"
              :class="livePrediction.winner === 'red' ? 'border-red-400/70 shadow-lg shadow-red-500/20' : 'border-red-500/20'">
              <p class="text-red-400 text-[10px] font-mono tracking-widest">EQUIPO ROJO</p>
              <p :class="tumorColor(livePrediction.redTumor)" class="text-3xl font-mono font-black mt-1">{{ livePrediction.redTumor }}</p>
              <p class="text-red-300/60 text-[9px] font-mono">tumor de equipo</p>
            </div>
          </div>

          <!-- ARAM / otros queues -->
          <div v-else class="mb-4 bg-black/20 border border-white/10 rounded-xl p-3 text-center">
            <p class="text-white/50 text-xs font-mono">
              Queue {{ liveGame?.queue_id }} no tiene predicción de tumor de equipo. Mira los priors individuales abajo.
            </p>
          </div>

          <!-- CTA principal: Apostar -->
          <div v-if="liveGame && liveGame.match_id && isLiveQueueBettable" class="mb-3">
            <button @click="emit('openCreateBet')"
              class="w-full bg-[#c89b3c]/15 hover:bg-[#c89b3c]/25 border border-[#c89b3c]/50 hover:border-[#c89b3c] text-[#c89b3c] hover:text-[#e0b84e] font-mono font-bold text-sm px-5 py-2.5 rounded-lg transition flex items-center justify-center gap-2"
              title="Apuesta TC sobre el resultado de esta partida">
              <span class="text-base">☢</span>
              <span class="tracking-widest">APOSTAR</span>
              <span class="text-[10px] text-[#c89b3c]/60 font-normal hidden sm:inline">· P2P o vs sistema</span>
            </button>
          </div>

          <!-- Acciones secundarias -->
          <div class="flex items-center justify-center gap-3 mb-4 flex-wrap">
            <button @click="emit('resolveLivePrediction')" :disabled="resolving"
              class="text-xs font-mono px-3 py-1.5 border border-white/15 text-white/60 hover:text-accent hover:border-accent-40 rounded transition disabled:opacity-30">
              {{ resolving ? 'Comprobando...' : '✅ Comprobar resultado' }}
            </button>
            <button @click="emit('retryRefresh')" :disabled="liveLoading"
              class="text-xs font-mono px-3 py-1.5 border border-white/15 text-white/60 hover:text-accent hover:border-accent-40 rounded transition disabled:opacity-30"
              title="Recalcula priors saltando la caché de 6h">
              ↻ Forzar refresh
            </button>
            <span v-if="liveGame && liveGame.match_id && !isLiveQueueBettable"
              class="text-[11px] font-mono px-2 py-1.5 text-white/30 italic"
              title="Apuestas solo en SoloQ y Flex">
              🚫 sin apuestas (no ranked)
            </span>
            <div v-if="resolveResult" class="text-xs font-mono flex items-center gap-2">
              <template v-if="(resolveResult as any).pending">
                <span class="text-yellow-400">⏳ {{ (resolveResult as any).pending }}</span>
              </template>
              <template v-else>
                <span :class="resolveResult.correct ? 'text-green-400' : 'text-red-400'">{{ resolveResult.correct ? '✓ ACERTÓ' : '✗ FALLÓ' }}</span>
                <span class="text-white/40">predijo {{ resolveResult.predicted === 'blue' ? '🔵' : resolveResult.predicted === 'red' ? '🔴' : '⚖️' }} · ganó {{ resolveResult.actual === 'blue' ? '🔵' : '🔴' }}</span>
              </template>
            </div>
          </div>

          <!-- Lane matchups -->
          <div v-if="laneMatchups.length" class="mb-4 bg-black/20 border border-white/10 rounded-xl p-3">
            <p class="text-white/30 text-[10px] font-mono tracking-widest mb-2">⚔ MATCHUPS POR LÍNEA</p>
            <div class="space-y-1.5">
              <div v-for="m in laneMatchups" :key="m.role"
                class="grid grid-cols-[44px_1fr_50px_1fr] gap-2 items-center text-[11px] font-mono">
                <span class="text-white/50 text-[10px] font-bold text-center">{{ ROLE_LABEL[m.role] || m.role.slice(0,3) }}</span>
                <div class="flex items-center gap-2 justify-end min-w-0"
                  :class="m.edge === 'blue' ? 'text-blue-300' : m.edge === 'red' ? 'text-white/40' : 'text-white/60'">
                  <span class="truncate text-[10px]">{{ m.blue.nombre.split('#')[0] }}</span>
                  <span :class="tumorColor(m.blue.avg_tumor_score ?? 0)" class="font-bold w-6 text-right">{{ m.blue.avg_tumor_score ?? '?' }}</span>
                </div>
                <div class="text-center">
                  <span v-if="m.edge === 'blue'" class="text-blue-400">◀</span>
                  <span v-else-if="m.edge === 'red'" class="text-red-400">▶</span>
                  <span v-else class="text-white/20">=</span>
                </div>
                <div class="flex items-center gap-2 min-w-0"
                  :class="m.edge === 'red' ? 'text-red-300' : m.edge === 'blue' ? 'text-white/40' : 'text-white/60'">
                  <span :class="tumorColor(m.red.avg_tumor_score ?? 0)" class="font-bold w-6">{{ m.red.avg_tumor_score ?? '?' }}</span>
                  <span class="truncate text-[10px]">{{ m.red.nombre.split('#')[0] }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Teams (5v5) -->
          <div v-if="!isArena" class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <template v-for="side in SIDES" :key="side.id">
              <div>
                <p :class="side.color" class="text-[11px] font-mono font-bold mb-2 tracking-widest">{{ side.label }}</p>
                <div class="space-y-2">
                  <div v-for="p in liveGame.players.filter(x => x.team_id === side.id)" :key="p.puuid"
                    :class="p.is_me ? 'border-accent-50 bg-accent-10' : 'border-white/10'"
                    class="flex items-center gap-3 bg-black/30 border rounded-xl p-3">
                    <div class="relative shrink-0">
                      <img v-if="champData[String(p.champion_id)]"
                        :src="championIconUrl(champData[String(p.champion_id)], ddragonVersion)"
                        @error="championIconFallback"
                        class="w-12 h-12 rounded-lg border border-white/20 transition-transform duration-200 hover:scale-110" />
                      <div class="absolute -right-1 top-0 flex flex-col gap-0.5">
                        <img v-if="p.spell1_id && SUMMONER_SPELLS[p.spell1_id]"
                          :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/spell/${SUMMONER_SPELLS[p.spell1_id]}.png`"
                          class="w-4 h-4 rounded-sm border border-black/60" />
                        <img v-if="p.spell2_id && SUMMONER_SPELLS[p.spell2_id]"
                          :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/spell/${SUMMONER_SPELLS[p.spell2_id]}.png`"
                          class="w-4 h-4 rounded-sm border border-black/60" />
                      </div>
                      <div v-if="p.perks && p.perks.primary" class="absolute -left-1 -bottom-1 flex gap-0.5">
                        <span class="w-3 h-3 rounded-full border border-black/60"
                          :style="{ background: (RUNE_STYLES[p.perks.primary || 0]?.color || '#666') }"
                          :title="RUNE_STYLES[p.perks.primary || 0]?.name || ''"></span>
                        <span v-if="p.perks.secondary" class="w-2 h-2 rounded-full border border-black/60 self-end"
                          :style="{ background: (RUNE_STYLES[p.perks.secondary || 0]?.color || '#666') }"
                          :title="RUNE_STYLES[p.perks.secondary || 0]?.name || ''"></span>
                      </div>
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-1.5 flex-wrap">
                        <span v-if="p.is_watched" title="En tu watch list" class="text-base">💀</span>
                        <a v-if="!p.streamer_mode" :href="profileUrl(p.nombre)" target="_blank" rel="noopener"
                          class="text-white text-sm font-mono truncate hover:text-accent hover:underline transition"
                          :class="p.is_watched ? 'text-red-300' : ''"
                          :title="`Abrir perfil de ${p.nombre}`">{{ p.nombre }}{{ p.is_me ? ' (TÚ)' : '' }}</a>
                        <p v-else class="text-white/60 text-sm font-mono truncate italic">{{ p.nombre }}</p>
                        <span v-if="p.streamer_mode" title="Modo streamer activado — score estimado con la media del equipo"
                          class="text-[9px] font-mono font-bold bg-sky-500/20 border border-sky-400/40 text-sky-300 px-1.5 py-0.5 rounded">🥷 STREAMER</span>
                        <span v-if="p.is_main" class="text-[9px] font-mono font-bold bg-purple-500/20 border border-purple-400/40 text-purple-300 px-1.5 py-0.5 rounded">🎯 MAIN</span>
                        <span v-if="p.smurf_signals && p.smurf_signals.length"
                          :title="p.smurf_signals.join(' · ')"
                          class="text-[9px] font-mono font-bold bg-pink-500/20 border border-pink-400/40 text-pink-300 px-1.5 py-0.5 rounded animate-pulse">🥷 SUS</span>
                        <span v-if="p.is_tilted" title="Tilteado: últimas 3 partidas muy malas"
                          class="text-[9px] font-mono font-bold bg-orange-500/20 border border-orange-400/40 text-orange-300 px-1.5 py-0.5 rounded animate-pulse">🔥 TILT</span>
                        <span v-if="p.is_hotstreak" title="Hotstreak: últimas 3 partidas jugando muy bien"
                          class="text-[9px] font-mono font-bold bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 px-1.5 py-0.5 rounded">📈 HOT</span>
                        <span v-if="p.duo_group"
                          title="Posible duo detectado en partidas recientes"
                          class="text-[9px] font-mono font-bold bg-cyan-500/20 border border-cyan-400/40 text-cyan-300 px-1.5 py-0.5 rounded">DUO {{ p.duo_group }}</span>
                        <button @click.stop="emit('toggleBlacklist', p.champion_name)" :title="championBlacklist.includes(p.champion_name) ? 'Quitar de blacklist' : 'Añadir a blacklist'"
                          class="text-[9px] font-mono px-1 py-0.5 rounded border transition"
                          :class="championBlacklist.includes(p.champion_name) ? 'bg-red-500/20 border-red-400/40 text-red-300' : 'border-white/10 text-white/30 hover:text-red-300 hover:border-red-500/40'">
                          {{ championBlacklist.includes(p.champion_name) ? '🚫' : '+' }}
                        </button>
                      </div>
                      <div class="flex items-center gap-2 flex-wrap">
                        <p :class="tierColor[p.tier] ?? 'text-white/40'" class="text-[10px] font-mono">{{ p.tier }} {{ p.division }}</p>
                        <p v-if="p.estimated_games && p.estimated_games > 0" class="text-[10px] font-mono text-white/50">
                          · ~{{ p.estimated_games }} games
                          <span class="text-white/30">(M{{ p.mastery_level }})</span>
                        </p>
                        <p v-if="p.champion_winrate !== null && p.champion_winrate !== undefined" class="text-[10px] font-mono"
                          :class="p.champion_winrate >= 60 ? 'text-green-400' : p.champion_winrate >= 50 ? 'text-yellow-400' : 'text-red-400'">
                          · {{ p.champion_winrate }}% WR ({{ p.champion_games }}/{{ p.champion_total_sample }})
                        </p>
                      </div>
                    </div>
                    <div class="text-right flex flex-col items-end gap-0.5">
                      <p :class="[tumorColor(p.avg_tumor_score ?? 0), p.score_is_team_avg ? 'opacity-60 italic' : '']" class="text-2xl font-mono font-bold leading-none">
                        <template v-if="typeof p.avg_tumor_score === 'number'">
                          <TumorScoreCounter :value="p.avg_tumor_score" />{{ p.score_is_team_avg ? '*' : '' }}
                        </template>
                        <template v-else>?</template>
                      </p>
                      <p class="text-white/30 text-[9px] font-mono">{{ p.score_is_team_avg ? 'media equipo' : tumorLabel(p.avg_tumor_score ?? 0) }}</p>
                      <button v-if="canBetPlayer(p)" @click.stop="emit('openPlayerBet', p)"
                        class="text-[10px] mt-0.5 px-1.5 py-0.5 rounded border border-yellow-500/40 text-yellow-300 hover:bg-yellow-900/20 hover:border-yellow-400/70 transition font-mono"
                        title="Apostar a que este jugador será sus">
                        🎯 apostar
                      </button>
                      <span v-else-if="!p.is_me && existingPlayerBet && existingPlayerBet.target_puuid === p.puuid"
                        class="text-[9px] text-yellow-400 font-mono italic"
                        title="Ya apostaste a este jugador">
                        🎯 apostado
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* Misma transition "modal" que el resto: fade simple del backdrop. Sin
   esto el v-if entraría/saldría sin animación cuando este componente
   está aislado del CSS scoped del Overview. */
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
