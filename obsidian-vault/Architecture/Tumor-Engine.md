---
tags: [architecture, tumor, scoring]
---

# Architecture · Tumor Engine

Archivo: [`tumor_engine.py`](../../zuru-web-backend/src/tumor_engine.py). Tests: [`tests/test_tumor_engine.py`](../../zuru-web-backend/tests/test_tumor_engine.py) — **30 tests, mantener en verde**.

## Concepto

**Tumor score = qué tan malo fue ese jugador en esa partida**. Rango 0-100. 0 = perfecto, 100 = catástrofe total. Niveles narrativos:

| Tumor | Etiqueta común |
|-------|-----------------|
| ≤ 20  | Limpio / Cracked |
| 20-40 | Normal good |
| 40-60 | Normal |
| **60** | **SUS** ← break-even bravery |
| 60-80 | Tumor inflamado |
| 80-100 | Tumor maligno |

## 5 ejes

1. **KDA** vs threshold por rango
2. **CS/min** vs threshold por rol+rango
3. **Damage/min a champs** vs threshold
4. **Alive %** = 1 - dead_time/game_time; threshold 85%
5. **Vision/min** (clamped a 0 para no-supports) vs threshold por rol

Cada eje produce un `bad_score(value, threshold)`:

```python
def bad_score(value, threshold):
    if threshold <= 0: return 0.0
    if value >= threshold: return 0.0
    return max(0.0, min(100.0, (1.0 - value / threshold) * 100.0))
```

Pesos por rol:
- ADC/MID: KDA 25, CS 30, DMG 25, ALIVE 10, VIS 10
- TOP: KDA 25, CS 25, DMG 30, ALIVE 10, VIS 10
- JG: KDA 30, CS 20, DMG 20, ALIVE 15, VIS 15
- SUP: KDA 30, CS 5, DMG 15, ALIVE 15, VIS 35

Tumor final = `sum(pesos × bad_score por eje) / sum(pesos)`.

## API pública

```python
compute_match_tumor_from_stats(stats: dict, role: str, tier: str, duration_s: int) -> float
compute_match_tumor(participant: dict, duration_s: int, tier: str) -> float
    # adapter: extrae stats desde dict Riot participant
compute_prior_tumor(matches: list[float]) -> float
    # avg de últimos N (con peso decreciente para los más viejos)
compute_team_tumor(players: list[dict]) -> dict
    # {median, mean, sum, valid_count}
predict_team_outcome(players, tie_threshold=4, confidence_scale=6) -> dict
    # winner, confidence, reasoning
```

## predict_team_outcome — reglas críticas

(Fuente: testeado a fondo, fix histórico en commit `3fd8cdb`)

1. **Median absoluto decide ganador** cuando difieren. NUNCA debe pasar que `winner.team_tumor > loser.team_tumor`.
2. **Tiebreaker** sólo cuando medianas son EXACTAMENTE iguales: usa **mean-of-valid-priors** (no `sum`), para no sesgar por número de jugadores con tier conocido.
3. **Confidence**:
   - Si `abs_diff > 0`: `confidence = abs_diff * confidence_scale` capped 100
   - Si tiebreaker con mean: `int(abs(blue_mean - red_mean)) * 2` capped 40
   - Sin diferencia: 0
4. Devuelve `predicted_winner: 'blue'|'red'` y `confidence: int`.

## Invariante de tests

`test_winner_median_never_exceeds_loser` — para todas las combinaciones posibles, el lado predicho NUNCA tiene mediana mayor. Si rompes esto, el codebase falla en producción y los users ven "el de mejor pinta perdió".

## Constantes a tunear (rango)

`KDA_BASE`, `CS_PM_BASE_*`, `DMG_PM_BASE_*`, `VIS_PM_BASE_*` en tumor_engine.py — multiplicadores por tier en `TIER_MULTIPLIER`.

⚠ Si tocas thresholds: validar 30 tests + comparar predicciones contra una semana de juego histórico (snapshots en `predictions.db`).
