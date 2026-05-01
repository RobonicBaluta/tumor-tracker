<template>
  <div class="flex items-center justify-between gap-4">
    <div class="flex-1 min-w-0">
      <p class="text-white text-sm font-mono">{{ label }}</p>
      <p v-if="desc" class="text-white/40 text-[10px] font-mono">{{ desc }}</p>
    </div>
    <button @click="emit('update:modelValue', !modelValue)"
      :class="modelValue ? 'bg-yellow-600' : 'bg-white/15'"
      class="relative w-11 h-6 rounded-full shrink-0 p-0 border-0 cursor-pointer overflow-hidden"
      style="transition: background-color 0.15s ease">
      <span
        class="absolute w-5 h-5 bg-white rounded-full shadow"
        :style="{ left: modelValue ? '22px' : '2px', top: '2px', transition: 'left 0.15s ease' }" />
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{ label: string; desc?: string; modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>
