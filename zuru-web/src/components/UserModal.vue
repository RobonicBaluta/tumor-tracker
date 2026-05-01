<template>
  <Transition name="modal">
    <div v-if="show" class="fixed inset-0 z-[60] bg-black/70 backdrop-blur-sm overflow-y-auto"
      @click.self="emit('close')">
      <div class="min-h-screen flex items-center justify-center p-4 py-16" @click.self="emit('close')">
      <div class="bg-[#0d1b2a] border border-yellow-500/30 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[88vh] flex flex-col my-auto">
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
              ? 'bg-yellow-900/40 text-yellow-300 border-yellow-500/50'
              : 'text-white/40 border-transparent hover:text-white/70'"
            class="text-xs font-mono px-3 py-1.5 rounded border transition">
            {{ tab.label }}
          </button>
        </div>

        <div class="flex-1 overflow-y-auto p-5">
          <!-- ACHIEVEMENTS -->
          <div v-if="active === 'achievements'">
            <p class="text-white/40 text-[10px] font-mono tracking-widest mb-3">
              {{ $t('user.unlocked_count', { count: unlockedCount, total: achievements.length }) }}
            </p>
            <div class="grid grid-cols-2 gap-3">
              <div v-for="a in achievements" :key="a.badge"
                :class="a.unlocked ? 'border-yellow-500/40 bg-yellow-900/10' : 'border-white/10 bg-black/20 opacity-50'"
                class="rounded-xl border p-3 flex items-start gap-3">
                <span class="text-3xl shrink-0" :class="!a.unlocked ? 'grayscale' : ''">{{ a.icon }}</span>
                <div class="flex-1 min-w-0">
                  <p class="text-white text-sm font-mono font-bold truncate">{{ a.name }}</p>
                  <p class="text-white/50 text-[11px] font-mono">{{ a.desc }}</p>
                  <p v-if="a.unlocked" class="text-yellow-400 text-[10px] font-mono mt-1">
                    ✓ {{ $t('user.unlocked') }}
                  </p>
                  <p v-else class="text-white/30 text-[10px] font-mono mt-1">
                    🔒 {{ $t('user.locked') }}
                  </p>
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
                    :class="locale === 'es' ? 'bg-yellow-900/40 text-yellow-300 border-yellow-500/50' : 'text-white/50 border-white/10 hover:text-white/80'"
                    class="text-xs font-mono px-3 py-1.5 rounded border transition flex-1">
                    🇪🇸 {{ $t('user.spanish') }}
                  </button>
                  <button @click="changeLocale('en')"
                    :class="locale === 'en' ? 'bg-yellow-900/40 text-yellow-300 border-yellow-500/50' : 'text-white/50 border-white/10 hover:text-white/80'"
                    class="text-xs font-mono px-3 py-1.5 rounded border transition flex-1">
                    🇬🇧 {{ $t('user.english') }}
                  </button>
                </div>
              </div>
              <div v-if="auth?.user.value" class="bg-black/30 border border-white/10 rounded-xl p-4">
                <p class="text-white/30 text-[10px] font-mono tracking-widest mb-2">{{ $t('user.account').toUpperCase() }}</p>
                <p class="text-white text-sm font-mono">{{ auth.user.value.username }}</p>
                <p v-if="auth.user.value.riot_id" class="text-[#c89b3c] text-xs font-mono">{{ auth.user.value.riot_id }}</p>
                <p v-else class="text-white/40 text-xs font-mono italic">{{ $t('user.no_riot_linked') }}</p>
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
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, watch, inject } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLocale, type LocaleKey } from '../i18n'
import ToggleRow from './ToggleRow.vue'

const props = defineProps<{ show: boolean; initialTab?: string }>()
const emit = defineEmits<{ close: [] }>()

const auth = inject<any>('auth')
const { locale, t } = useI18n()

function changeLocale(l: LocaleKey) {
  setLocale(l)
}

type TabKey = 'achievements' | 'settings'
const tabs = computed<{ key: TabKey; label: string }[]>(() => [
  { key: 'achievements', label: `🏅 ${t('user.achievements')}` },
  { key: 'settings', label: `⚙ ${t('user.settings')}` },
])
const active = ref<TabKey>('achievements')

const achievements = ref<any[]>([])
const settings = ref<Record<string, boolean> | null>(null)

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
  }
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
