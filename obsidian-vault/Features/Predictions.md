---
tags: [feature, predictions]
---

# Predictions

5v5 winner forecast basado en `predict_team_outcome` de [[../Architecture/Tumor-Engine]].

## Flujo

1. User abre `/getOverview` con su Riot ID
2. Backend genera predicción a partir de los priors históricos de los 10 players
3. User puede submitear su propia predicción con `POST /predict` → guardada en `predictions` table (PK: match_id + viewer_puuid)
4. Partida termina
5. `_resolve_pending_predictions()` (llamado desde `/predictionStats`):
   - Match v5 → si terminado: `actual_winner = 'blue' if blue.win else 'red'`
   - Actualiza row con `correct = (predicted == actual)`
   - **Resuelve TAMBIÉN bets matched del mismo match** (`resolve_bets_for_match`)
   - **Resuelve TAMBIÉN stat bets del mismo match**

## Datos

```python
{
    "match_id": str,
    "viewer_puuid": str,
    "viewer_name": str,
    "viewer_team": "blue" | "red",
    "blue_sum": float, "red_sum": float,
    "blue_score": float, "red_score": float,  # team tumor score (lo importante)
    "predicted_winner": "blue" | "red",
    "confidence": int,
    "created_at": float,
    "resolved": 0|1,
    "actual_winner": str | None,
    "correct": 0|1|None,
    "resolved_at": float
}
```

Si `predicted_winner is None` (user no quiso predecir) → row se marca `resolved=1` con `correct=None`.

## Stats globales

`GET /predictionStats` devuelve:
```json
{
  "total": <prediccs resueltas con predicted>,
  "correct": <correctas>,
  "accuracy": <pct>,
  "pending": <pending>,
  "recent": [<10 más recientes>]
}
```

UI: Overview.vue muestra accuracy global con color (`green ≥60%`, `yellow ≥50%`, `red <50%`).

## Reglas duras (fix histórico, commit 3fd8cdb)

1. NUNCA `winner.team_tumor > loser.team_tumor`
2. Tiebreaker en empate exacto usa **mean-of-valid-priors**, no `sum` (no sesgo por streamer count)

Si rompes esto: validar con [tests](../../zuru-web-backend/tests/test_tumor_engine.py) (30 tests).

Ver [[../Decisions/Prediction-Tiebreaker-Mean-Of-Valid]].
