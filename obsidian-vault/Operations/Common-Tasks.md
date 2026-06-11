---
tags: [operations, tasks]
---

# Common Tasks

## Correr local

### Backend
```bash
cd zuru-web-backend
pip install -r requirements.txt   # primera vez
python src/main.py                # dev :5000
# o producción-like:
gunicorn -w 2 -b 0.0.0.0:5000 main:app --chdir src/
```

### Frontend
```bash
cd zuru-web
npm install                       # primera vez
npm run dev                       # :5173
```

### Inicio combinado
```bash
python start-zuru.py              # script del owner; arranca backend + frontend
```

## Tests

```bash
cd zuru-web-backend
python -m pytest tests/test_tumor_engine.py -q
# DEBE pasar 30/30 antes de deploy
```

```bash
cd zuru-web
npx vue-tsc --noEmit              # typecheck
npm run build                     # build + type check completo
```

## Verificar import del backend (sin instalar deps)

```bash
python -m py_compile src/main.py src/users_db.py src/bravery_engine.py
```

## Stats de Riot cache

`GET /healthz/cache` (si existe) o desde `riot_infra.cache_stats()`.

## Reset local DB (para test)

```bash
rm zuru-web-backend/src/users.db zuru-web-backend/src/predictions.db
# auto se recrean al primer request al backend
```

## Crear nueva migración (= añadir columna)

1. Editar `_init_sqlite` y `_init_pg` en `users_db.py` añadiendo el ALTER condicional
2. Editar `_<TABLE>_COLS` para incluir la columna nueva
3. Editar `_row_to_<table>` para mapearla
4. (Si aplica) editar el endpoint que devuelve los rows para incluir la columna en JSON

## Ver predicciones históricas

```bash
sqlite3 zuru-web-backend/src/predictions.db
> SELECT match_id, blue_score, red_score, predicted_winner, actual_winner, correct FROM predictions WHERE resolved=1 ORDER BY created_at DESC LIMIT 20;
```

Útil para spot-checking del tumor engine.

## Limpiar bravery locks viejos (prod)

```sql
DELETE FROM bravery_locks WHERE status='pending' AND created_at < EXTRACT(EPOCH FROM NOW() - INTERVAL '1 day');
```

(O `time.time() - 86400` en SQLite local)

## Forzar resolución de un match concreto

```bash
curl -X POST https://tumor-tracker-api.onrender.com/resolvePrediction \
  -H "Content-Type: application/json" \
  -d '{"match_id": "EUW1_1234567890", "viewer_puuid": "<puuid>"}'
```
