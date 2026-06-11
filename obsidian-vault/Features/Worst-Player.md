---
tags: [feature, worst-player]
---

# Worst Player

## Lógica de selección

`get_worst_player_in_match(participants, puuid, game_name, tag_line, game_duration=None, tier=None)`

- Si `game_duration` y `tier` están disponibles → selecciona por **HIGHEST tumor_score**
- Else fallback: selecciona por **MIN KDA** (legacy)

Bug histórico: la UI mostraba `tumor_score` pero la selección era por KDA. A veces seleccionaba a alguien con KDA bajo pero tumor decente, contradictorio. Fix: pasar `game_duration` y `tier` desde el call site (`getOverview` línea ~1112).

## Endpoint

`GET /el-peor?game_name=&tag_line=` → devuelve el "peor" jugador (excluyendo al viewer).
