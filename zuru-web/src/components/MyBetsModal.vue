<template>
  <Teleport to="body">
  <Transition name="modal">
    <div v-if="show" class="fixed inset-0 z-[60] bg-black/70 backdrop-blur-sm flex items-start sm:items-center justify-center overflow-y-auto p-4 pt-[8vh] sm:pt-4"
      @click.self="emit('close')">
      <div class="bg-[#0d1b2a] border border-yellow-500/30 rounded-2xl shadow-2xl shadow-yellow-900/30 w-full max-w-2xl max-h-[85vh] flex flex-col">
        <!-- Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <div>
            <p class="text-yellow-200 font-mono font-bold flex items-center gap-2">
              <span>☢</span><span>{{ $t('bets.my_bets') }}</span>
            </p>
            <p v-if="summary" class="text-white/40 text-[10px] font-mono mt-0.5">
              {{ summary.total }} · {{ summary.won }}W / {{ summary.lost }}L
              <span :class="summary.net >= 0 ? 'text-green-400' : 'text-red-400'" class="font-bold">
                {{ summary.net >= 0 ? '+' : '' }}{{ summary.net }} TC
              </span>
            </p>
          </div>
          <button @click="emit('close')" class="text-white/40 hover:text-white text-xl transition">✕</button>
        </div>

        <!-- Filtro -->
        <div class="flex gap-1 px-5 py-2 border-b border-white/5">
          <button v-for="f in filters" :key="f.key" @click="filter = f.key"
            :class="filter === f.key ? 'bg-yellow-900/40 text-yellow-300 border-yellow-500/50' : 'text-white/40 border-transparent hover:text-white/70'"
            class="text-[11px] font-mono px-2.5 py-1 rounded border transition">
            {{ f.label }}
          </button>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="flex-1 flex items-center justify-center py-12">
          <p class="text-white/40 text-sm font-mono animate-pulse">{{ $t('common.loading') }}</p>
        </div>
        <!-- Empty state -->
        <div v-else-if="!filtered.length" class="flex-1 flex flex-col items-center justify-center py-16 px-6 text-center">
          <p class="text-white/40 text-sm font-mono">{{ $t('bets.no_bets_filter') }}</p>
          <p class="text-white/20 text-xs font-mono mt-2">{{ $t('bets.bet_creation_hint') }}</p>
        </div>
        <!-- Lista -->
        <div v-else class="flex-1 overflow-y-auto divide-y divide-white/5">
          <div v-for="b in filtered" :key="b.id" class="px-5 py-3 hover:bg-white/5 transition">
            <div class="flex items-start gap-3">
              <!-- Icono según rol del user -->
              <div class="text-2xl shrink-0 w-8 text-center">
                {{ statusIcon(b) }}
              </div>

              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <code class="text-yellow-300 font-mono text-sm tracking-wider">{{ b.share_code }}</code>
                  <span :class="statusBadge(b.status).cls" class="text-[9px] font-mono px-1.5 py-0.5 rounded uppercase">
                    {{ statusBadge(b.status).label }}
                  </span>
                  <span class="text-white/30 text-[10px] font-mono ml-auto">{{ formatDate(b.created_at) }}</span>
                </div>

                <p class="text-white/70 text-xs font-mono mt-1">
                  <span :class="myRole(b) === 'creator' ? 'text-yellow-300' : 'text-cyan-300'" class="font-bold">{{ myRole(b) === 'creator' ? $t('bets.you_created') : $t('bets.you_accepted') }}</span>
                  <template v-if="b.bet_kind === 'stat'">
                    · 📊 <span class="text-purple-300 font-bold">{{ b.target_name || '?' }}</span>
                    <span :class="mySide(b) === 'over' ? 'text-green-300' : 'text-orange-300'" class="font-bold">
                      {{ mySide(b) === 'over' ? ' ▲ MÁS' : ' ▼ MENOS' }}
                    </span>
                    de <span class="text-yellow-300">{{ b.threshold }}</span> {{ b.stat_type }}
                  </template>
                  <template v-else>
                    · {{ $t('bets.bet_on') }}
                    <span :class="mySide(b) === 'blue' ? 'text-blue-300' : 'text-red-300'" class="font-bold">
                      {{ mySide(b) === 'blue' ? '🔵 BLUE' : '🔴 RED' }}
                    </span>
                  </template>
                </p>

                <p class="text-white/50 text-[11px] font-mono mt-1">
                  vs
                  <span v-if="opponent(b)" class="text-white/70">{{ opponent(b)?.username }}</span>
                  <span v-else class="text-white/30 italic">{{ $t('bets.waiting_taker') }}</span>
                  · {{ $t('bets.stake') }} <span class="text-yellow-300">{{ b.amount }} TC</span>
                  · {{ b.match_id }}
                </p>

                <!-- Resultado -->
                <p v-if="b.status === 'resolved'" class="text-xs font-mono mt-1.5"
                  :class="isPush(b) ? 'text-white/50' : didIWin(b) ? 'text-green-400' : 'text-red-400'">
                  <template v-if="b.bet_kind === 'stat'">
                    {{ isPush(b) ? '↻ Push (refund)' : didIWin(b) ? '✓ ' + $t('bets.won_amount', { amount: b.amount }) : '✗ ' + $t('bets.lost_amount', { amount: b.amount }) }}
                    · actual: <span class="font-bold">{{ b.stat_actual }}</span> / target {{ b.threshold }}
                  </template>
                  <template v-else>
                    {{ didIWin(b) ? '✓ ' + $t('bets.won_amount', { amount: b.amount }) : '✗ ' + $t('bets.lost_amount', { amount: b.amount }) }}
                    · {{ $t('bets.won_team') }} {{ b.winner_side === 'blue' ? '🔵' : '🔴' }}
                  </template>
                </p>

                <!-- Acciones -->
                <div v-if="b.status === 'open' && myRole(b) === 'creator'" class="flex gap-2 mt-2">
                  <button @click="copyLink(b)"
                    class="text-[10px] font-mono px-2 py-1 border border-white/15 text-white/60 hover:text-white hover:border-white/30 rounded">
                    {{ copiedCode === b.share_code ? '✓ ' + $t('common.copied') : '📋 ' + $t('bets.copy_link') }}
                  </button>
                  <button @click="onCancel(b)" :disabled="cancelling === b.share_code"
                    class="text-[10px] font-mono px-2 py-1 border border-red-500/30 text-red-400 hover:bg-red-900/20 rounded disabled:opacity-30">
                    {{ cancelling === b.share_code ? $t('bets.cancelling') : $t('common.cancel') }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="px-5 py-3 border-t border-white/10 flex items-center justify-between">
          <p class="text-white/30 text-[10px] font-mono">
            {{ $t('bets.current_balance') }}: <span class="text-yellow-300 font-bold">{{ balance }} TC</span>
          </p>
          <button @click="refresh" class="text-[10px] font-mono text-white/40 hover:text-white/70">
            ↻ {{ $t('common.refresh') }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, inject, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ close: [] }>()

const auth = inject<any>('auth')

interface Bet {
  id: number
  share_code: string
  match_id: string
  game_id?: number
  creator_user_id: number
  creator_side: 'blue' | 'red' | 'over' | 'under'
  amount: number
  taker_user_id?: number | null
  status: 'open' | 'matched' | 'resolved' | 'cancelled'
  winner_side?: 'blue' | 'red' | 'over' | 'under' | null
  resolved_at?: number | null
  created_at: number
  creator?: { username: string, discord_id: string, avatar: string | null }
  taker?: { username: string, discord_id: string, avatar: string | null } | null
  bet_kind?: 'match' | 'stat'
  target_puuid?: string | null
  target_name?: string | null
  stat_type?: 'kills' | 'deaths' | 'assists' | 'kda' | null
  threshold?: number | null
  stat_actual?: number | null
}

const bets = ref<Bet[]>([])
const loading = ref(false)
const filter = ref<'all' | 'open' | 'matched' | 'resolved'>('all')
const { t } = useI18n()
const filters = computed(() => [
  { key: 'all' as const,      label: t('bets.all') },
  { key: 'open' as const,     label: t('bets.pending') },
  { key: 'matched' as const,  label: t('bets.in_progress') },
  { key: 'resolved' as const, label: t('bets.resolved') },
])
const copiedCode = ref('')
const cancelling = ref('')

const balance = computed(() => auth?.user.value?.currency ?? 0)

watch(() => props.show, async v => {
  if (v) await refresh()
})

async function refresh() {
  if (!auth) return
  loading.value = true
  try {
    // Antes de listar, resolvemos las que ya tengan partida terminada en Riot.
    // Esto cierra el agujero de "creé bets, jugué, cerré la app, no se resolvieron solas".
    try { await auth.resolveMyPendingBets() } catch {}
    bets.value = await auth.fetchMyBets()
  } catch {
    bets.value = []
  } finally {
    loading.value = false
  }
}

const filtered = computed(() => {
  if (filter.value === 'all') return bets.value
  return bets.value.filter(b => b.status === filter.value)
})

const myUserId = computed(() => auth?.user.value?.id)

function myRole(b: Bet): 'creator' | 'taker' {
  return b.creator_user_id === myUserId.value ? 'creator' : 'taker'
}

function mySide(b: Bet): 'blue' | 'red' | 'over' | 'under' {
  if (myRole(b) === 'creator') return b.creator_side
  // Taker takes opposite side
  if (b.creator_side === 'blue') return 'red'
  if (b.creator_side === 'red') return 'blue'
  if (b.creator_side === 'over') return 'under'
  return 'over'
}

function opponent(b: Bet) {
  return myRole(b) === 'creator' ? b.taker : b.creator
}

function didIWin(b: Bet) {
  if (b.status !== 'resolved' || !b.winner_side) return false
  return mySide(b) === b.winner_side
}

function isPush(b: Bet) {
  return b.status === 'resolved' && b.bet_kind === 'stat' && !b.winner_side
}

function statusIcon(b: Bet) {
  if (b.status === 'open')      return '⏳'
  if (b.status === 'matched')   return '⚔'
  if (b.status === 'cancelled') return '🚫'
  if (b.status === 'resolved')  return didIWin(b) ? '✅' : '❌'
  return '·'
}

function statusBadge(status: string) {
  const map: Record<string, { label: string, cls: string }> = {
    open:      { label: t('bets.pending'),     cls: 'bg-yellow-900/40 text-yellow-400' },
    matched:   { label: t('bets.in_progress'), cls: 'bg-cyan-900/40 text-cyan-300' },
    resolved:  { label: t('bets.resolved'),    cls: 'bg-white/10 text-white/60' },
    cancelled: { label: t('common.cancel'),    cls: 'bg-red-900/40 text-red-400' },
  }
  return map[status] || { label: status, cls: 'bg-white/5 text-white/40' }
}

function formatDate(ts: number) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleString('es-ES', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

async function copyLink(b: Bet) {
  const url = `${window.location.origin}${window.location.pathname}#/bet/${b.share_code}`
  try {
    await navigator.clipboard.writeText(url)
    copiedCode.value = b.share_code
    setTimeout(() => { copiedCode.value = '' }, 2000)
  } catch {}
}

async function onCancel(b: Bet) {
  if (!confirm(t('bets.confirm_cancel', { code: b.share_code, amount: b.amount }))) return
  cancelling.value = b.share_code
  try {
    await auth.cancelBet(b.share_code)
    await refresh()
  } catch (e: any) {
    alert(e.message || 'Error cancelando')
  } finally {
    cancelling.value = ''
  }
}

const summary = computed(() => {
  // Pushes (stat bet ties) no cuentan como win ni loss; sólo refund.
  const resolved = bets.value.filter(b => b.status === 'resolved' && !isPush(b))
  if (!resolved.length) return null
  const won = resolved.filter(b => didIWin(b)).length
  const lost = resolved.length - won
  const net = resolved.reduce((s, b) => s + (didIWin(b) ? b.amount : -b.amount), 0)
  return { total: bets.value.length, won, lost, net }
})
</script>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
