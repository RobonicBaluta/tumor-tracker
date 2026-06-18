<script setup lang="ts">
// Extraído de Overview.vue para code-split (#16 cont.). Mismo patrón que
// LiveGameModal de la sesión anterior: template-only extraction. TODO el
// state, refs, watchers, fetch handlers (loadAnalytics, runBacktest,
// loadDeathHeatmap, drawHeatmap, backtestPoller, resize listener) vive en
// Overview. Este componente sólo RENDERIZA props y emite events para que
// el padre dispare las mutations correspondientes.
//
// Bonus: el canvas del heatmap se expone via defineExpose para que el
// padre pueda seguir llamando a drawHeatmap sobre el mismo canvas DOM.

import { ref } from 'vue'
import {
  championIconUrl,
  championIconFallback,
  tumorColor,
} from '../composables/overviewConstants'

// Tipos LAXOS — el parent tiene interfaces estrictas, aquí Record<string,any>
// para evitar TS contravariance (igual que con LivePlayer en LiveGameModal).
type AnyObj = Record<string, any>

interface AnalyticsFilters {
  champion: string
  role: string
  result: string
  count: number
}

defineProps<{
  show: boolean
  analyticsData: AnyObj | null
  analyticsLoading: boolean
  analyticsError: string
  /** v-model:filters="analyticsFilters" desde el padre. El modal emite
   *  update:filters al cambiar cualquier select. */
  filters: AnalyticsFilters
  backtestData: AnyObj | null
  backtestLoading: boolean
  backtestProgress: { step: string; progress: number; total: number }
  heatmapData: AnyObj | null
  heatmapLoading: boolean
  /** Sort key activo para la sección Duos (parent owns it). */
  duoSortBy: 'combined' | 'games' | 'winrate'
  /** Lista ya sorted que el padre computa. */
  sortedDuos: AnyObj[]
  /** Computeds que dependen de analyticsData; calculados en el padre para
   *  no duplicar lógica entre modal y resto del overview. */
  hourly24: Array<{ hour: number; games: number; winrate: number; avg_tumor: number }>
  hourMaxTumor: number
  weekDelta: { better: boolean; pct: number } | null
  evolutionPoints: Array<{ x: number; y: number; win: boolean; champion: string; tumor: number }>
  evolutionLinePoints: string
  evolutionAreaPath: string
  loadingFlavor: string
  summoner: string
  ddragonVersion: string
  profileUrl: (nombre: string) => string
}>()

const emit = defineEmits<{
  close: []
  'update:filters': [filters: AnalyticsFilters]
  'reset-filters': []
  'load-analytics': []
  'run-backtest': []
  'load-heatmap': []
  'open-champ-stats': [name: string]
  'update-duo-sort': [sort: 'combined' | 'games' | 'winrate']
}>()

// Canvas DOM ref local — el padre lo accede via defineExpose y le pinta
// el heatmap. Sin esto, drawHeatmap del padre no sabría qué canvas tocar
// porque vive aquí en el modal.
// IMPORTANTE: Vue 3 auto-desempaqueta refs cuando se exponen via defineExpose.
// El padre lee `analyticsModalRef.value.heatmapCanvas` y obtiene directamente
// `HTMLCanvasElement | null` (NO `Ref<HTMLCanvasElement | null>`). Si en el
// futuro envuelves esto en computed/reactive/getter explícito, el contrato
// cambia y drawHeatmap del padre se rompe.
const heatmapCanvas = ref<HTMLCanvasElement | null>(null)
defineExpose({ heatmapCanvas })

// Helper: emit update:filters cambiando un solo field. Usado por cada
// <select> en el filter bar. Crea un nuevo objeto en lugar de mutar la
// prop (read-only por contract).
function updateFilter<K extends keyof AnalyticsFilters>(
  filtersValue: AnalyticsFilters,
  key: K,
  value: AnalyticsFilters[K],
) {
  emit('update:filters', { ...filtersValue, [key]: value })
  emit('load-analytics')
}
</script>

<template>
  <!-- `appear` para que la PRIMERA apertura tenga animación de entrada.
       Sin él, como el modal vive en un chunk lazy, el Transition wrapper se
       monta con `show=true` ya activo y Vue interpreta ese frame inicial como
       render no animado. Bug real cazado por la review adversaria. -->
  <Transition name="modal" appear>
    <div v-if="show" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start sm:items-center justify-center overflow-y-auto p-4 pt-[8vh] sm:pt-4"
      @click.self="emit('close')">
      <div class="bg-theme-from border border-purple-500/30 rounded-2xl shadow-2xl shadow-purple-900/30 w-full max-w-5xl max-h-[92vh] overflow-y-auto">
        <div class="flex items-center justify-between px-6 py-4 border-b border-white/10 sticky top-0 bg-theme-from/95 backdrop-blur z-10">
          <p class="text-white font-mono font-bold">📊 Analíticas · {{ summoner }}</p>
          <button @click="emit('close')" class="text-white/40 hover:text-white text-xl transition">✕</button>
        </div>

        <div v-if="analyticsLoading" class="flex items-center justify-center py-16">
          <div class="w-full max-w-2xl px-6 py-8">
            <p class="text-white/50 font-mono text-xs text-center mb-6 animate-pulse" :key="loadingFlavor">{{ loadingFlavor }}</p>
            <div class="space-y-5">
              <div class="bg-white/5 rounded-xl p-5 h-24 shimmer"></div>
              <div class="bg-white/5 rounded-xl p-5 h-40 shimmer"></div>
              <div class="grid grid-cols-3 gap-3">
                <div class="bg-white/5 rounded-xl h-20 shimmer"></div>
                <div class="bg-white/5 rounded-xl h-20 shimmer"></div>
                <div class="bg-white/5 rounded-xl h-20 shimmer"></div>
              </div>
            </div>
          </div>
        </div>
        <div v-else-if="analyticsError" class="py-16 text-center">
          <p class="text-red-400 font-mono text-sm">{{ analyticsError }}</p>
        </div>
        <div v-else-if="analyticsData" class="p-4 sm:p-6 space-y-8">

          <!-- Filter bar -->
          <section>
            <p class="text-white/30 text-[10px] font-mono tracking-widest mb-2">🔎 FILTROS</p>
            <div class="flex flex-wrap gap-2 items-center bg-black/30 border border-white/10 rounded-xl p-3">
              <select :value="filters.role" @change="updateFilter(filters, 'role', ($event.target as HTMLSelectElement).value)"
                class="bg-black/40 border border-white/15 text-white/70 text-xs font-mono rounded px-2 py-1">
                <option value="">Cualquier rol</option>
                <option value="TOP">Top</option>
                <option value="JUNGLE">Jungle</option>
                <option value="MIDDLE">Mid</option>
                <option value="BOTTOM">ADC</option>
                <option value="UTILITY">Support</option>
              </select>
              <select :value="filters.result" @change="updateFilter(filters, 'result', ($event.target as HTMLSelectElement).value)"
                class="bg-black/40 border border-white/15 text-white/70 text-xs font-mono rounded px-2 py-1">
                <option value="">Todas</option>
                <option value="win">Solo wins</option>
                <option value="loss">Solo losses</option>
              </select>
              <select :value="filters.champion" @change="updateFilter(filters, 'champion', ($event.target as HTMLSelectElement).value)"
                class="bg-black/40 border border-white/15 text-white/70 text-xs font-mono rounded px-2 py-1 max-w-[160px]">
                <option value="">Cualquier champ</option>
                <option v-for="c in (analyticsData.champion_pool || [])" :key="c.champion" :value="c.champion">
                  {{ c.champion }} ({{ c.games }})
                </option>
              </select>
              <select :value="filters.count" @change="updateFilter(filters, 'count', Number(($event.target as HTMLSelectElement).value))"
                class="bg-black/40 border border-white/15 text-white/70 text-xs font-mono rounded px-2 py-1">
                <option :value="20">Últimas 20</option>
                <option :value="30">Últimas 30</option>
                <option :value="50">Últimas 50</option>
              </select>
              <button @click="emit('reset-filters'); emit('load-analytics')"
                class="text-[11px] font-mono text-white/40 hover:text-white/70 px-2 py-1 border border-white/10 rounded">Reset</button>
              <span class="text-white/30 text-[10px] font-mono ml-auto">{{ analyticsData.total_matches }} partidas</span>
            </div>
          </section>

          <!-- Backtest del modelo -->
          <section>
            <div class="flex items-center justify-between mb-3">
              <p class="text-white/30 text-[10px] font-mono tracking-widest">🧪 BACKTEST DEL PREDICTOR</p>
              <button @click="emit('run-backtest')" :disabled="backtestLoading"
                class="text-[11px] font-mono px-2.5 py-1 border border-purple-500/40 text-purple-300 hover:border-purple-400/80 rounded disabled:opacity-40">
                {{ backtestLoading ? 'Procesando...' : (backtestData ? 'Volver a ejecutar' : 'Ejecutar') }}
              </button>
            </div>
            <div v-if="backtestLoading" class="bg-black/30 border border-purple-500/20 rounded-xl p-4 space-y-3">
              <p class="text-purple-200 font-mono text-xs">{{ backtestProgress.step || 'Procesando...' }}</p>
              <div class="w-full bg-white/5 border border-white/10 rounded-full h-2 overflow-hidden">
                <div class="h-full bg-gradient-to-r from-purple-500 to-fuchsia-400 transition-all duration-500"
                  :style="{ width: `${Math.min(100, (backtestProgress.progress / Math.max(1, backtestProgress.total)) * 100)}%` }"></div>
              </div>
              <p class="text-white/40 font-mono text-[10px]">{{ backtestProgress.progress }}/{{ backtestProgress.total }} partidas — sigue navegando, te avisamos al terminar 🔔</p>
            </div>
            <div v-else-if="backtestData" class="bg-black/30 border border-purple-500/20 rounded-xl p-4">
              <div class="flex items-baseline gap-6">
                <div>
                  <p :class="backtestData.accuracy >= 60 ? 'text-green-400' : backtestData.accuracy >= 50 ? 'text-yellow-400' : 'text-red-400'"
                    class="text-4xl font-mono font-black">{{ backtestData.accuracy }}%</p>
                  <p class="text-white/40 text-[10px] font-mono">acierto real</p>
                </div>
                <div class="text-sm font-mono text-white/60">
                  <p>{{ backtestData.correct }} / {{ backtestData.total }} aciertos</p>
                  <p class="text-white/30 text-xs">{{ backtestData.ties }} partidas sin predicción clara</p>
                </div>
              </div>
            </div>
            <p v-else class="text-white/30 font-mono text-xs">Ejecuta el modelo sobre tus últimas 20 partidas ya acabadas para ver su acierto real.</p>
          </section>

          <!-- Lane diff -->
          <section v-if="analyticsData.lane_diff">
            <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">⚔ DIFF VS TU LANER</p>
            <div class="bg-black/30 border border-white/10 rounded-xl p-4">
              <div class="grid grid-cols-4 gap-4 text-center">
                <div>
                  <p :class="analyticsData.lane_diff.win_lane_rate >= 50 ? 'text-green-400' : 'text-red-400'"
                    class="text-3xl font-mono font-black">{{ analyticsData.lane_diff.win_lane_rate }}%</p>
                  <p class="text-white/40 text-[10px] font-mono">ganaste lane</p>
                </div>
                <div>
                  <p :class="analyticsData.lane_diff.avg_cs_diff > 0 ? 'text-green-400' : 'text-red-400'"
                    class="text-2xl font-mono font-black">{{ analyticsData.lane_diff.avg_cs_diff > 0 ? '+' : '' }}{{ analyticsData.lane_diff.avg_cs_diff }}</p>
                  <p class="text-white/40 text-[10px] font-mono">CS diff</p>
                </div>
                <div>
                  <p :class="analyticsData.lane_diff.avg_dmg_diff > 0 ? 'text-green-400' : 'text-red-400'"
                    class="text-2xl font-mono font-black">{{ analyticsData.lane_diff.avg_dmg_diff > 0 ? '+' : '' }}{{ Math.round(analyticsData.lane_diff.avg_dmg_diff / 1000) }}k</p>
                  <p class="text-white/40 text-[10px] font-mono">DMG diff</p>
                </div>
                <div>
                  <p :class="analyticsData.lane_diff.avg_kda_diff > 0 ? 'text-green-400' : 'text-red-400'"
                    class="text-2xl font-mono font-black">{{ analyticsData.lane_diff.avg_kda_diff > 0 ? '+' : '' }}{{ analyticsData.lane_diff.avg_kda_diff }}</p>
                  <p class="text-white/40 text-[10px] font-mono">KDA diff</p>
                </div>
              </div>
              <p class="text-white/30 text-[9px] font-mono mt-3 text-center">
                Promedio sobre {{ analyticsData.lane_diff.games }} partidas comparando contigo y tu rival directo en la misma posición.
              </p>
            </div>
          </section>

          <!-- Tilt forecast -->
          <section v-if="analyticsData.tilt_forecast">
            <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">🌡 TILT FORECAST</p>
            <div class="bg-black/30 border rounded-xl p-4"
              :class="analyticsData.tilt_forecast.score >= 60 ? 'border-red-500/40' : analyticsData.tilt_forecast.score >= 30 ? 'border-yellow-500/40' : 'border-green-500/40'">
              <div class="flex items-baseline gap-4">
                <p :class="analyticsData.tilt_forecast.score >= 60 ? 'text-red-400' : analyticsData.tilt_forecast.score >= 30 ? 'text-yellow-400' : 'text-green-400'"
                  class="text-4xl font-mono font-black">{{ analyticsData.tilt_forecast.score }}</p>
                <div>
                  <p class="text-white text-sm font-mono">Riesgo de tilt: <span class="font-bold uppercase">{{ analyticsData.tilt_forecast.level }}</span></p>
                  <p class="text-white/60 text-xs font-mono italic">"{{ analyticsData.tilt_forecast.advice }}"</p>
                </div>
              </div>
              <ul v-if="analyticsData.tilt_forecast.reasons && analyticsData.tilt_forecast.reasons.length" class="mt-3 space-y-1">
                <li v-for="r in analyticsData.tilt_forecast.reasons" :key="r"
                  class="text-white/50 text-[11px] font-mono flex items-center gap-2">
                  <span>·</span><span>{{ r }}</span>
                </li>
              </ul>
            </div>
          </section>

          <!-- Weekly comparison -->
          <section v-if="analyticsData.week_stats && (analyticsData.week_stats.this || analyticsData.week_stats.last)">
            <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">📅 COMPARATIVA SEMANAL</p>
            <div class="grid grid-cols-2 gap-4">
              <div v-for="(w, label) in { 'Esta semana': analyticsData.week_stats.this, 'Semana pasada': analyticsData.week_stats.last }" :key="label"
                class="bg-black/30 border border-white/10 rounded-xl p-4">
                <p class="text-white/40 text-[10px] font-mono tracking-widest">{{ label }}</p>
                <div v-if="w" class="flex items-end gap-4 mt-2">
                  <div>
                    <p class="text-white text-2xl font-mono font-black">{{ w.games }}</p>
                    <p class="text-white/30 text-[9px] font-mono">partidas</p>
                  </div>
                  <div>
                    <p :class="w.winrate >= 50 ? 'text-green-400' : 'text-red-400'" class="text-2xl font-mono font-black">{{ w.winrate }}%</p>
                    <p class="text-white/30 text-[9px] font-mono">WR ({{ w.wins }}W)</p>
                  </div>
                  <div>
                    <p :class="tumorColor(w.avg_tumor)" class="text-2xl font-mono font-black">{{ w.avg_tumor }}</p>
                    <p class="text-white/30 text-[9px] font-mono">tumor medio</p>
                  </div>
                </div>
                <p v-else class="text-white/30 text-xs font-mono mt-3">Sin partidas</p>
              </div>
            </div>
            <p v-if="weekDelta" class="text-white/40 text-xs font-mono mt-3">
              <span :class="weekDelta.better ? 'text-green-400' : 'text-red-400'">
                {{ weekDelta.better ? '↓' : '↑' }} {{ Math.abs(weekDelta.pct) }}% de tumor vs semana pasada
              </span>
              — {{ weekDelta.better ? 'vas mejorando' : 'vas peor' }}
            </p>
          </section>

          <!-- Tumor evolution line chart (SVG) -->
          <section v-if="analyticsData.evolution && analyticsData.evolution.length > 1">
            <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">📈 EVOLUCIÓN DEL TUMOR SCORE</p>
            <div class="bg-black/30 border border-white/10 rounded-xl p-4">
              <svg :viewBox="`0 0 600 180`" class="w-full h-44">
                <line v-for="y in [0, 25, 50, 75, 100]" :key="y"
                  :x1="30" :x2="590" :y1="160 - y * 1.4" :y2="160 - y * 1.4"
                  stroke="rgba(255,255,255,0.07)" stroke-width="1" />
                <text v-for="y in [0, 25, 50, 75, 100]" :key="`t${y}`"
                  :x="5" :y="164 - y * 1.4" fill="rgba(255,255,255,0.25)" font-size="9" font-family="monospace">{{ y }}</text>
                <path :d="evolutionAreaPath" fill="url(#tumorGradient)" />
                <defs>
                  <linearGradient id="tumorGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="rgba(239,68,68,0.4)" />
                    <stop offset="100%" stop-color="rgba(239,68,68,0)" />
                  </linearGradient>
                </defs>
                <polyline :points="evolutionLinePoints" fill="none" stroke="#f87171" stroke-width="1.8" />
                <circle v-for="(pt, i) in evolutionPoints" :key="i" :cx="pt.x" :cy="pt.y" r="3"
                  :fill="pt.win ? '#4ade80' : '#f87171'" stroke="#0d1b2a" stroke-width="1">
                  <title>{{ pt.champion }} · {{ pt.win ? 'WIN' : 'LOSS' }} · tumor {{ pt.tumor }}</title>
                </circle>
              </svg>
              <p class="text-white/30 text-[9px] font-mono mt-1">Verde = win · Rojo = loss · Eje Y = tumor score</p>
            </div>
          </section>

          <!-- Horario tóxico -->
          <section v-if="analyticsData.hour_stats && analyticsData.hour_stats.length">
            <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">🕒 HORARIO TÓXICO</p>
            <div class="bg-black/30 border border-white/10 rounded-xl p-4">
              <div class="flex items-end gap-[2px]" style="height: 140px;">
                <div v-for="h in hourly24" :key="h.hour"
                  class="flex-1 h-full flex flex-col items-center justify-end gap-1 group relative">
                  <div class="w-full rounded-t transition-all relative"
                    :class="h.games === 0 ? 'bg-white/5' : h.winrate >= 60 ? 'bg-green-500/70' : h.winrate >= 50 ? 'bg-yellow-500/70' : 'bg-red-500/70'"
                    :style="{ height: h.games === 0 ? '4px' : `${Math.max(8, (h.avg_tumor / hourMaxTumor) * 100)}%` }"></div>
                  <span class="text-white/30 text-[8px] font-mono">{{ String(h.hour).padStart(2, '0') }}</span>
                  <div v-if="h.games > 0" class="hidden group-hover:block absolute -top-12 left-1/2 -translate-x-1/2 bg-black/95 border border-white/20 rounded px-2 py-1 text-[10px] font-mono text-white whitespace-nowrap z-10 shadow-xl">
                    {{ String(h.hour).padStart(2,'0') }}h · {{ h.games }}g · {{ h.winrate }}% WR · {{ h.avg_tumor }} tumor
                  </div>
                </div>
              </div>
              <p class="text-white/30 text-[9px] font-mono mt-2">Altura = tumor medio · Color = winrate · Pasa el ratón por encima</p>
            </div>
          </section>

          <!-- Death heatmap -->
          <section>
            <div class="flex items-center justify-between mb-3">
              <p class="text-white/30 text-[10px] font-mono tracking-widest">💀 HEATMAP DE MUERTES (SR)</p>
              <button @click="emit('load-heatmap')" :disabled="heatmapLoading"
                class="text-[11px] font-mono px-2.5 py-1 border border-red-500/40 text-red-300 hover:border-red-400/80 rounded disabled:opacity-40">
                {{ heatmapLoading ? 'Procesando...' : (heatmapData ? 'Recargar' : 'Cargar últimas 10') }}
              </button>
            </div>
            <div v-if="heatmapData" class="bg-black/30 border border-white/10 rounded-xl p-3">
              <p class="text-white/50 text-[10px] font-mono mb-2">
                {{ heatmapData.total_deaths }} muertes en {{ heatmapData.matches_processed }} partidas. Más rojo = más muertes en esa zona.
              </p>
              <div class="relative mx-auto rounded-lg overflow-hidden" style="max-width: 480px; aspect-ratio: 1 / 1;">
                <div class="absolute inset-0"
                  style="background:
                    radial-gradient(circle at 8% 92%, rgba(59,130,246,0.20) 0%, transparent 18%),
                    radial-gradient(circle at 92% 8%, rgba(239,68,68,0.20) 0%, transparent 18%),
                    linear-gradient(135deg, #1a2e3a 0%, #0f1f2a 50%, #2a1a1a 100%);"></div>
                <svg class="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                  <path d="M 5,20 L 5,5 L 80,5 L 80,15" fill="none" stroke="rgba(255,255,255,0.10)" stroke-width="0.7" />
                  <path d="M 20,95 L 95,95 L 95,80" fill="none" stroke="rgba(255,255,255,0.10)" stroke-width="0.7" />
                  <path d="M 12,88 L 88,12" fill="none" stroke="rgba(255,255,255,0.10)" stroke-width="0.7" />
                  <path d="M 70,30 Q 50,50 30,70" fill="none" stroke="rgba(56,189,248,0.18)" stroke-width="2" />
                </svg>
                <div class="absolute top-1 left-3 text-[9px] font-mono text-white/30">TOP</div>
                <div class="absolute bottom-1 right-3 text-[9px] font-mono text-white/30">BOT</div>
                <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[9px] font-mono text-white/20 rotate-[-45deg]">MID</div>
                <div class="absolute bottom-2 left-3 text-[9px] font-mono text-blue-400/50">BLUE</div>
                <div class="absolute top-2 right-3 text-[9px] font-mono text-red-400/50">RED</div>
                <canvas ref="heatmapCanvas" class="absolute inset-0 w-full h-full pointer-events-none" />
              </div>
              <p v-if="!heatmapData.total_deaths" class="text-white/40 text-xs font-mono italic text-center mt-2">
                Sin muertes en las últimas {{ heatmapData.matches_processed }} partidas. Bien jugado 👀
              </p>
            </div>
            <p v-else class="text-white/30 font-mono text-xs">
              Pulsa cargar para ver dónde mueres más en el mapa. Solo SR ranked (SoloQ/Flex), las últimas 10 partidas.
            </p>
          </section>

          <!-- Champion pool -->
          <section v-if="analyticsData.champion_pool && analyticsData.champion_pool.length">
            <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">🏆 CHAMPION POOL</p>
            <div class="grid grid-cols-2 md:grid-cols-5 gap-2">
              <div v-for="c in analyticsData.champion_pool" :key="c.champion"
                @click.stop="emit('open-champ-stats', c.champion)"
                class="bg-black/30 border border-white/10 rounded-xl p-2 flex items-center gap-2 cursor-pointer hover:border-yellow-500/40 transition"
                :title="`Ver stats con ${c.champion}`">
                <img :src="championIconUrl(c.champion, ddragonVersion)" @error="championIconFallback"
                  class="w-10 h-10 rounded-lg border border-white/20 shrink-0 transition-transform group-hover:scale-105" />
                <div class="min-w-0 flex-1">
                  <p class="text-white text-[11px] font-mono truncate">{{ c.champion }}</p>
                  <p class="text-[9px] font-mono">
                    <span :class="c.winrate >= 60 ? 'text-green-400' : c.winrate >= 50 ? 'text-yellow-400' : 'text-red-400'">{{ c.winrate }}%</span>
                    <span class="text-white/30"> · {{ c.games }}g</span>
                  </p>
                  <p :class="tumorColor(c.avg_tumor)" class="text-[9px] font-mono">{{ c.avg_tumor }} tumor</p>
                </div>
              </div>
            </div>
          </section>

          <!-- Best teammates / Worst nemesis -->
          <section v-if="(analyticsData.best_teammates && analyticsData.best_teammates.length) || (analyticsData.worst_nemesis && analyticsData.worst_nemesis.length)">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div v-if="analyticsData.best_teammates && analyticsData.best_teammates.length">
                <p class="text-green-400/70 text-[10px] font-mono tracking-widest mb-2">🌟 BEST TEAMMATES</p>
                <div class="bg-black/30 border border-green-500/20 rounded-xl divide-y divide-white/5">
                  <div v-for="d in analyticsData.best_teammates" :key="d.puuid" class="flex items-center gap-3 px-3 py-2">
                    <img :src="championIconUrl(d.top_champion, ddragonVersion)" @error="championIconFallback"
                      @click.stop="emit('open-champ-stats', d.top_champion)"
                      class="w-8 h-8 rounded-lg border border-white/20 cursor-pointer hover:border-yellow-500/60 hover:scale-105 transition"
                      :title="`Ver tus stats con ${d.top_champion}`" />
                    <div class="flex-1 min-w-0">
                      <p class="text-white text-[11px] font-mono truncate">{{ d.nombre }}</p>
                      <p class="text-white/30 text-[9px] font-mono">{{ d.games }} partidas</p>
                    </div>
                    <p class="text-green-400 text-sm font-mono font-black">{{ d.winrate }}%</p>
                  </div>
                </div>
              </div>
              <div v-if="analyticsData.worst_nemesis && analyticsData.worst_nemesis.length">
                <p class="text-red-400/70 text-[10px] font-mono tracking-widest mb-2">💢 WORST NEMESIS</p>
                <div class="bg-black/30 border border-red-500/20 rounded-xl divide-y divide-white/5">
                  <div v-for="d in analyticsData.worst_nemesis" :key="d.puuid" class="flex items-center gap-3 px-3 py-2">
                    <img :src="championIconUrl(d.top_champion, ddragonVersion)" @error="championIconFallback"
                      @click.stop="emit('open-champ-stats', d.top_champion)"
                      class="w-8 h-8 rounded-lg border border-white/20 cursor-pointer hover:border-yellow-500/60 hover:scale-105 transition"
                      :title="`Ver tus stats con ${d.top_champion}`" />
                    <div class="flex-1 min-w-0">
                      <p class="text-white text-[11px] font-mono truncate">{{ d.nombre }}</p>
                      <p class="text-white/30 text-[9px] font-mono">{{ d.games }} partidas</p>
                    </div>
                    <p class="text-red-400 text-sm font-mono font-black">{{ d.winrate }}%</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- Duos: media de tumor cuando jugáis juntos -->
          <section v-if="analyticsData.duo_stats && analyticsData.duo_stats.length">
            <div class="flex items-center justify-between mb-3">
              <p class="text-white/30 text-[10px] font-mono tracking-widest">🤝 DUOS · TUMOR MEDIO JUNTOS</p>
              <div class="flex gap-1">
                <button @click="emit('update-duo-sort', 'combined')"
                  :class="duoSortBy === 'combined' ? 'bg-yellow-900/40 text-yellow-300' : 'text-white/40 hover:text-white/70'"
                  class="text-[9px] font-mono px-2 py-0.5 rounded border border-white/10">tumor</button>
                <button @click="emit('update-duo-sort', 'games')"
                  :class="duoSortBy === 'games' ? 'bg-yellow-900/40 text-yellow-300' : 'text-white/40 hover:text-white/70'"
                  class="text-[9px] font-mono px-2 py-0.5 rounded border border-white/10">partidas</button>
                <button @click="emit('update-duo-sort', 'winrate')"
                  :class="duoSortBy === 'winrate' ? 'bg-yellow-900/40 text-yellow-300' : 'text-white/40 hover:text-white/70'"
                  class="text-[9px] font-mono px-2 py-0.5 rounded border border-white/10">winrate</button>
              </div>
            </div>
            <div class="bg-black/30 border border-white/10 rounded-xl divide-y divide-white/5">
              <div v-for="(d, i) in sortedDuos" :key="d.puuid" class="flex items-center gap-3 px-4 py-3">
                <span class="text-white/30 text-xs font-mono w-6">#{{ i + 1 }}</span>
                <img :src="championIconUrl(d.top_champion, ddragonVersion)" @error="championIconFallback"
                  @click.stop="emit('open-champ-stats', d.top_champion)"
                  class="w-10 h-10 rounded-lg border border-white/20 cursor-pointer hover:border-yellow-500/60 hover:scale-105 transition"
                  :title="`Ver tus stats con ${d.top_champion}`" />
                <div class="flex-1 min-w-0">
                  <a :href="profileUrl(d.nombre)" target="_blank" rel="noopener" @click.stop
                    class="text-white text-sm font-mono truncate block hover:text-accent hover:underline transition">{{ d.nombre }}</a>
                  <p class="text-white/30 text-[10px] font-mono">{{ d.top_champion }} · {{ d.games }} partidas juntos · {{ d.wins }}W/{{ d.games - d.wins }}L</p>
                </div>
                <div class="text-center w-16 shrink-0">
                  <p :class="tumorColor(d.combined_avg_tumor ?? 0)" class="text-2xl font-mono font-black">{{ d.combined_avg_tumor ?? '?' }}</p>
                  <p class="text-white/30 text-[9px] font-mono">tumor medio</p>
                </div>
                <div class="text-right w-20 shrink-0">
                  <p class="text-[10px] font-mono">
                    <span class="text-white/40">tú</span>
                    <span :class="tumorColor(d.my_avg_tumor ?? 0)" class="ml-1 font-bold">{{ d.my_avg_tumor ?? '?' }}</span>
                  </p>
                  <p class="text-[10px] font-mono">
                    <span class="text-white/40">él</span>
                    <span :class="tumorColor(d.their_avg_tumor ?? 0)" class="ml-1 font-bold">{{ d.their_avg_tumor ?? '?' }}</span>
                  </p>
                  <p :class="d.winrate >= 60 ? 'text-green-400' : d.winrate >= 50 ? 'text-yellow-400' : 'text-red-400'"
                    class="text-[11px] font-mono font-bold mt-0.5">{{ d.winrate }}%</p>
                </div>
              </div>
            </div>
            <p class="text-white/30 text-[10px] font-mono italic mt-2">
              "tumor medio" = media del tumor combinado de ambos en las partidas que jugasteis juntos. Más alto = pareja más tóxica.
            </p>
          </section>

        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* Shimmer (skeleton loading state) — copia local del global definido en
   Overview, así el modal queda autocontenido. */
@keyframes shimmer-bg {
  0%   { background-position: -200% 0; }
  100% { background-position:  200% 0; }
}
.shimmer {
  background-image: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.04) 0%,
    rgba(255, 255, 255, 0.12) 50%,
    rgba(255, 255, 255, 0.04) 100%
  );
  background-size: 200% 100%;
  animation: shimmer-bg 1.6s ease-in-out infinite;
}
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
