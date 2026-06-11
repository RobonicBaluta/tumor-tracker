---
tags: [operations, deploy]
---

# Deploy

## Remotes

```
origin    git@github.com:jonzuru/zuruweb.git
personal  https://github.com/RobonicBaluta/tumor-tracker.git
```

**Vercel y Render escuchan a `personal/main`**, no a origin. Si pusheas sólo a origin no deploya.

## Script `deploy.sh`

Workflow estándar:
1. Estoy en `server-fix` (o feature branch)
2. Confirmo cambios commiteados
3. `./deploy.sh` → checkout main, pull, merge --no-ff <feature>, push origin + personal
4. Trap restore_branch → vuelve al branch original aunque algo falle

Si hay cambios sin commitear NO del feature (e.g. `recent_summoners.json` que se modifica al usar la app local), el script aborta. Stash:
```bash
git stash push -u -- zuru-web-backend/src/recent_summoners.json start-zuru.py
./deploy.sh
git stash pop
```

`deploy.sh` excluye automáticamente `.claude/` y `.claude/settings.local.json`.

## Servicios

- **Vercel** (frontend): https://tumor-tracker-ecru.vercel.app/
  - Build command: `cd zuru-web && npm run build`
  - Output dir: `zuru-web/dist`
  - Auto-detect Vite
  - ~30-60s para deploy
- **Render** (backend): https://tumor-tracker-api.onrender.com/
  - Python 3.11
  - Build: `pip install -r zuru-web-backend/requirements.txt`
  - Start: `cd zuru-web-backend/src && gunicorn -w 2 -b 0.0.0.0:$PORT main:app`
  - Free tier: cold start ~30-50s; deploy ~2-4 min
  - Env vars críticas: `RIOT_API_KEY`, `DATABASE_URL` (Postgres), `JWT_SECRET`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`

## Healthcheck

```bash
curl -s https://tumor-tracker-api.onrender.com/healthz/redis
```

200 OK → backend up.

## Frontend env

`zuru-web/.env.production`:
```
VITE_API_BASE=https://tumor-tracker-api.onrender.com
```

## Migración DB

Schema usa auto-migración inline (`ALTER TABLE ADD COLUMN IF NOT EXISTS`). No hay sistema explícito de migrations. Cuando añades una columna:
1. Actualiza `_init_sqlite` (loop con `PRAGMA table_info`)
2. Actualiza `_init_pg` (loop con `IF NOT EXISTS`)
3. Actualiza `_<TABLE>_COLS` constante
4. Actualiza `_row_to_<table>` mapper
5. Deploy → el siguiente startup ejecuta el ALTER, idempotente

## Rollback

Si algo se rompe en prod:
```bash
# en el repo local
git checkout main
git revert HEAD --no-edit
git push origin main
git push personal main
```

Vercel y Render redeployan automáticamente con el revert.
