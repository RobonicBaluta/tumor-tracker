---
tags: [architecture, bravery]
---

# Architecture · Bravery

Archivo: [`bravery_engine.py`](../../zuru-web-backend/src/bravery_engine.py). Endpoints en [`main.py`](../../zuru-web-backend/src/main.py) líneas ~4900-5170. UI: [`BraveryPanel.vue`](../../zuru-web/src/components/BraveryPanel.vue).

## Concepto

ARAM-mode opcional para ranked. Aleatorizas champion (+ lane + items) → lockeas con un stake → juegas tu próxima partida con ese setup → tumor de la partida × style multiplier = payout.

## Data Dragon

Cache 24h en memoria (proceso). Pre-warm en thread daemon al import del módulo. `warm_cache_async()` idempotente.

Champions: `{id (int, key Riot), key (slug "Aatrox"), name}`.

Items filtrados:
- `into = []` (no upgradeables → finales)
- `gold.total >= 2000`
- tags sin `Consumable` ni `Trinket`
- mapa 11 (Summoner's Rift) activo
- sin `requiredAlly` (no items Ornn ally-locked)
- sin `requiredChampion` (no items champ-locked)

## Style multiplier

```python
def style_mult_for_dims(dims):
    n = len(dims & {'champion', 'lane', 'items'})
    if n <= 1: return 1.0   # champion only
    if n == 2: return 1.30
    return 1.70             # champ + lane + items
```

## Compliance post-partida

`compute_compliance(lock, participant)`:

- `champion_match` — OBLIGATORIO. Si False, lock pierde todo el stake.
- `lane_match` — si dim `lane` activa, compara con `teamPosition` Riot
- `items_hit_rate` — si dim `items` activa: `len(items_rolled & items_played) / len(items_rolled)`
- `effective_mult` = style_mult ajustado:
  - `lane_match=False` → `-0.30` (mínimo 1.0)
  - `items_hit_rate` → `*= (0.5 + 0.5 * hit_rate)`

## Payout — SUS = 60 break-even

```python
SUS_TUMOR_THRESHOLD = 60.0

def compute_payout(stake, tumor_score, compliance):
    if not compliance['champion_match']:
        return 0
    if tumor_score is None:
        return 0
    perf = max(0.0, min(1.5, 1.0 + (60.0 - tumor_score) / 40.0))
    return int(round(stake * perf * compliance['effective_mult']))
```

Tabla:

| Tumor | perf  | × style 1.0 | × style 1.3 | × style 1.7 |
|-------|-------|-------------|-------------|-------------|
| 20    | 1.5   | 1.5         | 1.95        | 2.55        |
| 40    | 1.5   | 1.5         | 1.95        | 2.55        |
| **60**| **1.0** | **1.0** (break-even) | 1.30 | 1.70 |
| 80    | 0.5   | 0.5         | 0.65        | 0.85        |
| 100   | 0.0   | 0           | 0           | 0           |

Decisión: ver [[../Decisions/Tumor-Threshold-Sus-60]].

## Flujo

1. **GET /bravery/data** → DDragon cacheado
2. **POST /bravery/roll** → genera roll sin escrow. Body: `{dimensions, lane_filter?, item_count?}`.
3. **POST /bravery/lock** → escrow del stake, status=`pending`. Devuelve lock.
4. User juega su próxima partida.
5. **POST /bravery/resolve-mine** o trigger automático (al abrir panel) → `_resolve_one_bravery`:
   - `_matches_after_lock` (Match v5 ids con startTime > lock.created_at)
   - Match details → participant del user
   - `compute_match_tumor` → tumor_score
   - `compute_compliance` → compliance + effective_mult
   - `compute_payout` → payout
   - `resolve_bravery_lock(id, match_id, tumor, compliance, payout)`
   - Notification al user

## Lifetime

- TTL inicial: 3h para jugar (lock.expires_at)
- Después de 6h sin partida (`BRAVERY_REFUND_AFTER`): refund automático
- User sólo puede tener 1 `pending` a la vez (gate: `user_has_pending_bravery`)

## Frontend (BraveryPanel.vue)

- `roomCode` prop: `null` = solo, `"ABCD12"` = sala (muestra otros locks de la sala)
- Estados:
  1. Not logged in
  2. DDragon loading (con retry a 3s + botón reintentar)
  3. Pending lock (mostrar champ + lane + items + botón comprobar/cancel)
  4. Builder con tabla payout + dimensions toggle + roll button
- Image URLs: `https://ddragon.leagueoflegends.com/cdn/<v>/img/champion/<key>.png` y `/img/item/<id>.png`
