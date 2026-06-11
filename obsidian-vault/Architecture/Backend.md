---
tags: [architecture, backend]
---

# Architecture · Backend

## main.py — el monolito

~5100 LOC. Todos los endpoints viven aquí. No partir sin razón fuerte. Map:

| Rango              | Sección                                      |
|--------------------|----------------------------------------------|
| 1-30               | Imports                                      |
| 30-500             | Helpers Riot (riot_get, detect_platform, predicciones)  |
| 500-540            | SQLite predictions.db + `live_snapshots`     |
| 540-1830           | `getOverview` (el endpoint gigante de live game) |
| 1830-2100          | Auth flow (Discord), `/auth/me`              |
| 2100-2400          | Player analytics, role stats, duos          |
| 2400-2600          | Clusters + archetypes                        |
| 2600-3140          | Currency, daily rewards, achievements        |
| 3140-3200          | Rooms (crear/join/leave/delete)              |
| 3200-3700          | Bets P2P, House, Stat (preview-multiplier, create, resolve-mine) |
| 3700-4000          | Challenges 1v1 (single/bo3/tumor_race/streak) |
| 4000-4100          | Open feeds                                    |
| 4100-4400          | Room bets (pool)                              |
| 4400-4500          | Predictions stats global                      |
| 4500-4700          | `/resolvePrediction`, `/predictionStats`     |
| 4700-4900          | Worst player, blacklist, misc                |
| 4900-5170          | **Bravery endpoints** (data/roll/lock/cancel/mine/room/resolve-mine) |

## Funciones críticas

- **`riot_get(url)`** — wrapper con retries + rate-limit. SIEMPRE usar en lugar de `requests.get`.
- **`_current_user()`** — extrae JWT del header, devuelve dict de user. Null si no logueado.
- **`_get_match_prediction(match_id)`** — lee predicción desde SQLite `live_snapshots`. NO usar `live_game_cache.json` (es per-puuid+champion, otra cosa).
- **`_compute_house_multiplier(match_id, side)`** — usa prediction + UNDERDOG_BONUS + decay temporal. Ver [[../Features/Bets]].
- **`_resolve_pending_predictions()`** — barre predicciones; AHORA TAMBIÉN resuelve bets matched del mismo match_id. Ver [[../Features/Bets]].
- **`_auto_resolve_orphan_bets()`** — segundo sweep para bets en matches sin predicción asociada. Llamado desde `/predictionStats`.
- **`_live_elapsed_seconds(match_id)`** — segundos elapsed desde `game_start_ts` del snapshot. None si no hay snapshot.

## Endpoints por familia

### Auth
- `GET /auth/discord/login`, `GET /auth/discord/callback` — OAuth flow
- `POST /auth/link-riot`, `POST /auth/unlink-riot`
- `GET /auth/me` — devuelve user + balance

### Live game
- `GET /getOverview?game_name=&tag_line=` — ⭐ el grande
- `GET /matchDetail/<match_id>`
- `GET /el-peor?game_name=&tag_line=`
- `GET /historicalMatches?game_name=&tag_line=&page=`

### Predicciones
- `POST /predict` — submitea una predicción
- `GET /predictionStats` — sweep autoresolve + accuracy global
- `POST /resolvePrediction` — fuerza resolve de un match concreto

### Bets
- `GET /bets/open` — feed público
- `GET /bets/preview-multiplier?match_id=&side=` — con decay + close flag
- `POST /bets/create`
- `POST /bets/<share_code>/accept`, `POST /bets/<share_code>/cancel`
- `POST /bets/resolve-mine` — disparado al abrir MyBetsModal
- `GET /bets/mine`

### Challenges 1v1
- `POST /challenges/create` — body opcional `challenged_user_id` para dirigir
- `POST /challenges/<code>/accept`, `cancel`
- `GET /challenges/open` — feed; filtra targeted-to-others
- `GET /challenges/mine`
- `POST /challenges/poll` — disparo manual del poller bo* (también hay cron interno)

### Rooms
- `POST /rooms/create`, `GET /rooms/mine`
- `GET /rooms/<code>`, `POST /rooms/<code>/join`, `POST /rooms/<code>/leave`
- `DELETE /rooms/<code>` (owner only)
- `POST /rooms/<code>/bets/create`, `.../join`, `.../start`, `.../cancel`
- `GET /rooms/<code>/bets`, `POST /rooms/bets/poll`

### Bravery
- `GET /bravery/data` — DDragon (version, champions, items)
- `POST /bravery/roll` — sin escrow
- `POST /bravery/lock` — escrow
- `POST /bravery/<id>/cancel`
- `GET /bravery/mine`, `GET /bravery/room/<code>`
- `POST /bravery/resolve-mine`

## tumor_engine.py

```
compute_match_tumor_from_stats(stats_5_axis, role, tier, duration)
compute_match_tumor(participant, duration, tier)  # adapter desde Riot participant dict
compute_prior_tumor(matches)
compute_team_tumor(players)
predict_team_outcome(players, tie_threshold=4, confidence_scale=6)
```

Reglas críticas:
- **Median absoluto** decide winner (no sum)
- Tiebreaker en empate exacto usa **mean-of-valid-priors** (no sum, para no sesgar por streamer count)
- Tests en `tests/test_tumor_engine.py` — 30 tests obligatorios verdes antes de deploy

Ver [[Tumor-Engine]].

## bravery_engine.py

- Pull DDragon (versions → champion.json + item.json) con cache 24h
- Filtro items finales: `into=[]`, `gold>=2000`, no consumables/trinkets, mapa 11 activo, no requiredAlly
- `style_mult_for_dims`: 1.0 / 1.30 / 1.70
- `compute_compliance(lock, participant)`: champion_match (obligatorio), lane_match, items_hit_rate → effective_mult
- `compute_payout`: piecewise centrado en **SUS_TUMOR_THRESHOLD=60**

Ver [[Bravery]].

## auth.py

- Discord OAuth: redirect to discord → callback → JWT issued
- `JWT_SECRET` desde env var
- Token vive en localStorage del frontend
- `_current_user()` extrae bearer token y resuelve user

## riot_infra.py

- SQLite cache (`riot_cache.db`) con TTL por endpoint
- Rate limiter por header `X-Rate-Limit-Count`
- Retry con backoff exponencial en 429/5xx
