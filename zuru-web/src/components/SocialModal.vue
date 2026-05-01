<template>
  <Transition name="modal">
    <div v-if="show" class="fixed inset-0 z-[60] bg-black/70 backdrop-blur-sm overflow-y-auto"
      @click.self="emit('close')">
      <div class="min-h-screen flex items-center justify-center p-4 py-16" @click.self="emit('close')">
      <div class="bg-[#0d1b2a] border border-yellow-500/30 rounded-2xl shadow-2xl shadow-yellow-900/30 w-full max-w-3xl max-h-[88vh] flex flex-col my-auto">
        <div class="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <p class="text-yellow-200 font-mono font-bold flex items-center gap-2">
            <span>🌐</span><span>Social</span>
          </p>
          <button @click="emit('close')" class="text-white/40 hover:text-white text-xl transition">✕</button>
        </div>

        <!-- Tabs -->
        <div class="flex gap-1 px-5 py-2 border-b border-white/10">
          <button v-for="t in tabs" :key="t.key" @click="active = t.key"
            :class="active === t.key
              ? 'bg-yellow-900/40 text-yellow-300 border-yellow-500/50'
              : 'text-white/40 border-transparent hover:text-white/70'"
            class="text-xs font-mono px-3 py-1.5 rounded border transition">
            {{ t.label }}
          </button>
        </div>

        <!-- Content -->
        <div class="flex-1 overflow-y-auto p-5">
          <!-- HOT BETS -->
          <div v-if="active === 'hot'">
            <p class="text-white/40 text-[10px] font-mono tracking-widest mb-3">APUESTAS ABIERTAS · ACEPTA UNA</p>
            <p v-if="!openBets.length" class="text-white/30 text-sm font-mono text-center py-8">
              No hay apuestas abiertas ahora mismo. Crea una desde el modal de live game.
            </p>
            <div class="space-y-2">
              <div v-for="b in openBets" :key="b.id"
                class="bg-black/30 border border-white/10 hover:border-yellow-500/40 transition rounded-xl p-3 flex items-center gap-3">
                <div class="text-2xl">{{ b.creator_side === 'blue' ? '🔵' : '🔴' }}</div>
                <div class="flex-1 min-w-0">
                  <p class="text-white text-sm font-mono truncate">
                    <span class="font-bold">{{ b.creator?.username || 'Anónimo' }}</span>
                    apuesta <span class="text-yellow-300 font-bold">{{ b.amount }} TC</span>
                  </p>
                  <p class="text-white/40 text-[10px] font-mono">match {{ b.match_id }}</p>
                </div>
                <button @click="onAccept(b)"
                  class="text-xs font-mono px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-black font-bold rounded">
                  Aceptar {{ b.creator_side === 'blue' ? '🔴' : '🔵' }}
                </button>
              </div>
            </div>
          </div>

          <!-- LEADERBOARDS -->
          <div v-else-if="active === 'leaderboards'">
            <div class="flex gap-1 mb-3">
              <button v-for="lk in leaderboardKinds" :key="lk.key" @click="lbKind = lk.key; loadLeaderboard()"
                :class="lbKind === lk.key
                  ? 'bg-yellow-900/40 text-yellow-300 border-yellow-500/50'
                  : 'text-white/40 border-transparent hover:text-white/70'"
                class="text-[10px] font-mono px-2 py-1 rounded border transition">
                {{ lk.label }}
              </button>
            </div>
            <div v-if="!leaderboard.length" class="text-white/30 text-sm font-mono text-center py-8">
              Sin datos todavía.
            </div>
            <div v-else class="space-y-1">
              <div v-for="(u, i) in leaderboard" :key="u.user_id"
                class="bg-black/30 border border-white/10 rounded-lg px-3 py-2 flex items-center gap-3">
                <span class="font-mono font-bold w-6 text-center"
                  :class="i < 3 ? 'text-[#c89b3c]' : 'text-white/30'">
                  {{ i < 3 ? ['🥇','🥈','🥉'][i] : '#' + (i + 1) }}
                </span>
                <img v-if="u.avatar" :src="`https://cdn.discordapp.com/avatars/${u.user_id}/${u.avatar}.png?size=32`"
                  class="w-7 h-7 rounded-full" />
                <div class="flex-1 min-w-0">
                  <p class="text-white text-sm font-mono truncate">{{ u.username }}</p>
                  <p v-if="u.riot_id" class="text-[#c89b3c] text-[10px] font-mono">{{ u.riot_id }}</p>
                </div>
                <div class="text-right text-xs font-mono">
                  <p v-if="lbKind === 'currency'" class="text-yellow-300 font-bold">{{ u.currency }} TC</p>
                  <p v-else-if="lbKind === 'bets'" class="text-yellow-300 font-bold">
                    {{ u.won_count }} W · +{{ u.net_won }} TC
                  </p>
                  <p v-else-if="lbKind === 'accuracy'" class="text-green-400 font-bold">
                    {{ u.accuracy }}% · {{ u.hits }}/{{ u.total }}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- FRIENDS -->
          <div v-else-if="active === 'friends'">
            <div class="flex gap-2 mb-4">
              <input v-model="friendSearchInput" placeholder="Riot ID (Nombre#TAG)"
                class="flex-1 bg-black/40 border border-white/15 rounded-lg px-3 py-2 text-white font-mono text-sm focus:border-yellow-500/60 focus:outline-none" />
              <button @click="onAddFriend" :disabled="addingFriend"
                class="text-xs font-mono px-3 py-2 bg-yellow-600 hover:bg-yellow-500 disabled:opacity-30 text-black font-bold rounded-lg">
                {{ addingFriend ? '...' : '+ Añadir' }}
              </button>
            </div>
            <p v-if="friendError" class="text-red-400 text-xs font-mono mb-3">{{ friendError }}</p>
            <p v-if="!friends.length" class="text-white/30 text-sm font-mono text-center py-8">
              Aún no tienes amigos. Añade por Riot ID.
            </p>
            <div class="space-y-1">
              <div v-for="f in friends" :key="f.id"
                class="bg-black/30 border border-white/10 rounded-lg px-3 py-2 flex items-center gap-3">
                <img v-if="f.other_user?.avatar" :src="`https://cdn.discordapp.com/avatars/${f.other_user.discord_id}/${f.other_user.avatar}.png?size=32`"
                  class="w-7 h-7 rounded-full" />
                <div v-else class="w-7 h-7 rounded-full bg-[#5865F2] flex items-center justify-center text-white text-xs font-bold">
                  {{ f.other_user?.username?.[0]?.toUpperCase() ?? '?' }}
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-white text-sm font-mono truncate">{{ f.other_user?.username || 'Usuario' }}</p>
                  <p class="text-white/40 text-[10px] font-mono">
                    {{ f.status === 'pending' ? (f.direction === 'sent' ? 'Pendiente (enviada)' : 'Te ha invitado') :
                       f.status === 'accepted' ? 'Amigos' :
                       f.status === 'rejected' ? 'Rechazada' : f.status }}
                  </p>
                </div>
                <div class="flex gap-1">
                  <button v-if="f.status === 'pending' && f.direction === 'received'" @click="onAcceptFriend(f.id)"
                    class="text-[10px] font-mono px-2 py-1 bg-green-700 hover:bg-green-600 text-white rounded">
                    Aceptar
                  </button>
                  <button v-if="f.status === 'pending' && f.direction === 'received'" @click="onRejectFriend(f.id)"
                    class="text-[10px] font-mono px-2 py-1 border border-red-500/30 text-red-400 hover:bg-red-900/20 rounded">
                    Rechazar
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- ROOMS -->
          <div v-else-if="active === 'rooms'">
            <div class="grid grid-cols-2 gap-3 mb-4">
              <div class="bg-black/30 border border-white/10 rounded-xl p-3">
                <p class="text-white/40 text-[10px] font-mono mb-2">CREAR SALA</p>
                <div class="flex gap-2">
                  <input v-model="newRoomName" placeholder="Nombre (opcional)"
                    class="flex-1 bg-black/40 border border-white/15 rounded px-2 py-1.5 text-white font-mono text-xs focus:border-yellow-500/60 focus:outline-none" />
                  <button @click="onCreateRoom"
                    class="text-xs font-mono px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-black font-bold rounded">
                    Crear
                  </button>
                </div>
              </div>
              <div class="bg-black/30 border border-white/10 rounded-xl p-3">
                <p class="text-white/40 text-[10px] font-mono mb-2">UNIRSE POR CÓDIGO</p>
                <div class="flex gap-2">
                  <input v-model="joinCodeInput" placeholder="ABCD12" maxlength="6"
                    class="flex-1 bg-black/40 border border-white/15 rounded px-2 py-1.5 text-white font-mono text-xs uppercase focus:border-yellow-500/60 focus:outline-none" />
                  <button @click="onJoinRoom"
                    class="text-xs font-mono px-3 py-1.5 bg-yellow-600 hover:bg-yellow-500 text-black font-bold rounded">
                    Entrar
                  </button>
                </div>
              </div>
            </div>

            <div v-if="currentRoom" class="bg-black/30 border border-yellow-500/40 rounded-xl p-4">
              <div class="flex items-center justify-between mb-3">
                <div>
                  <p class="text-yellow-300 font-mono font-bold">{{ currentRoom.name || 'Sala sin nombre' }}</p>
                  <code class="text-white/60 font-mono text-xl tracking-widest">{{ currentRoom.code }}</code>
                </div>
                <button @click="copyRoomLink" class="text-[10px] font-mono px-2 py-1 border border-white/15 text-white/60 hover:text-white rounded">
                  {{ roomCopied ? '✓ Copiado' : '📋 Link' }}
                </button>
              </div>
              <p class="text-white/40 text-[10px] font-mono mb-2">MIEMBROS ({{ currentRoom.members.length }}/8)</p>
              <div class="space-y-1">
                <div v-for="m in currentRoom.members" :key="m.riot_id"
                  class="flex items-center justify-between bg-black/20 border border-white/5 rounded px-2 py-1">
                  <span class="text-white text-xs font-mono">{{ m.riot_id }}</span>
                  <button v-if="auth?.user.value?.riot_id === m.riot_id" @click="onLeaveRoom(m.riot_id)"
                    class="text-[10px] font-mono text-red-400 hover:text-red-300">salir</button>
                </div>
              </div>
              <p v-if="!currentRoom.members.length" class="text-white/30 text-xs font-mono text-center py-4">
                Sin miembros aún. Invita por código.
              </p>
            </div>
            <p v-else class="text-white/30 text-sm font-mono text-center py-8">
              Crea una sala o únete con un código de 6 chars.
            </p>
          </div>
        </div>
      </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch, inject } from 'vue'

const props = defineProps<{ show: boolean; initialTab?: string }>()
const emit = defineEmits<{ close: []; refresh: [] }>()

const auth = inject<any>('auth')

type TabKey = 'hot' | 'leaderboards' | 'friends' | 'rooms'
const tabs: { key: TabKey; label: string }[] = [
  { key: 'hot', label: '🔥 Hot Bets' },
  { key: 'leaderboards', label: '🏆 Leaderboards' },
  { key: 'friends', label: '👥 Amigos' },
  { key: 'rooms', label: '🏠 Salas' },
]
const leaderboardKinds = [
  { key: 'currency' as const, label: 'Más TC' },
  { key: 'bets' as const, label: 'Mejores apostadores' },
  { key: 'accuracy' as const, label: 'Mejor accuracy' },
]

const active = ref<'hot' | 'leaderboards' | 'friends' | 'rooms'>('hot')
const openBets = ref<any[]>([])
const lbKind = ref<'currency' | 'bets' | 'accuracy'>('currency')
const leaderboard = ref<any[]>([])
const friends = ref<any[]>([])
const friendSearchInput = ref('')
const addingFriend = ref(false)
const friendError = ref('')
const newRoomName = ref('')
const joinCodeInput = ref('')
const currentRoom = ref<any>(null)
const roomCopied = ref(false)

watch(() => props.show, async v => {
  if (v) {
    if (props.initialTab) active.value = props.initialTab as 'hot' | 'leaderboards' | 'friends' | 'rooms'
    await loadActive()
  }
})

watch(active, () => loadActive())

async function loadActive() {
  if (active.value === 'hot') openBets.value = await auth.fetchOpenBets()
  if (active.value === 'leaderboards') await loadLeaderboard()
  if (active.value === 'friends') friends.value = await auth.fetchFriends()
}

async function loadLeaderboard() {
  leaderboard.value = await auth.fetchLeaderboard(lbKind.value)
}

async function onAccept(b: any) {
  try {
    await auth.acceptBet(b.share_code)
    await loadActive()
    emit('refresh')
  } catch (e: any) {
    alert(e.message || 'Error')
  }
}

async function onAddFriend() {
  if (!friendSearchInput.value.trim()) return
  addingFriend.value = true
  friendError.value = ''
  try {
    await auth.addFriend(friendSearchInput.value.trim())
    friendSearchInput.value = ''
    friends.value = await auth.fetchFriends()
  } catch (e: any) {
    friendError.value = e.message || 'Error'
  } finally {
    addingFriend.value = false
  }
}

async function onAcceptFriend(id: number) {
  await auth.acceptFriend(id)
  friends.value = await auth.fetchFriends()
}

async function onRejectFriend(id: number) {
  await auth.rejectFriend(id)
  friends.value = await auth.fetchFriends()
}

async function onCreateRoom() {
  try {
    currentRoom.value = await auth.createRoom(newRoomName.value)
    newRoomName.value = ''
  } catch (e: any) {
    alert(e.message || 'Error creando sala')
  }
}

async function onJoinRoom() {
  const code = joinCodeInput.value.trim().toUpperCase()
  if (!code) return
  try {
    currentRoom.value = await auth.joinRoom(code)
    joinCodeInput.value = ''
  } catch (e: any) {
    alert(e.message || 'Error uniéndose')
  }
}

async function onLeaveRoom(riotId: string) {
  if (!currentRoom.value) return
  await auth.leaveRoom(currentRoom.value.code, riotId)
  currentRoom.value = await auth.fetchRoom(currentRoom.value.code)
}

async function copyRoomLink() {
  if (!currentRoom.value) return
  const url = `${window.location.origin}${window.location.pathname}#/room/${currentRoom.value.code}`
  try {
    await navigator.clipboard.writeText(url)
    roomCopied.value = true
    setTimeout(() => { roomCopied.value = false }, 2000)
  } catch {}
}
</script>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
