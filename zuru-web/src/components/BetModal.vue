<template>
  <Transition name="modal">
    <div v-if="show" class="fixed inset-0 z-[60] bg-black/70 backdrop-blur-sm overflow-y-auto"
      @click.self="emit('close')">
      <div class="min-h-screen flex items-center justify-center p-4 py-16" @click.self="emit('close')">
      <div class="bg-[#0d1b2a] border border-yellow-500/40 rounded-2xl shadow-2xl shadow-yellow-900/30 w-full max-w-md my-auto">
        <div class="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <p class="text-yellow-200 font-mono font-bold flex items-center gap-2">
            <span>☢</span>
            <span>{{ title }}</span>
          </p>
          <button @click="emit('close')" class="text-white/40 hover:text-white text-xl transition">✕</button>
        </div>

        <!-- Crear apuesta -->
        <div v-if="mode === 'create'" class="p-5 space-y-4">
          <p class="text-white/60 text-xs font-mono">{{ $t('bets.share_link_msg') }}</p>

          <div>
            <p class="text-white/40 text-[10px] font-mono tracking-widest mb-2">{{ $t('bets.bet_on').toUpperCase() }}</p>
            <div class="grid grid-cols-2 gap-2">
              <button @click="side = 'blue'"
                :class="side === 'blue' ? 'bg-blue-600 border-blue-400 text-white shadow-lg shadow-blue-900/50' : 'bg-blue-950/30 border-blue-500/30 text-blue-300/70 hover:border-blue-400/60'"
                class="px-4 py-3 rounded-lg border font-mono font-bold transition">
                🔵 {{ $t('bets.blue_wins') }}
              </button>
              <button @click="side = 'red'"
                :class="side === 'red' ? 'bg-red-600 border-red-400 text-white shadow-lg shadow-red-900/50' : 'bg-red-950/30 border-red-500/30 text-red-300/70 hover:border-red-400/60'"
                class="px-4 py-3 rounded-lg border font-mono font-bold transition">
                🔴 {{ $t('bets.red_wins') }}
              </button>
            </div>
          </div>

          <div>
            <p class="text-white/40 text-[10px] font-mono tracking-widest mb-2">{{ $t('bets.amount').toUpperCase() }} ({{ $t('bets.max') }} {{ balance }} TC)</p>
            <input type="number" v-model.number="amount" :min="10" :max="balance"
              class="w-full bg-black/40 border border-white/15 rounded-lg px-3 py-2 text-white font-mono text-lg focus:border-yellow-500/60 focus:outline-none" />
            <div class="flex gap-2 mt-2">
              <button v-for="preset in [25, 50, 100, 250]" :key="preset"
                @click="amount = Math.min(balance, preset)"
                :disabled="preset > balance"
                class="text-[11px] font-mono px-2 py-1 border border-white/15 text-white/60 hover:text-white hover:border-white/30 rounded disabled:opacity-30">
                {{ preset }}
              </button>
              <button @click="amount = balance"
                class="text-[11px] font-mono px-2 py-1 border border-yellow-500/30 text-yellow-300 hover:bg-yellow-900/20 rounded ml-auto">
                {{ $t('bets.all_in') }}
              </button>
            </div>
          </div>

          <p v-if="error" class="text-red-400 text-xs font-mono">{{ error }}</p>

          <button @click="onCreate" :disabled="creating || !side || amount <= 0 || amount > balance"
            class="w-full bg-yellow-600 hover:bg-yellow-500 disabled:bg-yellow-900/40 disabled:text-white/30 text-black font-mono font-bold px-4 py-3 rounded-lg transition">
            {{ creating ? $t('bets.creating') : `${amount} TC ${side === 'blue' ? '🔵' : '🔴'}` }}
          </button>
        </div>

        <!-- Apuesta creada (mostrar share link) -->
        <div v-else-if="mode === 'created'" class="p-5 space-y-4">
          <div class="bg-green-950/40 border border-green-500/40 rounded-xl p-4 text-center">
            <p class="text-green-300 text-sm font-mono font-bold">✓ {{ $t('bets.bet_created') }}</p>
            <p class="text-white/60 text-xs font-mono mt-1">{{ createdBet?.amount }} TC · {{ $t('bets.share_link_msg') }}</p>
          </div>

          <div>
            <p class="text-white/40 text-[10px] font-mono tracking-widest mb-2">{{ $t('bets.share_code').toUpperCase() }}</p>
            <div class="flex items-center gap-2">
              <code class="flex-1 bg-black/40 border border-white/15 rounded-lg px-3 py-2 text-yellow-300 font-mono text-xl tracking-widest text-center">{{ createdBet?.share_code }}</code>
              <button @click="copyLink"
                class="px-3 py-2 border border-white/15 text-white/70 hover:text-yellow-300 hover:border-yellow-500/40 rounded-lg font-mono text-sm transition">
                {{ copied ? '✓' : '📋' }}
              </button>
            </div>
            <p class="text-white/30 text-[10px] font-mono mt-2 break-all">{{ shareLink }}</p>
          </div>

          <button @click="emit('close')"
            class="w-full bg-white/10 hover:bg-white/15 text-white font-mono px-4 py-2 rounded-lg transition">
            {{ $t('common.close') }}
          </button>
        </div>

        <!-- Aceptar apuesta -->
        <div v-else-if="mode === 'accept' && betToAccept" class="p-5 space-y-4">
          <div class="bg-black/30 border border-white/10 rounded-xl p-4 text-center">
            <p class="text-white/40 text-[10px] font-mono tracking-widest">{{ betToAccept.creator?.username }} → {{ $t('bets.bet_on').toUpperCase() }}</p>
            <p class="text-3xl mt-1">{{ betToAccept.creator_side === 'blue' ? '🔵' : '🔴' }}</p>
            <p class="text-yellow-300 text-2xl font-mono font-black mt-2">{{ betToAccept.amount }} TC</p>
            <p class="text-white/30 text-[10px] font-mono mt-1">match {{ betToAccept.match_id }}</p>
          </div>
          <p class="text-white/70 text-sm font-mono text-center">
            <span class="text-yellow-300 font-bold">{{ betToAccept.amount }} TC</span> →
            <span :class="betToAccept.creator_side === 'blue' ? 'text-red-300' : 'text-blue-300'" class="font-bold">
              {{ betToAccept.creator_side === 'blue' ? '🔴 ' + $t('bets.red_wins') : '🔵 ' + $t('bets.blue_wins') }}
            </span>
          </p>
          <p v-if="error" class="text-red-400 text-xs font-mono text-center">{{ error }}</p>
          <div class="flex gap-2">
            <button @click="emit('close')"
              class="flex-1 bg-white/10 hover:bg-white/15 text-white font-mono px-4 py-2 rounded-lg transition">
              {{ $t('common.cancel') }}
            </button>
            <button @click="onAccept" :disabled="accepting || (betToAccept.amount > balance)"
              class="flex-1 bg-yellow-600 hover:bg-yellow-500 disabled:bg-yellow-900/40 disabled:text-white/30 text-black font-mono font-bold px-4 py-2 rounded-lg transition">
              {{ accepting ? $t('bets.accepting') : (betToAccept.amount > balance ? $t('bets.insufficient_balance') : $t('common.accept')) }}
            </button>
          </div>
        </div>
      </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, inject, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  show: boolean
  mode: 'create' | 'created' | 'accept'
  matchId?: string
  gameId?: number
  betToAccept?: any
}>()

const emit = defineEmits<{
  close: []
  refresh: []
}>()

const auth = inject<any>('auth')
const { t } = useI18n()

const side = ref<'blue' | 'red' | ''>('')
const amount = ref(50)
const creating = ref(false)
const accepting = ref(false)
const error = ref('')
const createdBet = ref<any>(null)
const copied = ref(false)

const balance = computed(() => auth?.user.value?.currency ?? 0)

const title = computed(() => {
  if (props.mode === 'create') return t('bets.create_bet')
  if (props.mode === 'created') return t('bets.bet_created')
  if (props.mode === 'accept') return t('common.accept') + ' ' + t('bets.create_bet').toLowerCase()
  return ''
})

const shareLink = computed(() => {
  if (!createdBet.value) return ''
  return `${window.location.origin}${window.location.pathname}#/bet/${createdBet.value.share_code}`
})

watch(() => props.show, v => {
  if (v) {
    side.value = ''
    amount.value = 50
    error.value = ''
    createdBet.value = null
    copied.value = false
  }
})

async function onCreate() {
  if (!props.matchId) return
  creating.value = true
  error.value = ''
  try {
    const bet = await auth.createBet(props.matchId, props.gameId, side.value, amount.value)
    createdBet.value = bet
    // Mode change handled by parent re-emitting with mode='created'
    emit('refresh')
  } catch (e: any) {
    error.value = e.message || 'Error'
  } finally {
    creating.value = false
  }
}

async function onAccept() {
  if (!props.betToAccept) return
  accepting.value = true
  error.value = ''
  try {
    await auth.acceptBet(props.betToAccept.share_code)
    emit('refresh')
    emit('close')
  } catch (e: any) {
    error.value = e.message || 'Error'
  } finally {
    accepting.value = false
  }
}

async function copyLink() {
  if (!shareLink.value) return
  try {
    await navigator.clipboard.writeText(shareLink.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {}
}
</script>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
