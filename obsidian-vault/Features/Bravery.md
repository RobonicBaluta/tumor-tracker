---
tags: [feature, bravery]
---

# Bravery (Feature view)

> Para detalle técnico ver [[../Architecture/Bravery]].

## Para el usuario

1. Abre **Social → Bravery** (o dentro de una sala)
2. Elige qué aleatorizar: **Champion** (siempre) + opcional **Lane** + opcional **Items**
   - 1 dim (champ only) → ×1.0 style mult
   - 2 dim → ×1.30
   - 3 dim → ×1.70 ← más bravo, más payout
3. Roll → ves champion + lane (si activa) + 5 items (si activa)
4. Pones stake en TC → **Lock**
5. Juegas tu próxima partida con ese setup
6. Vuelve a Bravery → **Comprobar partida** → resolución

## Payout (visible en la UI como tabla)

| Tumor   | Multi base | Notas |
|---------|-----------|-------|
| ≤ 20    | ×1.5     | Cracked, máximo |
| 40      | ×1.5     | (capped) |
| **60 sus** | **×1.0** | **break-even** — recuperas tu stake |
| 80      | ×0.5     | Pierdes la mitad |
| 100     | ×0       | Pierdes todo el stake |

Total payout = `stake × perf × effective_mult` donde `effective_mult` puede ajustarse según compliance (lane/items).

## Compliance

- **Champion**: OBLIGATORIO. Si no juegas el champ asignado, pierdes todo.
- **Lane** (si activa): si jugaste otra lane, `effective_mult -= 0.3` (min 1.0)
- **Items** (si activa): `hit_rate = items_jugados ∩ items_random / items_random`; `effective_mult *= 0.5 + 0.5*hit_rate`

## Tiempos

- 3h para jugar la partida (TTL del lock)
- 6h sin partida → refund automático
- Sólo 1 lock pending a la vez por user

## En salas

- Cada miembro hace su propio lock (no se comparte el roll)
- BraveryPanel muestra "OTROS EN ESTA SALA" con los locks pending de los miembros
- Cuando los users juegan en la misma partida real, sus tumor_score se calcula desde la mismísima partida → comparación natural

## Pendientes / ideas

- Modo competitivo en sala: bonus al user con menor tumor entre los que jugaron en la misma partida
- Limitar champ pool a "tus mains" (filtrar por mastery > N)
- Leaderboard de bravery
