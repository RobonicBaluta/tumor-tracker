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
        class="bg-theme-from border border-accent-30 shadow-2xl w-full max-w-2xl max-h-[88vh] flex flex-col
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
            <!-- Loading / error visibles. Antes una respuesta vacía dejaba el
                 grid en blanco sin pista del por qué — bug reportado. -->
            <div v-if="achievementsLoading" class="text-white/40 text-sm font-mono text-center py-8 animate-pulse">
              Cargando trofeos…
            </div>
            <div v-else-if="achievementsError" class="border border-red-500/40 bg-red-950/30 rounded-xl p-4 text-center mb-4">
              <p class="text-red-300 text-sm font-mono mb-2">{{ achievementsError }}</p>
              <button @click="loadActive" class="text-xs font-mono px-3 py-1 rounded border border-red-400/40 text-red-200 hover:bg-red-900/30 transition">
                Reintentar
              </button>
            </div>
            <template v-else>
            <!-- Empty state cuando el endpoint respondió 200 pero con []
                 (e.g. backend a medio deployar, schema sin trofeos, etc.).
                 Sin esto el global bar mostraba "0/0 desbloqueados NaN%". -->
            <div v-if="achievements.length === 0" class="text-white/40 font-mono text-sm text-center py-10">
              No hay trofeos disponibles todavía.
              <button @click="loadActive" class="block mx-auto mt-3 text-xs font-mono px-3 py-1 rounded border border-white/15 hover:border-white/30 transition">
                Recargar
              </button>
            </div>
            <template v-else>
            <!-- Progreso global con barra -->
            <div class="mb-4 bg-gradient-to-r from-yellow-900/20 via-black/30 to-black/30 border border-yellow-500/30 rounded-xl p-3">
              <div class="flex items-center justify-between mb-1.5">
                <p class="text-yellow-200 text-[10px] font-mono tracking-widest">
                  🏆 {{ $t('user.unlocked_count', { count: unlockedCount, total: achievements.length }) }}
                </p>
                <p class="text-yellow-300 text-xs font-mono font-bold">
                  {{ achievements.length ? Math.round((unlockedCount / achievements.length) * 100) : 0 }}%
                </p>
              </div>
              <div class="h-2 bg-black/40 rounded-full overflow-hidden">
                <div class="h-full bg-gradient-to-r from-yellow-500 to-yellow-300 transition-all"
                  :style="{ width: achievements.length ? `${(unlockedCount / achievements.length) * 100}%` : '0%' }"></div>
              </div>
            </div>

            <!-- #47 — View-by-tier toggle. "Plano" = grid existente. "Por tier"
                 = 4 secciones agrupadas (bronze→platinum) con su propio
                 contador unlocked/total. -->
            <div class="flex items-center gap-1 mb-3">
              <button @click="achViewMode = 'flat'"
                :class="achViewMode === 'flat' ? 'bg-accent-15 text-accent border-accent-50' : 'text-white/40 border-white/15 hover:text-white/70'"
                class="text-[10px] font-mono px-2.5 py-1 rounded border transition">
                Lista plana
              </button>
              <button @click="achViewMode = 'tier'"
                :class="achViewMode === 'tier' ? 'bg-accent-15 text-accent border-accent-50' : 'text-white/40 border-white/15 hover:text-white/70'"
                class="text-[10px] font-mono px-2.5 py-1 rounded border transition">
                Por tier
              </button>
            </div>

            <!-- BY-TIER view: 4 secciones colapsables -->
            <div v-if="achViewMode === 'tier'" class="space-y-4">
              <section v-for="t in TIER_ORDER" :key="t">
                <div v-if="achievementsByTier[t]?.length"
                  class="flex items-center justify-between mb-2">
                  <p class="text-[10px] font-mono tracking-widest text-white/50 flex items-center gap-2">
                    <span :class="tierClasses(t).badge" class="text-[8px] font-mono font-black px-1.5 py-px rounded uppercase">{{ t }}</span>
                    <span>{{ tierUnlocked(t) }} / {{ achievementsByTier[t].length }} desbloqueados</span>
                  </p>
                </div>
                <div v-if="achievementsByTier[t]?.length" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button v-for="a in achievementsByTier[t]" :key="a.badge"
                    @click="selectedAch = a"
                    :class="[a.unlocked ? tierClasses(a.tier).unlocked : 'border-white/10 bg-black/20 hover:border-white/30 hover:bg-black/30']"
                    class="text-left rounded-xl border p-3 flex items-start gap-3 transition cursor-pointer">
                    <span class="text-3xl shrink-0 transition"
                      :class="a.unlocked ? '' : 'grayscale opacity-40'">{{ a.icon }}</span>
                    <div class="flex-1 min-w-0">
                      <p class="text-sm font-mono font-bold truncate"
                        :class="a.unlocked ? 'text-white' : 'text-white/60'">{{ a.name }}</p>
                      <p class="text-white/40 text-[11px] font-mono">{{ a.desc }}</p>
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
                      <p v-else-if="a.unlocked" class="text-yellow-400 text-[10px] font-mono mt-1">✓ {{ $t('user.unlocked') }}</p>
                      <p v-else class="text-white/30 text-[10px] font-mono mt-1">🔒 {{ $t('user.locked') }}</p>
                    </div>
                  </button>
                </div>
              </section>
            </div>

            <!-- FLAT view (default) -->
            <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button v-for="a in achievements" :key="a.badge"
                @click="selectedAch = a"
                :class="[
                  a.unlocked
                    ? tierClasses(a.tier).unlocked
                    : 'border-white/10 bg-black/20 hover:border-white/30 hover:bg-black/30',
                ]"
                class="text-left rounded-xl border p-3 flex items-start gap-3 transition cursor-pointer">
                <span class="text-3xl shrink-0 transition"
                  :class="a.unlocked ? '' : 'grayscale opacity-40'">{{ a.icon }}</span>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-1.5">
                    <p class="text-sm font-mono font-bold truncate"
                      :class="a.unlocked ? 'text-white' : 'text-white/60'">{{ a.name }}</p>
                    <span v-if="a.unlocked && a.tier"
                      :class="tierClasses(a.tier).badge"
                      class="text-[8px] font-mono font-black px-1 py-px rounded uppercase shrink-0">{{ a.tier }}</span>
                  </div>
                  <p class="text-white/40 text-[11px] font-mono">{{ a.desc }}</p>
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
              </button>
            </div>

            <!-- Detail panel sobre el achievement clickeado. Cierra al
                 clickar fuera o pulsando ✕. Bug HIGH cazado: el user clickaba
                 los trofeos esperando que algo pasara y nada. -->
            <Teleport to="body">
              <Transition name="modal">
                <div v-if="selectedAch" @click.self="selectedAch = null"
                  class="fixed inset-0 z-[120] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
                  <div class="bg-theme-from border rounded-2xl shadow-2xl max-w-sm w-full p-5"
                    :class="selectedAch.unlocked ? tierClasses(selectedAch.tier).border : 'border-white/20'">
                    <div class="flex items-start justify-between mb-4">
                      <span class="text-6xl"
                        :class="selectedAch.unlocked ? '' : 'grayscale opacity-40'">{{ selectedAch.icon }}</span>
                      <button @click="selectedAch = null" class="text-white/40 hover:text-white text-xl">✕</button>
                    </div>
                    <div class="flex items-center gap-2 mb-1">
                      <p class="text-white text-lg font-mono font-bold">{{ selectedAch.name }}</p>
                      <span v-if="selectedAch.tier"
                        :class="tierClasses(selectedAch.tier).badge"
                        class="text-[9px] font-mono font-black px-1.5 py-0.5 rounded uppercase">{{ selectedAch.tier }}</span>
                    </div>
                    <p class="text-white/60 text-sm font-mono leading-snug mb-3">{{ selectedAch.desc }}</p>
                    <div v-if="selectedAch.unlocked" class="border border-yellow-500/30 bg-yellow-900/10 rounded-lg px-3 py-2">
                      <p class="text-yellow-300 text-[10px] font-mono tracking-widest mb-0.5">✓ DESBLOQUEADO</p>
                      <p class="text-white/70 text-xs font-mono">+50 TC ganados al desbloquear</p>
                      <p v-if="selectedAch.unlocked_at" class="text-white/40 text-[10px] font-mono mt-1">
                        {{ formatAchDate(selectedAch.unlocked_at) }}
                      </p>
                    </div>
                    <div v-else-if="selectedAch.progress" class="border border-cyan-500/30 bg-cyan-900/10 rounded-lg px-3 py-2">
                      <p class="text-cyan-300 text-[10px] font-mono tracking-widest mb-1">⏳ EN PROGRESO</p>
                      <p class="text-white/70 text-xs font-mono mb-1">
                        {{ selectedAch.progress.current }} / {{ selectedAch.progress.target }}
                        ({{ Math.round((selectedAch.progress.current / selectedAch.progress.target) * 100) }}%)
                      </p>
                      <div class="h-1.5 bg-black/40 rounded-full overflow-hidden">
                        <div class="h-full bg-cyan-500"
                          :style="{ width: `${(selectedAch.progress.current / selectedAch.progress.target) * 100}%` }"></div>
                      </div>
                    </div>
                    <div v-else class="border border-white/10 bg-black/20 rounded-lg px-3 py-2">
                      <p class="text-white/40 text-[10px] font-mono tracking-widest mb-1">🔒 BLOQUEADO · CÓMO CONSEGUIRLO</p>
                      <p class="text-white/70 text-xs font-mono leading-relaxed">
                        {{ selectedAch.how_to || 'Cumple la condición y se desbloquea automáticamente.' }}
                      </p>
                    </div>
                  </div>
                </div>
              </Transition>
            </Teleport>
            </template><!-- /achievements.length > 0 -->
            </template><!-- /v-else (no loading + no error) -->
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
                  <!-- #50 — Sound effects local-only, no roundtrip al server. -->
                  <ToggleRow
                    label="🔊 Sound effects"
                    desc="Daily claim, mission reward, prediction correct. Sintetizado en browser, sin descargas."
                    :model-value="sfxEnabled"
                    @update:model-value="toggleSfx"
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
import { ref, computed, watch, inject, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from '../composables/useConfirm'

const { confirm } = useConfirm()
import { setLocale, type LocaleKey } from '../i18n'
import ToggleRow from './ToggleRow.vue'
import { sfx } from '../composables/useSfx'

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
const achievementsLoading = ref(false)
const achievementsError = ref('')
const selectedAch = ref<any | null>(null)
// #47 — Toggle entre lista plana y agrupado por tier.
const achViewMode = ref<'flat' | 'tier'>('flat')
const TIER_ORDER = ['bronze', 'silver', 'gold', 'platinum'] as const
const achievementsByTier = computed<Record<string, any[]>>(() => {
  const out: Record<string, any[]> = { bronze: [], silver: [], gold: [], platinum: [] }
  for (const a of achievements.value) {
    const t = (a.tier || 'bronze').toLowerCase()
    if (out[t]) out[t].push(a)
    else out.bronze.push(a)  // fallback para badges sin tier (no debería pasar)
  }
  return out
})
function tierUnlocked(tier: string): number {
  return (achievementsByTier.value[tier] || []).filter((a: any) => a.unlocked).length
}

// Tier visual mapping para el revamp de trofeos. Bronze/silver/gold/platinum
// con colores de marca progresivamente más calientes. El frontend solo lo
// usa para estilizar; el backend determina qué tier tiene cada badge.
function tierClasses(tier?: string) {
  switch (tier) {
    case 'platinum': return {
      unlocked: 'border-cyan-300/60 bg-gradient-to-br from-cyan-900/30 to-black/30 shadow-lg shadow-cyan-900/30',
      border: 'border-cyan-300/60',
      badge: 'bg-cyan-300/20 text-cyan-200 border border-cyan-300/40',
    }
    case 'gold': return {
      unlocked: 'border-yellow-500/60 bg-gradient-to-br from-yellow-900/25 to-black/30 shadow-lg shadow-yellow-900/30',
      border: 'border-yellow-500/60',
      badge: 'bg-yellow-500/20 text-yellow-200 border border-yellow-500/40',
    }
    case 'silver': return {
      unlocked: 'border-slate-300/50 bg-gradient-to-br from-slate-700/30 to-black/30 shadow shadow-slate-900/30',
      border: 'border-slate-300/50',
      badge: 'bg-slate-400/20 text-slate-200 border border-slate-300/40',
    }
    case 'bronze':
    default: return {
      unlocked: 'border-orange-700/50 bg-gradient-to-br from-orange-900/20 to-black/30 shadow shadow-orange-900/20',
      border: 'border-orange-700/50',
      badge: 'bg-orange-700/20 text-orange-200 border border-orange-700/40',
    }
  }
}

function formatAchDate(ts: number): string {
  try {
    const d = new Date(ts * 1000)
    return `Desbloqueado el ${d.toLocaleDateString()} ${d.toLocaleTimeString().slice(0, 5)}`
  } catch {
    return ''
  }
}

const settings = ref<Record<string, boolean> | null>(null)
const txHistory = ref<Array<{ delta: number; reason: string; at: number }>>([])
const txLoading = ref(false)

// #50 — Toggle local del opt-in de sfx. No va al server.
const sfxEnabled = ref(sfx.isEnabled())
function toggleSfx(v: boolean) {
  sfxEnabled.value = v
  sfx.setEnabled(v)
}

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

// Navbar monta este modal con `v-if="showUserModal"` + `:show="true"`,
// así que cuando el modal aparece `props.show` arranca en true y el watch
// nunca dispara su primera transición. Fix: load en onMounted además.
// (Mismo bug que MissionsModal — sin esto el tab activo queda vacío.)
onMounted(() => {
  if (props.show) {
    if (props.initialTab) active.value = props.initialTab as TabKey
    loadActive()
  }
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
    // Estado de loading + retry visible. Antes el fetch retornaba [] en
    // caso de error, el grid quedaba vacío sin ninguna pista, el user
    // entraba al tab y "no se cargaba nada".
    achievementsLoading.value = true
    achievementsError.value = ''
    try {
      const res = await auth.fetchAchievements()
      achievements.value = res
      // Empty array es estado legítimo (backend a medio deployar, schema
      // sin trofeos, etc.). Ya NO lo tratamos como error — el empty state
      // del template lo cubre con su propio mensaje + recarga.
    } catch (e: any) {
      achievementsError.value = e?.message || 'Error cargando trofeos.'
    } finally {
      achievementsLoading.value = false
    }
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
