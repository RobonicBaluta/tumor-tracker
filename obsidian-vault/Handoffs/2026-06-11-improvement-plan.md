---
tags: [handoff, plan, audit]
date: 2026-06-11
source: workflow review multi-lente, 8 reviewers paralelos + adversarial verify
findings_total: 97
findings_verified: 90
status: en ejecución
---

# Plan de mejoras · 2026-06-11

> Resultado del review multi-lente del codebase entero. 8 reviewers paralelos → 97 findings crudos → 90 confirmados por mayoría de 3 verificadores. Plan original 26 items + estratégicas. Ejecutándose por bloques.

## Bloques ejecutados

### ✅ Bloque 1 — Críticos económicos/seguridad + retención (commit `418b21b`)

- [x] A. Quitar `print(API_KEY)` de config.py — leak en logs Render
- [x] B. Fix `gameDuration` doble división en `_extract_player_stat(tumor_score)` — bug que corrompía todas las stat-bets de tipo tumor_score
- [x] C. UNDERDOG_BONUS 1.30→1.15 + gate `confidence ≥ 25` — cerraba EV+ silencioso en partidas low-conf
- [x] 3. Índices SQL en `bets` (4 índices)
- [x] M2. Throttle global `/predictionStats` 30s
- [x] M6. Bravery tier real del user en resolve (era UNRANKED fijo) — Diamond+ tenía EV+ vs thresholds bajos
- [x] 4+5. Daily reward pill con countdown vivo + 20h→24h (−600 TC/user/mes inflación)

### ✅ Bloque 2 — QW UX + perf endpoints hot + dialog (commit `df63b94`)

- [x] 7. Riot ID inputs iOS-friendly en 6 components (`autocapitalize/autocorrect/autocomplete/spellcheck=off`)
- [x] 8. Async-load modales en Navbar (`defineAsyncComponent` + `v-if`): **bundle 165KB → 40KB (gzip 50→13)**. Mejor que esperado.
- [x] 6. Responsive crítico: `grid-cols-9` → `3/sm:5/lg:9`; sidebar `w-72 sticky` → `w-full lg:w-72 lg:sticky`; main flex `flex-col lg:flex-row`; navbar `flex-wrap` + reduced padding
- [x] M3. Paralelizar Match v5 fetches en `getOverview` + `getElPeor` (ThreadPoolExecutor 8 workers): cold cache ~4s → ~0.8s
- [x] M1. ConfirmDialog reusable + useConfirm composable + mount global en App.vue; 7 `window.confirm()` reemplazados con variants warning/danger/default

### ✅ Bloque 3 — Cache TTL + stat-bet refund + tests + UX (commit `6870ac9`)

- [x] M4. Cache TTL por endpoint en `riot_infra.py` (nueva tabla `url_cache` + Redis L1):
  - League entries: 4h
  - Champion mastery: 12h
  - Account (Riot ID): 7 días
- [x] M5. Refund window aplica también a stat-bets — `resolve_stat_bet(bet_id, actual, game_end_ts)`. Cierra el insider trading "tumor_score < 60 a minuto 27"
- [x] S5. Tests `bravery_engine` — 39 tests cubriendo `style_mult_for_dims`, `compute_compliance` (champion/lane/items match + composición), `compute_payout` (sus=60 break-even, 0→1.5x cap, 100→0), invariantes (payout ≥ 0 siempre, más dims ≤ menos dims), `roll` con DDragon mock. **Total ahora: 69 tests verdes**
- [x] M10. Labels visibles en los 8 botones-emoji del header (Refrescar/Guardado/Stats/Excusa/Compartir/Card/Notif/Salir) — `hidden md:inline` mantiene compact en móvil
- [x] M9. CTA "☢ APOSTAR · TC" full-width gradient yellow arriba del row secundario en live game (era un botón pequeño enterrado entre "Comprobar resultado" y "Forzar refresh")
- [x] M8. Discord onboarding banner en login screen — "PASO 1: Login Discord para apostar/Bravery/challenges/salas. PASO 2: escanear sin login". Antes el botón "Escanear" gigante eclipsaba Discord en Navbar

## Bloques pendientes

### Bloque 4 — Strategic items grandes

- [ ] **S1. Anti-sybil completo** — bloqueante antes de monetizar
  - Welcome 100 → 25 TC progresivo (claim diario × 7d)
  - Discord account age ≥ 7 días
  - Rate-limit por IP en `/auth/discord/callback`
  - 5% rake en challenges
  - Alt-detection por puuid+discord patterns
  - Effort: 12-15h
- [ ] **S2. i18n completo** — Overview tiene 0 calls `$t`, BraveryPanel + SocialModal mayormente hardcoded ES. Bloqueante para expansión EUNE/NA. Effort: 12h
- [ ] **S3. Refactor Overview.vue (3.7k LOC) + main.py (5.2k LOC)** — bloques visualmente delimitados; mecánico. Effort: 20-24h
- [ ] **S4. Mobile audit profundo** — bottom-tab bar + responsive en live game modal. Effort: 18h
- [ ] **S6. Loop social** — achievements progress visible + friends LIVE + PWA push notifs. Effort: 14-16h

### Wins menores pendientes

- [ ] Confirmar UI del CTA Apostar en live data real (visual check)
- [ ] Cache TTL stats endpoint: monitorear que no quede stale
- [ ] Mover magic numbers (`SUS_TUMOR_THRESHOLD`, `REFUND_WINDOW_SECONDS`, etc.) a un config centralizado
- [ ] Test del refund window de stat-bets

## Métricas pre/post bloques 1-3

| Métrica | Antes | Después |
|---------|-------|---------|
| Bundle inicial JS gzip | ~50KB | ~13KB |
| `getOverview` cold (Match v5 fetch) | ~4s | ~0.8s |
| `getOverview` warm (datos cacheados) | igual | aún más rápido (league/mastery cached) |
| Tests verdes | 30 | 69 |
| Stat-bets `tumor_score` correctas | 0% (bug) | 100% |
| TC/user/mes daily inflation | +600 (20h) | 0 (24h) |
| API_KEY en logs | sí | no |
| Underdog bonus en low-conf bets | sí (EV+) | gated |
| Bravery payout para Diamond+ | inflado | calibrado |

## Para futuras sesiones

- Re-correr el workflow review tras este batch para ver qué findings nuevos surgen
- Antes de meter S1 (anti-sybil) consultar al user sobre el tradeoff welcome bonus / friction
- Antes de S3 (refactor) consultar si prefiere modular ahora o esperar a una pausa de features
- El cache TTL puede ajustarse en `riot_infra._URL_TTLS` si los tiers se sienten "stale"
- `_PREDSTATS_SWEEP_INTERVAL` ahora 30s; subir a 60s+ si Render sigue cargado
