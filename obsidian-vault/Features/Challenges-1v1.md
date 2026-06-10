---
tags: [feature, challenges, 1v1]
---

# Challenges 1v1

## Formats

```python
CHALLENGE_FORMATS = {
    "single":     1,    # legacy: ambos submitean 1 match manual
    "bo3":        2,    # first to 2 wins
    "tumor_race": 1,    # 1 match c/u, menor tumor gana
    "streak":     2,    # primer en 2 wins seguidas
}
```

UI cards en SocialModal:
- ⚡ Tumor Race · `#22d3ee` cyan · ~40 min
- 🔥 Win Streak · `#f97316` orange · ~1-3h
- ⚔ BO3 · `#a855f7` purple · ~3-6h
- 🎯 Stat Duel (single) · `#facc15` yellow · manual

## Endpoints

- `POST /challenges/create` — body `{stat_type, amount, comparison?, format?, challenged_user_id?}`
- `GET /challenges/open` — feed; **filtra** los dirigidos a otros (privacy)
- `POST /challenges/<code>/accept`, `cancel`
- `POST /challenges/<code>/submit-match` — solo `format=single`
- `GET /challenges/mine`
- `POST /challenges/poll` — disparo del poller

## target_user_id (NEW)

Columna añadida a `challenges` (sqlite + postgres). Cuando set:
- Sólo ese user puede aceptar (`accept_challenge` valida)
- Recibe push_notification al crear
- Feed `/challenges/open` excluye challenges dirigidas a otros, incluye las dirigidas al viewer con badge "📨 PARA TI"

`list_open_challenges(viewer_user_id, limit)` en users_db.py:1315.

## Poller (formats bo3, tumor_race, streak)

`/challenges/poll` y un cron interno (cada N minutos) llaman `_poll_one_challenge(ch)`:

1. `_matches_after_accepted(puuid, accepted_ts)` → match IDs ranked SoloQ+Flex tras accepted_at
2. `_enriched_matches_for_player(puuid, match_ids)` → lista `[(game_creation_ts, match_id, won, tumor_score)]` ordenada asc
3. Format-specific resolution:
   - **bo3**: primer en alcanzar `matches_required=2` wins gana. Tiebreaker en expiry: mayor `wins_total`, sino menor `tumor_total`.
   - **tumor_race**: compara primer match cronológico de cada user; menor tumor gana. Walkover si uno no jugó al expirar.
   - **streak**: primer en alcanzar streak de 2 wins. Tiebreaker en expiry: max streak alcanzado.

## Frontend

[SocialModal.vue](../../zuru-web/src/components/SocialModal.vue) — tab `challenges`:
- Create panel con cards visuales de formato + rival picker (amigos + share_code) + stake
- Hint en el botón:
  - `📨 Directo a tu amigo` si rival seleccionado
  - `🌐 Apuesta abierta — aparecerá en el feed público` si "Cualquiera"
- Lista "Mis challenges" con player vs player scoreboard, dots progress (bo3/streak)
- Feed "Open challenges" con border color del formato + badge "📨 PARA TI"

## Stat dropdown — bug fix histórico

Antes: el dropdown de stat aparecía incluso para bo3/tumor_race/streak (con `disabled`). Confundía. Ahora: `v-if="newChallengeFormat === 'single'"`.

## Gotchas

- `accept_challenge` también valida expires_at: si expiró, auto-cancel + refund al challenger.
- `lower_wins` default si stat_type=`deaths`, sino `higher_wins`.
