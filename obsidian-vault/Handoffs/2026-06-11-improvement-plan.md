---
tags: [handoff, plan, audit]
date: 2026-06-11
source: workflow review multi-lente, 8 reviewers paralelos + adversarial verify
findings_total: 97
findings_verified: 90
---

# Plan de mejoras · 2026-06-11

> Resultado del review multi-lente del codebase entero. 8 reviewers paralelos (UX, mobile, polish, perf-FE, perf-BE, missing-features, abuse, code-debt) → 97 findings crudos → 90 confirmados por mayoría de 3 verificadores skeptic-engineer + product-pm + senior-reviewer.

## Lectura de prioridad

**Cierra leaks económicos ANTES que UX.** El review encontró 2 bugs que están minteando TC silenciosamente + 1 leak de seguridad trivial. Cualquier mejora de retención sobre un sistema sangrando moneda envenena el producto.

---

## 🚨 CRÍTICO (verificado en el código, en curso ahora)

### A. `print(API_KEY)` en stdout
- **Archivo**: [config.py:9](../../zuru-web-backend/src/config.py#L9) — `print(f"API_KEY: {API_KEY}")`
- **Impacto**: Riot API key en logs de Render en cada arranque. Trivial de leakear.
- **Fix**: borrar la línea.
- **Effort**: 5 min.

### B. `_extract_player_stat(tumor_score)` divide gameDuration 2 veces
- **Archivo**: [main.py:3801](../../zuru-web-backend/src/main.py#L3801)
- **Bug**: pasa `duration_min = gameDuration / 60.0` a `compute_match_tumor_from_stats`, que internamente vuelve a hacer `mins = game_duration / 60.0`. Resultado: el engine cree que la partida duró ~0.5s, satura cs/min y dmg/min, tumor score sale brutalmente alto.
- **Efecto en producción**: TODAS las stat-bets `tumor_score` resuelven con valores corruptos. Apuestas `over`/`under` decididas por ruido.
- **Fix**: pasar `gameDuration` raw (segundos) en lugar de `duration_min`.
- **Effort**: 30 min (cambio + revisar callers).

### C. `UNDERDOG_BONUS` sin gate de confidence
- **Archivo**: [main.py:3318](../../zuru-web-backend/src/main.py#L3318) (`UNDERDOG_BONUS = 1.30`), aplicado en [`_compute_house_multiplier`](../../zuru-web-backend/src/main.py#L3387)
- **Bug**: en partidas con `confidence ~5` (early game, comps unknown), el ML está esencialmente diciendo "50/50". Pero apostar "contra el favorito" añade ×1.30. EV positivo silencioso sobre cada partida con baja confianza.
- **Fix**: gatear `if not is_against or confidence >= 25: bonus = 1.0`. Bajar UNDERDOG_BONUS a 1.15.
- **Effort**: 30 min + monitoring de prediction_logs para validar.

---

## Quick wins (≤2h cada uno, alto impacto visible)

| # | Mejora | Archivos | Esfuerzo |
|---|--------|----------|----------|
| 1 | Quitar `print(API_KEY)` | `config.py:9` | 0.1h |
| 2 | Fix `gameDuration` 2× tumor_score stat-bets | `main.py:3801` | 0.5h |
| 3 | Índices a tabla `bets` (idx_match_status, creator, taker, status_created) | `users_db.py:84-98` | 0.5h |
| 4 | Daily reward pill con cantidad + countdown | `Navbar.vue:166-172`, backend `+ next_claim_at` | 1.5h |
| 5 | Daily reward `20h` → `24h` (cierra +600 TC/mes inflación silenciosa) | `users_db.py:645-664` | 0.5h |
| 6 | Responsive crítico: `grid-cols-9` stats + match cards mobile | `Overview.vue:227, 327, 342-486, 1126` | 1.5h |
| 7 | Riot ID inputs: `autocapitalize/spellcheck/autocomplete=off` (iOS rompe lookup hoy) | `Overview.vue:55,60; Compare.vue:18,20; Tinder.vue:17,23; SocialModal.vue:462` | 0.5h |
| 8 | Async-load modales en Navbar (`defineAsyncComponent` + v-if): −15KB gzip bundle inicial | `Navbar.vue:3-5` | 0.75h |

## Medium (2-12h)

| # | Mejora | Esfuerzo | Notas |
|---|--------|----------|-------|
| M1 | Sustituir `window.confirm()` por `<ConfirmDialog>` reusable | 2.5h | 6 sitios afectados |
| M2 | Throttle global `/predictionStats` 30s + reemplazar `predictions_all()` por COUNT/LIMIT | 2.5h | corta ~80% de carga backend |
| M3 | Paralelizar Match v5 fetches en `getOverview` (cold cache 5-15s → 1-3s) | 1.5h | `_compute_live_game` ya tiene el patrón |
| M4 | Cache TTL en league/mastery/account (datos raros que se piden 20×/refresh) | 2h | `riot_infra.py:156-187` |
| M5 | Refund window stat-bets + close earlier (insider trading min 24+) | 1.5h | `users_db.py:824-828, 913+` |
| M6 | Bravery resolve: usar tier real del user (no `UNRANKED` fijo). Añadir columna `tier` a `bravery_locks` | 2.5h | Diamond+ tiene EV+ confirmado vs threshold UNRANKED |
| M7 | UNDERDOG_BONUS gate por confidence (ya en CRÍTICO C) | 2.5h | gating + monitoring |
| M8 | Onboarding: Discord primero, Riot ID después | 1.5h | `Overview.vue:43-71, Navbar.vue:176-180` |
| M9 | CTA "Apostar" prominente en header live game | 2.5h | `Overview.vue:906-915` |
| M10 | Header Overview: labels a los 8 emojis críticos | 2h | `Overview.vue:140-199` |

## Estratégicas (>12h o decisiones de producto)

### S1. Audit anti-sybil completo — **bloqueante antes de monetizar**
**Estado actual**:
- Discord nuevo → 100 TC instantáneo sin captcha
- Welcome RSO da otros 100 TC sin Discord
- Challenges entre alts = transfer zero-rake
- Achievements farmeables

**Plan**:
- Welcome 100 → 25 TC progresivo (claim diario × 7d)
- Discord account age ≥ 7 días
- Rate-limit por IP en `/auth/discord/callback`
- 5% rake en challenges
- Alt-detection por puuid+discord patterns
- Logging persistente de currency_transactions

**Effort**: 12-15h

### S2. i18n completo de Overview + BraveryPanel + Social Rooms
- `Overview.vue` tiene **0 calls a `$t`** (135 strings hardcoded ES)
- BraveryPanel + SocialModal:209-710 también hardcoded
- Cambiar idioma hoy afecta 30% UI
- **Bloqueante para expansión a EUNE/NA**
- **Effort**: 12h

### S3. Partir Overview.vue (3.7k LOC) + main.py (5.2k LOC) en módulos
- Overview ya tiene bloques visualmente delimitados (ScanningOverlay, LoginScreen, MatchListItem, AnalyticsModal, LiveGameModal)
- main.py también está dividido por comentarios `# ---`
- **Effort**: 20-24h. Mecánico, no creativo.

### S4. Mobile audit profundo
- 14 directivas responsive en 3.5k LOC Overview, mayoría ausentes
- App de LoL que se abre en móvil **mientras juegas** → retención crítica
- Bottom-tab bar + responsive en live game modal
- **Effort**: 18h

### S5. Tests del pipeline económico
- 0 tests para `bravery_engine.compute_payout/compliance`, `resolve_bet`, `_payout_decay_factor`
- Este review encontró 2 bugs económicos que tests parametrizados habrían atrapado
- **Antes de iterar más en economía, hay que poder iterar con red**
- **Effort**: 12-16h (test_bravery_engine + test_resolve_bet + test_payout_decay con SQLite in-memory + fixtures)

### S6. Loop social: friends LIVE + achievements progress + PWA push notifs
- Backend tiene 13+ achievements + streak counter + friends, **invisible en UI principal**
- Sin streak counter = Duolingo sin la llama
- Sin "amigos LIVE" no hay razón para tener amigos
- PWA notifs cierran el loop cuando cierras la pestaña
- **Effort**: 14-16h (friends live ~7h + achievements progress ~4h + PWA notifs opt-in ~3h)

---

## Plan de ejecución (lo que estoy haciendo AHORA)

1. **Bloque 1 — Críticos económicos/seguridad** (~1.5h)
   - [A] borrar print(API_KEY)
   - [B] fix gameDuration en tumor_score stat-bets
   - [C] gatear UNDERDOG_BONUS por confidence + bajar a 1.15

2. **Bloque 2 — Infra backend** (~1h)
   - [#3] índices SQL en `bets`
   - [M2] throttle global de `/predictionStats`

3. **Bloque 3 — Bravery fairness + Daily reward retención** (~2h)
   - [M6] tier real en bravery_locks
   - [#4][#5] daily reward pill + 24h

Commit + deploy al final del bloque 3.

## Lo que NO hago en este pase

- Refactor Overview/main.py → demasiado scope, deja para session dedicada
- Mobile audit profundo → necesita decisiones de producto (bottom-tab? PWA?)
- i18n → 12h y no es bloqueante
- Anti-sybil completo → decisión de producto (cuánto bajar el welcome, qué rake)

## Para futuras sesiones

- Si el user pide "haz más mejoras", consulta este archivo primero antes de hacer otro review.
- El review está cacheado en `tasks/w65vnrpdl.output` para replay.
- Re-correr el workflow después de cada release mayor para ver qué quedó.
