---
tags: [operations, deploy, gitlab, cpanel]
status: pending
---

# GitLab + cPanel Deploy (pendiente)

> Estado: **pendiente**. El user quiere desplegar también en su server cPanel. Token GitLab provisto pero devuelve 401 — esperando confirmación de scopes/URL.

## Lo que se decidió

- GitLab será el repo source para cPanel (cPanel Git Version Control hace pull desde aquí)
- Coexistirá con Vercel/Render (no los reemplaza por ahora)

## Lo que necesito que el user confirme

1. ¿gitlab.com o GitLab self-hosted? Token devuelve 401 contra gitlab.com — puede ser revocado o de otra instancia
2. URL del cPanel (sub.dominio.com)
3. Tipo de Python disponible en cPanel (3.10? 3.11?)
4. Base de datos disponible en cPanel: ¿Postgres o sólo MySQL?
5. ¿Migrate de Vercel/Render a cPanel o mantener todos?

## Plan tentativo

### Setup GitLab

```bash
git remote add gitlab https://oauth2:$GITLAB_TOKEN@gitlab.com/<user>/tumor-tracker.git
git push gitlab main
# después limpiar token de la URL:
git remote set-url gitlab https://gitlab.com/<user>/tumor-tracker.git
```

### Files a preparar para cPanel

1. **`passenger_wsgi.py`** (root) — punto de entrada para Phusion Passenger:
   ```python
   import sys, os
   sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'zuru-web-backend', 'src'))
   from main import app as application
   ```

2. **`requirements.txt`** (root o symlink) — cPanel Python App lo lee del root

3. **`.htaccess`** en `public_html` para SPA Vue (rewrite a index.html):
   ```apache
   RewriteEngine On
   RewriteBase /
   RewriteRule ^index\.html$ - [L]
   RewriteCond %{REQUEST_FILENAME} !-f
   RewriteCond %{REQUEST_FILENAME} !-d
   RewriteRule . /index.html [L]
   ```

4. **`.cpanel.yml`** — tasks de deploy automático:
   ```yaml
   ---
   deployment:
     tasks:
       - export DEPLOYPATH=/home/$USER/public_html
       - cd zuru-web && npm install && npm run build
       - /bin/cp -R zuru-web/dist/* $DEPLOYPATH/
       - cd /home/$USER/zuru-web-backend && pip install -r requirements.txt
       - touch /home/$USER/tmp/restart.txt
   ```

5. **`zuru-web/.env.production.cpanel`** — apunta el frontend al backend cPanel:
   ```
   VITE_API_BASE=https://api.tu-dominio.com
   ```

### Migración DB

- Si cPanel sólo tiene MySQL: el backend usa SQL crudo + Postgres-specific syntax (`SERIAL`, `DOUBLE PRECISION`, `RETURNING`). Migración no trivial.
- Si tiene Postgres: setear `DATABASE_URL` en cPanel Python App env vars.

### Pasos cPanel (manuales del user)

1. cPanel → Git Version Control → Create
   - Clone URL: `https://gitlab.com/<user>/tumor-tracker.git` (o SSH)
   - Repository Path: `/home/<user>/tumor-tracker`
2. cPanel → Setup Python App → Create
   - Python version: 3.11
   - App root: `/home/<user>/tumor-tracker`
   - App URL: `api.tu-dominio.com`
   - App startup file: `passenger_wsgi.py`
3. cPanel → Subdomain → crear `api.tu-dominio.com`
4. cPanel → MySQL/Postgres → crear DB + usuario
5. cPanel → Python App → Edit → env vars → setear `RIOT_API_KEY`, `DATABASE_URL`, `JWT_SECRET`, etc.

### Pendiente

- Validar token GitLab
- Decidir Postgres vs MySQL
- Crear `.cpanel.yml` + `passenger_wsgi.py` + `.htaccess`
- Probar deploy end-to-end
