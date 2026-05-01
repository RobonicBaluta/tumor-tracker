"""
Capa de DB para usuarios + currency (Tumor Coins).

Diseñado para que funcione con SQLite en local y PostgreSQL en Render.
Cuando `DATABASE_URL` está definida, usa psycopg2; si no, SQLite local.

Tablas:
  - users(id, discord_id UNIQUE, discord_username, discord_avatar,
          riot_puuid, riot_id, currency, created_at, last_login)
  - currency_transactions(id, user_id, delta, reason, created_at)
"""
import os
import sqlite3
import threading
import time

DATABASE_URL = os.getenv("DATABASE_URL")
USE_PG = DATABASE_URL is not None and DATABASE_URL.startswith(("postgres://", "postgresql://"))

if USE_PG:
    try:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
    except ImportError:
        # No instalado en local → fallback a SQLite
        USE_PG = False

_DB_PATH = os.path.join(
    os.environ.get("DATA_DIR", os.path.dirname(__file__)),
    "users.db",
)
_lock = threading.Lock()
_conn = None


def _get_conn():
    """Devuelve la conexión activa (PG o SQLite). Lazy init."""
    global _conn
    if _conn is not None:
        return _conn
    if USE_PG:
        # Render Postgres — psycopg2
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        _conn = psycopg2.connect(url, sslmode="require")
        _conn.autocommit = True
        _init_pg(_conn)
    else:
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False, isolation_level=None)
        _conn.execute("PRAGMA journal_mode=WAL")
        _init_sqlite(_conn)
    return _conn


def _init_sqlite(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT UNIQUE NOT NULL,
            discord_username TEXT,
            discord_avatar TEXT,
            riot_puuid TEXT,
            riot_id TEXT,
            currency INTEGER DEFAULT 0,
            created_at REAL NOT NULL,
            last_login REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS currency_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            delta INTEGER NOT NULL,
            reason TEXT,
            created_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_rewards (
            user_id INTEGER PRIMARY KEY,
            last_claim_at REAL NOT NULL
        )
    """)


def _init_pg(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            discord_id TEXT UNIQUE NOT NULL,
            discord_username TEXT,
            discord_avatar TEXT,
            riot_puuid TEXT,
            riot_id TEXT,
            currency INTEGER DEFAULT 0,
            created_at DOUBLE PRECISION NOT NULL,
            last_login DOUBLE PRECISION NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS currency_transactions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            delta INTEGER NOT NULL,
            reason TEXT,
            created_at DOUBLE PRECISION NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_rewards (
            user_id INTEGER PRIMARY KEY REFERENCES users(id),
            last_claim_at DOUBLE PRECISION NOT NULL
        )
    """)
    cur.close()


def _qmark(sql):
    """SQLite usa ?, PG usa %s. Convierte sobre la marcha."""
    return sql.replace("?", "%s") if USE_PG else sql


def _exec(sql, params=()):
    conn = _get_conn()
    with _lock:
        if USE_PG:
            cur = conn.cursor()
            cur.execute(_qmark(sql), params)
            return cur
        else:
            return conn.execute(sql, params)


def _exec_returning(sql, params=()):
    """Para INSERT...RETURNING id (PG) o lastrowid (sqlite)."""
    conn = _get_conn()
    with _lock:
        if USE_PG:
            cur = conn.cursor()
            cur.execute(_qmark(sql) + " RETURNING id", params)
            return cur.fetchone()[0]
        else:
            cur = conn.execute(sql, params)
            return cur.lastrowid


# ---------------------------------------------------------------------------
# Operaciones de usuario
# ---------------------------------------------------------------------------

def upsert_user_from_discord(discord_id, username, avatar_hash):
    """Crea o actualiza el usuario de Discord. Devuelve el row completo."""
    now = time.time()
    existing = get_user_by_discord(discord_id)
    if existing:
        _exec(
            "UPDATE users SET discord_username=?, discord_avatar=?, last_login=? WHERE discord_id=?",
            (username, avatar_hash, now, discord_id),
        )
        return get_user_by_discord(discord_id)
    new_id = _exec_returning(
        """INSERT INTO users (discord_id, discord_username, discord_avatar,
            currency, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, ?)""",
        (discord_id, username, avatar_hash, 100, now, now),  # 100 TC welcome bonus
    )
    # Welcome transaction
    _exec(
        "INSERT INTO currency_transactions (user_id, delta, reason, created_at) VALUES (?, ?, ?, ?)",
        (new_id, 100, "welcome bonus", now),
    )
    return get_user_by_discord(discord_id)


def get_user_by_discord(discord_id):
    cur = _exec(
        "SELECT id, discord_id, discord_username, discord_avatar, riot_puuid, riot_id, currency, created_at, last_login FROM users WHERE discord_id=?",
        (discord_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return _row_to_user(row)


def get_user_by_id(user_id):
    cur = _exec(
        "SELECT id, discord_id, discord_username, discord_avatar, riot_puuid, riot_id, currency, created_at, last_login FROM users WHERE id=?",
        (user_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return _row_to_user(row)


def _row_to_user(row):
    return {
        "id": row[0],
        "discord_id": row[1],
        "username": row[2],
        "avatar": row[3],
        "riot_puuid": row[4],
        "riot_id": row[5],
        "currency": row[6] or 0,
        "created_at": row[7],
        "last_login": row[8],
    }


def link_riot_account(user_id, riot_puuid, riot_id):
    _exec(
        "UPDATE users SET riot_puuid=?, riot_id=? WHERE id=?",
        (riot_puuid, riot_id, user_id),
    )


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

def add_currency(user_id, delta, reason):
    """Suma (o resta si delta<0) Tumor Coins al user. Registra la transacción.
    Devuelve el nuevo balance, o None si fallaría a negativo."""
    user = get_user_by_id(user_id)
    if not user:
        return None
    new_balance = user["currency"] + delta
    if new_balance < 0:
        return None
    _exec("UPDATE users SET currency=? WHERE id=?", (new_balance, user_id))
    _exec(
        "INSERT INTO currency_transactions (user_id, delta, reason, created_at) VALUES (?, ?, ?, ?)",
        (user_id, delta, reason, time.time()),
    )
    return new_balance


def get_recent_transactions(user_id, limit=20):
    cur = _exec(
        "SELECT delta, reason, created_at FROM currency_transactions WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    rows = cur.fetchall()
    return [{"delta": r[0], "reason": r[1], "at": r[2]} for r in rows]


def can_claim_daily(user_id):
    """True si el user no ha reclamado el daily en las últimas 20h."""
    cur = _exec("SELECT last_claim_at FROM daily_rewards WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if not row:
        return True
    return time.time() - (row[0] or 0) >= 20 * 3600


def claim_daily(user_id, amount=100):
    """Reclama el daily reward. Devuelve nuevo balance o None si ya reclamó."""
    if not can_claim_daily(user_id):
        return None
    now = time.time()
    cur = _exec("SELECT user_id FROM daily_rewards WHERE user_id=?", (user_id,))
    if cur.fetchone():
        _exec("UPDATE daily_rewards SET last_claim_at=? WHERE user_id=?", (now, user_id))
    else:
        _exec("INSERT INTO daily_rewards (user_id, last_claim_at) VALUES (?, ?)", (user_id, now))
    return add_currency(user_id, amount, "daily reward")
