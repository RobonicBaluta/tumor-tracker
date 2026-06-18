<script setup lang="ts">
import { computed, ref } from 'vue'

// Renderiza el avatar de Discord de un user. Si falta data (discord_id o
// avatar hash null) o si la imagen falla al cargar, cae a un cuadro con la
// inicial del username y el clásico azul Discord (#5865F2) — patrón que ya
// usaba el codebase inline en 5+ sitios antes de extraerse aquí.

interface Props {
  discordId?: string | null
  avatar?: string | null
  username?: string | null
  /** Tamaño Tailwind: w/h applied. Default md (w-7 h-7). */
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
  /** Forma. Default 'circle' — Discord usa redondo. 'square' útil si encaja
   *  con un set de avatares cuadrados (champion icons al lado, p.ej.). */
  shape?: 'circle' | 'square'
}

const props = withDefaults(defineProps<Props>(), {
  discordId: null,
  avatar: null,
  username: null,
  size: 'md',
  shape: 'circle',
})

const sizeClass = computed(() => {
  switch (props.size) {
    case 'xs': return 'w-5 h-5 text-[9px]'
    case 'sm': return 'w-6 h-6 text-[10px]'
    case 'md': return 'w-7 h-7 text-xs'
    case 'lg': return 'w-9 h-9 text-sm'
    case 'xl': return 'w-12 h-12 text-base'
  }
})
const radiusClass = computed(() => props.shape === 'square' ? 'rounded-md' : 'rounded-full')

// Tamaño de bitmap que pedimos a Discord CDN. Más pequeño = más rápido pero
// borroso en HiDPI a tamaños grandes. ?size=64 cubre xs/sm/md/lg con calidad.
// Para xl pedimos 128 para no quedar pixelado en retina.
const cdnSize = computed(() => props.size === 'xl' ? 128 : 64)

const imgFailed = ref(false)
const src = computed(() => {
  if (!props.discordId || !props.avatar) return null
  return `https://cdn.discordapp.com/avatars/${props.discordId}/${props.avatar}.png?size=${cdnSize.value}`
})

function onError() {
  // Discord puede devolver 404 si el avatar fue eliminado entre el fetch
  // del backend y el render. Caemos al fallback inicial.
  imgFailed.value = true
}

const initial = computed(() => {
  const u = props.username
  if (!u) return '?'
  // First grapheme — protege contra usernames que empiezan con emoji.
  // [...str][0] descompone surrogate pairs correctamente.
  const first = [...u][0]
  return (first || '?').toUpperCase()
})
</script>

<template>
  <img v-if="src && !imgFailed"
    :src="src"
    :alt="username || 'avatar'"
    :class="[sizeClass, radiusClass, 'shrink-0 object-cover']"
    @error="onError" />
  <span v-else
    :class="[sizeClass, radiusClass, 'shrink-0 bg-[#5865F2] flex items-center justify-center text-white font-bold leading-none']"
    :title="username || ''"
    role="img"
    :aria-label="username || 'avatar'">
    {{ initial }}
  </span>
</template>
