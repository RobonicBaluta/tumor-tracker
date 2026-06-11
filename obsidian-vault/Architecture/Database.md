---
tags: [architecture, database]
---

# Architecture · Database

## Dos motores

- **Local dev**: SQLite (3 archivos)
  - `users.db` — users, bets, challenges, rooms, room_members, bravery_locks, friendships, achievements, user_notifications, currency_transactions, daily_rewards, room_bets, room_bet_participants, blacklist, watch_list, settings
  - `predictions.db` — predictions, live_snapshots, prediction_logs
  - `riot_cache.db` — cache responses Riot por endpoint+TTL
- **Prod (Render)**: Postgres en `DATABASE_URL` env var. Schema en `_init_pg()` (users_db.py:261). Auto-migración con `ALTER TABLE ADD COLUMN IF NOT EXISTS`.

## Tablas críticas

### `users`
```
id, discord_id, discord_username, discord_avatar,
riot_puuid, riot_id, currency, created_at, last_login
```

### `bets`
```
id, share_code, match_id, game_id,
creator_user_id, creator_side, amount,
taker_user_id, status (open|matched|resolved|refunded|cancelled),
winner_side, resolved_at, created_at,
bet_kind (match|stat), target_puuid, target_name, stat_type, threshold,
is_house, payout_multiplier,
game_end_ts, refunded, refund_reason
```

- `bet_kind='match'` con `is_house=true` → vs sistema, payout = stake * payout_multiplier
- `bet_kind='match'` con `is_house=false` → P2P, payout = stake * 2 al ganador
- `bet_kind='stat'` → over/under stat de un player concreto

### `challenges`
```
id, share_code,
challenger_user_id, challenger_puuid,
challenged_user_id, challenged_puuid,
stat_type, comparison (higher_wins|lower_wins), amount,
challenger_match_id, challenger_value, challenged_match_id, challenged_value,
status (open|accepted|resolved|expired|cancelled),
winner_user_id, created_at, accepted_at, resolved_at, expires_at,
format (single|bo3|tumor_race|streak),
challenger_wins, challenged_wins,
challenger_tumor_total, challenged_tumor_total,
matches_required, last_polled_at,
target_user_id    -- si !NULL, sólo este user puede aceptar (challenge dirigida)
```

`CHALLENGE_FORMATS` en `users_db.py:1006`:
```python
{
    "single": 1,        # legacy: ambos submitean 1 match manual
    "bo3": 2,           # first to 2 wins
    "tumor_race": 1,    # 1 match c/u, menor tumor gana
    "streak": 2,        # primer a 2 wins seguidas
}
```

### `rooms` + `room_members`
```
rooms: id, code, owner_user_id, name, created_at
room_members: room_id, riot_id, joined_at  (PK: room_id+riot_id)
```

Notas:
- `room_members.riot_id` es TEXT (no fk a users.id) → un user con riot_id puede estar incluso si no se registró en la app
- Max 8 miembros (validado en endpoint, no en DB)
- Owner se añade auto al crear si tiene riot_id

### `bravery_locks` (NEW)
```
id, user_id, puuid, room_code (NULL=solo),
champion_id, champion_name, lane (NULL=no dim), items_json (NULL=no dim),
dimensions (1-3), style_mult,
stake, status (pending|resolved|refunded|cancelled),
match_id_resolved, tumor_score, payout, compliance_json,
created_at, resolved_at, expires_at
```

- Un user sólo puede tener 1 lock pending a la vez (`user_has_pending_bravery`)
- TTL 3h para jugar; refund automático tras 6h sin partida

### `predictions` (en predictions.db, SQLite separado en local; misma DB en prod)
```
match_id, viewer_puuid, viewer_name, viewer_team,
blue_sum, red_sum, blue_score, red_score,
predicted_winner, confidence, created_at,
resolved (0|1), actual_winner, correct, resolved_at
```

PK lógico = (match_id, viewer_puuid)

### `live_snapshots` (en predictions.db)
```
match_id PRIMARY KEY,
snapshot TEXT (JSON),
created_at
```

Snapshot contiene:
```json
{
  "prediction": {"winner": "blue|red", "confidence": int, ...},
  "game_start_ts": <epoch seconds>,
  "player_priors": {
    "<puuid>": {"prior_tumor": ..., "role": ..., "tier": ..., "is_tilted": ..., "is_hotstreak": ...}
  }
}
```

`game_start_ts` se añadió para [[../Features/Bets#Payout-decay]] — se calcula `time.time() - game_start_ts` = elapsed.

## Esquema auto-migración

Patrón estándar tanto SQLite como Postgres:

```python
# SQLite
ch_cols = {row[1] for row in conn.execute("PRAGMA table_info(challenges)").fetchall()}
for name, ddl in [...]:
    if name not in ch_cols:
        try: conn.execute(f"ALTER TABLE challenges ADD COLUMN {name} {ddl}")
        except Exception: pass

# Postgres
for col_def in [...]:
    try: cur.execute(f"ALTER TABLE challenges ADD COLUMN IF NOT EXISTS {col_def}")
    except Exception: pass
```

**Cuando añadas una columna**: actualizar AMBOS schemas (_init_sqlite y _init_pg) + `_<table>_COLS` constante + `_row_to_<table>` mapper.

## Caches no-DB

- `live_game_cache.json` — por puuid+champion: avg_tumor_score histórico, role inferred, last_match_ts. Es per-jugador, NO per-match. NO confundir con `live_snapshots`.
- `recent_summoners.json` — lista de últimos puuids vistos (UI dropdown). Lo modifica al usar la app local; **no commitear**.
- `saved_accounts.json` — backup de credenciales test, no commitear.
