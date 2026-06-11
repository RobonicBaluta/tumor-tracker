---
tags: [feature, rooms]
---

# Rooms

## Concepto

Salas de hasta 8 miembros (por `riot_id`, no por user_id) para:
- Compartir un código que invita
- Crear "room bets" (pool donde cada miembro stakea y se reparte)
- Jugar Bravery en grupo

## Endpoints

- `POST /rooms/create` — body `{name?}`
- `GET /rooms/<code>` — público
- `POST /rooms/<code>/join` — body `{riot_id?}`; usa JWT si omitido
- `POST /rooms/<code>/leave` — body `{riot_id?}`; usa JWT si omitido
- `DELETE /rooms/<code>` — sólo owner, borra todo (members + room)
- `GET /rooms/mine` — listado del user (owner o miembro)

## Schema (resumen)

```
rooms: id, code, owner_user_id, name, created_at
room_members: room_id, riot_id, joined_at  -- PK (room_id, riot_id)
```

Notar `room_members.riot_id` es TEXT (no FK a users). Permite invitar a un Riot ID que no está registrado en la app.

## Frontend (SocialModal tab `rooms`)

### Vista lista (cuando `currentRoom == null`)

- Cards arriba: "+ Crear sala" + "→ Unirse" (input código)
- Grid debajo: "🏠 MIS SALAS" con cards click→detalle. Badge `OWNER` si soy dueño.

### Vista detalle (cuando `currentRoom` set)

- Header: `← Salas` + nombre + código + botón Link
- Acciones destructivas en fila:
  - `🚪 Salir de la sala` (no-owner)
  - `⚠ Borrar sala (owner)` (con confirm)
- Grid de miembros (border yellow para `tú`)
- "💰 POOLS · ROOM BETS" — crear (owner) + lista con start/cancel/join
- "🎲 BRAVERY · SALA" — `<BraveryPanel :room-code="currentRoom.code" />`

### Persistencia

- `localStorage['zuruweb-last-room-code']` recuerda última sala vista
- `loadActive()` re-hidrata si sigue en `myRooms` (puede haberme ido entre sesiones)
- Al `onLeaveCurrent` o `onDeleteCurrent` o `onBackToList` se borra del localStorage

## Bug histórico fix

`onLeaveRoom` antes hacía `fetchRoom()` después de `leaveRoom()` → la sala se quedaba en la UI (porque `GET /rooms/<code>` devuelve la sala sin importar membresía).

Ahora:
```ts
async function onLeaveCurrent() {
  if (!confirm(...)) return
  await auth.leaveRoom(currentRoom.value.code)
  localStorage.removeItem(LAST_ROOM_KEY)
  currentRoom.value = null  // ← directo
  await loadMyRooms()
}
```

## Room Bets (pools)

`_resolve_one_room_bet` — al deadline:
- Cada participante tiene su `match_id` (la primera ranked solo posterior al start)
- Winners se reparten el pot de losers
- Si TODOS pierden y ≥ 2 estuvieron en la misma partida (puuids comparten match_id) → el de menor tumor cobra 10% del de mayor tumor
- Pendings al expirar se refundean

## Pendientes / ideas

- Chat in-room
- Invitaciones por user (no sólo riot_id) para que llegue notificación
- Modo "ranking interno" sumando ganancias por miembro
