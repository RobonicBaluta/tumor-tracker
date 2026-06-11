---
tags: [handoff]
date: 2026-06-10
commit: ea5b636
---

# Handoff · 2026-06-10 · Bravery + Rooms launched

## TL;DR (estado para que future-Claude pueda arrancar sin re-leer todo)

- Acabo de hacer un push gigante: **bets autoresolve global + payout decay + close window**, **1v1 challenges con friend picker + target_user_id + nuevos formats (single/bo3/tumor_race/streak)**, **clusters redesign con archetypes**, **Bravery feature completa**, **Rooms redesign con bug-fix de leave**.
- Backend deployado en Render: `https://tumor-tracker-api.onrender.com/` — healthz devuelve 200.
- Frontend deployado en Vercel: `https://tumor-tracker-ecru.vercel.app/`.
- 30/30 tests del tumor engine pasan.
- Branch actual: `server-fix`. Main al día.

## Lo que el user pidió y lo que se hizo (en orden)

1. ✅ "no se entiende bien que se elija al que no tiene el peor tumor score" → fix `get_worst_player_in_match` (selección por tumor cuando hay game_duration+tier)
2. ✅ "puedes definir mejor los clusteres y hacerlos más llamativos" + "cambies 'utility' que es eso?" → 9 archetypes nuevos con info dict (emoji/color/desc), UTILITY → SUP en UI, threshold scale bug fix
3. ✅ "mejora la interfaz del 1v1, cambia BO5 y BO10 por cosas más interesantes" → nuevos formats: Tumor Race + Win Streak (recomendado por user); UI completa rediseñada con cards, scoreboard, progress dots
4. ✅ "las apuestas no se auto-resuelven al refrescar" → `_resolve_pending_predictions` ahora también resuelve bets; `_auto_resolve_orphan_bets` para bets sin prediction
5. ✅ "payout decay según tiempo elapsed" → `PAYOUT_DECAY_*` constants, linear decay 5-25 min
6. ✅ "invalidar bets cerca del final" → `BET_CLOSE_AT_ELAPSED=25min`
7. ✅ "stat dropdown sólo en single + friend picker para versus" → `v-if`, dropdown amigos + share_code fallback
8. ✅ "modo Bravery con champ + lane + items + style mult" → bravery_engine.py + 7 endpoints + BraveryPanel.vue + DDragon cache
9. ✅ "apuestas abiertas para que cualquiera se una" → confirmé que ya existe vía share_code; mejoré el feed con formato visible y filtro target_user_id
10. ✅ "Bravery no veo nada" + "sus = 60 donde empiezas a perder" → DDragon pre-warm + UI loading states + payout curve recentrada en sus=60
11. ✅ "rooms funcionan raro" → bug de leave + redesign completo con lista + detalle + delete owner + persistencia localStorage
12. 🟡 "subir el proyecto a GitLab + deploy en server cPanel + vault Obsidian" → vault hecho. GitLab token devuelve 401, esperando confirmación scopes/URL. cPanel: archivos por preparar cuando token funcione.

## Lo único que queda pendiente

- **GitLab + cPanel deploy** — bloqueado en el token (401). Ver [[../Operations/GitLab-cPanel]].
- Probar en prod las features nuevas (rooms, bravery, challenges 1v1).

## Commits clave (últimos)

- `ea5b636` — Bravery mode, 1v1 redesign, bet auto-resolve + decay, rooms redesign
- `4806000` — Clusters redefined with archetypes
- `407f57c` — Worst player by tumor
- `3fd8cdb` — Fix prediction inversion (median-absolute + mean tiebreaker)
- `db2059d` — Duos shared tumor avg
- `cd55a83` — Auto-resolve pending bets on MyBetsModal open

## Para empezar la próxima sesión

1. Leer [[../00-Index]]
2. Si el user pregunta por un sistema concreto, ir directo a la nota correspondiente en `Features/` o `Architecture/`
3. Si hay decisión non-obvia, está en `Decisions/`
4. Para deploy: [[../Operations/Deploy]]
5. Si algo va mal: [[../Operations/Troubleshooting]]
