---
tags: [index, hub]
---

# 00 · Tumor Tracker · Index

> Tumor Tracker (a.k.a. ZuruWeb): companion web app para League of Legends. Genera un "tumor score" 5-axis (KDA, CS/min, dmg/min, alive%, vis/min) ponderado por rol+tier para juzgar partidas live + post-partida. Apuestas P2P y vs sistema, challenges 1v1, salas multi-user, bravery mode.

## Stack rápido

- **Frontend**: Vue 3 + TS + Vite + Tailwind 4 → desplegado en Vercel
- **Backend**: Flask + Python 3.11 + psycopg2 (Postgres prod, SQLite local) → desplegado en Render
- **Repo**: `RobonicBaluta/tumor-tracker` (remote `personal`) y `jonzuru/zuruweb` (remote `origin`). Vercel/Render escuchan `personal`. Ver [[Operations/Deploy]].

## Sub-índices

- 🏛 [[Architecture/00-Overview]] — mapa de carpetas, módulos clave, flujos
- 🎯 [[Features/00-Overview]] — features con archivos + endpoints
- ⚖ [[Decisions/00-Overview]] — decisiones de diseño con su porqué
- 🛠 [[Operations/00-Overview]] — deploy, troubleshooting

## Handoffs (estado del proyecto en el tiempo)

- [[Handoffs/2026-06-10-bravery-rooms-launched]] — último estado conocido

## Glosario

- **tumor score**: número 0-100. **0** = jugador perfecto, **100** = "tumor maligno" total. Punto **60 = sus** (sospechoso, break-even en bravery).
- **TC**: Tumor Coins, moneda interna para apuestas.
- **prior**: tumor histórico de un jugador (avg de sus últimas N partidas).
- **DDragon**: Data Dragon, CDN de Riot con champions/items/iconos del parche actual.

## Convenciones del vault

- Nombres en kebab-case (`my-note.md`)
- Frontmatter YAML con `tags:` cuando aporte
- Links con doble corchete `[[Note]]` o `[[Folder/Note]]`
- Si una nota habla de código, **siempre** incluir rutas con paths absolutos relativos al repo: `[main.py:3306](../../zuru-web-backend/src/main.py)` (Obsidian abre el link si está dentro del repo)
