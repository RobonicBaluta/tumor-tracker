"""
Cliente Redis compartido para cache + rate limiter distribuido.

Diseño:
  - Si REDIS_URL no está configurado, todas las funciones devuelven None / no-op.
    El resto de la app sigue funcionando con sus caches locales (SQLite, dict).
  - Upstash exige TLS: si la URL llega como `redis://`, la promovemos a `rediss://`.
  - Operaciones envueltas en try/except: nunca dejan caer una request por un Redis flaky.

Uso típico:
    from redis_client import r, r_get_json, r_set_json, redis_incr_with_ttl

    val = r_get_json("hot:matchcache:" + match_id)
    if val is None:
        val = expensive_fetch()
        r_set_json("hot:matchcache:" + match_id, val, ttl=600)
"""
import json
import logging
import os
import time

try:
    import redis as _redis_lib
except Exception:
    _redis_lib = None

_log = logging.getLogger("redis_client")
_log.addHandler(logging.NullHandler())


def _build_client():
    if _redis_lib is None:
        return None
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    # Upstash requiere TLS. Acepta `redis://` o `rediss://`; promovemos al TLS
    if url.startswith("redis://") and "upstash.io" in url:
        url = "rediss://" + url[len("redis://"):]
    try:
        client = _redis_lib.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=False,
            health_check_interval=30,
        )
        # Smoke test rápido. Si falla, lo damos por no disponible.
        client.ping()
        _log.info("Redis connected: %s", _redact(url))
        return client
    except Exception as exc:
        _log.warning("Redis disabled (%s): %s", _redact(url), exc)
        return None


def _redact(url):
    # Esconde la password al loggear: redis(s)://default:XXX@host
    try:
        if "@" in url and "://" in url:
            scheme, rest = url.split("://", 1)
            cred, host = rest.split("@", 1)
            if ":" in cred:
                user, _ = cred.split(":", 1)
                cred = f"{user}:***"
            return f"{scheme}://{cred}@{host}"
    except Exception:
        pass
    return url


# Cliente singleton (None si no configurado o no instalable)
r = _build_client()


def is_enabled():
    return r is not None


# ---------------------------------------------------------------------------
# Helpers tolerantes a fallo: nunca lanzan, solo devuelven None / no-op.
# ---------------------------------------------------------------------------

def r_get(key):
    if r is None:
        return None
    try:
        return r.get(key)
    except Exception as exc:
        _log.debug("redis GET fail: %s", exc)
        return None


def r_set(key, value, ttl=None):
    if r is None:
        return False
    try:
        if ttl:
            r.set(key, value, ex=ttl)
        else:
            r.set(key, value)
        return True
    except Exception as exc:
        _log.debug("redis SET fail: %s", exc)
        return False


def r_get_json(key):
    raw = r_get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def r_set_json(key, value, ttl=None):
    try:
        return r_set(key, json.dumps(value, separators=(",", ":")), ttl=ttl)
    except Exception:
        return False


def r_delete(key):
    if r is None:
        return False
    try:
        r.delete(key)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Rate limiter distribuido (sliding window via INCR + EXPIRE)
# ---------------------------------------------------------------------------

def acquire_slot(bucket_key, limit, per_seconds):
    """Intenta consumir un slot del bucket distribuido.

    Devuelve (ok, retry_after_seconds):
      - ok=True  → la llamada puede proceder.
      - ok=False → has llegado al límite; espera retry_after y reintenta.

    Si Redis está caído, devuelve (True, 0) — fallback al limiter local.
    Implementación: ventana de tiempo fija con clave que incluye un bucket
    redondeado, evita race conditions con un único INCR atómico.
    """
    if r is None:
        return True, 0
    try:
        bucket_id = int(time.time() // per_seconds)
        key = f"rl:{bucket_key}:{bucket_id}"
        # INCR + EXPIRE en pipeline → atómico
        with r.pipeline() as pipe:
            pipe.incr(key)
            pipe.expire(key, per_seconds + 1)
            count, _ = pipe.execute()
        if count <= limit:
            return True, 0
        # Devolvemos el tiempo hasta el siguiente bucket
        retry = per_seconds - (int(time.time()) % per_seconds)
        return False, retry
    except Exception as exc:
        _log.debug("redis acquire_slot fail (allowing): %s", exc)
        return True, 0
