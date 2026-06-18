<script setup lang="ts">
import { ref, computed, watch, inject } from 'vue'
import { API_BASE } from '../composables/useApi'
import { useToast } from '../composables/useToast'
import { sfx } from '../composables/useSfx'

interface Mission {
  key: string
  kind: 'daily' | 'weekly' | 'meta' | 'tumor'
  name: string
  desc: string
  target: number
  reward: number
  progress: number
  period: string
  claimable: boolean
  claimed: boolean
  claimed_at: number | null
}

interface MissionsResponse {
  daily: { period: string; missions: Mission[] }
  weekly: { period: string; missions: Mission[] }
}

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ close: [] }>()

const auth = inject<any>('auth')
const { toast } = useToast()

const loading = ref(false)
const error = ref('')
const data = ref<MissionsResponse | null>(null)
const claimingKey = ref<string>('')

function tzHeader(): Record<string, string> {
  try { return { 'X-TZ-Offset': String(-new Date().getTimezoneOffset()) } } catch { return {} }
}

async function load() {
  if (!auth?.token?.value) return
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`${API_BASE}/missions`, {
      headers: { Authorization: `Bearer ${auth.token.value}`, ...tzHeader() },
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    data.value = await res.json()
  } catch (e: any) {
    error.value = e?.message || 'No se pudieron cargar las misiones'
  } finally {
    loading.value = false
  }
}

async function claim(m: Mission, kind: 'daily' | 'weekly') {
  if (!m.claimable || claimingKey.value) return
  claimingKey.value = m.key
  try {
    const res = await fetch(`${API_BASE}/missions/claim`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${auth.token.value}`,
        'Content-Type': 'application/json',
        ...tzHeader(),
      },
      body: JSON.stringify({ mission_key: m.key, kind }),
    })
    const body = await res.json().catch(() => ({}))
    if (!res.ok) {
      toast.error(body.error || `Error ${res.status}`)
      return
    }
    // Update local state + refrescar el balance del user en useAuth.
    if (auth?.user?.value && typeof body.new_balance === 'number') {
      auth.user.value.currency = body.new_balance
    }
    sfx.success() // #50 — reward sound. opt-in, no-op si está disabled.
    toast.success(`+${m.reward} TC · ${m.name}`)
    await load()
  } finally {
    claimingKey.value = ''
  }
}

const totalReward = computed(() => {
  if (!data.value) return 0
  const all = [...data.value.daily.missions, ...data.value.weekly.missions]
  return all.filter(m => m.claimable).reduce((s, m) => s + m.reward, 0)
})

watch(() => props.show, v => { if (v) load() })
</script>

<template>
  <Teleport to="body">
    <Transition name="modal" appear>
      <div v-if="show" class="fixed inset-0 z-[105] bg-black/70 backdrop-blur-sm flex items-start sm:items-center justify-center overflow-y-auto p-4 pt-[8vh] sm:pt-4"
        @click.self="emit('close')">
        <div class="bg-theme-from border border-accent-30 rounded-2xl shadow-2xl shadow-black/30 w-full max-w-2xl max-h-[92vh] overflow-y-auto">
          <div class="flex items-center justify-between px-6 py-4 border-b border-white/10 sticky top-0 bg-theme-from/95 backdrop-blur z-10">
            <p class="text-white font-mono font-bold">🎯 Misiones</p>
            <button @click="emit('close')" class="text-white/40 hover:text-white text-xl transition">✕</button>
          </div>

          <div v-if="loading" class="text-white/40 text-sm font-mono text-center py-10 animate-pulse">
            Cargando misiones…
          </div>
          <div v-else-if="error" class="border border-red-500/40 bg-red-950/30 rounded-xl p-4 text-center m-6">
            <p class="text-red-300 text-sm font-mono mb-2">{{ error }}</p>
            <button @click="load" class="text-xs font-mono px-3 py-1 rounded border border-red-400/40 text-red-200 hover:bg-red-900/30 transition">
              Reintentar
            </button>
          </div>

          <template v-else-if="data">
            <div v-if="totalReward > 0"
              class="mx-6 mt-4 bg-gradient-to-r from-yellow-900/30 via-black/30 to-black/30 border border-yellow-500/40 rounded-xl px-4 py-2.5 flex items-center justify-between">
              <p class="text-yellow-200 text-xs font-mono">
                ¡Tienes <span class="font-bold">+{{ totalReward }} TC</span> esperando!
              </p>
              <span class="text-2xl">🎁</span>
            </div>

            <!-- DAILY -->
            <section class="p-6">
              <div class="flex items-baseline justify-between mb-3">
                <p class="text-white/40 text-[10px] font-mono tracking-widest">📅 DIARIAS</p>
                <p class="text-white/30 text-[10px] font-mono">{{ data.daily.period }}</p>
              </div>
              <div v-if="!data.daily.missions.length" class="text-white/30 font-mono text-xs italic">Sin misiones diarias.</div>
              <div v-else class="space-y-2.5">
                <div v-for="m in data.daily.missions" :key="m.key"
                  :class="[
                    'border rounded-xl p-3 flex items-center gap-3 transition',
                    m.claimed ? 'border-white/10 bg-black/20 opacity-60' :
                    m.claimable ? 'border-yellow-500/50 bg-yellow-900/15 shadow shadow-yellow-900/20' :
                    'border-white/10 bg-black/20'
                  ]">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-0.5">
                      <p class="text-white text-sm font-mono font-bold">{{ m.name }}</p>
                      <span v-if="m.kind === 'tumor'"
                        class="text-[8px] font-mono font-black px-1 py-px rounded uppercase bg-red-700/20 text-red-200 border border-red-700/40">tumor</span>
                      <span v-else
                        class="text-[8px] font-mono font-black px-1 py-px rounded uppercase bg-cyan-700/20 text-cyan-200 border border-cyan-700/40">meta</span>
                    </div>
                    <p class="text-white/40 text-[11px] font-mono">{{ m.desc }}</p>
                    <div class="mt-1.5">
                      <div class="flex items-center justify-between text-[9px] font-mono mb-0.5">
                        <span class="text-white/50">{{ m.progress }} / {{ m.target }}</span>
                        <span class="text-yellow-300">+{{ m.reward }} TC</span>
                      </div>
                      <div class="h-1.5 bg-black/40 rounded-full overflow-hidden">
                        <div :class="m.claimable ? 'bg-yellow-400' : 'bg-cyan-500'" class="h-full transition-all"
                          :style="{ width: `${Math.min(100, (m.progress / m.target) * 100)}%` }"></div>
                      </div>
                    </div>
                  </div>
                  <button v-if="m.claimable" @click="claim(m, 'daily')" :disabled="!!claimingKey"
                    class="shrink-0 text-xs font-mono font-bold px-3 py-2 rounded-lg border border-yellow-500/60 text-yellow-200 bg-yellow-900/30 hover:bg-yellow-900/60 transition disabled:opacity-40">
                    {{ claimingKey === m.key ? '...' : 'Reclamar' }}
                  </button>
                  <span v-else-if="m.claimed" class="shrink-0 text-[10px] font-mono text-green-400">✓ Hecho</span>
                  <span v-else class="shrink-0 text-[10px] font-mono text-white/30">{{ Math.round((m.progress / m.target) * 100) }}%</span>
                </div>
              </div>
            </section>

            <!-- WEEKLY -->
            <section class="px-6 pb-6">
              <div class="flex items-baseline justify-between mb-3">
                <p class="text-white/40 text-[10px] font-mono tracking-widest">🗓 SEMANALES</p>
                <p class="text-white/30 text-[10px] font-mono">{{ data.weekly.period }}</p>
              </div>
              <div v-if="!data.weekly.missions.length" class="text-white/30 font-mono text-xs italic">Sin misiones semanales.</div>
              <div v-else class="space-y-2.5">
                <div v-for="m in data.weekly.missions" :key="m.key"
                  :class="[
                    'border rounded-xl p-3 flex items-center gap-3 transition',
                    m.claimed ? 'border-white/10 bg-black/20 opacity-60' :
                    m.claimable ? 'border-purple-400/60 bg-purple-900/15 shadow shadow-purple-900/30' :
                    'border-white/10 bg-black/20'
                  ]">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-0.5">
                      <p class="text-white text-sm font-mono font-bold">{{ m.name }}</p>
                      <span v-if="m.kind === 'tumor'"
                        class="text-[8px] font-mono font-black px-1 py-px rounded uppercase bg-red-700/20 text-red-200 border border-red-700/40">tumor</span>
                      <span v-else
                        class="text-[8px] font-mono font-black px-1 py-px rounded uppercase bg-cyan-700/20 text-cyan-200 border border-cyan-700/40">meta</span>
                    </div>
                    <p class="text-white/40 text-[11px] font-mono">{{ m.desc }}</p>
                    <div class="mt-1.5">
                      <div class="flex items-center justify-between text-[9px] font-mono mb-0.5">
                        <span class="text-white/50">{{ m.progress }} / {{ m.target }}</span>
                        <span class="text-purple-300">+{{ m.reward }} TC</span>
                      </div>
                      <div class="h-1.5 bg-black/40 rounded-full overflow-hidden">
                        <div :class="m.claimable ? 'bg-purple-400' : 'bg-cyan-500'" class="h-full transition-all"
                          :style="{ width: `${Math.min(100, (m.progress / m.target) * 100)}%` }"></div>
                      </div>
                    </div>
                  </div>
                  <button v-if="m.claimable" @click="claim(m, 'weekly')" :disabled="!!claimingKey"
                    class="shrink-0 text-xs font-mono font-bold px-3 py-2 rounded-lg border border-purple-400/60 text-purple-200 bg-purple-900/30 hover:bg-purple-900/60 transition disabled:opacity-40">
                    {{ claimingKey === m.key ? '...' : 'Reclamar' }}
                  </button>
                  <span v-else-if="m.claimed" class="shrink-0 text-[10px] font-mono text-green-400">✓ Hecho</span>
                  <span v-else class="shrink-0 text-[10px] font-mono text-white/30">{{ Math.round((m.progress / m.target) * 100) }}%</span>
                </div>
              </div>
            </section>
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
