"""
Infra compartida para llamadas a la Riot API:
  - MatchCache: cache persistente SQLite de /match/v5/matches/{id}
  - RateLimiter: token bucket para app-level limits
  - riot_get(): GET con rate-limit, retry en 429 y caché para match details

Diseñado para dev key (20 req/sec · 100 req/2min) y para
subir a personal key (30 req/sec · 30000 req/10min) cambiando LIMITS.
"""
import json
import os
import sqlite3
import threading
import time

import requests

try:
    from redis_client import (
        r_get_json as _redis_get_json,
        r_set_json as _redis_set_json,
        is_enabled as _redis_enabled,
    )
except Exception:
    def _redis_get_json(*_a, **_kw): return None
    def _redis_set_json(*_a, **_kw): return False
    def _redis_enabled(): return False

DB_PATH = os.path.join(
    os.environ.get("DATA_DIR", os.path.dirname(__file__)),
    "riot_cache.db",
)


# ---------------------------------------------------------------------------
# Match cache (SQLite)
# ---------------------------------------------------------------------------

_db_lock = threading.Lock()
_conn = None


def _get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS match_cache (
                match_id TEXT PRIMARY KEY,
                json     TEXT NOT NULL,
                cached_at INTEGER NOT NULL
            )
            """
        )
    return _conn


_REDIS_MATCH_TTL = 24 * 3600  # 24h: matches son inmutables, podemos cachear largo


def cache_get_match(match_id):
    # L1: Redis (rápido, compartido entre workers)
    hit = _redis_get_json(f"match:{match_id}")
    if hit is not None:
        return hit
    # L2: SQLite (persistente)
    with _db_lock:
        cur = _get_conn().execute(
            "SELECT json FROM match_cache WHERE match_id = ?", (match_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        try:
            data = json.loads(row[0])
        except Exception:
            return None
    # Promover a L1 para próximas reads
    _redis_set_json(f"match:{match_id}", data, ttl=_REDIS_MATCH_TTL)
    return data


def cache_put_match(match_id, data):
    with _db_lock:
        _get_conn().execute(
            "INSERT OR REPLACE INTO match_cache (match_id, json, cached_at) VALUES (?, ?, ?)",
            (match_id, json.dumps(data), int(time.time())),
        )
    _redis_set_json(f"match:{match_id}", data, ttl=_REDIS_MATCH_TTL)


def cache_stats():
    with _db_lock:
        cur = _get_conn().execute("SELECT COUNT(*) FROM match_cache")
        return {"cached_matches": cur.fetchone()[0], "redis_enabled": _redis_enabled()}


# ---------------------------------------------------------------------------
# Rate limiter (token bucket)
# ---------------------------------------------------------------------------

# App-level Riot limits para dev key. Cada (capacity, per_seconds).
# Personal key: [(30, 1), (30000, 600)]
LIMITS = [(20, 1), (100, 120)]


class _Bucket:
    __slots__ = ("capacity", "per", "tokens", "last")

    def __init__(self, capacity, per):
        self.capacity = capacity
        self.per = per
        self.tokens = float(capacity)
        self.last = time.monotonic()

    def take(self):
        """Bloquea hasta poder consumir 1 token."""
        while True:
            now = time.monotonic()
            elapsed = now - self.last
            # rellena proporcional al tiempo transcurrido
            self.tokens = min(self.capacity, self.tokens + elapsed * (self.capacity / self.per))
            self.last = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
            # esperar lo justo para tener 1 token
            need = 1 - self.tokens
            wait = need * (self.per / self.capacity)
            time.sleep(wait)


_limiter_lock = threading.Lock()
_buckets = [_Bucket(c, p) for (c, p) in LIMITS]


def _throttle():
    with _limiter_lock:
        for b in _buckets:
            b.take()
    # NOTE: el limiter distribuido en Redis se omite a propósito.
    # Render free tier corre 1 worker → no hay contención cross-worker, y un
    # round-trip a Upstash (~80ms) por cada llamada a la Riot API añade segundos
    # al /liveGame (50+ llamadas). Si en el futuro escalamos a >1 worker:
    #   for cap, per in LIMITS:
    #       ok, retry = _redis_acquire_slot(f"riot:{cap}_{per}", cap, per)
    #       if not ok and retry > 0: time.sleep(min(retry, 5))


# ---------------------------------------------------------------------------
# riot_get: combina rate limit + retry 429 + cache de match details
# ---------------------------------------------------------------------------

def riot_get(url, headers, max_retries=4, cache_matches=True):
    """GET con rate limit, retry 429 y cache automática de match details.

    - Si la URL es `/lol/match/v5/matches/<id>` (sin subpaths), consulta cache SQLite.
    - Si no está en cache, hace la request, respetando token bucket.
    - Retry en 429 usando Retry-After.

    Devuelve un objeto tipo `requests.Response`-lite con `.status_code` y `.json()`.
    """
    cached_match_id = None
    if cache_matches and "/match/v5/matches/" in url:
        tail = url.rsplit("/match/v5/matches/", 1)[1]
        if "/" not in tail and "?" not in tail:
            cached_match_id = tail
            hit = cache_get_match(cached_match_id)
            if hit is not None:
                return _CachedResponse(hit)

    for attempt in range(max_retries + 1):
        _throttle()
        res = requests.get(url, headers=headers)
        if res.status_code == 429 and attempt < max_retries:
            wait = int(res.headers.get("Retry-After", "10"))
            time.sleep(min(wait, 60))
            continue
        if res.status_code == 200 and cached_match_id is not None:
            try:
                cache_put_match(cached_match_id, res.json())
            except Exception:
                pass
        return res
    return res


class _CachedResponse:
    """Imita el API mínimo de `requests.Response` para hits en cache."""
    def __init__(self, data):
        self._data = data
        self.status_code = 200
        self.headers = {}

    def json(self):
        return self._data

    @property
    def text(self):
        return json.dumps(self._data)
