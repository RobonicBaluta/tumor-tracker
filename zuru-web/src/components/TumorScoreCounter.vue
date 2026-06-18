<script setup lang="ts">
import { toRef } from 'vue'
import { useCountUp } from '../composables/useCountUp'

// Wrapper de useCountUp para usar en v-for: cada instancia tiene su propio
// estado interno y anima el valor que se le pase desde 0 (o el último
// valor) al actual. Renderiza UN span con la cuenta — el estilo se hereda
// del padre vía class/style pasthrough.

const props = withDefaults(defineProps<{
  value: number | null | undefined
  /** Duración en ms. Default 700. */
  duration?: number
  /** Si true, render directo sin animación inicial (luego sí en cambios). */
  skipInitial?: boolean
}>(), {
  duration: 700,
  skipInitial: false,
})

const target = toRef(props, 'value')
const { display } = useCountUp(target, {
  duration: props.duration,
  skipInitial: props.skipInitial,
})
</script>

<template>
  <span>{{ display }}</span>
</template>
