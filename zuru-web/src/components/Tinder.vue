<template>
  <div class="flex-1 flex flex-col justify-center items-center bg-gradient-to-br from-[#ee6bc2] to-[#965499] p-8">
    <div class="w-full max-w-2xl">
      <div class="bg-black/25 backdrop-blur-md p-[60px] px-[80px] rounded-2xl text-center shadow-2xl animate-fade mb-8">
        <h1 class="text-white font-mono text-6xl mb-2">
          Tinder
        </h1>

        <div class="h-[4px] w-[70%] mx-auto my-6 bg-linear-to-br from-transparent via-white to-transparent"></div>

        <p class="text-white/60 text-lg">
          Encuentra tu cancer ❤️
        </p>
      </div>

      <!-- Form Card -->
      <div class="bg-black/25 backdrop-blur-md p-8 rounded-2xl shadow-2xl animate-fade">
        <form @submit.prevent="fetchPlayer" class="space-y-6">
          <!-- Game Name Input -->
          <div>
            <label class="block text-white text-sm font-semibold mb-2">Nombre del Juego</label>
            <input v-model="formData.gameName" type="text" placeholder="Nombre de invocador"
              class="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:pink transition"
              required />
          </div>

          <!-- Tag Line Input -->
          <div>
            <label class="block text-white text-sm font-semibold mb-2">Tag/Usuario</label>
            <input v-model="formData.tagLine" type="text" placeholder="TAG (ej: EUW)"
              class="w-32 px-4 py-3 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:pink-400 transition"
              required />
          </div>

          <!-- Submit Button -->
          <button type="submit" :disabled="loading"
            class="w-full bg-gradient-to-r from-pink-500 to-purple-600 hover:from-pink-400 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-3 rounded-lg transition transform hover:scale-105">
            {{ loading ? 'Buscando...' : 'Encuentra tu cancer ❤️' }}
          </button>

          <!-- Error Message -->
          <div v-if="error" class="bg-red-500/20 border border-red-500 text-red-200 px-4 py-3 rounded-lg">
            {{ error }}
          </div>
        </form>
      </div>

      <div v-if="playerData" class="mt-8 animate-fade">

        <!-- Background Splash -->
        <div class="relative rounded-2xl overflow-hidden shadow-2xl animate-reveal" :style="{
          backgroundImage: `url(https://ddragon.leagueoflegends.com/cdn/img/champion/splash/${playerData.campeon}_0.jpg)`
        }">

          <!-- Overlay -->
          <div class="absolute inset-0 bg-black/70 backdrop-blur-sm"></div>

          <!-- Content -->
          <div class="relative p-10 text-center">

            <!-- Champion Icon -->
            <img :src="`https://ddragon.leagueoflegends.com/cdn/13.24.1/img/champion/${playerData.campeon}.png`"
              class="w-28 h-28 mx-auto mb-4 rounded-xl shadow-lg animate-pop" />

            <!-- Name -->
            <h2 class="text-white text-3xl font-bold">
              {{ playerData.nombre }}#{{ playerData.tag }}
            </h2>

            <!-- Champion -->
            <p class="text-white/60 mb-6">{{ playerData.campeon }}</p>

            <!-- KDA -->
            <div class="mb-6">
              <p class="text-white/60 text-sm">KDA</p>
              <div class="text-5xl font-bold text-yellow-400 animate-pulse-slow">
                {{ playerData.kda.toFixed(2) }}
              </div>
            </div>

            <!-- Stats -->
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
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface PlayerData {
  assists: number
  campeon: string
  deaths: number
  kda: number
  kills: number
  nombre: string
  tag: string   // 👈 nuevo
}

const formData = ref({
  gameName: '',
  tagLine: ''
})

const playerData = ref<PlayerData | null>(null)
const loading = ref(false)
const error = ref('')

const fetchPlayer = async () => {
  loading.value = true
  error.value = ''

  try {
    const params = new URLSearchParams({
      game_name: formData.value.gameName,
      tag_line: formData.value.tagLine
    })

    const response = await fetch(`http://localhost:5000/getElPeor?${params}`)

    if (!response.ok) {
      throw new Error(`Error: ${response.statusText}`)
    }

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
  from {
    opacity: 0;
    transform: translateY(10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade {
  animation: fade 0.6s ease forwards;
}

@keyframes reveal {
  0% {
    opacity: 0;
    transform: rotateY(90deg) scale(0.8);
  }
  100% {
    opacity: 1;
    transform: rotateY(0deg) scale(1);
  }
}

.animate-reveal {
  animation: reveal 0.7s ease forwards;
  transform-style: preserve-3d;
}

@keyframes pop {
  0% {
    transform: scale(0.5);
    opacity: 0;
  }
  70% {
    transform: scale(1.1);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.animate-pop {
  animation: pop 0.5s ease forwards;
}

@keyframes pulseSlow {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.animate-pulse-slow {
  animation: pulseSlow 2s infinite;
}
</style>
