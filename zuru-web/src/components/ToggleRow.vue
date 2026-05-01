<template>
  <div class="flex items-center justify-between gap-4">
    <div class="flex-1 min-w-0">
      <p class="text-white text-sm font-mono">{{ label }}</p>
      <p v-if="desc" class="text-white/40 text-[10px] font-mono">{{ desc }}</p>
    </div>
    <button @click="emit('update:modelValue', !modelValue)"
      :class="modelValue ? 'bg-yellow-600' : 'bg-white/10'"
      class="relative w-10 h-5 rounded-full transition shrink-0">
      <span
        :class="modelValue ? 'translate-x-5' : 'translate-x-0.5'"
        class="absolute top-0.5 w-4 h-4 bg-white rounded-full transition" />
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{ label: string; desc?: string; modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>
