---
tags: [architecture, riot, api]
---

# Architecture · Riot API

## Endpoints usados

| URL template (en `config.py`)                      | Uso                                          |
|----------------------------------------------------|----------------------------------------------|
| `ACCOUNT_BY_RIOT_ID_URL/{name}/{tag}`              | Resolver Riot ID → puuid                     |
| `MATCHES_BY_PUUID_URL/{puuid}/ids?queue=&count=`   | Historial de match IDs                       |
| `MATCH_DETAILS_URL/{match_id}`                     | Detail full de match terminado (Match v5)    |
| `LEAGUE_ENTRIES_BY_PUUID_URL/{puuid}`              | Tier + division (RANKED_SOLO)                |
| `ACTIVE_GAME_URL` (spectator_url())                | Live game (Spectator v5)                     |
| `CHAMPION_MASTERY_URL`                             | Mastery por champion                         |

Plataforma se autodetecta con `detect_platform(puuid)` probando regiones.

## Auth

`headers` desde `config.py` con `X-Riot-Token: <API_KEY>`. API key en env var `RIOT_API_KEY` en prod; en local en `config.py` (no commitear).

## Rate limit

- Development key: 20 req/s, 100 req/2min
- Production key (lo que tenemos): 500 req/s, 30k req/10min
- `riot_get` wrapper en [riot_infra.py](../../zuru-web-backend/src/riot_infra.py) hace:
  - Cache SQLite (`riot_cache.db`) con TTL por endpoint
  - Retry con backoff exponencial en 429/5xx (hasta 4 intentos)
  - Mide tiempo + cuenta hits en `cache_stats()`

## Queues relevantes

```python
QUEUE_RANKED_SOLO = 420
QUEUE_RANKED_FLEX = 440
QUEUE_NORMAL_DRAFT = 400
QUEUE_NORMAL_BLIND = 430
QUEUE_ARAM = 450
QUEUE_ARENA = 1700 / 1710 (varies)
RANKED_QUEUES = {420, 440}
BETTING_ALLOWED_QUEUES = {420, 440}   # apuestas solo SoloQ + Flex
```

`is_ranked_queue(qid)`, `allows_betting(qid)`, `queue_name(qid)` en config.py.

## Datos críticos en Match v5 participant

```
puuid, championId, teamId (100=blue, 200=red),
win, teamPosition (TOP|JUNGLE|MIDDLE|BOTTOM|UTILITY),
kills, deaths, assists, totalMinionsKilled, neutralMinionsKilled,
totalDamageDealtToChampions, goldEarned, visionScore,
challenges.killParticipation, challenges.kda,
item0..item6, summoner1Id, summoner2Id,
totalTimeSpentDead, timePlayed
```

En `info`:
```
gameStartTimestamp, gameEndTimestamp, gameDuration (s), queueId
```

`game_end_ts` se usa para refund window: bets creadas <60s antes de game end se refundean (`REFUND_WINDOW_SECONDS=60`).

## Datos de Spectator v5 (live)

```
gameId, gameQueueConfigId, gameStartTime (epoch ms), gameLength (s),
participants[]: puuid, championId, teamId, summonerName, ...
bannedChampions[]
```

`gameStartTime` se guarda en live_snapshots como `game_start_ts` (segundos epoch).

## Data Dragon (DDragon)

Separado de la Riot API normal. CDN público sin API key.

- `https://ddragon.leagueoflegends.com/api/versions.json` → array, primero = latest
- `https://ddragon.leagueoflegends.com/cdn/<v>/data/en_US/champion.json`
- `https://ddragon.leagueoflegends.com/cdn/<v>/data/en_US/item.json`
- `https://ddragon.leagueoflegends.com/cdn/<v>/img/champion/<Aatrox>.png`
- `https://ddragon.leagueoflegends.com/cdn/<v>/img/item/<3157>.png`

Cacheado 24h en `bravery_engine.py`. Pre-warm en thread daemon al import.
