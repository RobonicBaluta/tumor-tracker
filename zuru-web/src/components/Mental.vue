<script setup lang="ts">
import { ref, computed } from 'vue';

const textoCompleto = 'que ambos tienen relación directa con el origen de todos los males\n\nque viene a ser tu mental\n\nrara vez te he escuchado decir que las cosas podrían haber salido mejor\n\n y siempre lo enfocas en que ha salido mal por culpa de x e y factores\n\nno tienes control en la partida más allá de tu personaje\n\n asi que en vez de frustrarte por lo que otros hacen mal\n\n tendrías que pensar en que puedes hacer tú por sacarlo adelante\n\ny si la respuesta es que son tan malos que no hay nada que hacer\n\n para poder salir adelante la siguiente pregunta es por que sigues jugando a estas alturas?\n\n prueba a deshabilitar el chat general y jugar sin música ni nada de fondo\n\n luego mandas los resultados';

const textos = computed(() => {
  return textoCompleto.split('\n\n').map(p => p.trim()).filter(p => p.length > 0);
});
const pregunta = ref('');

const resultado = ref('');
const showResult1 = ref(false);
const showTexto = ref(false);

const handleSubmit = () => {
  // Reset
  showResult1.value = false;
  showTexto.value = false;

  // ⏱️ Secuencia tipo "diagnóstico"
  setTimeout(() => {
    resultado.value = 'Tienes mal mental';
    showResult1.value = true;
  }, 800);

  setTimeout(() => {
    showTexto.value = true;
  }, 800 + 2500); // Después de que termine la animación fade
};
</script>
<template>
  <div
    class="flex-1 flex flex-col justify-center items-center bg-gradient-to-br from-[#462121] to-[#5b0d5e] relative overflow-hidden">

    <div
      class="bg-white/40 backdrop-blur-md w-[80%] h-[80%] overflow-y-auto rounded-2xl text-center shadow-2xl animate-fade relative z-10">
      <h1 class="text-black font-mono text-6xl mb-8 mt-8 p-[1rem]">
        Buen Mental
      </h1>

      <div class="h-[4px] w-[70%] mx-auto my-6 bg-linear-to-br from-transparent mb-16 via-black to-transparent"></div>

      <div class="">
        <form @submit.prevent="handleSubmit" class="flex justify-center gap-3">
          <input v-model="pregunta" type="text" placeholder="¿Cual es tu pregunta?"
            class="w-[32rem] px-4 py-3 rounded-md bg-gray-200 focus:bg-white outline-none focus:ring-2 focus:ring-[#d174dd] transition" />

          <button type="submit"
            class="bg-[#961f90] hover:bg-[#d174ee] active:translate-y-[1px] hover:-translate-y-[2px] text-[#ffffff] px-5 py-3 rounded-md font-bold transition">
            Diagnosis
          </button>
        </form>
        <div v-if="showResult1" class="mt-16 text-[8rem] font-[Comic sans MS] font-bold text-[#cfd84fcb] animate-fade">
          {{ resultado }}
        </div>
        <div v-if="showTexto" class="mt-8 text-[2rem] text-black px-8 font-serif italic space-y-6">
          <div v-for="(parrafo, index) in textos" :key="index" class="animate-typewriter" :style="{ animationDelay: `${index * 0.5}s` }">
            {{ parrafo }}
          </div>
        </div>
      </div>

    </div>

    <video autoplay loop playsinline class="absolute top-0 left-0 w-full h-full object-cover">
      <source src="@/assets/tibet.webm" type="video/webm" />
    </video>
  </div>
</template>

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
  animation: fade 2.5s ease forwards;
}

@keyframes typewriter {
  0% {
    clip-path: inset(0 100% 0 0);
    opacity: 0;
  }
  100% {
    clip-path: inset(0 0 0 0);
    opacity: 1;
  }
}

.animate-typewriter {
  animation: typewriter 1.5s ease-out forwards;
  opacity: 0;
}
</style>
