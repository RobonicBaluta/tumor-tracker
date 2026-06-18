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

## Siguiente sesión — pendientes

Tras la batch 13 quedan ~19 items (de 50). Por valor/effort:

- **#34 Bravery rerolls con coste TC** (1.5h, engagement)
- **#50 Sound effects** (2h, personality polish)
- **#28 Compare múltiple 3-5 jugadores** (3h)
- **#32 Smurf detector con mastery progression** (2h)
- **#33 Comparar vs promedio del tier** (4h)
- **#29 Ranking semanal entre amigos** (3h)
- **#30 Notif resumen diario** (4h)
- **#46 Bravery leaderboard** (4h)
- **#47 Achievements tiers bronze/silver/gold** (3h)
- **#48 Weekly mission con reward 100 TC** (4h)
- Skip / deferred: #20 ProcessPool (validar plan Render primero),
  #21 Redis migration (10-15h, sesión dedicada), #36/#37/#38 mega-refactors,
  #3 ya cubierto por #41, #8/#12/#19 bajo valor

## Mi top-5 priorizado (orden de ejecución)

1. **#1 alerts → toast** — 30 min, pulido inmediato
2. **#22 cache DDragon defensivo** — 30 min, evita roturas silenciosas
3. **#23 friends/live invalidation** — 15 min, UX clarísima
4. **#27 perfil público pulido** — 1.5h, mejora el share del card
5. **#41 bottom-nav mobile** — 3-4h, mayor impacto retention mobile

## Estado de ejecución

### Sesión 2026-06-18 — bloque cerrado

- [x] 🔥 #1 alerts → useToast composable + Toast component
- [x] 🐛 #22 cache DDragon defensivo (warm-up + reuse)
- [x] 🐛 #23 invalidar friends/live cache
- [x] 🚀 #27 perfil público pulido
- [x] 🔥 #2 onepiece.mp3 → public/ (no era importado, mover puro y limpio)
- [x] 🔥 #4 pause pollers cuando tab hidden — composable `useVisibilityPoller` + 5 sites
- [x] 🔥 #6 glow dorado + text-shadow en card export (4 capas: summoner / hero / podio / QR halo)
- [x] 🔥 #7 `<img @error>` fallback en champion icons — 14 sites en Overview + 2 Compare + 1 Tinder + 4 BraveryPanel; helper `championIconFallback` con SVG data URL "?"
- [x] 🐛 #24 daily next_claim_at re-fetch tras claim (await fetchMe, race fixed)
- [x] 🐛 #26 INDEX sobre `predictions(viewer_puuid, resolved, predicted_winner, created_at DESC)`
- [x] 🚀 #35 export CSV de bet history desde MyBetsModal (filtro respetado, BOM + RFC 4180)
- [x] 🛠 #40 type stub para qrcode-generator (`src/types/qrcode-generator.d.ts`)

### Sesión 2026-06-18 (continuación) — fase mobile UX

- [x] 📱 #41 bottom-nav mobile (`BottomNav.vue`: Live/Stats/Card/Más + drawer)
- [x] 📱 #45 bottom-sheet UserModal en <sm (rounded-t-2xl, items-end, drag handle)
- [x] Header action strip oculta en mobile (`hidden sm:flex`)
- [x] Badge "👀 PERFIL PÚBLICO" fallback mobile bajo el título
- [x] Spacer `calc(6rem + env(safe-area-inset-bottom))` para iOS home indicator
- [x] Export error toast respeta safe-area-inset-bottom

### Sesión 2026-06-18 (continuación 3) — fase visual polish

- [x] 🎨 #14 Discord avatars — `Avatar.vue` (xs..xl, circle|square) + 5 sites swap (Navbar user menu, Friends LIVE, SocialModal Leaderboards/Friends/Room members) + backend LEFT JOIN en `get_room_members`. Room members ahora muestran avatar + username en vez de "👤" + riot_id raw.
- [x] 🎨 #9 Skeleton loaders — `SkeletonCard.vue` con variants match-detail (2 equipos × 5 filas) y match-row. Wired al loadingDetail del match modal.
- [x] 📱 #43 match cards densidad mobile — px/py/gap responsivos (sm:px-4 vs px-3), arrow divider oculta en `<sm`, space-y-2.5 entre cards (vs 4 desktop). Reducción ~120px scroll en feed típico de 20 partidas.

### Sesión 2026-06-18 (continuación 4) — fase fun + polish

- [x] 🎨 #13 confetti en prediction streak ≥3 — `canvas-confetti` lazy-import,
  helper `fireStreakConfetti` (130 particles + segunda salva 60p), throttle
  por matchId. Fix bug latente en `fetchPredictionStats` que devolvía streak
  global porque `(summoner.value as any).puuid` siempre era undefined.
- [x] 🎨 #10 microanimaciones — `useCountUp` composable + `TumorScoreCounter.vue`
  wrapper (rAF, ease-out cubic, ~700ms). Wired en live game team scores +
  match worst score. Hover scale `hover:scale-110` en live game champion
  icons + `group-hover:scale-105` en match card icon.
- [x] 📱 #42 pull-to-refresh — `usePullToRefresh` composable (touch-only,
  threshold 70px, resistencia 0.55, snap-back). Indicator con rotation
  proporcional al progress + spinner refrescando. Wire en Overview root.
- [x] 🐛 #25 bravery refund en toggle off — `refund_room_bravery_locks` con
  optimistic locking (UPDATE ... WHERE status='pending' + rowcount check)
  para evitar double-credit en race concurrente. Notif push a cada user
  afectado. 6 tests cubriendo happy path, idempotencia, concurrencia,
  multi-lock-per-user, cross-room aislamiento.

### Sesión 2026-06-18 (continuación 13) — batch #39 + #5 + #44 + #48

Cuatro items independientes en un mismo deploy. Cada uno con su recon, fix,
y la batch entera pasada por verify adversarial de 3 reviewers.

- [x] 🛠 **#39 Magic numbers → `econConfig.ts`**. Mirror del lado frontend de
  `econ_config.py` con SUS_TUMOR_THRESHOLD, BET_CLOSE_AT_ELAPSED_MIN,
  DAILY_REWARD_AMOUNT, DAILY_REWARD_INTERVAL_HOURS, WELCOME_BONUS_AMOUNT,
  LOYALTY_BONUS_AMOUNT, LOYALTY_BONUS_AT_CLAIMS, HOUSE_MULT_MAX. Swap 3
  call sites: BetModal.vue (25min), Navbar.vue fallback (100 TC), Overview.vue
  explainer ("tumor > 60"). Header del archivo es honesto: **NO** hay CI
  check todavía — disciplina manual hasta script de validación.

- [x] 🔥 **#5 v-tooltip directive (tap on mobile, hover on desktop)**.
  `src/directives/tooltip.ts` — directive global con singleton popup,
  auto-dismiss 2.5s, hide on tap-outside / scroll capture (cualquier
  scrollable ancestor, no solo window). Reactivo via WeakMap `metaMap` que
  guarda el último texto en mounted+updated (sin esto, el handler de
  touchstart leía el value stale del closure inicial — bug HIGH cazado por
  review). Cleanup en `unmounted`: remove listener + hideTooltip si era el
  anchor activo. Registrado en main.ts. Swap de 4 `title=` en Navbar.

- [x] 📱 **#44 PWA install prompt (custom, post-3-visitas)**.
  `usePwaInstall.ts` composable: captura `beforeinstallprompt` a **nivel
  módulo** (no en onMounted — bug HIGH: Chrome dispara el evento durante
  parse y se pierde si esperas a mount). Cuenta visitas en localStorage
  por día (key `pwa.visitDays.v1`); fallback in-memory para private mode
  donde LS tira SecurityError (sin esto, Safari private NUNCA vería el
  banner). VISIT_THRESHOLD=3 días distintos. Dismiss tiene cooldown 14d.
  iOS Safari: branch separado con instrucciones manuales (Compartir →
  Añadir a pantalla de inicio). `PwaInstallBanner.vue` montado en App.vue,
  bottom: `calc(env(safe-area-inset-bottom) + 6.5rem)` para no chocar con
  BottomNav.

- [x] 🎮 **#48 Daily-streak flame Duolingo-style**.
  Backend (`users_db.daily_streak(user_id, tz_offset_minutes)`): walk-back
  desde el día más reciente con bucketing en LOCAL del user (no UTC; sin
  esto un español que reclama a las 23:50 lunes + 00:30 martes ve la racha
  estancarse porque ambos timestamps caen en el mismo UTC-day). Aritmética
  con `timezone.utc` aware (deprecación de `utcfromtimestamp/utcnow` en
  Python 3.13+). LIMIT 90 + nuevo índice `idx_currency_tx_user_reason` en
  ambos schemas (SQLite + PG) — sin esto, full scan por cada /auth/me.
  `daily_status()` incluye `streak` + `streak_at_risk`. Endpoints
  `/auth/me`, `/currency/balance`, `/currency/daily` leen header
  `X-TZ-Offset` (minutos al este de UTC).
  Frontend: `useAuth` envía `X-TZ-Offset` (= `-getTimezoneOffset()`). Tipo
  User extendido con `daily.streak` / `streak_at_risk`. Navbar muestra
  badge 🔥+count cuando `streak ≥ 2 || streak_at_risk` — incluye el caso
  streak=1 a-punto-de-romperse (review MEDIUM: el at_risk con streak=1
  era INVISIBLE, justo al user que más necesitaba el recordatorio). Pulse
  + color naranja cuando at_risk. Tooltip via v-tooltip muestra "racha N"
  solo si N≥1 (en lugar de "racha 0" feo).

**Verify adversarial 3 reviewers (frontend, backend, integration/UX/sec)**
cazó 4 HIGH + 4 MEDIUM. Todos resueltos antes del commit:
- HIGH v-tooltip stale closure → WeakMap metaMap updated en mounted+updated.
- HIGH beforeinstallprompt race → listener a nivel módulo.
- HIGH falsa documentación econConfig (decía que había CI test, no existe)
  → header reescrito honesto.
- HIGH Python 3.13+ deprecation utcfromtimestamp/utcnow → timezone.utc
  aware.
- HIGH streak query unbounded + sin índice → LIMIT 90 + nuevo índice.
- MEDIUM private mode LS fail → fallback in-memory.
- MEDIUM streak >=2 escondía at_risk en streak=1 → v-if incluye at_risk.
- MEDIUM streak en UTC en lugar de local user → header X-TZ-Offset
  end-to-end.

LOW deferred: tooltip orphan al dismiss banner (cubierto por hideTooltip
en unmounted), recordVisit guard si standalone, todayKey usa LOCAL date
mientras streak usa offset header (acuerdo cross-convention).

### Sesión 2026-06-18 (continuación 12) — #16 code-split AnalyticsModal

- [x] ⚡ #16 (cont) Extraído `AnalyticsModal.vue` de Overview.vue (lines 985-1401,
  ~417 LOC). Mismo patrón template-only que `LiveGameModal`: state,
  refs, watchers, fetch handlers (loadAnalytics, runBacktest,
  loadDeathHeatmap, drawHeatmap, backtestPoller, resize listener) se
  quedan en Overview. Modal recibe ~20 props + emite 6 events.
- Chunk lazy `AnalyticsModal-*.js`: 24.18 KB raw / **6.73 KB gz** + 0.24 KB
  gz CSS. Initial bundle baja en torno a ese tamaño. Overview.vue cae a
  ~3935 líneas (de 4350).
- Bridge canvas: el `<canvas ref="heatmapCanvas">` del heatmap vive en
  el modal, pero `drawHeatmap()` corre en el padre (porque la lógica de
  fetch+pintado vive ahí). Solución: el modal hace
  `defineExpose({ heatmapCanvas })`, el padre lo lee como
  `analyticsModalRef.value?.heatmapCanvas` (Vue 3 auto-desempaqueta refs
  expuestos via defineExpose, así que el padre obtiene el
  `HTMLCanvasElement` directamente). Contrato documentado en ambos lados
  para evitar refactors futuros que lo rompan.
- v-model:filters: el padre tiene `analyticsFilters` ref, el modal lo
  recibe como prop, y cada `<select @change>` emite `update:filters` con
  un nuevo objeto inmutable. Cascada de emits sincrónica:
  `update:filters` → reasigna `analyticsFilters.value` → `load-analytics`
  → corre `loadAnalytics()` con los nuevos params.
- Adversarial verify (3 reviewers paralelos: boundary, canvas bridge,
  visual regression) cazó **1 HIGH** y varios LOW:
  - **HIGH (regresión visual)**: `<Transition name="modal">` no animaba
    en la PRIMERA apertura porque el wrapper se monta dentro del chunk
    lazy con `show=true` ya activo → Vue lo trata como render inicial,
    sin enter animation. Fix: añadido `appear` al `<Transition>` tanto
    en AnalyticsModal como en LiveGameModal (mismo bug latente que
    salió por el mismo patrón). Ahora la primera apertura fade-in
    correctamente.
  - **LOW (pre-existente, ahora resuelto)**: `closeAnalytics()` no
    limpiaba `heatmapData`. En segunda apertura, el canvas se montaba
    pero `drawHeatmap` no corría hasta la siguiente resize → canvas en
    blanco con header visible. Fix: `heatmapData.value = null` en
    `closeAnalytics()`.
  - **LOW (cleanup)**: el `setTimeout(50ms)` antes de `drawHeatmap`
    (heurística pre-extracción) se reemplaza por `await nextTick();
    await nextTick();` — cubre el ciclo padre + child sin recurrir a un
    wall-clock arbitrario.

### Sesión 2026-06-18 (continuación 11) — #15 GIF share

- [x] 🎨 #15 Share como GIF animado. Tumor counter 0 → finalTumor en
  ~1.2s con ease-out cubic, 36 frames @ 30fps, último frame se queda
  1.5s con label "☢ NUCLEAR/TUMOR/etc". Encoder gif.js con web worker
  (lazy chunked + worker URL via Vite ?url plugin — chunks ~21KB+17KB
  fuera del initial bundle). Cards 720×720 (vs PNG 1080) — messaging
  apps recomprimen igual, encoding 2-3s en lugar de 5-6s.
- Theme-aware: cada GIF usa el gradient + accent del theme actual. Hero
  number con drop shadow del color tumor + glow. Footer brand.
- UX: dropdown PNG/GIF en el botón Card (split button: click directo en
  el icono dispara PNG, ▾ abre menu). Durante encoding el botón muestra
  % de progreso en lugar del icono.
- Web Share API si disponible → fallback a anchor.download. Mismo patrón
  que la PNG existente.
- Verify 2 fixes: shadow state reset completo + ref al wrapper (en lugar
  de closest('.relative') que mataba el cierre del dropdown si el user
  clickeaba en cualquier `.relative` ancestor — champion icons, portrait
  cards, etc).

### Sesión 2026-06-18 (continuación 10) — #16 code-split LiveGameModal

- [x] ⚡ #16 (parcial) Extraído `LiveGameModal.vue` de Overview.vue. Lazy-loaded
  vía `defineAsyncComponent(() => import('./LiveGameModal.vue'))`. Estrategia:
  TEMPLATE ONLY — todo el state, refs, watchers, async handlers (closeLiveGame,
  resolveLivePrediction, searchLiveGame, checkExistingPlayerBet watcher) viven
  en Overview. El componente nuevo es 100% rendering: recibe props (~22) y
  emite events (close, openCreateBet, openPlayerBet, toggleBlacklist,
  resolveLivePrediction, retryRefresh). Riesgo bajo, sin async race ni
  stale refs.
- Bonus: refactor del bloque blue/red team duplicado en 1 `v-for` sobre
  SIDES const (~90 LOC menos).
- Bonus: el `border/bg-[#c89b3c]` del is_me highlight pasa a `border-accent-50
  bg-accent-10` → ahora respeta theme también dentro del modal.
- Bundle stats: Overview **169KB → 146KB / 46KB → 41KB gz** (–5KB inicial),
  LiveGameModal chunk separado **19KB / 6KB gz** que solo se baja cuando el
  user abre "En directo".
- Verify: 1 fix real aplicado (SIDES const extraída del template inline para
  estabilizar v-for keys). Falsa alarma sobre kebab/camel event names —
  Vue 3 los normaliza automáticamente.

### Sesión 2026-06-18 (continuación 9) — perf items 16-24

Status del bloque que el user pidió:

- [x] #17 `livePrediction` memoize por scalar key — el computed devolvía un
  objeto NUEVO cada poll (~600ms) aunque blue/red/winner/confidence fueran
  iguales → 8 bindings re-pintando ~100x/min. Ahora cache de identidad: si
  los 4 scalars coinciden con el previous, devuelve la MISMA referencia y
  Vue skipea el re-render. Per recon: ~99% reducción de reactividad
  innecesaria mientras el live game está abierto.
- [x] #18 prefetch de champion icons — al cargar `/playerAnalytics` se
  inyecta `<link rel="prefetch" as="image">` para los icons del
  champion_pool (top 20). Browser los baja en idle time y entran al HTTP
  cache. Idempotente vía `_prefetchedIcons` Set. SW ya existe pero no
  necesitamos tocarlo — el browser respeta el prefetch hint solo.
- [~] #19 virtual scrolling — **SKIP** per recon. Match list rara vez >50
  (pagination con "Load more" como checkpoint natural). vue-virtual-scroller
  +10KB con complejidad alta de refactor por las branches ranked/non-ranked.
  Re-visitar solo si telemetría muestra users con 200+ matches.
- [x] #22 cache DDragon defensivo — done en cb9cd9f.
- [x] #23 friends/live cache invalidation — done en cb9cd9f.
- [x] #24 daily next_claim_at refetch — done en cb9cd9f + verificado en
  continuación 6.

Deferred a sesiones dedicadas:
- #16 code-split Overview.vue — recon recomienda LiveGameModal primero
  (383 LOC, lowest coupling). Effort real ~2-3h por solo ese, +1h
  validación. Necesita branch + UX testing post-extract. Mejor en sesión
  exclusiva.
- #20 backend ProcessPoolExecutor — riesgo en Render free-tier (1 vCPU
  hace ProcessPool inútil o peor por overhead pickling) + match_res
  response objects no son trivialmente picklable. Necesita validar plan
  Render real antes de invertir.
- #21 Redis migration — recon revisó el effort de 2h → 10-15h reales
  (3 caches × wiring + tests + multi-worker). High value pero requiere
  sesión dedicada por scope.

### Sesión 2026-06-18 (continuación 8) — themes deep + champ picker + history DB

- [x] 🎨 Themes propagation Phase 1 — `--theme-accent` ahora se respeta en
  modal borders (5 modales), tab selections (3 modales), focus rings (4
  componentes). Nuevas utility classes en `style.css`: `text-accent`,
  `bg-accent-{10,15,20}`, `border-accent-{20..60}`, `hover:*`, `focus:*`.
  Pendiente Phase 2: decorative dividers, drawer accents, hardcoded gold
  en UserModal/SocialModal.
- [x] 🎨 ChampionPicker.vue — custom dropdown que reemplaza al `<select>`
  nativo. Muestra icono del champion + nombre + search + click-outside
  + Escape. Wired al filtro principal de Overview. v2: aplicar al
  analytics filter + BetModal player picker.
- [x] 🚀 viewer_match_history DB — tabla persistente per-viewer-per-match
  con PK (match_id, viewer_puuid) + 2 indexes. Helper
  `viewer_match_history_add` con INSERT OR IGNORE + skip si gameCreation=0
  (anti-epoch-1970). Wired en /getOverview en ambos paths (ranked + non-
  ranked). Nuevo endpoint `/championHistory` con agregaciones lifetime
  (total_games, wins, winrate, avg_kda, avg_tumor, avg_cs/damage/vision)
  + recent_matches ORDER BY game_date DESC. 5 tests pasan.
- [x] 🚀 ChampionStatsModal lifetime panel — fetch `/championHistory` al
  abrir + grid 4 stats. Race protection con request id contador
  (rápido switching A→B→A no muestra data stale). Error UI suprimido
  durante reload.
- [x] /getOverview ahora devuelve `viewer_puuid` para que el frontend
  pueda llamar a /championHistory sin re-resolver con Riot.

### Sesión 2026-06-18 (continuación 7) — champion stats modal

- [x] 🚀 #31 Champion stats modal — `ChampionStatsModal.vue` mostrando
  partidas/WR/KDA medio/tumor avg para el campeón seleccionado +
  strip horizontal con las últimas 10 partidas con ese champion. Data
  100% client-side (champion_pool del analytics endpoint + filter de
  matches por my_champion). Sin nuevo endpoint backend en v1.
- [x] Wire en 4 sitios de la sección Analytics: champion_pool grid,
  best_teammates icons, worst_nemesis icons, duos icons. Match card
  icons deferred a v2 (conflicto con openMatchDetail).
- [x] Bottom-sheet en mobile (items-end + rounded-t-2xl + safe-area).
  Splash blureado en el header como pattern visual. Cierre por ✕,
  click fuera, Escape.

### Sesión 2026-06-18 (continuación 6) — themes revamp + #24 verified

- [x] 🎨 #11 Themes revamp completo — fuera los 6 themes basados en rol
  (Naval/Jungla/Support/Mid/ADC/Top), entran 8 themes especiales:
  Demacia Royal 🏰 · Void Sovereign 🔮 · K/DA Neon 💫 · Worlds Gold 🏆 ·
  Inferno Ascent 🔥 · Pentakill Metal 🎸 · Star Guardian ✨ · Shadow
  Assassin ⚔️. Cada theme: {from, to, accent, label}. Default `royal`.
  Accent expuesto como CSS var `--theme-accent` en el root de App + Overview.
  Migration on-boot limpia localStorage de keys legacy O desconocidas
  (cubre legacy/jungla/etc. y values inyectados). Theme picker en Navbar
  con swatch preview (mini gradient + accent dot) + max-h-[70vh] +
  overflow para forward-compat con más themes.
- [x] 🐛 #24 daily next_claim_at re-fetch verificado: el fix cb9cd9f sigue
  funcionando — claimDaily await fetchMe(), Navbar.dailyCountdown lee
  user.daily.next_claim_at, backend daily_status computa next_claim_at
  fresh en cada request. Único gap menor: si fetchMe falla con error de
  red, el countdown queda stale hasta próximo /me — acceptable.

### Sesión 2026-06-18 (continuación 5) — clusters + bravery

- [x] 🧬 Clusters: archetype overlap fix — orden por tamaño DESC + tracking de
  keys usadas. Dos clusters ya no acaban con el mismo arquetipo (excepto
  "Promedio" catch-all que es legítimo repetir).
- [x] 🧬 Clusters UX: k selector (2/4/6/8), botón help con explicación
  embedded, click en card expande samples con W/L + recent_avg + indicadores
  inline 🌋/🔥 cuando is_tilted/is_hotstreak.
- [x] 🎲 Bravery items: fix filtro `maps["11"]` con default `False` — Arena-only
  items (map "30") que colaban antes ahora excluidos. Items con maps vacío
  también excluidos (defensive).
- [x] 🎲 Bravery solo random lane: pickeo frontend de TOP/JG/MID/ADC/SUP al
  hacer roll + botón 🎲 cambiar para re-rollearla. Rooms intactas (server
  sigue asignando al lockear desde el pool de 5).

### Siguiente sesión (limpieza 2026-06-18)

Estos items ya están hechos (los listo arriba en sus continuaciones):
- ~~#11 themes revamp~~ → DONE en cont. 6 (8 themes) + cont. 9-10 (theme.from
  propagation, radial bg overlay, color-mix utility classes, depth visual).
- ~~#24 daily next_claim_at re-fetch~~ → DONE en cb9cd9f + verificado en
  cont. 6.
- ~~#31 stats con champion modal~~ → DONE en cont. 7 (ChampionStatsModal +
  4 sites + #14 history DB en cont. 8).
- #16 code-split → PARCIAL en cont. 10 (LiveGameModal extraído). Próximo
  candidato: AnalyticsModal (419 LOC, mayor scope que LiveGameModal por
  tener internal state, filters y backtest runner).

Pendientes reales:
- [ ] 🎨 #15 "Compartir como GIF animado" — card con tumor counter 0→valor
- [ ] ⚡ #16 (cont.) AnalyticsModal extract (419 LOC, próximo en bundle ROI)
- [ ] 🚀 #28 Compare múltiple (3-5 jugadores, hoy solo 2)
- [ ] ⚡ #20 backend ProcessPoolExecutor (validar primero plan Render)
- [ ] ⚡ #21 Redis migration (10-15h reales)
