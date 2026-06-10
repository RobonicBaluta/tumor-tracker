---
tags: [feature, clusters, archetypes]
---

# Clusters · 9 archetypes

K-means en `player_priors_cache` produce N clusters de jugadores. Cada cluster recibe un archetype basado en thresholds.

## Archetype list (en `main.py:2436`)

| Key | Predicate | Emoji | Color | Descripción |
|-----|-----------|-------|-------|-------------|
| `tumor_cronico`    | `avg_prior > 65` | ☢ | red | Tumor permanente |
| `carry_estable`    | `avg_prior < 35 and win_rate > 55` | 🚀 | green | Carrying consistente |
| `solido`           | `avg_prior < 45 and win_rate > 50` | 🛡 | emerald | Buen jugador equilibrado |
| `victima`          | `avg_prior < 35 and win_rate < 45` | 😢 | sky | Bueno pero pierde |
| `inestable`        | `abs(avg_prior - avg_recent) > 20` | 🌪 | violet | Forma oscilante |
| `streamer_inflado` | streak_frac > 55 | 📸 | pink | Mucho hotstreak |
| `tilt_propenso`    | tilt_frac > 50 | 🔥 | orange | Mucho tilt |
| ... | ... | ... | ... | ... |

(Lista completa en código)

## Bug histórico (fix reciente)

Las predicate comparaban `streak_frac > 0.40` cuando `streak_frac` ya estaba en escala [0..100]. Resultaba que casi ningún archetype matcheaba. Fix: comparar contra valores [0..100] (40, 55, 50, etc.).

## UI · SocialModal tab `clusters`

Cards con:
- 5xl emoji
- Nombre coloreado según archetype.color
- Progress bars (green→yellow→red gradient) para `avg_prior` y `avg_recent`
- Green bar para `win_rate`
- Tilt/streak con glyphs
- Member list con `ROLE_LABEL[s.role] || s.role.slice(0,3)` (UTILITY → SUP, etc.)

## Endpoint

`GET /analytics/clusters` — devuelve array de clusters con `members`, `archetype`, `info` (name/emoji/color/desc/sort_dir).

ML logic: simple K-means con `k=3-5` según sample size. K-means cae back a "todos en 1 cluster" si dataset chico.

## Tunear

`ARCHETYPES` list (orden importa: primer match gana). Para tunear:
1. Ajustar threshold del predicate
2. Cambiar `info` (name, emoji, color, desc, sort_dir)
3. NO mover `tumor_cronico` del top (debe ganar a otros con avg_prior > 65)
