<template>
  <div class="flex-1 flex flex-col justify-center items-center bg-gradient-to-br from-[#ee6bc2] to-[#965499] p-8">
    <div class="w-full max-w-2xl">

      <!-- Header -->
      <div class="bg-black/25 backdrop-blur-md p-[60px] px-[80px] rounded-2xl text-center shadow-2xl animate-fade mb-8">
        <h1 class="text-white font-mono text-6xl mb-2">Tinder</h1>
        <div class="h-[4px] w-[70%] mx-auto my-6 bg-linear-to-br from-transparent via-white to-transparent"></div>
        <p class="text-white/60 text-lg">Encuentra tu cancer ❤️</p>
      </div>

      <!-- Form -->
      <div class="bg-black/25 backdrop-blur-md p-8 rounded-2xl shadow-2xl animate-fade">
        <form @submit.prevent="fetchPlayer" class="space-y-6">
          <div>
            <label class="block text-white text-sm font-semibold mb-2">Nombre del Juego</label>
            <input v-model="formData.gameName" type="text" placeholder="Nombre de invocador"
              class="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:pink transition"
              required />
          </div>
          <div>
            <label class="block text-white text-sm font-semibold mb-2">Tag/Usuario</label>
            <input v-model="formData.tagLine" type="text" placeholder="TAG (ej: EUW)"
              class="w-32 px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:pink-400 transition"
              required />
          </div>
          <button type="submit" :disabled="loading"
            class="w-full bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-400 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-3 rounded-lg transition transform hover:scale-105">
            {{ loading ? 'Buscando...' : 'Encuentra tu cancer ❤️' }}
          </button>
          <div v-if="error" class="bg-red-500/20 border border-red-500 text-red-200 px-4 py-3 rounded-lg">
            {{ error }}
          </div>
        </form>
      </div>

      <!-- Swipeable card -->
      <div v-if="playerData && !swiped" class="mt-8 select-none">

        <!-- Swipe hint labels -->
        <div class="flex justify-between mb-3 px-2">
          <span class="text-red-400/60 font-mono font-bold text-sm tracking-widest">← OLVIDAR</span>
          <span class="text-green-400/60 font-mono font-bold text-sm tracking-widest">REPORTAR →</span>
        </div>

        <!-- Card wrapper (draggable) -->
        <div
          ref="cardRef"
          class="relative rounded-2xl overflow-hidden shadow-2xl cursor-grab active:cursor-grabbing"
          :style="cardStyle"
          @pointerdown="onPointerDown"
          @pointermove="onPointerMove"
          @pointerup="onPointerUp"
          @pointercancel="onPointerUp"
        >
          <!-- Splash background -->
          <div class="absolute inset-0 bg-cover bg-center"
            :style="{ backgroundImage: `url(https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${playerData.campeon}_0.jpg)` }">
          </div>
          <div class="absolute inset-0 bg-black/70 backdrop-blur-sm"></div>

          <!-- OLVIDAR overlay -->
          <div class="absolute inset-0 flex items-center justify-center pointer-events-none z-20"
            :style="{ opacity: Math.max(0, -dragX / 80) }">
            <div class="border-4 border-red-500 text-red-400 font-black text-5xl font-mono px-6 py-2 rounded-xl rotate-12 tracking-widest">
              OLVIDADO
            </div>
          </div>

          <!-- REPORTADO overlay -->
          <div class="absolute inset-0 flex items-center justify-center pointer-events-none z-20"
            :style="{ opacity: Math.max(0, dragX / 80) }">
            <div class="border-4 border-green-500 text-green-400 font-black text-5xl font-mono px-6 py-2 rounded-xl -rotate-12 tracking-widest">
              REPORTADO
            </div>
          </div>

          <!-- Content -->
          <div class="relative p-10 text-center z-10" ref="shareCardRef">
            <img :src="`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion}/img/champion/${playerData.campeon}.png`"
              class="w-28 h-28 mx-auto mb-4 rounded-xl shadow-lg animate-pop" />
            <h2 class="text-white text-3xl font-bold">{{ playerData.nombre }}#{{ playerData.tag }}</h2>
            <p class="text-white/60 mb-6">{{ playerData.campeon }}</p>
            <div class="mb-6">
              <p class="text-white/60 text-sm">KDA</p>
              <div class="text-5xl font-bold text-yellow-400 animate-pulse-slow">{{ playerData.kda.toFixed(2) }}</div>
            </div>
            <div class="grid grid-cols-3 gap-4">
              <div class="bg-black/40 rounded-lg p-4 border border-white/10">
                <p class="text-white/60 text-sm">Kills</p>
                <p class="text-green-400 text-2xl font-bold">{{ playerData.kills }}</p>
              </div>
              <div class="bg-black/40 rounded-lg p-4 border border-white/10">
                <p class="text-white/60 text-sm">Deaths</p>
                <p class="text-red-400 text-2xl font-bold">{{ playerData.deaths }}</p>
              </div>
              <div class="bg-black/40 rounded-lg p-4 border border-white/10">
                <p class="text-white/60 text-sm">Assists</p>
                <p class="text-blue-400 text-2xl font-bold">{{ playerData.assists }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="flex gap-4 mt-6 justify-center">
          <button @click="triggerSwipe('left')"
            class="flex-1 py-3 rounded-xl font-bold font-mono border-2 border-red-500/50 text-red-400 hover:bg-red-500/20 transition text-lg">
            😮‍💨 Olvidar
          </button>
          <button @click="shareCard"
            class="px-6 py-3 rounded-xl font-bold font-mono border-2 border-white/20 text-white/60 hover:bg-white/10 transition">
            📤 Compartir
          </button>
          <button @click="triggerSwipe('right')"
            class="flex-1 py-3 rounded-xl font-bold font-mono border-2 border-green-500/50 text-green-400 hover:bg-green-500/20 transition text-lg">
            ☢️ Reportar
          </button>
        </div>
      </div>

      <!-- Post-swipe feedback -->
      <div v-if="swiped" class="mt-8 animate-fade text-center">
        <div v-if="swiped === 'right'"
          class="bg-green-500/10 border border-green-500/30 rounded-2xl p-8 mb-6">
          <p class="text-green-400 text-5xl mb-3">☢️</p>
          <p class="text-white font-bold text-xl">Reporte enviado a Riot Games</p>
          <p class="text-white/40 text-sm mt-2 font-mono">Ref. #{{ fakeReportId }} · En revisión</p>
        </div>
        <div v-else class="bg-white/5 border border-white/10 rounded-2xl p-8 mb-6">
          <p class="text-5xl mb-3">😮‍💨</p>
          <p class="text-white font-bold text-xl">Olvidado</p>
          <p class="text-white/40 text-sm mt-2">Que no vuelvas a ver a este individuo</p>
        </div>
        <button @click="reset"
          class="px-8 py-3 bg-gradient-to-r from-pink-500 to-purple-600 hover:opacity-90 text-white font-bold rounded-xl transition">
          Buscar otro ❤️
        </button>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { API_BASE } from '../composables/useApi'

const ddragonVersion = ref('15.1.1')
fetch('https://ddragon.leagueoflegends.com/api/versions.json')
  .then(r => r.json())
  .then(versions => { ddragonVersion.value = versions[0] })
  .catch(() => {})

interface PlayerData {
  assists: number
  campeon: string
  deaths: number
  kda: number
  kills: number
  nombre: string
  tag: string
}

const formData = ref({ gameName: '', tagLine: '' })
const playerData = ref<PlayerData | null>(null)
const loading = ref(false)
const error = ref('')
const swiped = ref<'left' | 'right' | null>(null)
const fakeReportId = ref('')

// Swipe state
const cardRef = ref<HTMLElement | null>(null)
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const shareCardRef = ref<HTMLElement | null>(null); void shareCardRef;
const dragX = ref(0)
const isDragging = ref(false)
const startX = ref(0)
const SWIPE_THRESHOLD = 110

const cardStyle = computed(() => {
  const flying = swiped.value
  if (flying === 'left')  return { transform: 'translateX(-160%) rotate(-25deg)', transition: 'transform 0.4s ease', opacity: '0' }
  if (flying === 'right') return { transform: 'translateX(160%) rotate(25deg)',  transition: 'transform 0.4s ease', opacity: '0' }
  return {
    transform: `translateX(${dragX.value}px) rotate(${dragX.value * 0.07}deg)`,
    transition: isDragging.value ? 'none' : 'transform 0.35s cubic-bezier(0.25,0.46,0.45,0.94)',
  }
})

const onPointerDown = (e: PointerEvent) => {
  if (!cardRef.value) return
  isDragging.value = true
  startX.value = e.clientX
  cardRef.value.setPointerCapture(e.pointerId)
}

const onPointerMove = (e: PointerEvent) => {
  if (!isDragging.value) return
  dragX.value = e.clientX - startX.value
}

const onPointerUp = () => {
  if (!isDragging.value) return
  isDragging.value = false
  if (Math.abs(dragX.value) >= SWIPE_THRESHOLD) {
    triggerSwipe(dragX.value > 0 ? 'right' : 'left')
  } else {
    dragX.value = 0
  }
}

const triggerSwipe = (dir: 'left' | 'right') => {
  dragX.value = dir === 'right' ? SWIPE_THRESHOLD : -SWIPE_THRESHOLD
  setTimeout(() => {
    if (dir === 'right') fakeReportId.value = Math.random().toString(36).slice(2, 10).toUpperCase()
    swiped.value = dir
  }, 400)
}

const reset = () => {
  swiped.value = null
  dragX.value = 0
  playerData.value = null
  fakeReportId.value = ''
}

// Share via Canvas
const shareCard = async () => {
  if (!playerData.value) return
  const p = playerData.value

  const W = 600, H = 700
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')!

  // Background gradient
  const grad = ctx.createLinearGradient(0, 0, W, H)
  grad.addColorStop(0, '#ee6bc2')
  grad.addColorStop(1, '#965499')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, W, H)

  // Splash art
  try {
    const splash = await loadImage(`https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${p.campeon}_0.jpg`)
    ctx.drawImage(splash, 0, 0, W, H)
  } catch {}

  // Dark overlay
  ctx.fillStyle = 'rgba(0,0,0,0.72)'
  ctx.fillRect(0, 0, W, H)

  // Champion icon
  try {
    const icon = await loadImage(`https://ddragon.leagueoflegends.com/cdn/${ddragonVersion.value}/img/champion/${p.campeon}.png`)
    const sz = 112
    roundedImage(ctx, icon, (W - sz) / 2, 80, sz, sz, 14)
  } catch {}

  // Name
  ctx.fillStyle = '#ffffff'
  ctx.font = 'bold 32px sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText(`${p.nombre}#${p.tag}`, W / 2, 230)

  // Champion name
  ctx.fillStyle = 'rgba(255,255,255,0.5)'
  ctx.font = '18px sans-serif'
  ctx.fillText(p.campeon, W / 2, 262)

  // KDA label
  ctx.fillStyle = 'rgba(255,255,255,0.5)'
  ctx.font = '14px monospace'
  ctx.fillText('KDA', W / 2, 310)

  ctx.fillStyle = '#facc15'
  ctx.font = 'bold 64px monospace'
  ctx.fillText(p.kda.toFixed(2), W / 2, 380)

  // Stats boxes
  const statY = 430, statH = 100, statW = 160, gap = 20
  const totalW = statW * 3 + gap * 2
  const startXStat = (W - totalW) / 2
  const stats = [
    { label: 'Kills',   value: p.kills,   color: '#4ade80' },
    { label: 'Deaths',  value: p.deaths,  color: '#f87171' },
    { label: 'Assists', value: p.assists, color: '#60a5fa' },
  ]
  stats.forEach((s, i) => {
    const x = startXStat + i * (statW + gap)
    ctx.fillStyle = 'rgba(0,0,0,0.4)'
    roundRect(ctx, x, statY, statW, statH, 12)
    ctx.fillStyle = 'rgba(255,255,255,0.12)'
    ctx.strokeStyle = 'rgba(255,255,255,0.15)'
    ctx.lineWidth = 1
    roundRect(ctx, x, statY, statW, statH, 12, true)
    ctx.fillStyle = 'rgba(255,255,255,0.45)'
    ctx.font = '13px sans-serif'
    ctx.fillText(s.label, x + statW / 2, statY + 28)
    ctx.fillStyle = s.color
    ctx.font = 'bold 36px sans-serif'
    ctx.fillText(String(s.value), x + statW / 2, statY + 72)
  })

  // Watermark
  ctx.fillStyle = 'rgba(255,255,255,0.25)'
  ctx.font = '13px monospace'
  ctx.fillText('zuruweb · Top Tumores', W / 2, H - 24)

  // Download
  const link = document.createElement('a')
  link.download = `tumor_${p.nombre.replace(/\s/g, '_')}.png`
  link.href = canvas.toDataURL('image/png')
  link.click()
}

const loadImage = (src: string): Promise<HTMLImageElement> =>
  new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })

const roundedImage = (ctx: CanvasRenderingContext2D, img: HTMLImageElement, x: number, y: number, w: number, h: number, r: number) => {
  ctx.save()
  ctx.beginPath()
  ctx.roundRect(x, y, w, h, r)
  ctx.clip()
  ctx.drawImage(img, x, y, w, h)
  ctx.restore()
}

const roundRect = (ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number, stroke = false) => {
  ctx.beginPath()
  ctx.roundRect(x, y, w, h, r)
  ctx.fill()
  if (stroke) ctx.stroke()
}

const fetchPlayer = async () => {
  loading.value = true
  error.value = ''
  swiped.value = null
  dragX.value = 0

  try {
    const params = new URLSearchParams({
      game_name: formData.value.gameName,
      tag_line: formData.value.tagLine
    })
    const response = await fetch(`${API_BASE}/getElPeor?${params}`)
    if (!response.ok) throw new Error(`Error: ${response.statusText}`)
    playerData.value = await response.json()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Error al buscar el jugador'
    playerData.value = null
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
@keyframes fade {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
.animate-fade { animation: fade 0.6s ease forwards; }

@keyframes pop {
  0%   { transform: scale(0.5); opacity: 0; }
  70%  { transform: scale(1.1); }
  100% { transform: scale(1);   opacity: 1; }
}
.animate-pop { animation: pop 0.5s ease forwards; }

@keyframes pulseSlow {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.6; }
}
.animate-pulse-slow { animation: pulseSlow 2s infinite; }
</style>
