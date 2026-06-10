---
tags: [operations, troubleshooting]
---

# Troubleshooting

## "Las apuestas no se resuelven al refrescar"

**Diagnóstico**:
1. ¿`/predictionStats` se está llamando? Abre DevTools Network al cargar la home.
2. Si sí pero las bets siguen `matched`: revisa logs del backend, busca exceptions en `_resolve_pending_predictions` o `_auto_resolve_orphan_bets`.
3. Posible causa común: Match v5 devuelve 404 porque la partida acaba de terminar (Riot tarda 1-3 min en publicar).

**Mitigaciones**:
- `_auto_resolve_orphan_bets` usa `min_age_seconds=180` precisamente para no quemar Riot con bets recién creadas.
- Si las bets son DE HACE TIEMPO y siguen pending → bug. Revisa `live_snapshots` y la columna `match_id` para confirmar que Riot devolverá 200 para esa ID.

Ver también [[../Features/Bets]].

## "Bravery no muestra nada"

**Diagnóstico**:
1. Abre DevTools Network → ¿`/bravery/data` devolvió 200?
2. Si 503: DDragon no respondió. En Render el cold start puede tardar. El panel reintenta a los 3s automáticamente.
3. Si 200 pero panel vacío: revisa el response. `version` debería ser un string, `champions` y `items` arrays no vacíos.

**Si nada de lo anterior**: re-trigger `warm_cache_async()` reiniciando Render (manual desde dashboard).

## "Salgo de una sala y sigue ahí"

**Causa histórica** (ya arreglada): `fetchRoom()` después de `leaveRoom()` re-cargaba la sala. Ahora `currentRoom = null` directo.

**Si vuelve a pasar**: verifica que `localStorage['zuruweb-last-room-code']` se borra. Si no, revisa `onLeaveCurrent`.

## "La predicción dice que ganará el equipo con peor tumor"

**Bug histórico** (commit 3fd8cdb). Causa: sum tiebreaker disparándose cuando medianas eran cercanas.

Si vuelve a pasar:
1. Logear `blue_median, red_median, blue_mean, red_mean, predicted_winner` en `predict_team_outcome`
2. Verificar invariante `predicted.team_median <= loser.team_median`
3. Correr `pytest tests/test_tumor_engine.py`

Ver [[../Decisions/Prediction-Tiebreaker-Mean-Of-Valid]].

## Discord login no funciona

1. Verificar `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI` en Render env vars
2. `DISCORD_REDIRECT_URI` debe matchear EXACTAMENTE el redirect URI en Discord Developer Portal
3. CORS: backend acepta `*` por defecto, no debería ser problema

## Riot API key expired

Sin warning. Síntomas:
- Todos los endpoints Riot devuelven 401
- `/getOverview` devuelve "Spectator error 401"

Fix:
1. Genera nueva key en https://developer.riotgames.com/
2. Update env var `RIOT_API_KEY` en Render
3. Restart service

## El backend se queda en cold start eterno (Render free)

Render free tier duerme tras 15 min idle. El primer request despierta el container (10-50s). Síntoma: timeout en `/auth/me` al cargar la app.

Mitigación: pinger cron desde Vercel cada 10 min (`fetch('/healthz/redis')`).
