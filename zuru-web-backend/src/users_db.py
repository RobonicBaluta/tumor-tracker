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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            share_code TEXT UNIQUE NOT NULL,
            match_id TEXT NOT NULL,
            game_id INTEGER,
            creator_user_id INTEGER NOT NULL,
            creator_side TEXT NOT NULL,
            amount INTEGER NOT NULL,
            taker_user_id INTEGER,
            status TEXT NOT NULL DEFAULT 'open',
            winner_side TEXT,
            resolved_at REAL,
            created_at REAL NOT NULL
        )
    """)
    # Notificaciones por usuario (servidor → cliente, polled).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT,
            link TEXT,
            icon TEXT,
            created_at REAL NOT NULL,
            read INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_notif_unread ON user_notifications(user_id, read)")
    # Friends list bidireccional con estados pending/accepted.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS friendships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at REAL NOT NULL,
            accepted_at REAL,
            UNIQUE(requester_id, target_id)
        )
    """)
    # Comparison rooms: group analytics.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            owner_user_id INTEGER NOT NULL,
            name TEXT,
            created_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS room_members (
            room_id INTEGER NOT NULL,
            riot_id TEXT NOT NULL,
            joined_at REAL NOT NULL,
            PRIMARY KEY (room_id, riot_id)
        )
    """)
    # Achievements desbloqueados por usuario
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_achievements (
            user_id INTEGER NOT NULL,
            badge TEXT NOT NULL,
            unlocked_at REAL NOT NULL,
            PRIMARY KEY (user_id, badge)
        )
    """)
    # Settings/preferences por usuario
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            public_profile INTEGER DEFAULT 1,
            allow_friend_requests INTEGER DEFAULT 1,
            notif_bets INTEGER DEFAULT 1,
            notif_friends INTEGER DEFAULT 1,
            updated_at REAL NOT NULL
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id SERIAL PRIMARY KEY,
            share_code TEXT UNIQUE NOT NULL,
            match_id TEXT NOT NULL,
            game_id BIGINT,
            creator_user_id INTEGER NOT NULL REFERENCES users(id),
            creator_side TEXT NOT NULL,
            amount INTEGER NOT NULL,
            taker_user_id INTEGER REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'open',
            winner_side TEXT,
            resolved_at DOUBLE PRECISION,
            created_at DOUBLE PRECISION NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT,
            link TEXT,
            icon TEXT,
            created_at DOUBLE PRECISION NOT NULL,
            read INTEGER DEFAULT 0
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_user_notif_unread ON user_notifications(user_id, read)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS friendships (
            id SERIAL PRIMARY KEY,
            requester_id INTEGER NOT NULL REFERENCES users(id),
            target_id INTEGER NOT NULL REFERENCES users(id),
            status TEXT NOT NULL DEFAULT 'pending',
            created_at DOUBLE PRECISION NOT NULL,
            accepted_at DOUBLE PRECISION,
            UNIQUE(requester_id, target_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            owner_user_id INTEGER NOT NULL REFERENCES users(id),
            name TEXT,
            created_at DOUBLE PRECISION NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS room_members (
            room_id INTEGER NOT NULL REFERENCES rooms(id),
            riot_id TEXT NOT NULL,
            joined_at DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (room_id, riot_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_achievements (
            user_id INTEGER NOT NULL REFERENCES users(id),
            badge TEXT NOT NULL,
            unlocked_at DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (user_id, badge)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY REFERENCES users(id),
            public_profile INTEGER DEFAULT 1,
            allow_friend_requests INTEGER DEFAULT 1,
            notif_bets INTEGER DEFAULT 1,
            notif_friends INTEGER DEFAULT 1,
            updated_at DOUBLE PRECISION NOT NULL
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


# ---------------------------------------------------------------------------
# Bets P2P
# ---------------------------------------------------------------------------

import secrets as _secrets


def _generate_bet_code():
    """6 chars alfanuméricos legibles (sin 0/O/1/I)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(_secrets.choice(alphabet) for _ in range(6))


def create_bet(creator_user_id, match_id, game_id, side, amount):
    """Crea una bet, escrowa el amount del creator. Devuelve dict o None si fallo."""
    if amount <= 0 or side not in ("blue", "red"):
        return None
    # Escrow del creator (resta amount)
    new_balance = add_currency(creator_user_id, -amount, f"bet escrow")
    if new_balance is None:
        return None  # saldo insuficiente

    # Genera código único (reintentos si colisiona)
    code = None
    for _ in range(10):
        candidate = _generate_bet_code()
        cur = _exec("SELECT id FROM bets WHERE share_code=?", (candidate,))
        if not cur.fetchone():
            code = candidate
            break
    if not code:
        # Refund
        add_currency(creator_user_id, amount, "bet refund (code collision)")
        return None

    bet_id = _exec_returning(
        """INSERT INTO bets (share_code, match_id, game_id, creator_user_id,
            creator_side, amount, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'open', ?)""",
        (code, match_id, game_id, creator_user_id, side, amount, time.time()),
    )
    return get_bet_by_id(bet_id)


def accept_bet(taker_user_id, share_code):
    """Acepta una bet existente. Escrowa el amount del taker. Devuelve dict o error_str."""
    bet = get_bet_by_code(share_code)
    if not bet:
        return "Apuesta no encontrada"
    if bet["status"] != "open":
        return f"Apuesta ya {bet['status']}"
    if bet["creator_user_id"] == taker_user_id:
        return "No puedes aceptar tu propia apuesta"

    new_balance = add_currency(taker_user_id, -bet["amount"], f"bet escrow")
    if new_balance is None:
        return "Saldo insuficiente"

    _exec(
        "UPDATE bets SET taker_user_id=?, status='matched' WHERE id=?",
        (taker_user_id, bet["id"]),
    )
    # Notificar al creator que su apuesta tiene rival
    try:
        taker = get_user_by_id(taker_user_id)
        push_notification(
            user_id=bet["creator_user_id"],
            notif_type="bet_matched",
            title="¡Tu apuesta tiene rival!",
            body=f"{taker['username']} apostó {bet['amount']} TC contra ti",
            link=f"#/bets",
            icon="⚔",
        )
    except Exception:
        pass
    return get_bet_by_id(bet["id"])


def cancel_bet(creator_user_id, bet_id):
    """Cancela una bet abierta (sin taker). Devuelve refund o None."""
    bet = get_bet_by_id(bet_id)
    if not bet or bet["status"] != "open" or bet["creator_user_id"] != creator_user_id:
        return None
    _exec("UPDATE bets SET status='cancelled' WHERE id=?", (bet_id,))
    add_currency(creator_user_id, bet["amount"], "bet cancelled refund")
    return bet


def resolve_bet(bet_id, winner_side):
    """Resuelve una bet matched. Paga al ganador, marca como resolved.
    Devuelve el bet actualizado."""
    bet = get_bet_by_id(bet_id)
    if not bet or bet["status"] != "matched":
        return None
    winner_user_id = bet["creator_user_id"] if bet["creator_side"] == winner_side else bet["taker_user_id"]
    loser_user_id = bet["taker_user_id"] if bet["creator_side"] == winner_side else bet["creator_user_id"]
    if winner_user_id is None:
        return None
    payout = bet["amount"] * 2
    add_currency(winner_user_id, payout, f"bet won · {bet['share_code']}")
    _exec(
        "UPDATE bets SET status='resolved', winner_side=?, resolved_at=? WHERE id=?",
        (winner_side, time.time(), bet_id),
    )
    # Notificaciones al ganador y perdedor
    try:
        push_notification(
            user_id=winner_user_id,
            notif_type="bet_won",
            title=f"Ganaste {payout} TC",
            body=f"Apuesta {bet['share_code']} resuelta",
            link="#/bets", icon="✅",
        )
        if loser_user_id:
            push_notification(
                user_id=loser_user_id,
                notif_type="bet_lost",
                title=f"Perdiste {bet['amount']} TC",
                body=f"Apuesta {bet['share_code']} perdida",
                link="#/bets", icon="❌",
            )
    except Exception:
        pass
    # Evaluar achievements para ambos
    try:
        evaluate_achievements(winner_user_id)
        if loser_user_id:
            evaluate_achievements(loser_user_id)
    except Exception:
        pass
    return get_bet_by_id(bet_id)


def resolve_bets_for_match(match_id, winner_side):
    """Resuelve TODAS las bets matched de ese match_id. Útil al cerrar live."""
    cur = _exec(
        "SELECT id FROM bets WHERE match_id=? AND status='matched'",
        (match_id,),
    )
    rows = cur.fetchall()
    return [resolve_bet(r[0], winner_side) for r in rows]


def get_bet_by_id(bet_id):
    cur = _exec(
        """SELECT id, share_code, match_id, game_id, creator_user_id, creator_side,
                  amount, taker_user_id, status, winner_side, resolved_at, created_at
           FROM bets WHERE id=?""",
        (bet_id,),
    )
    row = cur.fetchone()
    return _row_to_bet(row) if row else None


def get_bet_by_code(share_code):
    cur = _exec(
        """SELECT id, share_code, match_id, game_id, creator_user_id, creator_side,
                  amount, taker_user_id, status, winner_side, resolved_at, created_at
           FROM bets WHERE share_code=?""",
        (share_code,),
    )
    row = cur.fetchone()
    return _row_to_bet(row) if row else None


def list_open_bets(limit=50):
    """Bets abiertas que cualquiera puede aceptar. Las más recientes primero."""
    cur = _exec(
        """SELECT id, share_code, match_id, game_id, creator_user_id, creator_side,
                  amount, taker_user_id, status, winner_side, resolved_at, created_at
           FROM bets WHERE status='open'
           ORDER BY created_at DESC LIMIT ?""",
        (limit,),
    )
    rows = cur.fetchall()
    return [_row_to_bet(r) for r in rows]


# ---------------------------------------------------------------------------
# Leaderboards
# ---------------------------------------------------------------------------

def leaderboard_top_currency(limit=20):
    cur = _exec(
        """SELECT id, discord_username, discord_avatar, currency, riot_id
           FROM users
           ORDER BY currency DESC LIMIT ?""",
        (limit,),
    )
    rows = cur.fetchall()
    return [{"user_id": r[0], "username": r[1], "avatar": r[2], "currency": r[3], "riot_id": r[4]} for r in rows]


def leaderboard_top_bet_winners(limit=20):
    """Top users por bets ganadas."""
    cur = _exec(
        """SELECT u.id, u.discord_username, u.discord_avatar, u.currency,
                  COUNT(*) AS won_count,
                  SUM(b.amount) AS net_won
           FROM bets b
           JOIN users u ON u.id = (
                CASE WHEN b.creator_side = b.winner_side THEN b.creator_user_id ELSE b.taker_user_id END
           )
           WHERE b.status = 'resolved'
           GROUP BY u.id, u.discord_username, u.discord_avatar, u.currency
           ORDER BY won_count DESC, net_won DESC
           LIMIT ?""",
        (limit,),
    )
    rows = cur.fetchall()
    return [{
        "user_id": r[0], "username": r[1], "avatar": r[2], "currency": r[3],
        "won_count": r[4], "net_won": r[5],
    } for r in rows]


def get_user_bets(user_id, limit=50):
    cur = _exec(
        """SELECT id, share_code, match_id, game_id, creator_user_id, creator_side,
                  amount, taker_user_id, status, winner_side, resolved_at, created_at
           FROM bets
           WHERE creator_user_id=? OR taker_user_id=?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, user_id, limit),
    )
    rows = cur.fetchall()
    return [_row_to_bet(r) for r in rows]


def _row_to_bet(row):
    if not row:
        return None
    return {
        "id": row[0],
        "share_code": row[1],
        "match_id": row[2],
        "game_id": row[3],
        "creator_user_id": row[4],
        "creator_side": row[5],
        "amount": row[6],
        "taker_user_id": row[7],
        "status": row[8],
        "winner_side": row[9],
        "resolved_at": row[10],
        "created_at": row[11],
    }


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def push_notification(user_id, notif_type, title, body=None, link=None, icon=None):
    _exec(
        """INSERT INTO user_notifications (user_id, type, title, body, link, icon, created_at, read)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
        (user_id, notif_type, title, body, link, icon, time.time()),
    )


def get_unread_notifications(user_id, limit=20):
    cur = _exec(
        """SELECT id, type, title, body, link, icon, created_at
           FROM user_notifications
           WHERE user_id=? AND read=0
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit),
    )
    rows = cur.fetchall()
    return [{"id": r[0], "type": r[1], "title": r[2], "body": r[3], "link": r[4], "icon": r[5], "at": r[6]} for r in rows]


def mark_notifications_read(user_id, notif_ids=None):
    if notif_ids is None:
        _exec("UPDATE user_notifications SET read=1 WHERE user_id=?", (user_id,))
    else:
        for nid in notif_ids:
            _exec("UPDATE user_notifications SET read=1 WHERE id=? AND user_id=?", (nid, user_id))


# ---------------------------------------------------------------------------
# Friends
# ---------------------------------------------------------------------------

def send_friend_request(requester_id, target_id):
    if requester_id == target_id:
        return None
    # Si ya existe (en cualquier dirección), error
    cur = _exec(
        "SELECT id, status FROM friendships WHERE (requester_id=? AND target_id=?) OR (requester_id=? AND target_id=?)",
        (requester_id, target_id, target_id, requester_id),
    )
    existing = cur.fetchone()
    if existing:
        return {"id": existing[0], "status": existing[1]}
    fid = _exec_returning(
        "INSERT INTO friendships (requester_id, target_id, status, created_at) VALUES (?, ?, 'pending', ?)",
        (requester_id, target_id, time.time()),
    )
    return {"id": fid, "status": "pending"}


def accept_friend(target_id, friendship_id):
    cur = _exec(
        "SELECT requester_id, target_id, status FROM friendships WHERE id=?",
        (friendship_id,),
    )
    row = cur.fetchone()
    if not row or row[1] != target_id or row[2] != "pending":
        return False
    _exec(
        "UPDATE friendships SET status='accepted', accepted_at=? WHERE id=?",
        (time.time(), friendship_id),
    )
    return True


def reject_friend(target_id, friendship_id):
    _exec(
        "UPDATE friendships SET status='rejected' WHERE id=? AND target_id=?",
        (friendship_id, target_id),
    )
    return True


def list_friends(user_id):
    cur = _exec(
        """SELECT f.id, f.status,
                  CASE WHEN f.requester_id=? THEN f.target_id ELSE f.requester_id END AS other_id,
                  CASE WHEN f.requester_id=? THEN 'sent' ELSE 'received' END AS direction,
                  f.created_at, f.accepted_at
           FROM friendships f
           WHERE (f.requester_id=? OR f.target_id=?)
           ORDER BY f.created_at DESC""",
        (user_id, user_id, user_id, user_id),
    )
    rows = cur.fetchall()
    out = []
    other_ids = [r[2] for r in rows]
    briefs = get_users_brief(other_ids)
    for r in rows:
        out.append({
            "id": r[0],
            "status": r[1],
            "other_user": briefs.get(r[2]),
            "direction": r[3],
            "created_at": r[4],
            "accepted_at": r[5],
        })
    return out


def find_user_by_riot_id(riot_id):
    cur = _exec("SELECT id FROM users WHERE riot_id=?", (riot_id,))
    row = cur.fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Comparison rooms
# ---------------------------------------------------------------------------

def create_room(owner_user_id, name=""):
    code = None
    for _ in range(10):
        candidate = _generate_bet_code()
        cur = _exec("SELECT id FROM rooms WHERE code=?", (candidate,))
        if not cur.fetchone():
            code = candidate
            break
    if not code:
        return None
    rid = _exec_returning(
        "INSERT INTO rooms (code, owner_user_id, name, created_at) VALUES (?, ?, ?, ?)",
        (code, owner_user_id, name or "", time.time()),
    )
    return get_room_by_id(rid)


def get_room_by_id(room_id):
    cur = _exec(
        "SELECT id, code, owner_user_id, name, created_at FROM rooms WHERE id=?",
        (room_id,),
    )
    row = cur.fetchone()
    return _row_to_room(row) if row else None


def get_room_by_code(code):
    cur = _exec(
        "SELECT id, code, owner_user_id, name, created_at FROM rooms WHERE code=?",
        (code,),
    )
    row = cur.fetchone()
    return _row_to_room(row) if row else None


def _row_to_room(row):
    if not row:
        return None
    return {
        "id": row[0],
        "code": row[1],
        "owner_user_id": row[2],
        "name": row[3] or "",
        "created_at": row[4],
        "members": get_room_members(row[0]),
    }


def get_room_members(room_id):
    cur = _exec(
        "SELECT riot_id, joined_at FROM room_members WHERE room_id=? ORDER BY joined_at ASC",
        (room_id,),
    )
    rows = cur.fetchall()
    return [{"riot_id": r[0], "joined_at": r[1]} for r in rows]


def add_room_member(room_id, riot_id):
    _exec(
        "INSERT OR IGNORE INTO room_members (room_id, riot_id, joined_at) VALUES (?, ?, ?)" if not USE_PG else
        "INSERT INTO room_members (room_id, riot_id, joined_at) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
        (room_id, riot_id, time.time()),
    )


def remove_room_member(room_id, riot_id):
    _exec("DELETE FROM room_members WHERE room_id=? AND riot_id=?", (room_id, riot_id))


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------

ACHIEVEMENT_DEFS = {
    "first_login":      {"icon": "🎉", "name": "Bienvenido al hospital", "desc": "Primer login"},
    "first_bet":        {"icon": "🎲", "name": "First Blood Apostada", "desc": "Crea tu primera apuesta"},
    "first_bet_won":    {"icon": "💰", "name": "Apostador Iniciado", "desc": "Gana tu primera apuesta"},
    "ten_bets_won":     {"icon": "🏆", "name": "Bookie", "desc": "Gana 10 apuestas"},
    "fifty_bets_won":   {"icon": "👑", "name": "Casa de Apuestas", "desc": "Gana 50 apuestas"},
    "first_prediction": {"icon": "🔮", "name": "Vidente", "desc": "Primera predicción acertada"},
    "ten_predictions":  {"icon": "🎯", "name": "Predictor", "desc": "10 predicciones acertadas"},
    "streak_5":         {"icon": "🔥", "name": "Racha de Fuego", "desc": "5 predicciones acertadas seguidas"},
    "tumor_hunter":     {"icon": "☢", "name": "Cazador de Tumores", "desc": "Detecta 50 worst players"},
    "richie_rich":      {"icon": "💎", "name": "Richie Rich", "desc": "Acumula 1000 TC"},
    "social":           {"icon": "👥", "name": "Sociable", "desc": "Añade 3 amigos"},
    "all_in":           {"icon": "🎰", "name": "All In", "desc": "Apuesta todo tu balance en una sola"},
    "comeback_kid":     {"icon": "🔄", "name": "Comeback Kid", "desc": "Recuperar de 0 a 500 TC"},
}


def has_achievement(user_id, badge):
    cur = _exec("SELECT 1 FROM user_achievements WHERE user_id=? AND badge=?", (user_id, badge))
    return bool(cur.fetchone())


def unlock_achievement(user_id, badge):
    """Desbloquea un badge si no lo tenía. Empuja notificación + recompensa de TC."""
    if badge not in ACHIEVEMENT_DEFS:
        return False
    if has_achievement(user_id, badge):
        return False
    _exec(
        "INSERT INTO user_achievements (user_id, badge, unlocked_at) VALUES (?, ?, ?)",
        (user_id, badge, time.time()),
    )
    info = ACHIEVEMENT_DEFS[badge]
    add_currency(user_id, 50, f"achievement: {badge}")
    push_notification(
        user_id,
        notif_type="achievement",
        title=f"{info['icon']} Achievement: {info['name']}",
        body=f"{info['desc']} · +50 TC",
        link="#/achievements",
        icon=info['icon'],
    )
    return True


def list_achievements(user_id):
    cur = _exec(
        "SELECT badge, unlocked_at FROM user_achievements WHERE user_id=?",
        (user_id,),
    )
    rows = cur.fetchall()
    unlocked = {r[0]: r[1] for r in rows}
    out = []
    for badge, info in ACHIEVEMENT_DEFS.items():
        out.append({
            "badge": badge,
            "icon": info["icon"],
            "name": info["name"],
            "desc": info["desc"],
            "unlocked": badge in unlocked,
            "unlocked_at": unlocked.get(badge),
        })
    return out


def evaluate_achievements(user_id):
    """Recalcula achievements basándose en el estado actual del user.
    Llamar tras eventos clave (bet won, prediction correct, etc)."""
    user = get_user_by_id(user_id)
    if not user:
        return

    # First login
    unlock_achievement(user_id, "first_login")

    # Currency milestones
    if user["currency"] >= 1000:
        unlock_achievement(user_id, "richie_rich")

    # Bets stats
    cur = _exec(
        """SELECT COUNT(*) FROM bets
           WHERE status='resolved' AND winner_side IS NOT NULL
           AND (
                (creator_user_id=? AND creator_side=winner_side)
                OR (taker_user_id=? AND creator_side<>winner_side)
           )""",
        (user_id, user_id),
    )
    won = cur.fetchone()[0] or 0
    if won >= 1: unlock_achievement(user_id, "first_bet_won")
    if won >= 10: unlock_achievement(user_id, "ten_bets_won")
    if won >= 50: unlock_achievement(user_id, "fifty_bets_won")

    # Bet count
    cur = _exec("SELECT COUNT(*) FROM bets WHERE creator_user_id=?", (user_id,))
    if (cur.fetchone()[0] or 0) >= 1:
        unlock_achievement(user_id, "first_bet")

    # Friends count
    cur = _exec(
        "SELECT COUNT(*) FROM friendships WHERE status='accepted' AND (requester_id=? OR target_id=?)",
        (user_id, user_id),
    )
    if (cur.fetchone()[0] or 0) >= 3:
        unlock_achievement(user_id, "social")


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    "public_profile": 1,
    "allow_friend_requests": 1,
    "notif_bets": 1,
    "notif_friends": 1,
}


def get_settings(user_id):
    cur = _exec(
        "SELECT public_profile, allow_friend_requests, notif_bets, notif_friends FROM user_settings WHERE user_id=?",
        (user_id,),
    )
    row = cur.fetchone()
    if not row:
        return dict(DEFAULT_SETTINGS)
    return {
        "public_profile": bool(row[0]),
        "allow_friend_requests": bool(row[1]),
        "notif_bets": bool(row[2]),
        "notif_friends": bool(row[3]),
    }


def save_settings(user_id, **kwargs):
    current = get_settings(user_id)
    current.update({k: int(bool(v)) for k, v in kwargs.items() if k in DEFAULT_SETTINGS})
    cur = _exec("SELECT 1 FROM user_settings WHERE user_id=?", (user_id,))
    if cur.fetchone():
        _exec(
            """UPDATE user_settings SET public_profile=?, allow_friend_requests=?,
               notif_bets=?, notif_friends=?, updated_at=? WHERE user_id=?""",
            (current["public_profile"], current["allow_friend_requests"],
             current["notif_bets"], current["notif_friends"], time.time(), user_id),
        )
    else:
        _exec(
            """INSERT INTO user_settings (user_id, public_profile, allow_friend_requests,
               notif_bets, notif_friends, updated_at) VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, current["public_profile"], current["allow_friend_requests"],
             current["notif_bets"], current["notif_friends"], time.time()),
        )
    return current


def find_user_by_riot_id_public(riot_id):
    """Devuelve user info público si tiene public_profile=1."""
    cur = _exec(
        """SELECT u.id, u.discord_id, u.discord_username, u.discord_avatar, u.riot_id, u.currency, u.created_at
           FROM users u
           LEFT JOIN user_settings s ON s.user_id = u.id
           WHERE u.riot_id=?
             AND COALESCE(s.public_profile, 1) = 1""",
        (riot_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "discord_id": row[1],
        "username": row[2],
        "avatar": row[3],
        "riot_id": row[4],
        "currency": row[5],
        "created_at": row[6],
    }


def get_users_brief(user_ids):
    """Resumen barato de varios users (id → username, avatar). Usado en la UI de bets."""
    if not user_ids:
        return {}
    user_ids = [u for u in set(user_ids) if u is not None]
    if not user_ids:
        return {}
    placeholders = ",".join("?" for _ in user_ids)
    cur = _exec(
        f"SELECT id, discord_id, discord_username, discord_avatar FROM users WHERE id IN ({placeholders})",
        tuple(user_ids),
    )
    out = {}
    for row in cur.fetchall():
        out[row[0]] = {
            "id": row[0],
            "discord_id": row[1],
            "username": row[2],
            "avatar": row[3],
        }
    return out
