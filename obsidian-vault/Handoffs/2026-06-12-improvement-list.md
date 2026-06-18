---
tags: [handoff, plan, improvements]
date: 2026-06-12
status: en ejecución
---

# Plan de mejoras · 2026-06-12

> Lista exhaustiva de mejoras posibles tras la última iteración (hash routing, card rework, Fiddlesticks fix, notif race fix). Compuesta a partir de revisión directa del codebase + handoff del 2026-06-11. Cada item: dónde, esfuerzo estimado y por qué duele.
>
> ⭐ = lo que más llama atención por valor / esfuerzo.

## 🔥 Quick wins visibles (≤ 1h cada uno)

| # | Mejora | Por qué duele | Dónde |
|---|--------|---------------|-------|
| ⭐1 | **8× `alert()` nativos** → `useToast` o ConfirmDialog del producto | Rompen el theme cyberpunk; el user ya vio ConfirmDialog en otros sitios | `MyBetsModal.vue:302`, `Overview.vue:3644/3676/3681`, `SocialModal.vue:1062/1108/1122/1160` |
| ⭐2 | **`onepiece.mp3` en `src/assets/`** → mover a `public/` | Está siendo procesado por Vite. Public se sirve estático sin bundle. | `zuru-web/src/assets/onepiece.mp3` |
| 3 | Header en mobile: 8 botones colapsados, ya hay labels en md+ pero no hay menú "más" en sm- | Overflow visual y mala UX en móvil | `Overview.vue:140-200` |
| 4 | Modo dim cuando la app está en background tab → pausar pollers (`/predictionStats` 60s, `/friends/live` 90s) | Quema battery/data | `Overview.vue:3575`, `Navbar.vue:107` |
| 5 | Tooltip-on-tap en mobile (hoy `title=` solo hover) | Iconos siguen sin pista en móvil | Helpers en `useTooltip` o lib |
| 6 | Glow dorado sutil + text-shadow en `exportStatsImage` para profundidad | Card v3 sigue plana | `Overview.vue:exportStatsImage` |
| 7 | `<img @error>` fallback genérico cuando un champion icon 404 (otros aliases nuevos de Riot que no estén en `DDRAGON_CHAMP_ALIASES`) | Hoy se ve cuadradito vacío | Helper `championIconUrl` en `overviewConstants.ts` |

## 🎨 Visual / polish (1-4h)

| # | Mejora | Notas |
|---|--------|-------|
| ⭐8 | Reducir uso de `font-mono` (322 en Overview) — labels y prosa en sans-serif, números en mono | Hace que parezca menos CLI y más producto |
| ⭐9 | Skeleton loaders en match cards durante el scan inicial | Hoy: spinner gigante → datos. Mejor cards grises pulsantes. |
| 10 | Microanimaciones hover: icons scale, tumor scores con count-up de 0 → valor | Detalle "feel good" |
| 11 | Theme auto según role detectado (top → púrpura, jg → verde, etc.) | Persona sin pedir nada |
| 12 | Hover preview de un match (sin clickar): mini-popup con KDA detallado de los 10 | Reduce clicks |
| 13 | Confetti animation cuando prediction acierta + streak ≥3 | Engagement, canvas-confetti |
| 14 | Avatar Discord (no inicial cuadrada) en headers de challenges + room members | Trivial, datos ya están |
| 15 | "Compartir como GIF animado" — card con tumor avg counter 0→valor en 1.5s | Wow factor para share |

## ⚡ Performance

| # | Mejora | Effort | Impacto |
|---|--------|--------|---------|
| ⭐16 | Code-split `Overview.vue` (3.7k LOC, 140KB) en subcomponents lazy: LiveGameModal, AnalyticsModal, NotificationsSidebar, MatchListItem, LoginScreen | 4-6h | Bundle inicial 16KB gzip → ~8-10KB |
| 17 | Cache key del `livePrediction` computed — hoy se recalcula cada render | 30min | Pequeño pero notable con teams grandes |
| 18 | Service worker prefetch de DDragon icons top-50 champions del user en background tras login | 1.5h | Match cards instant |
| 19 | Virtual scrolling en match list cuando >50 matches (`vue-virtual-scroller`) | 1h | FPS en historiales largos |
| 20 | Backend `matches_overview` con ProcessPoolExecutor o asyncio para procesamiento CPU-bound | 1h | Cold `getOverview` ~800ms → ~300ms |
| 21 | Redis para `_LOGIN_RATE`, `_ACTION_RATE`, `_FRIENDS_LIVE_CACHE` (`redis_client.py` ya existe) | 2h | Permite gunicorn -w 2+ sin romper rate-limits |

## 🐛 Bugs latentes

| # | Problema | Fix |
|---|----------|-----|
| ⭐22 | `champ_id_to_name` carga DDragon en el primer call. Si falla, cache queda VACÍA permanentemente hasta restart | Warm-up en `bravery_engine.warm_cache_async` también; mismo cache | `main.py:136` |
| 23 | `/friends/live` cache 60s no se invalida al `accept_friend` → amigo recién aceptado "no in game" hasta 60s | `_FRIENDS_LIVE_CACHE.pop(user_id, None)` en `friends_accept` | `main.py` |
| 24 | `daily.next_claim_at` se calcula al request; tras claim el cliente no re-fetcha hasta reload manual | Forzar `auth.fetchMe()` post-claim | `Navbar.vue:claimDaily` |
| 25 | Si host hace toggle off Bravery con locks pending, quedan huérfanos sin pool de lanes válido | Cancel/refund auto al desactivar | `main.py:rooms_bravery_toggle` |
| 26 | `predictions_aggregate_stats` LIMIT 200 ordenando por COALESCE → full scan al crecer | `CREATE INDEX idx_predictions_resolved_recent ON predictions(viewer_puuid, resolved, resolved_at)` | `main.py predictions table init` |

## 🚀 Features que faltan

| # | Idea | Valor | Effort |
|---|------|-------|--------|
| ⭐27 | **Perfil `/u/<slug>` realmente público**: menos chrome (sin botones Apostar/Card/Excusa) cuando no eres tú | Compartir el link queda más limpio | 1.5h |
| ⭐28 | Compare múltiple (3-5 jugadores) — solo soporta 2 ahora | Stack premade insight | 3h |
| 29 | Ranking semanal local entre amigos (no global) | Loop social | 3h |
| 30 | Notif resumen al final del día: "Hoy 4 partidas, tumor 42 (mejor que ayer)" | Retention email-style | 4h |
| 31 | "Stats con ese champion" al click en un icon: modal con tu WR/KDA/tumor con ese campeón | High value, datos ya están | 2h |
| 32 | Smurf detector con account level + mastery progression checks | Refuerza el USP | 2h |
| 33 | Comparar contra promedio del tier: "KDA 2.4 vs Diamond IV avg 3.1" | Calibra rendimiento objetivamente | 4h |
| 34 | Bravery con rerolls infinitos a coste de TC | Engagement loop | 1.5h |
| 35 | Bet history exportable CSV desde el tab Historial de UserModal | Useful para users serios | 1h |

## 🛠 Tech debt / cleanup

| # | Cosa | Por qué |
|---|------|---------|
| 36 | Refactor `Overview.vue` (3.7k LOC) en componentes | Cada fix nuevo deja código rancio (S3 del plan original, 20-24h) |
| 37 | Refactor `main.py` (5.3k LOC) en Flask blueprints | Mismo motivo |
| 38 | i18n sweep completo (Overview tiene 0 calls `$t`) | Bloqueante NA/EUNE (7h) |
| 39 | Magic numbers frontend (tumor thresholds, DIMENSION_PENALTY, colors) → `econ_config.ts` mirror del backend | Si cambias `SUS_TUMOR_THRESHOLD=60` olvidas el frontend |
| 40 | Type stubs `@types/qrcode-generator` o `.d.ts` propio | Hoy `qrFactory(0, 'M')` es `any` |

## 📱 Mobile específico

| # | Mejora | |
|---|--------|---|
| ⭐41 | **Bottom nav bar mobile** — 8 botones del header → 4 sticky abajo (Buscar, Live, Card, Más) | Plan original S4 |
| 42 | Pull-to-refresh en match list | Pattern natural mobile |
| 43 | Match cards más densas en mobile (menos altura vertical) | Más matches visibles sin scroll |
| 44 | PWA install prompt custom tras 3 visitas (no esperar al browser) | Conversión PWA mayor |
| 45 | BetModal como bottom-sheet drawer en mobile (no inset-0 modal) | Más natural |

## 🎮 Gamification

| # | Idea | |
|---|------|---|
| ⭐46 | Leaderboard de Bravery (más wins, mejor mult sostenido) | Modo nuevo, sin leaderboard no engancha |
| 47 | Achievements con tiers bronze/silver/gold (no binario unlocked/locked) | Más slots de progreso visibles |
| 48 | Streak counter día-en-día tipo Duolingo (no solo predicciones) | Retención flame |
| 49 | Misión semanal: "esta semana gana 3 bets en SoloQ" → reward 100 TC | Loop semanal |
| 50 | Sound effects opcionales (silenciados por default). onepiece.mp3 ya está, faltan: ☢ click, daily chime, prediction correct | Personality |

## ⚠️ Estratégicas pendientes

- Welcome bonus 50 + 50 progresivo ya implementado, falta validar retention a 1 mes
- Rake en challenges (5% house edge) — anti-sybil pendiente decisión user
- i18n PT/FR tras sweep ES/EN
- Monetización opcional (cosmetic themes, custom card frames) — ¿interesa o queremos f2p?
- Discord bot que postee cuando amigo entra a partida

## Mi top-5 priorizado (orden de ejecución)

1. **#1 alerts → toast** — 30 min, pulido inmediato
2. **#22 cache DDragon defensivo** — 30 min, evita roturas silenciosas
3. **#23 friends/live invalidation** — 15 min, UX clarísima
4. **#27 perfil público pulido** — 1.5h, mejora el share del card
5. **#41 bottom-nav mobile** — 3-4h, mayor impacto retention mobile

## Estado de ejecución

- [ ] 🔥 #1 alerts → useToast composable + Toast component
- [ ] 🐛 #22 cache DDragon defensivo (warm-up + reuse)
- [ ] 🐛 #23 invalidar friends/live cache
- [ ] 🚀 #27 perfil público pulido
- [ ] 📱 #41 bottom-nav mobile (siguiente sesión, scope grande)
