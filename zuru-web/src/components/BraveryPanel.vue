<template>
  <div class="space-y-3">
    <!-- Header explicativo -->
    <div class="bg-gradient-to-br from-purple-900/20 via-black/40 to-pink-900/20 border border-purple-500/30 rounded-xl p-3">
      <p class="text-purple-300 text-[10px] font-mono tracking-widest mb-1">🎲 BRAVERY MODE</p>
      <p class="text-white/70 text-[11px] font-mono leading-relaxed">
        Sortea tu próxima partida. Más cosas aleatorizadas = más multiplicador de TC. Cumple el roll y gana según tu tumor.
      </p>
      <div class="flex gap-2 mt-2 text-[9px] font-mono">
        <span class="px-1.5 py-0.5 rounded bg-purple-900/60 text-purple-200">1 dim · x1.0</span>
        <span class="px-1.5 py-0.5 rounded bg-pink-900/60 text-pink-200">2 dim · x1.3</span>
        <span class="px-1.5 py-0.5 rounded bg-red-900/60 text-red-200">3 dim · x1.7</span>
      </div>
    </div>

    <!-- Si ya tiene lock pending, mostrarlo -->
    <div v-if="pendingLock" class="bg-black/40 border-2 border-yellow-500/60 rounded-xl p-3"
      :style="{ boxShadow: '0 0 25px -10px #facc15' }">
      <div class="flex items-center justify-between mb-2">
        <p class="text-yellow-300 text-[10px] font-mono font-bold tracking-widest">⏳ BRAVERY ACTIVO</p>
        <span class="text-[10px] font-mono text-white/40">x{{ pendingLock.style_mult.toFixed(2) }} · {{ pendingLock.stake }} TC</span>
      </div>
      <div class="flex items-center gap-3">
        <img v-if="champIcon(pendingLock.champion_name)" :src="champIcon(pendingLock.champion_name)" class="w-12 h-12 rounded shrink-0" />
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
        <button @click="onCancel(pendingLock.id)" :disabled="cancelling"
          class="text-[10px] font-mono px-2 py-1 border border-red-500/30 text-red-400 hover:bg-red-900/20 rounded">
          Cancelar
        </button>
      </div>
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
        <p class="text-white/40 text-[9px] font-mono tracking-widest mb-1">💡 PAYOUT POR TUMOR (×style)</p>
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
      <div class="grid grid-cols-3 gap-1.5 mb-3">
        <button v-for="d in DIMENSIONS" :key="d.key"
          @click="toggleDim(d.key)"
          :disabled="d.key === 'champion'"
          :class="dims.includes(d.key)
            ? 'bg-purple-700 border-purple-400 text-white shadow-lg'
            : 'bg-black/30 border-white/15 text-white/40 hover:border-white/40'"
          class="text-[10px] font-mono px-2 py-2 rounded border transition disabled:opacity-100">
          <div class="text-lg">{{ d.emoji }}</div>
          {{ d.label }}
        </button>
      </div>

      <div v-if="dims.includes('lane')" class="mb-2">
        <label class="text-white/40 text-[9px] font-mono tracking-widest">FILTRO LANE (opcional)</label>
        <select v-model="laneFilter"
          class="w-full bg-black/40 border border-white/15 rounded-lg px-2 py-1.5 text-white font-mono text-xs mt-1">
          <option :value="null">— random —</option>
          <option v-for="l in LANES" :key="l" :value="l">{{ LANE_LABEL[l] }}</option>
        </select>
      </div>

      <div class="grid grid-cols-2 gap-2 mb-2">
        <button @click="onRoll" :disabled="rolling || !ddragonReady"
          class="bg-gradient-to-br from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 disabled:opacity-40 text-white font-mono font-bold text-xs px-3 py-2 rounded">
          {{ rolling ? '🎲...' : '🎲 Aleatorio' }}
        </button>
        <div class="text-[10px] font-mono text-white/40 self-center text-right">
          Multi: <span class="text-purple-300 font-bold">x{{ currentStyleMult.toFixed(2) }}</span>
        </div>
      </div>

      <!-- Roll resultado -->
      <div v-if="lastRoll" class="bg-black/40 border border-purple-500/40 rounded-lg p-2 mt-2">
        <div class="flex items-center gap-2">
          <img v-if="champIcon(lastRoll.champion.name)" :src="champIcon(lastRoll.champion.name)" class="w-10 h-10 rounded shrink-0" />
          <div class="flex-1 min-w-0">
            <p class="text-white font-mono font-bold text-sm">{{ lastRoll.champion.name }}</p>
            <p v-if="lastRoll.lane" class="text-cyan-300 text-[10px] font-mono">📍 {{ LANE_LABEL[lastRoll.lane] || lastRoll.lane }}</p>
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
        <img v-if="champIcon(h.champion_name)" :src="champIcon(h.champion_name)" class="w-6 h-6 rounded" />
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
        <img v-if="champIcon(r.champion_name)" :src="champIcon(r.champion_name)" class="w-6 h-6 rounded" />
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

const props = defineProps<{
  roomCode?: string | null
}>()

const auth = useAuth()

const LANES = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
const LANE_LABEL: Record<string, string> = {
  TOP: '🛡 Top', JUNGLE: '🌳 Jungle', MIDDLE: '✨ Mid', BOTTOM: '🏹 ADC', UTILITY: '💚 Sup',
}
const DIMENSIONS = [
  { key: 'champion', emoji: '🎭', label: 'Champion' },
  { key: 'lane', emoji: '📍', label: 'Lane' },
  { key: 'items', emoji: '⚒', label: 'Items' },
]

const ddragon = ref<{ version: string; champions: any[]; items: any[] } | null>(null)
const ddragonError = ref('')
const ddragonReady = computed(() => !!ddragon.value?.version)
const isLoggedIn = computed(() => !!auth?.user.value)

const dims = ref<string[]>(['champion', 'lane', 'items'])
const laneFilter = ref<string | null>(null)
const stake = ref(50)
const lastRoll = ref<any>(null)
const rolling = ref(false)
const locking = ref(false)
const cancelling = ref(false)
const resolving = ref(false)
const error = ref('')

const history = ref<any[]>([])
const roomLocks = ref<any[]>([])

const myUserId = computed(() => auth?.user.value?.id)
const pendingLock = computed(() => history.value.find(h => h.status === 'pending') || null)
const historyResolved = computed(() => history.value.filter(h => h.status !== 'pending'))
const otherRoomLocks = computed(() =>
  roomLocks.value.filter(r => r.user_id !== myUserId.value && r.status === 'pending')
)

const currentStyleMult = computed(() => {
  const n = new Set(dims.value).size
  if (n <= 1) return 1.0
  if (n === 2) return 1.30
  return 1.70
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
      lane_filter: laneFilter.value,
      item_count: 5,
    })
    if (r) lastRoll.value = r
    else error.value = 'No se pudo aleatorizar'
  } finally {
    rolling.value = false
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
      lane: lastRoll.value.lane,
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
