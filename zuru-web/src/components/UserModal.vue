<template>
  <Teleport to="body">
  <Transition name="modal">
    <div v-if="show"
      class="fixed inset-0 z-[60] bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center overflow-y-auto p-0 pt-0 sm:p-4 sm:pt-4"
      @click.self="emit('close')">
      <!-- En <sm: bottom-sheet anclado al borde inferior, sin radius bajo y
           pb con safe-area-inset para escapar el home indicator iOS.
           En sm+: modal centrado clásico. -->
      <div
        class="bg-[#0d1b2a] border border-accent-30 shadow-2xl w-full max-w-2xl max-h-[88vh] flex flex-col
               rounded-t-2xl rounded-b-none sm:rounded-2xl"
        style="padding-bottom: env(safe-area-inset-bottom);">
        <!-- Drag handle visual mobile-only (no interactivo): hint de que esto
             es un sheet y se cierra con tap fuera/✕. -->
        <div class="sm:hidden flex justify-center pt-2 pb-1">
          <span class="block w-10 h-1 bg-white/20 rounded-full"></span>
        </div>
        <div class="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <p class="text-yellow-200 font-mono font-bold flex items-center gap-2">
            <span>{{ activeIcon }}</span>
            <span>{{ activeLabel }}</span>
          </p>
          <button @click="emit('close')" class="text-white/40 hover:text-white text-xl transition">✕</button>
        </div>

        <div class="flex gap-1 px-5 py-2 border-b border-white/10">
          <button v-for="tab in tabs" :key="tab.key" @click="active = tab.key"
            :class="active === tab.key
              ? 'bg-accent-15 text-accent border-accent-50'
              : 'text-white/40 border-transparent hover:text-white/70'"
            class="text-xs font-mono px-3 py-1.5 rounded border transition">
            {{ tab.label }}
          </button>
        </div>

        <div class="flex-1 overflow-y-auto p-5">
          <!-- ACHIEVEMENTS -->
          <div v-if="active === 'achievements'">
            <!-- Progreso global con barra -->
            <div class="mb-4 bg-gradient-to-r from-yellow-900/20 via-black/30 to-black/30 border border-yellow-500/30 rounded-xl p-3">
              <div class="flex items-center justify-between mb-1.5">
                <p class="text-yellow-200 text-[10px] font-mono tracking-widest">
                  🏆 {{ $t('user.unlocked_count', { count: unlockedCount, total: achievements.length }) }}
                </p>
                <p class="text-yellow-300 text-xs font-mono font-bold">
                  {{ Math.round((unlockedCount / achievements.length) * 100) }}%
                </p>
              </div>
              <div class="h-2 bg-black/40 rounded-full overflow-hidden">
                <div class="h-full bg-gradient-to-r from-yellow-500 to-yellow-300 transition-all"
                  :style="{ width: `${(unlockedCount / achievements.length) * 100}%` }"></div>
              </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div v-for="a in achievements" :key="a.badge"
                :class="a.unlocked
                  ? 'border-yellow-500/50 bg-gradient-to-br from-yellow-900/20 to-black/30 shadow-lg shadow-yellow-900/20'
                  : 'border-white/10 bg-black/20'"
                class="rounded-xl border p-3 flex items-start gap-3 transition">
                <span class="text-3xl shrink-0 transition"
                  :class="a.unlocked ? '' : 'grayscale opacity-40'">{{ a.icon }}</span>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-mono font-bold truncate"
                    :class="a.unlocked ? 'text-white' : 'text-white/60'">{{ a.name }}</p>
                  <p class="text-white/40 text-[11px] font-mono">{{ a.desc }}</p>
                  <!-- Progress bar para progresivos no desbloqueados -->
                  <div v-if="!a.unlocked && a.progress" class="mt-1.5">
                    <div class="flex items-center justify-between text-[9px] font-mono mb-0.5">
                      <span class="text-white/50">{{ a.progress.current }} / {{ a.progress.target }}</span>
                      <span class="text-cyan-400">{{ Math.round((a.progress.current / a.progress.target) * 100) }}%</span>
                    </div>
                    <div class="h-1 bg-black/40 rounded-full overflow-hidden">
                      <div class="h-full bg-cyan-500 transition-all"
                        :style="{ width: `${(a.progress.current / a.progress.target) * 100}%` }"></div>
                    </div>
                  </div>
                  <p v-else-if="a.unlocked" class="text-yellow-400 text-[10px] font-mono mt-1">
                    ✓ {{ $t('user.unlocked') }}
                  </p>
                  <p v-else class="text-white/30 text-[10px] font-mono mt-1">
                    🔒 {{ $t('user.locked') }}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- HISTORY -->
          <div v-else-if="active === 'history'" class="space-y-3">
            <div v-if="txLoading" class="text-white/40 text-sm font-mono text-center py-8">
              {{ $t('common.loading') }}
            </div>
            <div v-else-if="!txHistory.length" class="text-white/40 text-sm font-mono text-center py-8">
              No hay movimientos todavía. Cuando apuestes o reclames daily, verás aquí el historial.
            </div>
            <div v-else>
              <!-- Sumario rápido -->
              <div class="grid grid-cols-3 gap-2 mb-3">
                <div class="bg-green-900/20 border border-green-500/30 rounded-lg p-2 text-center">
                  <p class="text-green-300 text-[9px] font-mono tracking-widest">ENTRADAS</p>
                  <p class="text-green-400 text-base font-mono font-bold">+{{ txHistory.filter(t => t.delta > 0).reduce((a, t) => a + t.delta, 0) }}</p>
                </div>
                <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-2 text-center">
                  <p class="text-red-300 text-[9px] font-mono tracking-widest">SALIDAS</p>
                  <p class="text-red-400 text-base font-mono font-bold">{{ txHistory.filter(t => t.delta < 0).reduce((a, t) => a + t.delta, 0) }}</p>
                </div>
                <div class="bg-yellow-900/20 border border-yellow-500/30 rounded-lg p-2 text-center">
                  <p class="text-yellow-300 text-[9px] font-mono tracking-widest">NETO ÚLT.</p>
                  <p class="text-yellow-400 text-base font-mono font-bold"
                    :class="txHistory.reduce((a, t) => a + t.delta, 0) >= 0 ? 'text-green-400' : 'text-red-400'">
                    {{ txHistory.reduce((a, t) => a + t.delta, 0) >= 0 ? '+' : '' }}{{ txHistory.reduce((a, t) => a + t.delta, 0) }}
                  </p>
                </div>
              </div>

              <p class="text-white/30 text-[9px] font-mono tracking-widest mb-2">ÚLTIMAS 20 TRANSACCIONES</p>
              <div class="space-y-1 max-h-[50vh] overflow-y-auto pr-1">
                <div v-for="(tx, i) in txHistory" :key="i"
                  class="flex items-center gap-2 bg-black/30 border border-white/10 rounded-lg px-3 py-2">
                  <span class="text-lg shrink-0">{{ txCategoryFromReason(tx.reason).icon }}</span>
                  <div class="flex-1 min-w-0">
                    <p class="text-white text-xs font-mono font-bold truncate"
                      :class="txCategoryFromReason(tx.reason).color">
                      {{ txCategoryFromReason(tx.reason).label }}
                    </p>
                    <p class="text-white/40 text-[10px] font-mono truncate">{{ tx.reason }}</p>
                  </div>
                  <div class="text-right shrink-0">
                    <p class="font-mono text-sm font-bold"
                      :class="tx.delta > 0 ? 'text-green-400' : 'text-red-400'">
                      {{ tx.delta > 0 ? '+' : '' }}{{ tx.delta }}
                    </p>
                    <p class="text-white/30 text-[9px] font-mono">{{ timeAgo(tx.at) }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- SETTINGS -->
          <div v-else-if="active === 'settings'" class="space-y-4">
            <div v-if="!settings" class="text-white/40 text-sm font-mono text-center py-8">
              {{ $t('common.loading') }}
            </div>
            <div v-else class="space-y-3">
              <div class="bg-black/30 border border-white/10 rounded-xl p-4">
                <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">{{ $t('user.privacy').toUpperCase() }}</p>
                <div class="space-y-2">
                  <ToggleRow
                    :label="$t('user.public_profile')"
                    :desc="$t('user.public_profile_desc')"
                    :model-value="settings.public_profile"
                    @update:model-value="updateSetting('public_profile', $event)"
                  />
                  <ToggleRow
                    :label="$t('user.allow_friend_requests')"
                    :desc="$t('user.allow_friend_requests_desc')"
                    :model-value="settings.allow_friend_requests"
                    @update:model-value="updateSetting('allow_friend_requests', $event)"
                  />
                </div>
              </div>
              <div class="bg-black/30 border border-white/10 rounded-xl p-4">
                <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">{{ $t('user.notifications').toUpperCase() }}</p>
                <div class="space-y-2">
                  <ToggleRow
                    :label="$t('user.notif_bets')"
                    :desc="$t('user.notif_bets_desc')"
                    :model-value="settings.notif_bets"
                    @update:model-value="updateSetting('notif_bets', $event)"
                  />
                  <ToggleRow
                    :label="$t('user.notif_friends')"
                    :desc="$t('user.notif_friends_desc')"
                    :model-value="settings.notif_friends"
                    @update:model-value="updateSetting('notif_friends', $event)"
                  />
                </div>
              </div>
              <div class="bg-black/30 border border-white/10 rounded-xl p-4">
                <p class="text-white/30 text-[10px] font-mono tracking-widest mb-3">{{ $t('user.language').toUpperCase() }}</p>
                <div class="flex gap-2">
                  <button @click="changeLocale('es')"
                    :class="locale === 'es' ? 'bg-accent-15 text-accent border-accent-50' : 'text-white/50 border-white/10 hover:text-white/80'"
                    class="text-xs font-mono px-3 py-1.5 rounded border transition flex-1">
                    🇪🇸 {{ $t('user.spanish') }}
                  </button>
                  <button @click="changeLocale('en')"
                    :class="locale === 'en' ? 'bg-accent-15 text-accent border-accent-50' : 'text-white/50 border-white/10 hover:text-white/80'"
                    class="text-xs font-mono px-3 py-1.5 rounded border transition flex-1">
                    🇬🇧 {{ $t('user.english') }}
                  </button>
                </div>
              </div>
              <div v-if="auth?.user.value" class="bg-black/30 border border-white/10 rounded-xl p-4">
                <p class="text-white/30 text-[10px] font-mono tracking-widest mb-2">{{ $t('user.account').toUpperCase() }}</p>
                <p class="text-white text-sm font-mono">{{ auth.user.value.username }}</p>

                <!-- Riot ID linked -->
                <div v-if="auth.user.value.riot_id" class="flex items-center gap-2 mt-1">
                  <p class="text-[#c89b3c] text-xs font-mono flex-1 truncate">⚔ {{ auth.user.value.riot_id }}</p>
                  <button @click="onUnlinkRiot" :disabled="unlinking"
                    class="text-[10px] font-mono px-2 py-0.5 border border-red-500/30 text-red-400 hover:bg-red-900/20 rounded disabled:opacity-30">
                    {{ $t('user.unlink') }}
                  </button>
                </div>

                <!-- Riot ID link form -->
                <div v-else class="mt-2">
                  <p class="text-white/40 text-xs font-mono italic mb-2">{{ $t('user.no_riot_linked') }}</p>
                  <p class="text-white/30 text-[10px] font-mono mb-2">{{ $t('user.link_riot_help') }}</p>
                  <div class="flex gap-1.5 items-center">
                    <input v-model="linkGameName" :placeholder="$t('user.game_name')"
                      autocapitalize="off" autocorrect="off" autocomplete="off" spellcheck="false"
                      class="flex-1 min-w-0 bg-black/40 border border-white/15 rounded px-2 py-1 text-white font-mono text-xs focus:border-accent-60 focus:outline-none" />
                    <span class="text-white/30 text-sm font-mono">#</span>
                    <input v-model="linkTagLine" :placeholder="$t('user.tag_line')" maxlength="5"
                      autocapitalize="off" autocorrect="off" autocomplete="off" spellcheck="false"
                      class="w-16 bg-black/40 border border-white/15 rounded px-2 py-1 text-white font-mono text-xs focus:border-accent-60 focus:outline-none" />
                    <button @click="onLinkRiot" :disabled="linking || !linkGameName.trim() || !linkTagLine.trim()"
                      class="text-[10px] font-mono px-2.5 py-1 bg-yellow-600 hover:bg-yellow-500 disabled:bg-yellow-900/40 disabled:text-white/30 text-black font-bold rounded transition">
                      {{ linking ? $t('user.linking') : $t('user.link_btn') }}
                    </button>
                  </div>
                  <p v-if="linkError" class="text-red-400 text-[10px] font-mono mt-1">{{ linkError }}</p>
                </div>

                <p v-if="publicProfileUrl && settings.public_profile" class="text-white/40 text-[10px] font-mono mt-2">
                  {{ $t('user.public_profile_url') }}
                  <a :href="publicProfileUrl" target="_blank" class="text-[#c89b3c] hover:underline">{{ publicProfileUrl }}</a>
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, inject } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from '../composables/useConfirm'

const { confirm } = useConfirm()
import { setLocale, type LocaleKey } from '../i18n'
import ToggleRow from './ToggleRow.vue'

const props = defineProps<{ show: boolean; initialTab?: string }>()
const emit = defineEmits<{ close: [] }>()

const auth = inject<any>('auth')
const { locale, t } = useI18n()

function changeLocale(l: LocaleKey) {
  setLocale(l)
}

type TabKey = 'achievements' | 'history' | 'settings'
const tabs = computed<{ key: TabKey; label: string }[]>(() => [
  { key: 'achievements', label: `🏅 ${t('user.achievements')}` },
  { key: 'history', label: `📜 Historial` },
  { key: 'settings', label: `⚙ ${t('user.settings')}` },
])
const active = ref<TabKey>('achievements')

const achievements = ref<any[]>([])
const settings = ref<Record<string, boolean> | null>(null)
const txHistory = ref<Array<{ delta: number; reason: string; at: number }>>([])
const txLoading = ref(false)

// Riot ID link/unlink form
const linkGameName = ref('')
const linkTagLine = ref('')
const linking = ref(false)
const unlinking = ref(false)
const linkError = ref('')

async function onLinkRiot() {
  linkError.value = ''
  const name = linkGameName.value.trim()
  const tag = linkTagLine.value.trim()
  if (!name || !tag) return
  linking.value = true
  try {
    const result = await auth.linkRiot(name, tag)
    if (!result || result.error) {
      linkError.value = result?.error || 'No se pudo vincular'
      return
    }
    // Refresh user state so the riot_id appears
    await auth.fetchMe()
    linkGameName.value = ''
    linkTagLine.value = ''
  } catch (e: any) {
    linkError.value = e?.message || 'Error'
  } finally {
    linking.value = false
  }
}

async function onUnlinkRiot() {
  const ok = await confirm({
    title: 'Desvincular Riot ID',
    message: t('user.confirm_unlink'),
    confirmText: 'Desvincular',
    cancelText: 'Volver',
    variant: 'warning',
  })
  if (!ok) return
  unlinking.value = true
  try {
    await auth.unlinkRiot()
    await auth.fetchMe()
  } catch (e: any) {
    linkError.value = e?.message || 'Error'
  } finally {
    unlinking.value = false
  }
}

const unlockedCount = computed(() => achievements.value.filter(a => a.unlocked).length)
const activeIcon = computed(() => active.value === 'achievements' ? '🏅' : '⚙')
const activeLabel = computed(() => active.value === 'achievements' ? 'Logros' : 'Ajustes')

const publicProfileUrl = computed(() => {
  const rid = auth?.user.value?.riot_id
  if (!rid) return ''
  return `${window.location.origin}${window.location.pathname}#/u/${encodeURIComponent(rid.replace('#', '-'))}`
})

watch(() => props.show, async v => {
  if (v) {
    if (props.initialTab) active.value = props.initialTab as TabKey
    await loadActive()
  }
})

watch(active, () => loadActive())

async function loadActive() {
  if (active.value === 'achievements') {
    achievements.value = await auth.fetchAchievements()
  } else if (active.value === 'settings') {
    settings.value = await auth.fetchSettings()
  } else if (active.value === 'history') {
    txLoading.value = true
    try {
      const bal = await auth.refreshBalance?.()
      txHistory.value = bal?.recent_transactions ?? []
    } finally {
      txLoading.value = false
    }
  }
}

function txCategoryFromReason(reason: string): { icon: string; label: string; color: string } {
  const r = reason.toLowerCase()
  if (r.startsWith('welcome')) return { icon: '🎉', label: 'Bienvenida', color: 'text-yellow-300' }
  if (r.startsWith('loyalty')) return { icon: '🎁', label: 'Loyalty', color: 'text-yellow-300' }
  if (r.startsWith('daily')) return { icon: '📅', label: 'Daily', color: 'text-cyan-300' }
  if (r.startsWith('bet escrow')) return { icon: '🔒', label: 'Escrow', color: 'text-white/40' }
  if (r.startsWith('bet won') || r.startsWith('house bet won') || r.startsWith('stat bet won')) return { icon: '✅', label: 'Apuesta ganada', color: 'text-green-400' }
  if (r.startsWith('bet refund') || r.includes('push refund')) return { icon: '↩', label: 'Refund', color: 'text-cyan-300' }
  if (r.startsWith('bet cancelled') || r.startsWith('challenge cancel') || r.startsWith('challenge refund')) return { icon: '✕', label: 'Cancelado', color: 'text-white/50' }
  if (r.startsWith('challenge escrow')) return { icon: '🔒', label: 'Challenge escrow', color: 'text-white/40' }
  if (r.startsWith('challenge won')) return { icon: '⚔', label: 'Challenge ganado', color: 'text-purple-300' }
  if (r.startsWith('bravery escrow')) return { icon: '🔒', label: 'Bravery escrow', color: 'text-white/40' }
  if (r.startsWith('bravery payout')) return { icon: '🎲', label: 'Bravery payout', color: 'text-purple-300' }
  if (r.startsWith('bravery refund')) return { icon: '↩', label: 'Bravery refund', color: 'text-cyan-300' }
  if (r.startsWith('achievement')) return { icon: '🏅', label: 'Achievement', color: 'text-yellow-300' }
  return { icon: '·', label: reason, color: 'text-white/40' }
}

function timeAgo(epoch: number): string {
  const sec = Math.floor(Date.now() / 1000 - epoch)
  if (sec < 60) return `hace ${sec}s`
  if (sec < 3600) return `hace ${Math.floor(sec / 60)}min`
  if (sec < 86400) return `hace ${Math.floor(sec / 3600)}h`
  const d = Math.floor(sec / 86400)
  if (d < 30) return `hace ${d}d`
  const mo = Math.floor(d / 30)
  if (mo < 12) return `hace ${mo}mo`
  return `hace ${Math.floor(d / 365)}y`
}

async function updateSetting(key: string, value: boolean) {
  if (!settings.value) return
  settings.value = { ...settings.value, [key]: value }
  await auth.saveSettings({ [key]: value })
}
</script>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
