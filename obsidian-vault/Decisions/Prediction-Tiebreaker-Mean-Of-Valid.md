---
tags: [decision, prediction, tumor-engine]
date: 2026-06-09
commit: 3fd8cdb
---

# Prediction Tiebreaker usa Mean-of-Valid-Priors, no Sum

## Decisión

En `predict_team_outcome` (tumor_engine.py):
1. La **mediana absoluta** decide el ganador cuando difieren.
2. Tiebreaker SÓLO se activa en **empate exacto** entre medianas.
3. Cuando se activa, usa `mean(valid_priors)`, NO `sum`.

```python
blue_mean = sum(blue_valid_only) / len(blue_valid_only)
```

(en lugar del antiguo `blue_sum` que sumaba todos los priors incluyendo defaults).

## Por qué

### Bug original

5 de cada 50 snapshots históricos predecían que el lado con **mayor mediana de tumor** ganaba. Imposible — `tumor alto = malo`. Causa raíz:

1. `tie_threshold = 4`: cuando `|median_blue - median_red| < 4`, se consideraba "empate" y disparaba el tiebreaker
2. El tiebreaker comparaba `blue_sum` vs `red_sum` (suma de TODOS los priors, incluyendo defaults `50.0` para jugadores sin tier)
3. Si blue tiene 5 streamers (todos con prior conocido) y red tiene 3 (resto default 50), `red_sum = 3*X + 2*50` se inflaba artificialmente → blue parecía mejor incluso si su mediana era PEOR

### Fix

- Median absoluto sin tie_threshold blando → si median_blue=42.1 y median_red=42.0, blue gana (mejor), no tiebreaker.
- Tiebreaker SÓLO si `median_blue == median_red` exactamente.
- Cuando dispara, `mean(blue_valid_only)` ignora los defaults — sólo cuenta jugadores con prior real.

### Confidence rescaling

```python
if abs(median_diff) > 0:
    confidence = abs(median_diff) * confidence_scale   # 6 por defecto
else:
    # tiebreaker activo
    confidence = int(abs(blue_mean - red_mean) * 2)
    confidence = min(40, confidence)   # tiebreaker max 40
```

Idea: confidence basado en mediana es "fuerte"; basado en mean tiebreaker es "débil".

## Invariante (tests)

`test_winner_median_never_exceeds_loser` y otros en `tests/test_tumor_engine.py`:
- `test_median_difference_of_1_still_decides`
- `test_sum_tiebreaker_only_kicks_in_when_medians_exactly_equal`
- `test_streamer_count_does_not_distort_tiebreaker`

30/30 tests deben pasar. Si añades otro test de invariante, súbelo aquí también.

## Cómo aplicar

Si el user pide "haz la predicción más sensible" o "menos sensible":
- Más sensible: confidence_scale más alto (10 en lugar de 6)
- Menos sensible: confidence_scale más bajo (4)
- **NO toques** la lógica de tiebreaker sin volver a correr los tests.
