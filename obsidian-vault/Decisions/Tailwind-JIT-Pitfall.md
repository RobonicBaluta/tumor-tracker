---
tags: [decision, frontend, tailwind]
---

# Tailwind JIT no escanea ramas de ternarios

## Decisión

Para clases que dependen de runtime (toggle on/off, color por estado), prefiere `:style="{}"` inline en lugar de `:class="cond ? 'translate-x-[22px]' : 'translate-x-0'"`.

## Por qué

Tailwind JIT escanea archivos en build-time y genera SÓLO las clases que ENCUENTRA literalmente como strings. Una clase dentro de una rama de ternario a veces se detecta, a veces no — depende del parser. Resultados:
- En dev: a veces funciona porque el HMR escanea de otra forma
- En build: la clase no entra en el bundle → la clase no existe → el efecto visual no aparece

Esto pasó con un toggle button: `translate-x-[22px]` (clase arbitrary) no se generaba en producción, el círculo no se movía.

## Cómo aplicar

```vue
<!-- ❌ riesgoso para clases arbitrarias -->
<div :class="open ? 'translate-x-[22px]' : 'translate-x-0'" />

<!-- ✓ seguro: inline style -->
<div :style="{ transform: open ? 'translateX(22px)' : 'translateX(0)' }" />
```

Para clases NO-arbitrarias (las que están en el config standard de Tailwind como `bg-red-500`, `text-white`), el ternario sí funciona porque las clases ya estaban en el bundle.

## Edge case

Si quieres que la clase arbitraria entre en el bundle pase lo que pase, lista las clases en un comentario que Tailwind escanee:

```vue
<!-- safelist: translate-x-[22px] translate-x-0 -->
```

O añadirlo al `safelist` del `tailwind.config.ts`.

Pero en general, `:style` inline es más simple y libre de footguns.
