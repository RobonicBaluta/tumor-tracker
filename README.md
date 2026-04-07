# Tumor Tracker

League of Legends companion: rastrea a los peores compañeros que te tocan, predice
quién va a ganar tu partida en directo en base al tumor score histórico de los 10
jugadores, y te enseña tus estadísticas personales filtrables por rol/champion/fecha.

## Stack

- **Frontend**: Vue 3 + Vite + TypeScript + Tailwind 4
- **Backend**: Flask + Python 3.11 + SQLite (cache de match details + DB de predicciones)
- **Riot API**: Account v1, Match v5, League v4, Spectator v5, Champion Mastery v4
- **Deploy**: Vercel (frontend) + Render (backend con disco persistente)

## Local dev

### Backend

```bash
cd zuru-web-backend
python -m venv venv
venv/Scripts/activate    # Windows
# source venv/bin/activate    # Linux/Mac
pip install -r requirements.txt
echo "RIOT_API_TOKEN=RGAPI-tu-key" > src/.env
cd src && python main.py
```

Backend escucha en `http://localhost:5000`. Endpoints sanity:

- `GET /healthz` → `{"ok": true}`
- `GET /cacheStats` → cuenta de match details cacheados

### Frontend

```bash
cd zuru-web
npm install
npm run dev
```

Vite arranca en `http://localhost:5173`. Para apuntar a otro backend, crea
`zuru-web/.env.local`:

```
VITE_API_BASE=https://tu-backend.onrender.com
```

## Deploy

### Backend → Render (free tier)

1. Crea cuenta en [render.com](https://render.com) y conecta el repo de GitHub.
2. Click **"New +" → "Blueprint"** y selecciona este repo. Render detecta
   `render.yaml` y crea automáticamente el servicio web + el disco persistente
   de 1 GB montado en `/var/data`.
3. En el dashboard del servicio, ve a **Environment** y rellena:
   - `RIOT_API_TOKEN` → tu key (dev key caduca cada 24h, idealmente Personal Key)
   - `CORS_ORIGINS` → la URL de Vercel cuando la tengas, p.ej.
     `https://tumor-tracker.vercel.app`
4. Cada `git push` a `main` lanza un nuevo deploy automáticamente.

### Frontend → Vercel

1. [vercel.com/new](https://vercel.com/new), importa el repo.
2. **Root Directory** = `zuru-web`. Vercel detecta Vite por el `vercel.json`.
3. **Environment Variables**:
   - `VITE_API_BASE` = `https://tumor-tracker-api.onrender.com` (la URL que te
     dé Render).
4. Deploy. Cada push a `main` re-deploya.

### Después del primer deploy

- Copia la URL pública de Vercel y pégala en `CORS_ORIGINS` en Render.
- El backend de Render se duerme tras 15 min de inactividad en el plan free.
  La primera petición tarda ~30 s en despertarlo. Es normal.

## Estructura del repo

```
.
├── render.yaml                    # Blueprint de Render
├── .github/workflows/ci.yml       # Lint + build sanity en cada PR
├── zuru-web/                      # Frontend Vue
│   ├── vercel.json
│   ├── .env.example
│   └── src/
│       ├── components/            # Overview, Live, Tinder, Compare...
│       └── composables/           # useApi, useSummoner, overviewConstants
└── zuru-web-backend/              # Backend Flask
    ├── requirements.txt
    └── src/
        ├── main.py                # Endpoints
        ├── riot_infra.py          # Cache SQLite + token bucket rate limiter
        └── config.py              # URLs Riot
```

## Notas

- **Match cache** vive en SQLite (`riot_cache.db`). Persiste entre deploys gracias
  al disco de Render.
- **Predictions DB** (`predictions.db`) guarda cada predicción del live para
  calcular la accuracy global.
- **Token bucket** central evita 429s. Si subes a Personal API Key, cambia
  `LIMITS` en `riot_infra.py`.
