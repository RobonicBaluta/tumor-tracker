---
tags: [decision, bets, payout]
date: 2026-06-10
---

# Payout Decay Curve para House Bets

## Decisión

El multiplier de house bets decae linealmente entre los minutos 5 y 25 de la partida, con floor 0.55 del nominal.

```python
PAYOUT_DECAY_START = 5 * 60   # 300s, antes no hay decay
PAYOUT_DECAY_END   = 25 * 60  # 1500s, full decay
PAYOUT_DECAY_FLOOR = 0.55     # no cae por debajo de 55% nominal
```

Y la ventana de apuestas cierra a `BET_CLOSE_AT_ELAPSED = 25 * 60` (mismo punto que el final del decay).

## Por qué

- **Cuanto más avanza la partida, más fácil predecir el resultado** (oro, dragones, ratio kill, baron, etc.). Una apuesta a minuto 22 con visión total del game state es esencialmente "free money" si la house pagara el mismo multiplier que a minuto 1.
- **5 min de gracia** para que el user que abre la app a mitad de partida no se sienta engañado por un decay invisible.
- **Floor 0.55** evita que el multiplier colapse a casi nada justo antes del cierre — si pierde, sigue siendo una apuesta de verdad.
- **Cierre a 25 min** porque una SoloQ típica dura 28-32 min. Cerrar antes evita el "minuto 27 nexus cayendo" trade.

## Implementación

```python
def _payout_decay_factor(elapsed):
    if elapsed is None or elapsed <= START: return 1.0
    if elapsed >= END: return FLOOR
    frac = (elapsed - START) / (END - START)
    return 1.0 - frac * (1.0 - FLOOR)
```

Aplicado al final de `_compute_house_multiplier` (después de UNDERDOG_BONUS, antes del clamp).

## Edge cases

- `elapsed = None` (sin live snapshot, sin game_start_ts) → factor 1.0 (no decay). Decisión: si no podemos medir, no penalizamos.
- `elapsed > END` → factor FLOOR, pero `_is_betting_closed()` ya devuelve True y `/bets/create` rechaza con 400.
- `REFUND_WINDOW_SECONDS = 60` como red de seguridad: bets resueltas <60s antes de game_end → refund automático en `resolve_bet`.

## Cómo aplicar

- Si el user pide "que decae más rápido" → cambia el slope (e.g., START=3*60, FLOOR=0.40)
- Si pide "no decae hasta el final" → quita el decay del multiplier pero mantén el close window
- **NO tocar el floor sin tocar la lógica de refund**: si floor=0 podría hacer que multipliers muy bajos paguen menos que el stake — confundiría users.

## Tunear sin code change

Las 3 constantes están en `main.py` arriba de `_compute_house_multiplier`. Cambio simple, requiere redeploy.
