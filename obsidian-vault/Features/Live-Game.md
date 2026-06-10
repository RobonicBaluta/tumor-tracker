---
tags: [feature, live-game]
---

# Live Game (`getOverview`)

El endpoint **gigante** que orquesta todo.

## Endpoint

`GET /getOverview?game_name=<name>&tag_line=<tag>`

## Pasos (1400-1830 en main.py)

1. **Resolver Riot ID → puuid** vía Account v1
2. **Detect platform** (EUW/EUNE/NA/...) probando Spectator en cada región
3. **Spectator v5**: `/lol/spectator/v5/active-games/by-summoner/{puuid}`
4. Para cada participante (con thread pool):
   - League entries (tier+division)
   - Match history (últimos N por queue)
   - `compute_prior_tumor` desde matches
   - Inferir `role` desde recent history
   - Detect `is_tilted` (recent_avg_tumor >= 50 con N recent_losses)
   - Detect `is_hotstreak` (consecutive wins recientes)
   - Match v5 details cacheado para obtener detallado
5. **`predict_team_outcome`** con los priors
6. Bans + arena subteams (si queue es arena)
7. **`save_live_snapshot`** — guarda snapshot {prediction, game_start_ts, player_priors} para reutilizar en otros endpoints

## Salida

```json
{
  "game_id": <int>,
  "match_id": <str>,
  "queue_id": <int>,
  "viewer_puuid": <str>,
  "players": [<10 dicts>],
  "bans": [...],
  "prediction": {"winner": "blue|red", "confidence": int, ...},
  "is_predictable_5v5": <bool>,
  "arena_subteams": [...] (sólo arena)
}
```

## Performance

- Threadpool dentro de `_process_player` → procesado paralelo de 10 players
- `step()` con progress lock para streaming progress (SSE no, polling client-side)
- Cache Riot SQLite (riot_cache.db) corta llamadas repetidas

## Live cache

`live_game_cache.json` se actualiza al final con `{puuid, champion_id} → {avg_tumor_score, role_inferred, last_match_ts}`. Es per-jugador, NO per-match. Sirve para precarga rápida en próximos overviews.

NO confundir con `live_snapshots` (SQLite, per-match, con prediction).
