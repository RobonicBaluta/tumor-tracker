---
tags: [decision, bravery, tumor]
date: 2026-06-11
---

# Tumor Threshold = 60 (sus) como break-even de Bravery

## Decisión

En `bravery_engine.compute_payout`, el tumor score 60 es el punto de break-even (perf = 1.0). Por debajo ganas, por encima pierdes.

```python
SUS_TUMOR_THRESHOLD = 60.0
perf = clamp(1.0 + (60 - tumor) / 40, 0, 1.5)
```

## Por qué

El codebase ya usa **60 como "nivel sus"** en varios sitios:
- `main.py:3545` (literal "tumor score sus"): un stat bet auto-creado usa `threshold=60` para tumor over/under
- Clusters: `avg_prior > 65` es "tumor_cronico", `< 35` es "carry_estable" → el rango 35-65 es la zona "normal" con 60 como upper-normal
- `main.py:1337`: `avg_recent_tumor >= 50` se considera tilted

60 es coherente con la narrativa: tumor 50-60 = jugador "normal", tumor 60+ = inflado/sus. El user confirma esto explícitamente: "sus creo que podría ser el nivel donde empiezas a perder".

## Curva concreta

`perf = clamp(1.0 + (60 - tumor) / 40, 0, 1.5)`

| Tumor | perf |
|-------|------|
| 0     | 1.5 (capped) |
| 20    | 1.5 (capped) |
| 40    | 1.5 |
| **60**| **1.0** ← break-even |
| 80    | 0.5 |
| 100   | 0.0 |

Pendiente: -1/40 por cada punto tumor sobre 60. A tumor 80 (típico en partidas malas) ya pierdes la mitad. A 100 (catastrófico) pierdes todo.

## Cómo aplicar

- Si pides cambiar la curva del bravery payout: piensa antes si el "nivel donde empiezas a perder" debe seguir siendo 60. Si el user dice "no, debería ser 50" → es razonable, sólo asegúrate de cambiar la constante.
- **NO mover el threshold para otros sistemas** (clusters, tilt) — sólo se aplica al payout bravery.

## Edge cases

- `tumor_score is None` (sin Match v5 detail) → payout = 0
- `champion_match = False` → payout = 0 (override de la perf)
- Style mult independiente: multiplica al final, no afecta el cero
