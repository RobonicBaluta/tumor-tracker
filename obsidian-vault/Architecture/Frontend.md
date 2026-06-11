---
tags: [architecture, frontend]
---

# Architecture · Frontend

## Stack

- Vue 3 (Composition API + `<script setup>`)
- TypeScript
- Vite 8
- Tailwind 4 (con JIT — ¡cuidado con clases dinámicas, ver [[../Decisions/Tailwind-JIT-Pitfall]]!)
- vue-i18n para ES/EN

## Convenciones

- **Skill key**: usar siempre `<Teleport to="body">` para modales que viven dentro del Navbar (sticky+z-50 atrapa los children). Ver [[../Decisions/Modals-Teleport-To-Body]].
- **Tailwind dinámico**: prefiere `:style="{}"` cuando la clase depende de runtime — JIT no escanea las ramas de ternarios. Ej: `:style="open ? { transform: 'translateX(22px)' } : {}"` en lugar de `:class="open ? 'translate-x-[22px]' : ''"`.
- **NO emoji** salvo que el user los pida explícitamente.
- **Code references** en strings/markdown como `[main.py:3306](../zuru-web-backend/src/main.py)` formato VS Code.

## Components principales

### Overview.vue (~3500 LOC)
La vista principal. Hace `/getOverview`, pinta los 10 players, la predicción, el botón de bet, el botón de stat-bet. Tiene tabs internos: live, history, analytics, role stats.

### SocialModal.vue (~1100 LOC)
Modal con tabs:
- `hot` — feed de apuestas P2P abiertas
- `leaderboards` — currency/bets/accuracy
- `clusters` — archetypes (9: tumor_cronico, carry_estable, inestable, solido, victima, etc.). Ver [[../Features/Clusters]].
- `challenges` — 1v1: crear + feed open + mis challenges. Ver [[../Features/Challenges-1v1]].
- `bravery` — solo player. Usa `<BraveryPanel :room-code="null" />`. Ver [[../Features/Bravery]].
- `friends` — add/accept/reject
- `rooms` — lista de mis salas con vista detalle. Persiste last room en localStorage. Ver [[../Features/Rooms]].

### BetModal.vue
- `mode='create'` o `'accept'`
- Toggle entre `match` bet (blue/red) y `stat` bet (over/under)
- Preview multiplier con flag `betting_closed` y `decay_factor`
- House siempre on para live (no toggle UI)

### MyBetsModal.vue
- Lista bets del user (3 filtros: matched, resolved, all)
- Llama `resolveMyPendingBets` al abrir (idempotente). Patrón clave: ver [[../Features/Bets#Auto-resolve]].

### BraveryPanel.vue
- Reusable: `room-code=null` (single player) o `room-code='ABCD12'` (sala)
- Muestra tabla de payout por tumor (visible para que el user entienda)
- States: not logged → not ddragon → builder roll → lock pending → history
- Retry DDragon a los 3s si primera carga vacía (cold start Render)

### Navbar.vue
- Sticky + z-50 → ¡importante! por eso modales necesitan Teleport
- Login Discord
- Botones: MyBets, Social
- Notifs badge

### Otros
- **UserModal.vue** — perfil + settings
- **Tinder.vue** — UI estilo swipe para predicciones rápidas (legacy/exp)
- **Mental.vue** — tilt score detector
- **Compare.vue** — comparar dos players
- **DiagnosisForm.vue** — input Riot ID

## useAuth.ts (composable)

Es el SDK completo del frontend. Funciones por familia:

- Auth: `loginWithDiscord`, `logout`, `fetchMe`, `refreshBalance`, `linkRiot`, `unlinkRiot`, `handleAuthRedirect`
- Bets: `createBet`, `createStatBet`, `placePlayerBet`, `acceptBet`, `cancelBet`, `fetchBet`, `fetchMyBets`, `resolveMyPendingBets`, `fetchOpenBets`, `previewMultiplier`
- Challenges: `createChallenge`, `acceptChallenge`, `cancelChallenge`, `fetchMyChallenges`, `fetchOpenChallenges`, `submitChallengeMatch`, `pollChallenges`
- Rooms: `createRoom`, `joinRoom`, `leaveRoom`, `fetchRoom`, **`fetchMyRooms`**, **`deleteRoom`**
- Room bets: `createRoomBet`, `joinRoomBet`, `startRoomBet`, `cancelRoomBet`, `fetchRoomBets`
- Friends: `fetchFriends`, `addFriend`, `acceptFriend`, `rejectFriend`
- Notifs: `fetchNotifications`, `markNotificationsRead`
- Clusters/lb: `fetchClusters`, `fetchLeaderboard`, `fetchDeathHeatmap`
- Bravery: `braveryData`, `braveryRoll`, `braveryLock`, `braveryCancel`, `braveryMine`, `braveryRoomLocks`, `braveryResolveMine`

`authedFetch(path)` añade `Authorization: Bearer <jwt>`. Llamadas sin token usan `fetch` directo.

## i18n

`src/i18n/locales/{es,en}.json`. La mayoría de strings nuevos van también con `t('key')` pero algunos textos nuevos van hardcoded en ES (refactor pendiente).

## Build

```bash
cd zuru-web
npm run build     # vue-tsc -b && vite build
npm run dev       # dev server :5173
```

Salida en `dist/`. Vercel build command auto-detecta.
