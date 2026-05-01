<template>
  <Transition name="onboarding">
    <div v-if="visible" class="fixed inset-0 z-[200] bg-black/85 backdrop-blur-sm flex items-center justify-center p-6"
      @click.self="next">
      <div class="bg-[#0d1b2a] border border-yellow-500/40 rounded-2xl shadow-2xl shadow-yellow-900/30 max-w-md w-full p-6 relative">
        <div class="flex items-center justify-between mb-4">
          <p class="text-yellow-300 text-[10px] font-mono tracking-widest">
            PASO {{ step + 1 }}/{{ steps.length }}
          </p>
          <button @click="dismiss" class="text-white/30 hover:text-white text-sm font-mono">
            Saltar
          </button>
        </div>

        <div class="text-center mb-5">
          <p class="text-5xl mb-3">{{ current.emoji }}</p>
          <h2 class="text-yellow-200 font-mono text-xl font-bold mb-2">{{ current.title }}</h2>
          <p class="text-white/70 text-sm font-mono leading-relaxed whitespace-pre-line">{{ current.body }}</p>
        </div>

        <!-- Dots -->
        <div class="flex justify-center gap-1.5 mb-4">
          <div v-for="(_, i) in steps" :key="i"
            :class="i === step ? 'bg-yellow-400 w-6' : 'bg-white/15 w-1.5'"
            class="h-1.5 rounded-full transition-all" />
        </div>

        <div class="flex gap-2">
          <button v-if="step > 0" @click="step--"
            class="flex-1 bg-white/10 hover:bg-white/15 text-white font-mono text-sm py-2 rounded-lg transition">
            Atrás
          </button>
          <button @click="next"
            class="flex-1 bg-yellow-600 hover:bg-yellow-500 text-black font-mono font-bold text-sm py-2 rounded-lg transition">
            {{ step === steps.length - 1 ? '¡Vamos!' : 'Siguiente' }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const STORAGE_KEY = 'zuruweb-onboarding-done'

const visible = ref(false)
const step = ref(0)

const steps = [
  {
    emoji: '☢',
    title: '¡Bienvenido a Tumor Tracker!',
    body: 'La app que detecta a los peores compañeros que te tocan en League.\nVamos a darte un tour rápido.',
  },
  {
    emoji: '🔍',
    title: 'Top Tumores',
    body: 'Mete tu Riot ID y verás un análisis de tus últimas partidas:\nquién fue el peor compañero, KDA, daño y un score 0-100 por jugador.',
  },
  {
    emoji: '🔴',
    title: 'En directo',
    body: 'Si estás en partida ahora, escanea a los 10 jugadores.\nEl modelo predice quién va a ganar basado en su histórico.',
  },
  {
    emoji: '☢',
    title: 'Tumor Coins',
    body: 'Login con Discord y empieza con 100 TC.\nGanas TC con predicciones acertadas, daily reward y apuestas P2P.',
  },
  {
    emoji: '🎲',
    title: 'Apuestas P2P',
    body: 'En el modal de live game pulsa "Apostar".\nElige lado, cantidad, comparte el código.\nEl que gane se lleva el doble.',
  },
  {
    emoji: '🏅',
    title: 'Logros y leaderboards',
    body: 'Desbloquea badges jugando y apostando.\nCompite por aparecer en los rankings globales de TC y accuracy.',
  },
]

const current = computed(() => steps[step.value])

function next() {
  if (step.value === steps.length - 1) {
    dismiss()
  } else {
    step.value++
  }
}

function dismiss() {
  localStorage.setItem(STORAGE_KEY, '1')
  visible.value = false
}

onMounted(() => {
  if (!localStorage.getItem(STORAGE_KEY)) {
    setTimeout(() => { visible.value = true }, 1000)
  }
})

// Expose method to trigger manually
defineExpose({
  open: () => { step.value = 0; visible.value = true }
})
</script>

<style scoped>
.onboarding-enter-active, .onboarding-leave-active { transition: opacity 0.3s; }
.onboarding-enter-from, .onboarding-leave-to { opacity: 0; }
</style>
