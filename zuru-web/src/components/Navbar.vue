<script setup lang="ts">
import { computed, inject, ref, onMounted, defineAsyncComponent } from 'vue';
import { useVisibilityPoller } from '../composables/useVisibilityPoller';
import { DAILY_REWARD_AMOUNT } from '../composables/econConfig';
import { sfx } from '../composables/useSfx';
// Modales lazy: la mayoría de visitas no los abre. Saca ~15KB gzip del bundle inicial.
const MyBetsModal = defineAsyncComponent(() => import('./MyBetsModal.vue'));
const SocialModal = defineAsyncComponent(() => import('./SocialModal.vue'));
const UserModal = defineAsyncComponent(() => import('./UserModal.vue'));
const MissionsModal = defineAsyncComponent(() => import('./MissionsModal.vue'));
import Avatar from './Avatar.vue';

const props = defineProps<{
  currentPage: string;
}>();

const emit = defineEmits<{
  navigate: [page: string];
}>();

const themeKey = inject<ReturnType<typeof ref>>('themeKey')!
const setTheme = inject<(k: string) => void>('setTheme')!
const THEMES = inject<Record<string, { from: string; to: string; accent: string; label: string }>>('THEMES')!
const auth = inject<any>('auth')

const showThemes = ref(false)
const showUserMenu = ref(false)
const claimingDaily = ref(false)
const dailyResult = ref<{ awarded: number } | null>(null)
const showMyBets = ref(false)
const showSocial = ref(false)
const showMissions = ref(false)
const socialInitialTab = ref<string | undefined>(undefined)
const showUserModal = ref(false)
const userModalTab = ref<string | undefined>(undefined)
const notifications = ref<any[]>([])
const showNotifPanel = ref(false)

// Friends LIVE state
interface FriendsLiveResponse {
  friends: Array<{
    user_id: number; username: string; avatar: string | null;
    discord_id: string; riot_id: string;
    champion_name: string | null; champion_id: number | null;
    queue_id: number; queue_name: string;
    game_start_time: number; game_length: number; in_game: boolean;
  }>
  checked: number
  cached: boolean
  next_refresh_at: number
}
const friendsLiveData = ref<FriendsLiveResponse | null>(null)
const showFriendsLive = ref(false)
const friendsLiveLoading = ref(false)

const friendsLiveCount = computed(() => friendsLiveData.value?.friends?.length ?? 0)

const unreadCount = computed(() => notifications.value.length)

async function pollNotifs() {
  if (!auth?.isLoggedIn.value) return
  notifications.value = await auth.fetchNotifications()
}

async function pollFriendsLive() {
  if (!auth?.isLoggedIn.value) return
  friendsLiveLoading.value = true
  try {
    const data = await auth.fetchFriendsLive()
    if (data) friendsLiveData.value = data
  } finally {
    friendsLiveLoading.value = false
  }
}

function onToggleFriendsLive() {
  showFriendsLive.value = !showFriendsLive.value
  // Si nunca se ha cargado o el cache caducó, refresh al abrir
  if (showFriendsLive.value) {
    const stale = !friendsLiveData.value ||
      (friendsLiveData.value?.next_refresh_at ?? 0) < (Date.now() / 1000)
    if (stale) pollFriendsLive()
  }
}

function onRefreshFriendsLive() {
  pollFriendsLive()
}

function onOpenLiveFriend(f: any) {
  // Abrir el Overview de ese amigo via hash route
  if (f.riot_id) {
    const safe = encodeURIComponent(f.riot_id)
    window.location.hash = `#/u/${safe}`
  }
}

function formatGameLength(seconds: number): string {
  if (!seconds || seconds < 0) return ''
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function notifTimeAgo(epoch: number): string {
  const sec = Math.floor(Date.now() / 1000 - epoch)
  if (sec < 60) return `${sec}s`
  if (sec < 3600) return `${Math.floor(sec / 60)}m`
  if (sec < 86400) return `${Math.floor(sec / 3600)}h`
  return `${Math.floor(sec / 86400)}d`
}

async function markAllRead() {
  if (!notifications.value.length) return
  const ids = notifications.value.map(n => n.id)
  try {
    await auth.markNotificationsRead(ids)
    // Sólo vaciamos local si el backend confirmó. Si falló, mantenemos
    // las notifs visibles — en el próximo poll volverían igualmente
    // porque siguen con read=0, y eso confundiría visualmente.
    notifications.value = []
  } catch {
    // Silencioso: la próxima poll las refrescará. El user verá que sigue ahí
    // y puede reintentar.
  }
}

function openNotif(n: any) {
  // Si la notif lleva un link tipo "#/bets" abrir Mis Apuestas, "#/friends" abrir Social>friends, etc
  if (n.link === '#/bets') showMyBets.value = true
  else if (n.link === '#/friends') { socialInitialTab.value = 'friends'; showSocial.value = true }
  // Marcar leída
  auth.markNotificationsRead([n.id])
  notifications.value = notifications.value.filter(x => x.id !== n.id)
}

// Pollers visibility-aware: se pausan cuando la pestaña está hidden y se
// re-disparan al volver al foreground (ahorro de battery/data en background).
// Los callbacks ya hacen short-circuit interno si !auth.isLoggedIn — así el
// poller funciona aunque el user haga login después del mount, sin tener que
// re-armar setInterval.
useVisibilityPoller(pollNotifs, 30000, { immediate: true })
useVisibilityPoller(pollFriendsLive, 90000)
onMounted(() => {
  // Primer pull friendsLive a los 5s sólo si ya hay sesión: no bloquea load.
  // Si no hay sesión todavía, el poller arrancará en el siguiente tick (90s).
  if (auth?.isLoggedIn.value) setTimeout(pollFriendsLive, 5000)
})

const navBgColor = computed(() => {
  const colors: Record<string, string> = {
    'oncologico': 'bg-[#143a32]',
    'mental': 'bg-[#2f0535]',
    'tinder': 'bg-[#762d79]',
    'overview': 'bg-theme-from',
    'compare': 'bg-[#1a0d2e]',
  };
  return colors[props.currentPage] || 'bg-[#143a32]';
});

// Tick cada 60s para refrescar el countdown del daily reward. Pausable en
// background — al volver al foreground el composable hace fire-on-visible y
// el countdown salta al tiempo correcto sin esperar al próximo tick.
const nowTs = ref(Date.now() / 1000)
useVisibilityPoller(() => { nowTs.value = Date.now() / 1000 }, 60_000)

const dailyAmount = computed(() => auth?.user.value?.daily?.amount ?? DAILY_REWARD_AMOUNT)
const dailyStreak = computed(() => (auth?.user.value?.daily?.streak ?? 0) as number)
const dailyStreakAtRisk = computed(() => Boolean(auth?.user.value?.daily?.streak_at_risk))
const dailyCountdown = computed(() => {
  const next = auth?.user.value?.daily?.next_claim_at
  if (!next) return ''
  const secs = Math.max(0, Math.floor(next - nowTs.value))
  if (secs <= 0) return '✓'
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  if (h >= 1) return `${h}h ${m}m`
  return `${m}m`
})

const claimDaily = async () => {
  if (claimingDaily.value) return
  claimingDaily.value = true
  dailyResult.value = null
  const result = await auth.claimDaily()
  if (result) {
    dailyResult.value = result
    sfx.chime() // #50 — daily claim feel-good chime, no-op si opt-in está off.
  }
  claimingDaily.value = false
  setTimeout(() => { dailyResult.value = null }, 3000)
}
</script>

<template>
  <nav :class="[navBgColor, 'backdrop-blur-md border-b border-accent-30 sticky top-0 z-50 shadow-lg']"
    :style="{ boxShadow: '0 4px 24px -8px color-mix(in srgb, var(--theme-accent, #c89b3c) 35%, transparent)' }">
    <div class="max-w-6xl mx-auto px-3 sm:px-6 py-3 flex flex-wrap justify-center items-center gap-2 sm:gap-4">
      <!-- Anchor tags en lugar de buttons para que:
           - El URL del hover se vea en bottom-left del navegador
           - Right-click / middle-click → "Abrir en nueva pestaña" funcionen
           - aria-current="page" da accesibilidad de SPA decente
           @click.prevent: bloqueamos la navegación nativa (que dispararía
           hashchange + navigate) y emitimos manualmente para no doblar el evento. -->
      <a href="#/" @click.prevent="emit('navigate', 'overview')"
        :aria-current="currentPage === 'overview' ? 'page' : undefined"
        :class="[
          'px-6 py-2.5 rounded-lg font-bold transition duration-300 font-mono text-sm tracking-wide',
          'hover:-translate-y-1 active:translate-y-0 no-underline',
          currentPage === 'overview'
            ? 'text-black shadow-lg'
            : 'text-white bg-white/10 hover:bg-white/20 border border-accent-30'
        ]"
        :style="currentPage === 'overview' ? {
          backgroundColor: 'var(--theme-accent, #c89b3c)',
          boxShadow: '0 10px 15px -3px color-mix(in srgb, var(--theme-accent, #c89b3c) 55%, transparent)'
        } : undefined">
        Top Tumores
      </a>
      <a href="#/compare" @click.prevent="emit('navigate', 'compare')"
        :aria-current="currentPage === 'compare' ? 'page' : undefined"
        :class="[
          'px-6 py-2.5 rounded-lg font-bold transition duration-300 font-mono text-sm tracking-wide',
          'hover:-translate-y-1 active:translate-y-0 no-underline',
          currentPage === 'compare'
            ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/50'
            : 'text-white bg-white/10 hover:bg-white/20 border border-accent-30'
        ]">
        Versus ⚔️
      </a>

      <div class="flex-1"></div>

      <!-- Hot bets / leaderboards -->
      <!-- #49 — Missions diarias/semanales. Trigger compacto al lado del
           Social. Lazy modal, sin coste en initial bundle. -->
      <button v-if="auth && auth.isLoggedIn.value" @click="showMissions = true"
        class="relative px-3 py-2 text-sm rounded-lg border border-white/15 text-white/70 hover:text-purple-300 hover:border-purple-500/40 transition font-mono"
        v-tooltip="'Misiones diarias y semanales'">
        🎯
      </button>

      <button v-if="auth && auth.isLoggedIn.value" @click="socialInitialTab = 'hot'; showSocial = true"
        class="relative px-3 py-2 text-sm rounded-lg border border-white/15 text-white/70 hover:text-yellow-300 hover:border-yellow-500/40 transition font-mono"
        v-tooltip="'Hot Bets · Leaderboards · Amigos · Salas'">
        🌐
      </button>

      <!-- Friends LIVE: amigos en partida ahora -->
      <div v-if="auth && auth.isLoggedIn.value" class="relative">
        <button @click="onToggleFriendsLive"
          class="relative px-3 py-2 text-sm rounded-lg border transition flex items-center gap-1"
          :class="friendsLiveCount > 0
            ? 'border-red-500/60 text-red-300 bg-red-950/40 hover:bg-red-900/40 animate-pulse'
            : 'border-white/15 text-white/50 hover:text-white/80 hover:border-white/30'"
          v-tooltip="friendsLiveCount > 0 ? `${friendsLiveCount} ${friendsLiveCount === 1 ? 'amigo' : 'amigos'} en partida` : 'Sin amigos en partida'">
          <span class="text-base">🟢</span>
          <span v-if="friendsLiveCount > 0" class="text-[10px] font-mono font-bold">{{ friendsLiveCount }}</span>
        </button>
        <Transition name="dropdown">
          <div v-if="showFriendsLive"
            class="absolute right-0 top-12 w-80 bg-theme-from border border-accent-30 rounded-xl shadow-2xl z-50 max-h-96 overflow-hidden flex flex-col">
            <div class="flex items-center justify-between px-4 py-2 border-b border-white/10">
              <p class="text-white/70 text-xs font-mono font-bold">🟢 Amigos en partida</p>
              <button v-if="friendsLiveData" @click="onRefreshFriendsLive" :disabled="friendsLiveLoading"
                class="text-[10px] font-mono text-white/40 hover:text-white/70 disabled:opacity-40">
                {{ friendsLiveLoading ? '...' : '↻' }}
              </button>
            </div>
            <div v-if="friendsLiveLoading && !friendsLiveData"
              class="px-4 py-8 text-center">
              <p class="text-white/30 text-xs font-mono">Buscando partidas...</p>
            </div>
            <div v-else-if="!friendsLiveCount" class="px-4 py-8 text-center">
              <p class="text-white/30 text-xs font-mono">Ningún amigo en partida ahora</p>
              <p v-if="friendsLiveData?.checked" class="text-white/20 text-[10px] font-mono mt-1">
                ({{ friendsLiveData.checked }} amigos chequeados)
              </p>
            </div>
            <div v-else class="overflow-y-auto divide-y divide-white/5">
              <button v-for="f in friendsLiveData?.friends || []" :key="f.user_id"
                @click="onOpenLiveFriend(f); showFriendsLive = false"
                class="w-full text-left px-4 py-3 hover:bg-white/5 transition flex items-center gap-3">
                <Avatar :discord-id="f.discord_id" :avatar="f.avatar" :username="f.username" size="lg" />
                <div class="flex-1 min-w-0">
                  <p class="text-white text-xs font-mono font-bold truncate">{{ f.username }}</p>
                  <p class="text-white/50 text-[10px] font-mono truncate">
                    <span v-if="f.champion_name" class="text-red-300">{{ f.champion_name }}</span>
                    <span v-if="f.queue_name" class="text-white/30"> · {{ f.queue_name }}</span>
                  </p>
                </div>
                <span class="text-[9px] font-mono text-white/40 shrink-0">
                  {{ formatGameLength(f.game_length) }}
                </span>
              </button>
            </div>
            <div v-if="friendsLiveData?.next_refresh_at" class="px-4 py-1.5 border-t border-white/5 bg-black/30">
              <p class="text-white/30 text-[9px] font-mono text-center">
                cache 60s · próximo refresh manual
              </p>
            </div>
          </div>
        </Transition>
      </div>

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
          <div v-if="showNotifPanel" class="absolute right-0 top-12 w-80 bg-theme-from border border-accent-30 rounded-xl shadow-2xl z-50 max-h-96 overflow-hidden flex flex-col">
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
                  <div class="flex items-baseline justify-between gap-2">
                    <p class="text-white text-xs font-mono font-bold truncate">{{ n.title }}</p>
                    <p v-if="n.created_at" class="text-white/30 text-[9px] font-mono shrink-0">{{ notifTimeAgo(n.created_at) }}</p>
                  </div>
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
        <button v-if="auth.user.value" @click="claimDaily"
          :disabled="claimingDaily || !auth.user.value.can_claim_daily"
          class="text-xs font-mono px-2.5 py-1.5 rounded-lg transition flex items-center gap-1.5 disabled:cursor-not-allowed"
          :class="auth.user.value.can_claim_daily
            ? 'border border-yellow-500/60 text-yellow-300 bg-yellow-900/20 hover:bg-yellow-900/40 animate-pulse'
            : 'border border-white/15 text-white/40'"
          v-tooltip="auth.user.value.can_claim_daily
            ? `+${dailyAmount} TC disponible${dailyStreak >= 1 ? ` · 🔥 racha ${dailyStreak}` : ''}`
            : `Próximo daily en ${dailyCountdown}${dailyStreak >= 1 ? ` · 🔥 racha ${dailyStreak}` : ''}`">
          <span class="text-base leading-none">🎁</span>
          <span v-if="auth.user.value.can_claim_daily" class="font-bold">+{{ dailyAmount }}</span>
          <span v-else class="text-[10px]">{{ dailyCountdown }}</span>
        </button>
        <!-- #48 Daily-streak flame Duolingo-style. Visible cuando hay racha
             ≥2 O cuando está at_risk (incluido streak=1 a punto de romperse).
             at_risk solo o streak<2 con riesgo era invisible al user que MÁS
             necesita el recordatorio. Bug MEDIUM cazado por review. -->
        <div v-if="auth.user.value && (dailyStreak >= 2 || dailyStreakAtRisk)"
          class="text-xs font-mono px-2 py-1.5 rounded-lg border flex items-center gap-1 select-none"
          :class="dailyStreakAtRisk
            ? 'border-orange-500/50 text-orange-300 bg-orange-950/30 animate-pulse'
            : 'border-yellow-500/40 text-yellow-200 bg-yellow-950/20'"
          v-tooltip="dailyStreakAtRisk
            ? `Racha de ${dailyStreak} días — reclama hoy o se rompe`
            : `Racha de ${dailyStreak} días consecutivos reclamando daily`">
          <span class="text-base leading-none">🔥</span>
          <span class="font-bold">{{ dailyStreak }}</span>
        </div>
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
          <Avatar :discord-id="auth.user.value?.discord_id" :avatar="auth.user.value?.avatar"
            :username="auth.user.value?.username" size="sm" />
          <span class="text-white text-xs font-mono">{{ auth.user.value?.username }}</span>
        </button>

        <Transition name="dropdown">
          <div v-if="showUserMenu && auth.isLoggedIn.value" class="absolute right-0 top-12 bg-theme-from border border-accent-30 rounded-xl shadow-2xl p-2 min-w-[200px] z-50">
            <div class="px-3 py-2 border-b border-white/10 mb-1">
              <p class="text-white text-sm font-mono">{{ auth.user.value?.username }}</p>
              <p v-if="auth.user.value?.riot_id" class="text-[#c89b3c] text-[10px] font-mono">{{ auth.user.value?.riot_id }}</p>
              <p v-else class="text-white/40 text-[10px] font-mono italic">Sin Riot ID vinculado</p>
            </div>
            <button @click="showMyBets = true; showUserMenu = false"
              class="w-full text-left px-3 py-1.5 rounded-lg text-xs font-mono text-yellow-300 hover:bg-yellow-900/20 transition">
              ☢ Mis apuestas
            </button>
            <button @click="userModalTab = 'achievements'; showUserModal = true; showUserMenu = false"
              class="w-full text-left px-3 py-1.5 rounded-lg text-xs font-mono text-yellow-300 hover:bg-yellow-900/20 transition">
              🏅 Logros
            </button>
            <button @click="userModalTab = 'settings'; showUserModal = true; showUserMenu = false"
              class="w-full text-left px-3 py-1.5 rounded-lg text-xs font-mono text-white/60 hover:bg-white/10 hover:text-white transition">
              ⚙ Ajustes
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
          v-tooltip="'Cambiar tema'">
          🎨
        </button>
        <Transition name="dropdown">
          <div v-if="showThemes" class="absolute right-0 top-10 bg-theme-from border border-accent-40 rounded-xl shadow-2xl p-2 min-w-[200px] max-h-[70vh] overflow-y-auto z-50">
            <p class="text-white/30 text-[9px] font-mono tracking-widest px-2 pb-2">TEMA</p>
            <button v-for="(t, key) in THEMES" :key="key"
              @click="setTheme(key); showThemes = false"
              :class="themeKey === key ? 'bg-white/15 text-white' : 'text-white/60 hover:bg-white/10 hover:text-white'"
              class="w-full text-left px-3 py-1.5 rounded-lg text-xs font-mono transition flex items-center justify-between gap-2">
              <span class="flex items-center gap-2 min-w-0">
                <!-- Swatch preview: mini gradient + accent dot. Da pista visual
                     antes de aplicar el theme. -->
                <span class="relative w-6 h-3.5 rounded shrink-0 border border-white/10"
                  :style="{ background: `linear-gradient(135deg, ${t.from}, ${t.to})` }">
                  <span v-if="t.accent"
                    class="absolute -right-0.5 -top-0.5 w-1.5 h-1.5 rounded-full border border-black/30"
                    :style="{ background: t.accent }"></span>
                </span>
                <span class="truncate">{{ t.label }}</span>
              </span>
              <span v-if="themeKey === key" class="text-[10px] shrink-0">✓</span>
            </button>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Daily reward toast -->
    <Transition name="dropdown">
      <div v-if="dailyResult" class="fixed top-20 right-6 z-[100] bg-yellow-900/90 border border-yellow-500/60 rounded-xl shadow-2xl px-4 py-3 backdrop-blur">
        <p class="text-yellow-300 text-[10px] font-mono tracking-widest">{{ $t('daily.label') }}</p>
        <p class="text-yellow-100 font-mono text-sm font-bold">+{{ dailyResult.awarded }} ☢ TC</p>
      </div>
    </Transition>

    <!-- Async-loaded: sólo se descargan al primer click del botón correspondiente.
         v-if (no v-show) garantiza que defineAsyncComponent no fuerce el fetch al mount.
         Al cerrar se desmontan; al reabrir el chunk ya está cacheado, abre instantáneo. -->
    <MyBetsModal v-if="showMyBets" :show="true" @close="showMyBets = false" />
    <SocialModal v-if="showSocial" :show="true" :initial-tab="socialInitialTab" @close="showSocial = false" />
    <UserModal v-if="showUserModal" :show="true" :initial-tab="userModalTab" @close="showUserModal = false" />
    <MissionsModal v-if="showMissions" :show="true" @close="showMissions = false" />
  </nav>
</template>

<style scoped>
.dropdown-enter-active, .dropdown-leave-active { transition: opacity 0.15s, transform 0.15s; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
