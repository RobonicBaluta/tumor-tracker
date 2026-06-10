---
tags: [operations, env]
---

# Env Vars

## Backend (Render / local)

| Var | Uso | Notas |
|-----|-----|-------|
| `RIOT_API_KEY` | Riot API | Production key con headers en config.py |
| `DATABASE_URL` | Postgres URL | Si no está set, fallback a SQLite local |
| `JWT_SECRET` | Sign JWTs | Genera random 32+ chars; rota → invalida tokens |
| `DISCORD_CLIENT_ID` | OAuth | Discord Developer Portal |
| `DISCORD_CLIENT_SECRET` | OAuth | NO commitear |
| `DISCORD_REDIRECT_URI` | OAuth | Match EXACTO con Discord Portal |
| `REDIS_URL` | Cache opcional | Si no, fallback a SQLite cache |
| `PORT` | Bind port | Render lo setea automáticamente |
| `FLASK_ENV` | dev/prod | `production` en Render |

Local en `zuru-web-backend/src/.env` (no commiteado) o exporta antes de correr.

## Frontend (Vercel / local)

`zuru-web/.env.production`:
```
VITE_API_BASE=https://tumor-tracker-api.onrender.com
```

`zuru-web/.env.development` (local):
```
VITE_API_BASE=http://localhost:5000
```

## Verificar env vars en Render

Dashboard → service → Environment → ver/editar. Cambios disparan redeploy.

## Verificar env vars en Vercel

Dashboard → project → Settings → Environment Variables. Cambios requieren redeploy manual.
