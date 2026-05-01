<script setup lang="ts">
import { computed, inject, ref, onMounted, onUnmounted } from 'vue';
import MyBetsModal from './MyBetsModal.vue';
import SocialModal from './SocialModal.vue';

const props = defineProps<{
  currentPage: string;
}>();

const emit = defineEmits<{
  navigate: [page: string];
}>();

const themeKey = inject<ReturnType<typeof ref>>('themeKey')!
const setTheme = inject<(k: string) => void>('setTheme')!
const THEMES = inject<Record<string, { from: string; to: string; label: string }>>('THEMES')!
const auth = inject<any>('auth')

const showThemes = ref(false)
const showUserMenu = ref(false)
const claimingDaily = ref(false)
const dailyResult = ref<{ awarded: number } | null>(null)
const showMyBets = ref(false)
const showSocial = ref(false)
const socialInitialTab = ref<string | undefined>(undefined)
const notifications = ref<any[]>([])
const showNotifPanel = ref(false)
let notifPollerId: ReturnType<typeof setInterval> | null = null

const unreadCount = computed(() => notifications.value.length)

async function pollNotifs() {
  if (!auth?.isLoggedIn.value) return
  notifications.value = await auth.fetchNotifications()
}

async function markAllRead() {
  if (!notifications.value.length) return
  const ids = notifications.value.map(n => n.id)
  await auth.markNotificationsRead(ids)
  notifications.value = []
}

function openNotif(n: any) {
  // Si la notif lleva un link tipo "#/bets" abrir Mis Apuestas, "#/friends" abrir Social>friends, etc
  if (n.link === '#/bets') showMyBets.value = true
  else if (n.link === '#/friends') { socialInitialTab.value = 'friends'; showSocial.value = true }
  // Marcar leída
  auth.markNotificationsRead([n.id])
  notifications.value = notifications.value.filter(x => x.id !== n.id)
}

onMounted(() => {
  if (auth?.isLoggedIn.value) {
    pollNotifs()
    notifPollerId = setInterval(pollNotifs, 30000) // cada 30s
  }
})
onUnmounted(() => {
  if (notifPollerId) clearInterval(notifPollerId)
})

const navBgColor = computed(() => {
  const colors: Record<string, string> = {
    'oncologico': 'bg-[#143a32]',
    'mental': 'bg-[#2f0535]',
    'tinder': 'bg-[#762d79]',
    'overview': 'bg-[#0d1b2a]',
    'compare': 'bg-[#1a0d2e]',
  };
  return colors[props.currentPage] || 'bg-[#143a32]';
});

const avatarUrl = computed(() => {
  const u = auth?.user.value
  if (!u || !u.avatar) return null
  return `https://cdn.discordapp.com/avatars/${u.discord_id}/${u.avatar}.png?size=64`
})

const claimDaily = async () => {
  if (claimingDaily.value) return
  claimingDaily.value = true
  dailyResult.value = null
  const result = await auth.claimDaily()
  if (result) dailyResult.value = result
  claimingDaily.value = false
  setTimeout(() => { dailyResult.value = null }, 3000)
}
</script>

<template>
  <nav :class="[navBgColor, 'backdrop-blur-md border-b border-white/20 sticky top-0 z-50 shadow-lg']">
    <div class="max-w-6xl mx-auto px-6 py-3 flex justify-center items-center gap-4">
      <button @click="emit('navigate', 'overview')" :class="[
        'px-6 py-2.5 rounded-lg font-bold transition duration-300 font-mono text-sm tracking-wide',
        'hover:-translate-y-1 active:translate-y-0',
        currentPage === 'overview'
          ? 'bg-[#c89b3c] text-black shadow-lg shadow-[#c89b3c]/50'
          : 'text-white bg-white/10 hover:bg-white/20 border border-white/20'
      ]">
        Top Tumores
      </button>
      <button @click="emit('navigate', 'compare')" :class="[
        'px-6 py-2.5 rounded-lg font-bold transition duration-300 font-mono text-sm tracking-wide',
        'hover:-translate-y-1 active:translate-y-0',
        currentPage === 'compare'
          ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/50'
          : 'text-white bg-white/10 hover:bg-white/20 border border-white/20'
      ]">
        Versus ⚔️
      </button>

      <div class="flex-1"></div>

      <!-- Hot bets / leaderboards -->
      <button v-if="auth && auth.isLoggedIn.value" @click="socialInitialTab = 'hot'; showSocial = true"
        class="relative px-3 py-2 text-sm rounded-lg border border-white/15 text-white/70 hover:text-yellow-300 hover:border-yellow-500/40 transition font-mono"
        title="Hot Bets · Leaderboards · Amigos · Salas">
        🌐
      </button>

      <!-- Notifications bell -->
      <div v-if="auth && auth.isLoggedIn.value" class="relative">
        <button @click="showNotifPanel = !showNotifPanel; if (showNotifPanel) pollNotifs()"
          class="relative px-3 py-2 text-sm rounded-lg border border-white/15 text-white/70 hover:text-yellow-300 hover:border-yellow-500/40 transition">
          🔔
          <span v-if="unreadCount > 0"
            class="absolute -top-1 -right-1 bg-red-500 text-white text-[9px] font-bold rounded-full min-w-4 h-4 px-1 flex items-center justify-center">
            {{ unreadCount }}
          </span>
        </button>
        <Transition name="dropdown">
          <div v-if="showNotifPanel" class="absolute right-0 top-12 w-80 bg-[#0d1b2a] border border-white/20 rounded-xl shadow-2xl z-50 max-h-96 overflow-hidden flex flex-col">
            <div class="flex items-center justify-between px-4 py-2 border-b border-white/10">
              <p class="text-white/70 text-xs font-mono font-bold">🔔 Notificaciones</p>
              <button v-if="notifications.length" @click="markAllRead"
                class="text-[10px] font-mono text-white/40 hover:text-white/70">Marcar leídas</button>
            </div>
            <div v-if="!notifications.length" class="px-4 py-8 text-center">
              <p class="text-white/30 text-xs font-mono">Sin notificaciones nuevas</p>
            </div>
            <div v-else class="overflow-y-auto divide-y divide-white/5">
              <button v-for="n in notifications" :key="n.id" @click="openNotif(n); showNotifPanel = false"
                class="w-full text-left px-4 py-3 hover:bg-white/5 transition flex items-start gap-3">
                <span class="text-lg shrink-0">{{ n.icon || '·' }}</span>
                <div class="flex-1 min-w-0">
                  <p class="text-white text-xs font-mono font-bold truncate">{{ n.title }}</p>
                  <p v-if="n.body" class="text-white/40 text-[10px] font-mono truncate">{{ n.body }}</p>
                </div>
              </button>
            </div>
          </div>
        </Transition>
      </div>

      <!-- Tumor Coins balance + daily reward -->
      <div v-if="auth && auth.isLoggedIn.value" class="flex items-center gap-2">
        <div class="flex items-center gap-1.5 bg-yellow-900/30 border border-yellow-500/40 rounded-lg px-3 py-1.5 font-mono text-yellow-300 text-sm">
          <span class="text-base">☢</span>
          <span class="font-bold">{{ auth.user.value?.currency ?? 0 }}</span>
          <span class="text-yellow-500/70 text-[10px]">TC</span>
        </div>
        <button v-if="auth.user.value && !auth.user.value.last_daily_blocked" @click="claimDaily"
          :disabled="claimingDaily"
          class="text-xs font-mono px-2.5 py-1.5 border border-yellow-500/40 text-yellow-300 hover:bg-yellow-900/30 rounded-lg transition disabled:opacity-30"
          title="Reclamar daily reward (cada 20h)">
          🎁
        </button>
      </div>

      <!-- Login / user menu -->
      <div v-if="auth" class="relative">
        <button v-if="!auth.isLoggedIn.value" @click="auth.loginWithDiscord()"
          class="px-3 py-2 text-sm font-bold rounded-lg bg-[#5865F2] text-white hover:bg-[#4752c4] transition flex items-center gap-2 font-mono">
          <svg width="16" height="16" viewBox="0 0 71 55" fill="currentColor"><path d="M60.1 4.9C55.5 2.8 50.5 1.3 45.4 0.4c-0.1 0-0.2 0-0.2 0.1c-0.6 1.1-1.3 2.6-1.8 3.7c-5.5-0.8-10.9-0.8-16.3 0c-0.5-1.1-1.2-2.6-1.8-3.7c-0.1-0.1-0.2-0.1-0.2-0.1c-5.1 0.9-10.1 2.4-14.7 4.5c-0.1 0-0.1 0.1-0.1 0.1C0.9 19.2-1.5 33 0.7 46.7c0 0.1 0.1 0.1 0.1 0.2c5.9 4.3 11.7 7 17.4 8.7c0.1 0 0.2 0 0.2-0.1c1.4-1.9 2.6-3.9 3.6-6c0.1-0.1 0-0.2-0.1-0.3c-2-0.7-3.9-1.6-5.7-2.6c-0.1-0.1-0.1-0.3 0-0.3c0.4-0.3 0.8-0.6 1.2-0.9c0.1 0 0.2-0.1 0.2 0c11.9 5.4 24.7 5.4 36.5 0c0.1 0 0.2 0 0.2 0c0.4 0.3 0.8 0.6 1.2 0.9c0.1 0.1 0.1 0.3 0 0.3c-1.8 1.1-3.7 1.9-5.7 2.6c-0.1 0-0.1 0.2-0.1 0.3c1.1 2.1 2.3 4.1 3.6 6c0.1 0.1 0.2 0.1 0.3 0.1c5.7-1.8 11.5-4.4 17.4-8.7c0.1 0 0.1-0.1 0.1-0.2c2.6-15.8-1.1-29.5-9.9-41.7C60.2 5 60.2 4.9 60.1 4.9zM23.7 38.3c-3.5 0-6.4-3.2-6.4-7.2c0-4 2.8-7.2 6.4-7.2c3.6 0 6.4 3.3 6.4 7.2C30.1 35.1 27.3 38.3 23.7 38.3zM47.4 38.3c-3.5 0-6.4-3.2-6.4-7.2c0-4 2.8-7.2 6.4-7.2c3.6 0 6.4 3.3 6.4 7.2C53.8 35.1 51 38.3 47.4 38.3z"/></svg>
          Login
        </button>
        <button v-else @click="showUserMenu = !showUserMenu"
          class="flex items-center gap-2 px-2 py-1.5 rounded-lg border border-white/20 bg-white/10 hover:bg-white/20 transition">
          <img v-if="avatarUrl" :src="avatarUrl" class="w-6 h-6 rounded-full" />
          <span v-else class="w-6 h-6 rounded-full bg-[#5865F2] flex items-center justify-center text-white text-xs font-bold">
            {{ auth.user.value?.username?.[0]?.toUpperCase() ?? '?' }}
          </span>
          <span class="text-white text-xs font-mono">{{ auth.user.value?.username }}</span>
        </button>

        <Transition name="dropdown">
          <div v-if="showUserMenu && auth.isLoggedIn.value" class="absolute right-0 top-12 bg-[#0d1b2a] border border-white/20 rounded-xl shadow-2xl p-2 min-w-[200px] z-50">
            <div class="px-3 py-2 border-b border-white/10 mb-1">
              <p class="text-white text-sm font-mono">{{ auth.user.value?.username }}</p>
              <p v-if="auth.user.value?.riot_id" class="text-[#c89b3c] text-[10px] font-mono">{{ auth.user.value?.riot_id }}</p>
              <p v-else class="text-white/40 text-[10px] font-mono italic">Sin Riot ID vinculado</p>
            </div>
            <button @click="showMyBets = true; showUserMenu = false"
              class="w-full text-left px-3 py-1.5 rounded-lg text-xs font-mono text-yellow-300 hover:bg-yellow-900/20 transition">
              ☢ Mis apuestas
            </button>
            <button @click="auth.refreshBalance(); showUserMenu = false"
              class="w-full text-left px-3 py-1.5 rounded-lg text-xs font-mono text-white/60 hover:bg-white/10 hover:text-white transition">
              ↻ Actualizar balance
            </button>
            <button @click="auth.logout(); showUserMenu = false"
              class="w-full text-left px-3 py-1.5 rounded-lg text-xs font-mono text-red-400 hover:bg-red-900/20 transition">
              Cerrar sesión
            </button>
          </div>
        </Transition>
      </div>

      <!-- Theme picker -->
      <div class="relative">
        <button @click="showThemes = !showThemes"
          class="w-8 h-8 rounded-full border border-white/20 bg-white/10 hover:bg-white/20 transition flex items-center justify-center text-sm"
          title="Cambiar tema">
          🎨
        </button>
        <Transition name="dropdown">
          <div v-if="showThemes" class="absolute right-0 top-10 bg-[#0d1b2a] border border-white/20 rounded-xl shadow-2xl p-2 min-w-[140px] z-50">
            <p class="text-white/30 text-[9px] font-mono tracking-widest px-2 pb-2">TEMA</p>
            <button v-for="(t, key) in THEMES" :key="key"
              @click="setTheme(key); showThemes = false"
              :class="themeKey === key ? 'bg-white/15 text-white' : 'text-white/60 hover:bg-white/10 hover:text-white'"
              class="w-full text-left px-3 py-1.5 rounded-lg text-xs font-mono transition flex items-center justify-between">
              {{ t.label }}
              <span v-if="themeKey === key" class="text-[10px]">✓</span>
            </button>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Daily reward toast -->
    <Transition name="dropdown">
      <div v-if="dailyResult" class="fixed top-20 right-6 z-[100] bg-yellow-900/90 border border-yellow-500/60 rounded-xl shadow-2xl px-4 py-3 backdrop-blur">
        <p class="text-yellow-300 text-[10px] font-mono tracking-widest">DAILY REWARD</p>
        <p class="text-yellow-100 font-mono text-sm font-bold">+{{ dailyResult.awarded }} ☢ TC</p>
      </div>
    </Transition>

    <MyBetsModal :show="showMyBets" @close="showMyBets = false" />
    <SocialModal :show="showSocial" :initial-tab="socialInitialTab" @close="showSocial = false" />
  </nav>
</template>

<style scoped>
.dropdown-enter-active, .dropdown-leave-active { transition: opacity 0.15s, transform 0.15s; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
