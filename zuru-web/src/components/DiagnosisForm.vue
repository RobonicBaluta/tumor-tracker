<script setup lang="ts">
import { ref, computed } from 'vue';
import opFondo from '@/assets/opfondo.jpg';


const nombreInvocador = ref('');

const result1 = ref('');
const result2 = ref('');

const showResult1 = ref(false);
const showResult2 = ref(false);

const onePieceMsg = ref(false);
const onePieceMode = ref(false);

const backgroundStyle = computed(() => {
    return onePieceMode.value
        ? {
            backgroundImage: `url(${opFondo})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center'
        }
        : {};
});

const handleSubmit = () => {
    // Reset
    showResult1.value = false;
    showResult2.value = false;
    onePieceMsg.value = false;
    onePieceMode.value = false;

    result1.value = '';
    result2.value = '';

    // ⏱️ Secuencia tipo "diagnóstico"
    setTimeout(() => {
        result1.value = nombreInvocador.value;
        showResult1.value = true;
    }, 800);

    setTimeout(() => {
        result2.value = 'Tienes cáncer ✅';
        showResult2.value = true;
    }, 1800);

    setTimeout(() => {
        onePieceMsg.value = true;
        onePieceMode.value = true;
    }, 3200);
};
</script>

<template>
    <div class="flex-1 flex flex-col justify-center items-center transition-all duration-[1500ms]"
        :class="!onePieceMode ? 'bg-gradient-to-br from-[#143e54] to-[#27472e]' : ''" :style="backgroundStyle">
        <div class="bg-black/25 backdrop-blur-md p-[60px] px-[80px] rounded-2xl text-center shadow-2xl">
            <h1 class="text-white font-mono text-6xl mb-2">
                Oncológico Zurutuza
            </h1>

            <div class="h-[4px] w-[70%] mx-auto my-6 bg-linear-to-br from-transparent via-white to-transparent"></div>

            <form @submit.prevent="handleSubmit" class="flex justify-center gap-3">
                <input v-model="nombreInvocador" type="text" placeholder="Introduce nombre"
                    class="px-4 py-3 rounded-md bg-gray-200 focus:bg-white outline-none focus:ring-2 focus:ring-[#58d69b] transition" />

                <button type="submit"
                    class="bg-[#54af8c] hover:bg-[#58d69b] active:translate-y-[1px] hover:-translate-y-[2px] text-white px-5 py-3 rounded-md font-bold transition">
                    Diagnosis
                </button>
            </form>

            <!-- RESULTADOS -->
            <div v-if="showResult1" class="mt-8 text-4xl font-bold text-[#ec7895] animate-result">
                {{ result1 }}
            </div>

            <!-- RESULTADO 2 -->
            <div v-if="showResult2" class="mt-2 text-4xl font-bold text-[#e6dd91] animate-result delay-200">
                {{ result2 }}
            </div>
        </div>

        <!-- ONE PIECE -->
        <div v-if="onePieceMsg"
            class="mt-10 px-10 py-6 text-2xl font-bold text-white bg-black/60 backdrop-blur-md rounded-xl shadow-xl border border-white/20 animate-slideUp">
            Severinho ve One Piece
        </div>
    </div>
</template>

<style scoped>
@keyframes resultAppear {
    0% {
        opacity: 0;
        transform: translateY(15px) scale(0.98);
    }

    60% {
        opacity: 1;
        transform: translateY(-2px) scale(1.01);
    }

    100% {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

.animate-result {
    animation: resultAppear 0.6s ease forwards;
}

/* pequeño delay opcional para el segundo */
.delay-200 {
    animation-delay: 0.2s;
}

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

@keyframes slideUp {
    from {
        opacity: 0;
        transform: translateY(20px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.animate-fade {
    animation: fade 0.6s ease forwards;
}

.animate-slideUp {
    animation: slideUp 0.8s ease forwards;
}
</style>