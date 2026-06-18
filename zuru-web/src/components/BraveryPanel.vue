<template>
  <div class="space-y-3">
    <!-- Header explicativo -->
    <div class="bg-gradient-to-br from-purple-900/20 via-black/40 to-pink-900/20 border border-purple-500/30 rounded-xl p-3">
      <p class="text-purple-300 text-[10px] font-mono tracking-widest mb-1">
        🎲 {{ $t('bravery.title').toUpperCase() }} MODE · {{ roomCode ? $t('bravery.mode_room').toUpperCase() : $t('bravery.mode_solo').toUpperCase() }}
      </p>
      <p class="text-white/70 text-[11px] font-mono leading-relaxed">
        {{ roomCode ? $t('bravery.intro_room') : $t('bravery.intro_solo') }}
      </p>
      <!-- Tabla de penalty por dimensión -->
      <div class="flex gap-2 mt-2 text-[9px] font-mono">
        <span class="px-1.5 py-0.5 rounded bg-green-900/60 text-green-200">champ · ×1.0</span>
        <span v-if="roomCode" class="px-1.5 py-0.5 rounded bg-yellow-900/60 text-yellow-200">+lane · -10%</span>
        <span class="px-1.5 py-0.5 rounded bg-red-900/60 text-red-200">+items · -25%</span>
      </div>
    </div>

    <!-- Banner: estado bravery de la sala -->
    <div v-if="roomCode && roomBraveryStatus !== null"
      class="rounded-lg border-2 p-2.5 flex items-center gap-2"
      :class="roomBraveryStatus ? 'border-purple-500/60 bg-purple-900/15' : 'border-white/15 bg-black/20'">
      <span class="text-xl shrink-0">{{ roomBraveryStatus ? '🎲' : '⏸' }}</span>
      <div class="flex-1 min-w-0">
        <p class="text-[11px] font-mono font-bold"
          :class="roomBraveryStatus ? 'text-purple-300' : 'text-white/50'">
          {{ roomBraveryStatus ? 'Bravery activo en la sala' : 'Bravery no iniciado' }}
        </p>
        <p class="text-[9px] font-mono text-white/40">
          {{ roomBraveryStatus
            ? 'Cada miembro lockea su setup random'
            : (isRoomOwner ? 'Activa Bravery para que todos lockean' : 'Espera a que el host active') }}
        </p>
      </div>
      <button v-if="isRoomOwner" @click="onToggleRoomBravery" :disabled="togglingBravery"
        class="text-[10px] font-mono font-bold px-2 py-1 rounded shrink-0 disabled:opacity-40"
        :class="roomBraveryStatus
          ? 'bg-red-900/40 text-red-300 hover:bg-red-900/60'
          : 'bg-purple-700 text-white hover:bg-purple-600'">
        {{ togglingBravery ? '...' : (roomBraveryStatus ? 'Cerrar' : '🎲 Iniciar') }}
      </button>
    </div>

    <!-- Si ya tiene lock pending, mostrarlo -->
    <div v-if="pendingLock" class="bg-black/40 border-2 border-yellow-500/60 rounded-xl p-3"
      :style="{ boxShadow: '0 0 25px -10px #facc15' }">
      <div class="flex items-center justify-between mb-2">
        <p class="text-yellow-300 text-[10px] font-mono font-bold tracking-widest">⏳ BRAVERY ACTIVO</p>
        <span class="text-[10px] font-mono text-white/40">x{{ pendingLock.style_mult.toFixed(2) }} · {{ pendingLock.stake }} TC</span>
      </div>
      <div class="flex items-center gap-3">
        <img v-if="champIcon(pendingLock.champion_name)" :src="champIcon(pendingLock.champion_name)" @error="championIconFallback" class="w-12 h-12 rounded shrink-0" />
        <div class="flex-1 min-w-0">
          <p class="text-white font-mono font-bold text-sm">{{ pendingLock.champion_name }}</p>
          <p v-if="pendingLock.lane" class="text-cyan-300 text-[10px] font-mono">
            📍 {{ LANE_LABEL[pendingLock.lane] || pendingLock.lane }}
          </p>
        </div>
      </div>
      <div v-if="pendingLock.items && pendingLock.items.length" class="flex gap-1 mt-2 flex-wrap">
        <div v-for="it in pendingLock.items" :key="it.id"
          class="flex items-center gap-1 px-1.5 py-0.5 rounded bg-white/5 border border-white/10">
          <img v-if="itemIcon(it.id)" :src="itemIcon(it.id)" class="w-5 h-5" />
          <span class="text-[9px] font-mono text-white/70">{{ it.name }}</span>
        </div>
      </div>
      <div class="flex gap-2 mt-3">
        <button @click="onResolveMine" :disabled="resolving"
          class="flex-1 bg-cyan-700 hover:bg-cyan-600 disabled:opacity-40 text-white font-mono font-bold text-xs px-3 py-1.5 rounded">
          {{ resolving ? '...' : '🔄 Comprobar partida' }}
        </button>
        <button v-if="!pendingLock.reroll_used"
          @click="onReroll(pendingLock.id)" :disabled="rerolling"
          class="text-[10px] font-mono px-2 py-1 bg-purple-700 hover:bg-purple-600 disabled:opacity-40 text-white font-bold rounded">
          {{ rerolling ? '...' : '🎲 Reroll (1)' }}
        </button>
        <button @click="onCancel(pendingLock.id)" :disabled="cancelling"
          class="text-[10px] font-mono px-2 py-1 border border-red-500/30 text-red-400 hover:bg-red-900/20 rounded">
          Cancelar
        </button>
      </div>
      <p v-if="pendingLock.reroll_used"
        class="text-white/30 text-[9px] font-mono mt-1 italic">
        ya rerolleaste · setup definitivo
      </p>
    </div>

    <!-- Si no hay login → mensaje claro -->
    <div v-else-if="!isLoggedIn" class="bg-black/30 border border-white/10 rounded-xl p-4 text-center">
      <p class="text-white/60 text-xs font-mono">Inicia sesión con Discord para jugar a Bravery.</p>
    </div>

    <!-- Si DDragon aún no cargó: estado claro de loading o error -->
    <div v-else-if="!ddragonReady" class="bg-black/30 border border-white/10 rounded-xl p-4 text-center">
      <p v-if="ddragonError" class="text-red-400 text-xs font-mono">{{ ddragonError }}</p>
      <p v-else class="text-white/60 text-xs font-mono animate-pulse">
        ⏳ Cargando Data Dragon (champions + items del último parche)...
      </p>
      <button v-if="ddragonError" @click="loadData"
        class="mt-2 text-[10px] font-mono px-2 py-1 bg-yellow-700 hover:bg-yellow-600 text-black font-bold rounded">
        Reintentar
      </button>
    </div>

    <!-- Builder de nuevo roll -->
    <div v-else class="bg-black/30 border border-white/10 rounded-xl p-3">
      <!-- Tabla de payouts según tumor — explicación -->
      <div class="mb-3 p-2 rounded-lg bg-black/40 border border-purple-500/20">
        <p class="text-white/40 text-[9px] font-mono tracking-widest mb-1">💡 PAYOUT POR TUMOR (× tu style)</p>
        <div class="grid grid-cols-5 gap-1 text-center">
          <div class="rounded bg-green-900/40 py-1">
            <p class="text-green-300 text-[9px] font-mono font-bold">≤20</p>
            <p class="text-green-200 text-[10px] font-mono">×1.5</p>
          </div>
          <div class="rounded bg-emerald-900/40 py-1">
            <p class="text-emerald-300 text-[9px] font-mono font-bold">40</p>
            <p class="text-emerald-200 text-[10px] font-mono">×1.5</p>
          </div>
          <div class="rounded bg-yellow-900/40 py-1">
            <p class="text-yellow-300 text-[9px] font-mono font-bold">60 sus</p>
            <p class="text-yellow-200 text-[10px] font-mono">×1.0</p>
          </div>
          <div class="rounded bg-orange-900/40 py-1">
            <p class="text-orange-300 text-[9px] font-mono font-bold">80</p>
            <p class="text-orange-200 text-[10px] font-mono">×0.5</p>
          </div>
          <div class="rounded bg-red-900/40 py-1">
            <p class="text-red-300 text-[9px] font-mono font-bold">100</p>
            <p class="text-red-200 text-[10px] font-mono">×0</p>
          </div>
        </div>
        <p class="text-white/40 text-[9px] font-mono mt-1 italic">
          Tumor ≤60 ganas. Tumor &gt;60 pierdes. Tumor 100 → pierdes todo el stake.
        </p>
      </div>
      <p class="text-white/40 text-[10px] font-mono tracking-widest mb-2">QUÉ ALEATORIZAR</p>
      <div class="grid gap-1.5 mb-3" :class="visibleDimensions.length === 2 ? 'grid-cols-2' : 'grid-cols-3'">
        <button v-for="d in visibleDimensions" :key="d.key"
          @click="toggleDim(d.key)"
          :disabled="d.key === 'champion'"
          :class="dims.includes(d.key)
            ? 'bg-purple-700 border-purple-400 text-white shadow-lg'
            : 'bg-black/30 border-white/15 text-white/40 hover:border-white/40'"
          class="text-[10px] font-mono px-2 py-2 rounded border transition disabled:opacity-100">
          <div class="text-lg">{{ d.emoji }}</div>
          {{ d.label }}
          <p v-if="d.penalty" class="text-[8px] mt-0.5 opacity-70">−{{ Math.round(d.penalty * 100) }}%</p>
        </button>
      </div>

      <!-- Hint sala: lanes disponibles -->
      <p v-if="roomCode && roomBraveryActive" class="text-cyan-300/70 text-[10px] font-mono mb-2">
        📍 En sala: lane se asigna random al lockear · {{ lanesRemaining }}/5 disponibles
      </p>

      <div class="grid grid-cols-2 gap-2 mb-2">
        <button @click="onRoll" :disabled="rolling || !ddragonReady || lockBlocked"
          class="bg-gradient-to-br from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 disabled:opacity-40 text-white font-mono font-bold text-xs px-3 py-2 rounded">
          {{ rolling ? '🎲...' : '🎲 Aleatorio' }}
        </button>
        <div class="text-[10px] font-mono text-white/50 self-center text-right">
          Multi:
          <span class="font-bold"
            :class="currentStyleMult >= 1.0 ? 'text-green-300' : currentStyleMult >= 0.8 ? 'text-yellow-300' : 'text-red-300'">
            x{{ currentStyleMult.toFixed(2) }}
          </span>
        </div>
      </div>
      <p v-if="lockBlocked" class="text-yellow-400/80 text-[10px] font-mono italic">
        ⏸ El host aún no ha activado Bravery en esta sala.
      </p>

      <!-- Roll resultado -->
      <div v-if="lastRoll" class="bg-black/40 border border-purple-500/40 rounded-lg p-2 mt-2">
        <div class="flex items-center gap-2">
          <img v-if="champIcon(lastRoll.champion.name)" :src="champIcon(lastRoll.champion.name)" @error="championIconFallback" class="w-10 h-10 rounded shrink-0" />
          <div class="flex-1 min-w-0">
            <p class="text-white font-mono font-bold text-sm">{{ lastRoll.champion.name }}</p>
            <!-- Sala: lane viene del server, no se re-rollea aquí. -->
            <p v-if="roomCode && lastRoll.lane" class="text-cyan-300 text-[10px] font-mono">
              📍 {{ LANE_LABEL[lastRoll.lane] || lastRoll.lane }}
            </p>
            <!-- Solo: lane sugerida pickeada en frontend con re-roll a un click. -->
            <div v-else-if="!roomCode && soloLane" class="flex items-center gap-1.5 mt-0.5">
              <span class="text-cyan-300 text-[10px] font-mono">📍 {{ LANE_LABEL[soloLane] || soloLane }}</span>
              <button @click="pickSoloLane"
                class="text-[9px] font-mono px-1.5 py-0.5 rounded border border-cyan-500/30 text-cyan-300/70 hover:bg-cyan-900/30 hover:text-cyan-200 transition"
                title="Lane aleatoria">
                🎲 cambiar
              </button>
            </div>
          </div>
        </div>
        <div v-if="lastRoll.items" class="flex gap-1 mt-1.5 flex-wrap">
          <div v-for="it in lastRoll.items" :key="it.id"
            class="flex items-center gap-1 px-1 py-0.5 rounded bg-white/5">
            <img v-if="itemIcon(it.id)" :src="itemIcon(it.id)" class="w-4 h-4" />
            <span class="text-[9px] font-mono text-white/60">{{ it.name }}</span>
          </div>
        </div>

        <!-- Stake + lock -->
        <div class="grid grid-cols-2 gap-2 mt-2">
          <input type="number" v-model.number="stake" :min="10"
            class="bg-black/50 border border-white/15 rounded px-2 py-1 text-white font-mono text-xs"
            placeholder="Stake TC" />
          <button @click="onLock" :disabled="locking || !stake || stake <= 0"
            class="bg-yellow-600 hover:bg-yellow-500 disabled:opacity-40 text-black font-mono font-bold text-xs px-3 py-1 rounded">
            {{ locking ? '...' : `🔒 ${stake} TC` }}
          </button>
        </div>
      </div>
    </div>

    <p v-if="error" class="text-red-400 text-[10px] font-mono">{{ error }}</p>

    <!-- Historial -->
    <div v-if="historyResolved.length" class="space-y-1.5">
      <p class="text-white/30 text-[10px] font-mono tracking-widest">HISTORIAL</p>
      <div v-for="h in historyResolved.slice(0, 5)" :key="h.id"
        class="bg-black/20 border border-white/10 rounded px-2 py-1.5 flex items-center gap-2 text-[10px] font-mono">
        <img v-if="champIcon(h.champion_name)" :src="champIcon(h.champion_name)" @error="championIconFallback" class="w-6 h-6 rounded" />
        <span class="text-white/70 truncate flex-1">{{ h.champion_name }}{{ h.lane ? ' · ' + (LANE_LABEL[h.lane] || h.lane) : '' }}</span>
        <span :class="(h.payout || 0) > h.stake ? 'text-green-400' : h.status === 'refunded' ? 'text-yellow-400' : 'text-red-400'"
          class="font-bold">
          {{ h.status === 'refunded' ? `+${h.payout} ↩` : `${(h.payout || 0) - h.stake >= 0 ? '+' : ''}${(h.payout || 0) - h.stake} TC` }}
        </span>
      </div>
    </div>

    <!-- Si es room: locks de otros miembros -->
    <div v-if="roomCode && otherRoomLocks.length" class="space-y-1.5">
      <p class="text-white/30 text-[10px] font-mono tracking-widest">OTROS EN ESTA SALA</p>
      <div v-for="r in otherRoomLocks" :key="r.id"
        class="bg-black/20 border border-white/10 rounded px-2 py-1.5 flex items-center gap-2 text-[10px] font-mono">
        <img v-if="champIcon(r.champion_name)" :src="champIcon(r.champion_name)" @error="championIconFallback" class="w-6 h-6 rounded" />
        <span class="text-white/70 truncate flex-1">{{ r.champion_name }}{{ r.lane ? ' · ' + (LANE_LABEL[r.lane] || r.lane) : '' }}</span>
        <span class="text-purple-300">x{{ r.style_mult.toFixed(2) }}</span>
        <span class="text-white/40">{{ r.stake }} TC</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAuth } from '../composables/useAuth'
import { championIconFallback } from '../composables/overviewConstants'

const props = defineProps<{
  roomCode?: string | null
  /** Si la sala tiene bravery_active=true. null/undef si no aplica (single player). */
  roomBraveryActive?: boolean | null
  /** Si el viewer es owner de la sala (sólo aplica si roomCode set). */
  isRoomOwner?: boolean
}>()

const emit = defineEmits<{
  /** Owner pidió toggle del flag bravery_active de la sala. El padre llama al endpoint. */
  toggleRoomBravery: []
}>()

const auth = useAuth()

const LANE_LABEL: Record<string, string> = {
  TOP: '🛡 Top', JUNGLE: '🌳 Jungle', MIDDLE: '✨ Mid', BOTTOM: '🏹 ADC', UTILITY: '💚 Sup',
}
// Penalty al style_mult por dimensión (debe matchear bravery_engine.DIMENSION_PENALTY).
// Lane NO es elegible: en sala se asigna automáticamente al lockear (pool de 5).
// En solo no existe (no eliges lane en SoloQ).
const DIMENSIONS = [
  { key: 'champion', emoji: '🎭', label: 'Champion', penalty: 0 },
  { key: 'items',    emoji: '⚒', label: 'Items',    penalty: 0.25 },
]
const LANE_PENALTY = 0.10

const ddragon = ref<{ version: string; champions: any[]; items: any[] } | null>(null)
const ddragonError = ref('')
const ddragonReady = computed(() => !!ddragon.value?.version)
const isLoggedIn = computed(() => !!auth?.user.value)

// Default dims: champ obligatorio + items toggle opcional. Lane no es toggle.
const dims = ref<string[]>(['champion', 'items'])
const stake = ref(50)
const lastRoll = ref<any>(null)

// Solo bravery: lane sugerida random pickeada en frontend (no afecta al lock).
// En salas el server asigna lane del pool de 5 al hacer lock (no tocamos eso).
// El user en solo puede re-rollearla con el botón debajo del champion.
const SOLO_LANES = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY'] as const
const soloLane = ref<string | null>(null)
function pickSoloLane() {
  const next = SOLO_LANES[Math.floor(Math.random() * SOLO_LANES.length)]
  // Si por casualidad sale la misma, re-pickea una vez para sensación de cambio
  if (next === soloLane.value && SOLO_LANES.length > 1) {
    const alt = SOLO_LANES.filter(l => l !== soloLane.value)
    soloLane.value = alt[Math.floor(Math.random() * alt.length)]
  } else {
    soloLane.value = next
  }
}
const rolling = ref(false)
const locking = ref(false)
const cancelling = ref(false)
const resolving = ref(false)
const rerolling = ref(false)
const togglingBravery = ref(false)
const error = ref('')

const history = ref<any[]>([])
const roomLocks = ref<any[]>([])

const myUserId = computed(() => auth?.user.value?.id)

const roomBraveryStatus = computed(() =>
  props.roomCode ? !!props.roomBraveryActive : null
)
const lockBlocked = computed(() =>
  !!props.roomCode && !props.roomBraveryActive
)
// Cuántas lanes quedan libres en la sala (informativo)
const lanesTaken = computed(() => {
  if (!props.roomCode) return new Set<string>()
  return new Set(roomLocks.value.filter(l => l.status === 'pending' && l.lane).map(l => l.lane))
})
const lanesRemaining = computed(() => 5 - lanesTaken.value.size)
const visibleDimensions = DIMENSIONS  // 2 dims max, lane es automática en sala
const pendingLock = computed(() => history.value.find(h => h.status === 'pending') || null)
const historyResolved = computed(() => history.value.filter(h => h.status !== 'pending'))
const otherRoomLocks = computed(() =>
  roomLocks.value.filter(r => r.user_id !== myUserId.value && r.status === 'pending')
)

const currentStyleMult = computed(() => {
  const s = new Set(dims.value)
  if (!s.has('champion')) return 1.0
  let mult = 1.0
  for (const d of DIMENSIONS) {
    if (s.has(d.key)) mult -= d.penalty
  }
  // En sala se añade lane automáticamente al lockear → preview con su penalty
  if (props.roomCode) mult -= LANE_PENALTY
  return Math.max(0.5, Math.round(mult * 1000) / 1000)
})

function toggleDim(d: string) {
  if (d === 'champion') return  // champion siempre on
  if (dims.value.includes(d)) {
    dims.value = dims.value.filter(x => x !== d)
  } else {
    dims.value = [...dims.value, d]
  }
}

function champIcon(name: string | undefined) {
  if (!name || !ddragon.value?.version) return ''
  const champ = ddragon.value.champions.find(c => c.name === name)
  if (!champ) return ''
  return `https://ddragon.leagueoflegends.com/cdn/${ddragon.value.version}/img/champion/${champ.key}.png`
}

function itemIcon(id: number) {
  if (!ddragon.value?.version) return ''
  return `https://ddragon.leagueoflegends.com/cdn/${ddragon.value.version}/img/item/${id}.png`
}

async function loadData() {
  ddragonError.value = ''
  try {
    const d = await auth.braveryData()
    if (!d) {
      ddragonError.value = '❌ Data Dragon no respondió. Reintenta en unos segundos.'
      return
    }
    ddragon.value = d
  } catch (e: any) {
    ddragonError.value = `❌ Error: ${e.message || 'desconocido'}`
  }
}

async function loadMine() {
  history.value = await auth.braveryMine()
}

async function loadRoom() {
  if (props.roomCode) {
    roomLocks.value = await auth.braveryRoomLocks(props.roomCode)
  }
}

async function onRoll() {
  rolling.value = true
  error.value = ''
  try {
    const r = await auth.braveryRoll({
      dimensions: dims.value,
      room_code: props.roomCode || null,
      item_count: 5,
    })
    if (r) {
      lastRoll.value = r
      // En solo no llega lane desde backend; pickeamos una random local para
      // que el user pueda jugar SR pretendiendo este lane. En sala lastRoll.lane
      // ya viene asignado por el server al lockear.
      if (!props.roomCode) pickSoloLane()
    } else error.value = 'No se pudo aleatorizar'
  } finally {
    rolling.value = false
  }
}

async function onToggleRoomBravery() {
  if (togglingBravery.value) return
  togglingBravery.value = true
  try {
    emit('toggleRoomBravery')
  } finally {
    togglingBravery.value = false
  }
}

async function onLock() {
  if (!lastRoll.value) return
  locking.value = true
  error.value = ''
  try {
    await auth.braveryLock({
      champion_id: lastRoll.value.champion.id,
      champion_name: lastRoll.value.champion.name,
      lane: null,  // lane se asigna server-side (sala) o queda null (solo)
      items: lastRoll.value.items,
      stake: stake.value,
      room_code: props.roomCode || null,
    })
    lastRoll.value = null
    await loadMine()
    await loadRoom()
  } catch (e: any) {
    error.value = e.message || 'Error'
  } finally {
    locking.value = false
  }
}

async function onCancel(lid: number) {
  cancelling.value = true
  try {
    await auth.braveryCancel(lid)
    await loadMine()
    await loadRoom()
  } finally {
    cancelling.value = false
  }
}

async function onReroll(lid: number) {
  rerolling.value = true
  error.value = ''
  try {
    await auth.braveryReroll(lid)
    await loadMine()
    await loadRoom()
  } catch (e: any) {
    error.value = e.message || 'Error en reroll'
  } finally {
    rerolling.value = false
  }
}

async function onResolveMine() {
  resolving.value = true
  try {
    await auth.braveryResolveMine()
    await loadMine()
    await loadRoom()
  } finally {
    resolving.value = false
  }
}

onMounted(async () => {
  await loadData()
  if (isLoggedIn.value) {
    await loadMine()
    await loadRoom()
  }
  // Si DDragon falló, reintenta en 3s (puede ser warm-up del backend en cold start)
  if (!ddragonReady.value && !ddragonError.value) {
    setTimeout(() => {
      if (!ddragonReady.value) loadData()
    }, 3000)
  }
})

watch(() => props.roomCode, async () => {
  await loadRoom()
})
</script>
