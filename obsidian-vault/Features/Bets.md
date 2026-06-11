---
tags: [feature, bets]
---

# Bets

## Tipos

- **Match P2P**: 2 users, lado blue/red, payout 2x al ganador.
- **Match House**: 1 user vs sistema. Payout = stake × dynamic multiplier (basado en confidence + UNDERDOG_BONUS + decay temporal).
- **Stat**: over/under sobre una stat de un player concreto (kills/deaths/assists/kda/cs/gold/damage/tumor_score).

## Endpoints

- `GET /bets/open` — feed público de P2P abiertas
- `GET /bets/preview-multiplier?match_id=&side=` → `{multiplier, is_underdog, underdog_bonus, elapsed_seconds, betting_closed, close_at_elapsed, decay_factor}`
- `POST /bets/create` — body: match bet `{match_id, game_id, side, amount, is_house?}` o stat `{..., bet_kind:'stat', target_puuid, stat_type, threshold}`
- `POST /bets/<code>/accept`, `POST /bets/<code>/cancel`
- `POST /bets/resolve-mine` — autoresolve solo del user; ya se llama desde el modal MyBets
- `GET /bets/mine`
- `POST /bets/player` — atajo: apuesta 1-click sobre un player con threshold automático

## Multiplier dinámico (`_compute_house_multiplier`)

```python
prob_winner = min(0.92, 0.5 + 0.42 * (pred.confidence / 100))
is_against = (side != pred.winner)
prob_side = prob_winner if not is_against else (1 - prob_winner)
mult = 0.95 / max(0.08, prob_side)
if is_against: mult *= UNDERDOG_BONUS   # 1.30
mult *= _payout_decay_factor(elapsed)
return clamp(mult, 1.05, 6.5)
```

## Payout decay temporal

Constantes (main.py):
- `PAYOUT_DECAY_START = 5 * 60`  # antes de min 5: sin decay
- `PAYOUT_DECAY_END = 25 * 60`   # a 25 min: floor
- `PAYOUT_DECAY_FLOOR = 0.55`    # multi no cae por debajo de 55% nominal

```python
def _payout_decay_factor(elapsed):
    if elapsed is None or elapsed <= START: return 1.0
    if elapsed >= END: return FLOOR
    frac = (elapsed - START) / (END - START)
    return 1.0 - frac * (1.0 - FLOOR)
```

`elapsed = time.time() - snapshot.game_start_ts` (de Spectator).

## Close window

- `BET_CLOSE_AT_ELAPSED = 25 * 60` (25 min)
- `_is_betting_closed(match_id)` → True si elapsed >= 25min
- `/bets/create` rechaza 400 con "Ventana cerrada"
- `/bets/preview-multiplier` devuelve `betting_closed: true` para que el frontend deshabilite el botón

## Auto-resolve (clave)

Históricamente sólo se resolvía cuando el user abría MyBetsModal. AHORA:

### Caminos de resolución

1. `_resolve_pending_predictions()` — llamado por `GET /predictionStats`. Para cada match con prediction unresolved: Match v5 → si terminado → marca pred resolved + **resuelve bets del mismo match_id** (`resolve_bets_for_match`) + resuelve stat bets de ese match.
2. `_auto_resolve_orphan_bets(max_matches=15)` — para bets cuyo match_id no tiene prediction asociada. Se llama también desde `/predictionStats`. Throttling: `min_age_seconds=180` en `list_pending_match_ids` para no quemar Riot rate con bets recién creadas.
3. `POST /bets/resolve-mine` — sólo bets del user (legacy, sigue activo desde MyBetsModal).
4. `POST /resolvePrediction` — un solo match, llamado al clickar "Comprobar resultado".

### Refund window

En `resolve_bet`: si `game_end_ts != None` y `(game_end_ts - bet.created_at) < REFUND_WINDOW_SECONDS (60)` → refund (no resolve). Red de seguridad por si una bet escapa del close window.

## Game_end_ts extraction

```python
end_ms = info.get("gameEndTimestamp")
if end_ms:
    game_end_ts = end_ms / 1000.0
else:
    start_ms = info.get("gameStartTimestamp")
    dur = info.get("gameDuration", 0)
    game_end_ts = (start_ms / 1000.0) + dur if start_ms else None
```

## Frontend

- [BetModal.vue](../../zuru-web/src/components/BetModal.vue) — preview con decay + betting_closed visual
- [MyBetsModal.vue](../../zuru-web/src/components/MyBetsModal.vue) — abre y dispara `auth.resolveMyPendingBets()`
- Tab "hot" en SocialModal → feed `/bets/open`

## Gotchas históricos

- **`load_live_cache` ≠ `live_snapshots`**. `live_cache` (JSON) es por puuid+champion. `live_snapshots` (SQLite) es por match. Usar `_get_match_prediction(match_id)` que lee del segundo. Bug histórico: usar el cache incorrecto provocaba "siempre favorito" en `_compute_house_multiplier`.
