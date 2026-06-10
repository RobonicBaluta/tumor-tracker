---
tags: [architecture, overview]
---

# Architecture · Overview

## Layout del repo

```
zuruweb/
├── zuru-web-backend/          # Flask API
│   ├── src/
│   │   ├── main.py            # ~5100 LOC — todos los endpoints, gigantesco. Owner del API.
│   │   ├── users_db.py        # ~2100 LOC — schema + helpers SQLite/Postgres
│   │   ├── tumor_engine.py    # scoring 5-axis, predict_team_outcome
│   │   ├── bravery_engine.py  # DDragon cache + roll + compute_payout (sus=60)
│   │   ├── auth.py            # Discord OAuth + JWT
│   │   ├── config.py          # URLs Riot, queues, BETTING_ALLOWED_QUEUES
│   │   ├── riot_infra.py      # cache + rate limit + retry para Riot
│   │   ├── ml_predictor.py    # ML opcional (no usado por defecto)
│   │   ├── live_game_cache.json   # cache de live games por puuid+champion
│   │   ├── predictions.db     # SQLite con predictions + live_snapshots
│   │   ├── users.db           # SQLite con users, bets, challenges, rooms, bravery_locks
│   │   └── riot_cache.db      # SQLite con cache de respuestas Riot
│   └── tests/test_tumor_engine.py  # 30 tests, pasar siempre antes de deploy
├── zuru-web/                  # Vue 3 frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── Overview.vue        # ~3500 LOC — vista principal live game
│   │   │   ├── SocialModal.vue     # ~1100 LOC — tabs: hot, lb, clusters, challenges, bravery, friends, rooms
│   │   │   ├── BetModal.vue        # crear bet / aceptar bet con preview multiplier
│   │   │   ├── MyBetsModal.vue     # bets del user; dispara auto-resolve al abrir
│   │   │   ├── BraveryPanel.vue    # reusable: solo (room=null) o sala
│   │   │   ├── Navbar.vue, UserModal.vue, Tinder.vue, Mental.vue, Compare.vue
│   │   ├── composables/
│   │   │   ├── useAuth.ts          # JWT + balance + TODAS las llamadas API
│   │   │   └── overviewConstants.ts
│   │   └── i18n/locales/{es,en}.json
│   └── dist/                  # build de producción → desplegado
├── deploy.sh                  # merge server-fix→main + push a origin + personal
├── obsidian-vault/            # ← este vault
└── start-zuru.py              # script local del owner para correr la app
```

## Sub-páginas

- [[Backend]] — endpoints clave, módulos, flujo de auth
- [[Frontend]] — components, composables, build
- [[Database]] — schemas SQLite local + Postgres prod, tablas críticas
- [[Riot-API]] — endpoints usados, cache, rate limit
- [[Tumor-Engine]] — 5-axis scoring, predict, thresholds
- [[Bravery]] — DDragon, style mult, compliance, payout

## Flujo principal end-to-end

1. **User abre la home** → Vue carga, llama `/predictionStats` → backend ejecuta `_resolve_pending_predictions()` (resuelve predicciones pendientes vía Match v5) + `_auto_resolve_orphan_bets()` (sweep de bets matched sin predicción). Pinta accuracy global.
2. **User pone Riot ID** → `/getOverview?game_name=...&tag_line=...` → backend hace Account v1 → Spectator v5 → para cada participante: League entries + Match history + tumor scoring + caching → devuelve `players`, `prediction`, `arena_subteams`. Guarda snapshot live para reutilizar.
3. **User apuesta** → BetModal hace `/bets/preview-multiplier` (devuelve mult + decay + betting_closed) → si OK, `/bets/create` → escrow del stake.
4. **Partida termina** → user abre MyBetsModal o vuelve a la home → trigger auto-resolve → Match v5 → `resolve_bet` paga payout. Notification.

## Persistencia

- **Local dev**: SQLite (`users.db`, `predictions.db`, `riot_cache.db`)
- **Prod (Render)**: Postgres via `psycopg2`. Schema en `users_db._init_pg`. Auto-migración inline via `ALTER TABLE ADD COLUMN IF NOT EXISTS`.
- Las tablas críticas son **bets**, **challenges**, **rooms**+**room_members**, **bravery_locks**, **users**, **predictions** (en predictions.db, separada).

Ver detalle en [[Database]].
