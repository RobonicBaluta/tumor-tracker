---
tags: [decision, frontend, ui]
---

# Modales con `<Teleport to="body">`

## Decisión

Todo modal/overlay que viva dentro de **Navbar.vue** (o cualquier ancestor con `position: sticky` + `z-index: 50`) DEBE envolverse en `<Teleport to="body">`.

## Por qué

Navbar usa `sticky top-0 z-50` para fijarse arriba. Cualquier child con `position: fixed` queda atrapado en el stacking context del Navbar y:
- No puede cubrir lo que está fuera del Navbar
- Aparece por debajo del contenido principal
- Si el modal usa `z-index: 100`, sigue debajo porque z-index sólo importa dentro del mismo stacking context

## Cómo aplicar

```vue
<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="fixed inset-0 ...">
        <!-- modal content -->
      </div>
    </Transition>
  </Teleport>
</template>
```

Cierre del template:
```vue
  </Transition>
  </Teleport>
</template>
```

## Ejemplos en el repo

- `SocialModal.vue` ✓
- `BetModal.vue` ✓
- `MyBetsModal.vue` ✓
- `UserModal.vue` ✓
- `OnboardingTour.vue` ✓

Si añades uno nuevo, sigue el patrón.

## Edge case

Si el modal necesita compartir contexto con el componente padre (composables/i18n) **sí lo mantiene** — Teleport sólo mueve el DOM, no el componente. Funcs y refs siguen vivos.
