---
tags: [decision, bravery]
---

# Sólo 1 bravery lock pending por user

## Decisión

`/bravery/lock` rechaza con 400 si el user ya tiene un lock `status='pending'`.

```python
if _users.user_has_pending_bravery(user["id"]):
    return jsonify({"error": "Ya tienes un bravery pending. Cancélalo o juega antes de crear otro."}), 400
```

## Por qué

- El resolver toma "la próxima partida tras el lock" como la partida vinculada. Con N locks pending, ¿cuál match resuelve cuál lock? Ambigüedad.
- El user no puede jugar 2 partidas a la vez en cuentas distintas (asumimos 1 cuenta principal vinculada).
- Si quisieras varios locks en paralelo, tendrías que correlacionar de algún modo (champion played? lane?) — código mucho más complejo y modos de fallo nuevos.

## Cómo aplicar

Si el user pide "varios locks a la vez" → propon:
- Sólo 1 ACTIVE; los demás en cola
- O 1 por modo (1 SoloQ + 1 Normal + 1 ARAM)
- O 1 por champ específico

Y discute cómo se resolverían (matching ambiguo).
