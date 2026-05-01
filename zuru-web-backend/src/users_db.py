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
    # Migración stat bets en SQLite: PRAGMA + ALTER TABLE selectivo.
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(bets)").fetchall()}
    new_cols = [
        ("bet_kind", "TEXT NOT NULL DEFAULT 'match'"),
        ("target_puuid", "TEXT"),
        ("target_name", "TEXT"),
        ("stat_type", "TEXT"),
        ("threshold", "REAL"),
        ("stat_actual", "REAL"),
    ]
    for name, ddl in new_cols:
        if name not in existing_cols:
            try:
                conn.execute(f"ALTER TABLE bets ADD COLUMN {name} {ddl}")
            except Exception:
                pass
    # 1v1 challenges: dos users, cada uno juega su propia partida, se comparan stats.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            share_code TEXT UNIQUE NOT NULL,
            challenger_user_id INTEGER NOT NULL,
            challenger_puuid TEXT NOT NULL,
            challenged_user_id INTEGER,
            challenged_puuid TEXT,
            stat_type TEXT NOT NULL,
            comparison TEXT NOT NULL DEFAULT 'higher_wins',
            amount INTEGER NOT NULL,
            challenger_match_id TEXT,
            challenger_value REAL,
            challenged_match_id TEXT,
            challenged_value REAL,
            status TEXT NOT NULL DEFAULT 'open',
            winner_user_id INTEGER,
            created_at REAL NOT NULL,
            accepted_at REAL,
            resolved_at REAL,
            expires_at REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_challenges_status ON challenges(status, created_at)")


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
    # Migración stat bets: añade columnas idempotentemente.
    for col_def in [
        "bet_kind TEXT NOT NULL DEFAULT 'match'",
        "target_puuid TEXT",
        "target_name TEXT",
        "stat_type TEXT",
        "threshold DOUBLE PRECISION",
        "stat_actual DOUBLE PRECISION",
    ]:
        try:
            cur.execute(f"ALTER TABLE bets ADD COLUMN IF NOT EXISTS {col_def}")
        except Exception:
            pass
    cur.execute("""
        CREATE TABLE IF NOT EXISTS challenges (
            id SERIAL PRIMARY KEY,
            share_code TEXT UNIQUE NOT NULL,
            challenger_user_id INTEGER NOT NULL REFERENCES users(id),
            challenger_puuid TEXT NOT NULL,
            challenged_user_id INTEGER REFERENCES users(id),
            challenged_puuid TEXT,
            stat_type TEXT NOT NULL,
            comparison TEXT NOT NULL DEFAULT 'higher_wins',
            amount INTEGER NOT NULL,
            challenger_match_id TEXT,
            challenger_value DOUBLE PRECISION,
            challenged_match_id TEXT,
            challenged_value DOUBLE PRECISION,
            status TEXT NOT NULL DEFAULT 'open',
            winner_user_id INTEGER REFERENCES users(id),
            created_at DOUBLE PRECISION NOT NULL,
            accepted_at DOUBLE PRECISION,
            resolved_at DOUBLE PRECISION,
            expires_at DOUBLE PRECISION
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_challenges_status ON challenges(status, created_at)")
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


VALID_STAT_TYPES = {"kills", "deaths", "assists", "kda"}


def create_bet(
    creator_user_id, match_id, game_id, side, amount,
    bet_kind="match", target_puuid=None, target_name=None,
    stat_type=None, threshold=None,
):
    """Crea una bet, escrowa el amount del creator. Devuelve dict o None si fallo.

    bet_kind='match': side es 'blue'|'red', sin params extra.
    bet_kind='stat':  side es 'over'|'under', target_puuid + stat_type + threshold obligatorios.
    """
    if amount <= 0:
        return None

    if bet_kind == "match":
        if side not in ("blue", "red"):
            return None
    elif bet_kind == "stat":
        if side not in ("over", "under"):
            return None
        if not target_puuid or stat_type not in VALID_STAT_TYPES or threshold is None:
            return None
        try:
            threshold = float(threshold)
        except Exception:
            return None
    else:
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
        add_currency(creator_user_id, amount, "bet refund (code collision)")
        return None

    bet_id = _exec_returning(
        """INSERT INTO bets (share_code, match_id, game_id, creator_user_id,
            creator_side, amount, status, created_at,
            bet_kind, target_puuid, target_name, stat_type, threshold)
            VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?)""",
        (code, match_id, game_id, creator_user_id, side, amount, time.time(),
         bet_kind, target_puuid, target_name, stat_type, threshold),
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
    """Resuelve TODAS las bets de tipo 'match' matched de ese match_id."""
    cur = _exec(
        "SELECT id FROM bets WHERE match_id=? AND status='matched' AND bet_kind='match'",
        (match_id,),
    )
    rows = cur.fetchall()
    return [resolve_bet(r[0], winner_side) for r in rows]


def resolve_stat_bet(bet_id, actual_value):
    """Resuelve una stat bet matched. actual_value es la stat real del target_puuid.

    Compara actual vs threshold según el creator_side ('over'/'under').
    Empate (actual == threshold) → push (refund a ambos).
    """
    bet = get_bet_by_id(bet_id)
    if not bet or bet["status"] != "matched" or bet["bet_kind"] != "stat":
        return None
    if bet["threshold"] is None or actual_value is None:
        return None

    # Determinar ganador
    creator_won = None
    if actual_value > bet["threshold"]:
        creator_won = (bet["creator_side"] == "over")
    elif actual_value < bet["threshold"]:
        creator_won = (bet["creator_side"] == "under")
    # exact tie → push (refund)

    if creator_won is None:
        # Push: refund a ambos
        _exec(
            "UPDATE bets SET status='resolved', resolved_at=?, stat_actual=? WHERE id=?",
            (time.time(), float(actual_value), bet_id),
        )
        add_currency(bet["creator_user_id"], bet["amount"], f"bet push refund · {bet['share_code']}")
        if bet["taker_user_id"]:
            add_currency(bet["taker_user_id"], bet["amount"], f"bet push refund · {bet['share_code']}")
        return get_bet_by_id(bet_id)

    winner_user_id = bet["creator_user_id"] if creator_won else bet["taker_user_id"]
    loser_user_id = bet["taker_user_id"] if creator_won else bet["creator_user_id"]
    if winner_user_id is None:
        return None
    payout = bet["amount"] * 2
    add_currency(winner_user_id, payout, f"stat bet won · {bet['share_code']}")
    # Para stat bets, winner_side contiene 'over'|'under' del lado ganador.
    winner_side_label = bet["creator_side"] if creator_won else ("over" if bet["creator_side"] == "under" else "under")
    _exec(
        "UPDATE bets SET status='resolved', winner_side=?, resolved_at=?, stat_actual=? WHERE id=?",
        (winner_side_label, time.time(), float(actual_value), bet_id),
    )
    try:
        push_notification(
            user_id=winner_user_id,
            notif_type="bet_won",
            title=f"Ganaste {payout} TC",
            body=f"{bet['target_name'] or '?'} hizo {actual_value} {bet['stat_type']} (target {bet['threshold']})",
            link="#/bets", icon="✅",
        )
        if loser_user_id:
            push_notification(
                user_id=loser_user_id,
                notif_type="bet_lost",
                title=f"Perdiste {bet['amount']} TC",
                body=f"{bet['target_name'] or '?'} hizo {actual_value} {bet['stat_type']}",
                link="#/bets", icon="❌",
            )
    except Exception:
        pass
    try:
        evaluate_achievements(winner_user_id)
        if loser_user_id:
            evaluate_achievements(loser_user_id)
    except Exception:
        pass
    return get_bet_by_id(bet_id)


def list_stat_bets_for_match(match_id):
    """Devuelve stat bets matched de ese match_id (para resolver tras la partida)."""
    cur = _exec(
        f"SELECT {_BET_COLS} FROM bets WHERE match_id=? AND status='matched' AND bet_kind='stat'",
        (match_id,),
    )
    return [_row_to_bet(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# 1v1 Challenges: dos users, cada uno juega su propia partida, se comparan stats
# ---------------------------------------------------------------------------

VALID_CHALLENGE_STATS = {"kills", "deaths", "assists", "kda", "cs", "gold", "damage"}
CHALLENGE_DEFAULT_TTL = 24 * 3600  # 24h para aceptar y jugar

_CHALLENGE_COLS = (
    "id, share_code, challenger_user_id, challenger_puuid, "
    "challenged_user_id, challenged_puuid, stat_type, comparison, amount, "
    "challenger_match_id, challenger_value, challenged_match_id, challenged_value, "
    "status, winner_user_id, created_at, accepted_at, resolved_at, expires_at"
)


def _row_to_challenge(row):
    if not row:
        return None
    return {
        "id": row[0],
        "share_code": row[1],
        "challenger_user_id": row[2],
        "challenger_puuid": row[3],
        "challenged_user_id": row[4],
        "challenged_puuid": row[5],
        "stat_type": row[6],
        "comparison": row[7],
        "amount": row[8],
        "challenger_match_id": row[9],
        "challenger_value": row[10],
        "challenged_match_id": row[11],
        "challenged_value": row[12],
        "status": row[13],
        "winner_user_id": row[14],
        "created_at": row[15],
        "accepted_at": row[16],
        "resolved_at": row[17],
        "expires_at": row[18],
    }


def create_challenge(challenger_user_id, stat_type, amount, comparison="higher_wins"):
    """Crea un challenge 1v1. Escrowa el amount del challenger.

    'higher_wins' es lo natural para kills/assists/kda/cs/gold/damage.
    'lower_wins' es lo natural para deaths.
    """
    if amount <= 0 or stat_type not in VALID_CHALLENGE_STATS:
        return None
    if comparison not in ("higher_wins", "lower_wins"):
        return None
    user = get_user_by_id(challenger_user_id)
    if not user or not user.get("riot_puuid"):
        return None
    new_balance = add_currency(challenger_user_id, -amount, "challenge escrow")
    if new_balance is None:
        return None  # saldo insuficiente
    code = None
    for _ in range(10):
        candidate = _generate_bet_code()
        cur = _exec("SELECT id FROM challenges WHERE share_code=?", (candidate,))
        if not cur.fetchone():
            code = candidate
            break
    if not code:
        add_currency(challenger_user_id, amount, "challenge refund (code collision)")
        return None
    now = time.time()
    cid = _exec_returning(
        """INSERT INTO challenges (
            share_code, challenger_user_id, challenger_puuid,
            stat_type, comparison, amount, status, created_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
        (code, challenger_user_id, user["riot_puuid"], stat_type,
         comparison, amount, now, now + CHALLENGE_DEFAULT_TTL),
    )
    return get_challenge_by_id(cid)


def accept_challenge(challenged_user_id, share_code):
    """Acepta un challenge. Escrowa el amount. Devuelve dict o str de error."""
    ch = get_challenge_by_code(share_code)
    if not ch:
        return "Challenge no encontrado"
    if ch["status"] != "open":
        return f"Challenge ya {ch['status']}"
    if ch["challenger_user_id"] == challenged_user_id:
        return "No puedes aceptar tu propio challenge"
    if ch["expires_at"] and time.time() > ch["expires_at"]:
        # Auto-expirar y devolver stake al challenger
        _exec("UPDATE challenges SET status='expired' WHERE id=?", (ch["id"],))
        add_currency(ch["challenger_user_id"], ch["amount"], f"challenge expired refund · {ch['share_code']}")
        return "Challenge expirado"
    user = get_user_by_id(challenged_user_id)
    if not user or not user.get("riot_puuid"):
        return "Necesitas vincular tu Riot ID antes de aceptar challenges"
    new_balance = add_currency(challenged_user_id, -ch["amount"], "challenge escrow")
    if new_balance is None:
        return "Saldo insuficiente"
    _exec(
        "UPDATE challenges SET challenged_user_id=?, challenged_puuid=?, status='accepted', accepted_at=? WHERE id=?",
        (challenged_user_id, user["riot_puuid"], time.time(), ch["id"]),
    )
    try:
        push_notification(
            user_id=ch["challenger_user_id"],
            notif_type="challenge_accepted",
            title="¡Challenge aceptado!",
            body=f"{user['username']} aceptó tu challenge {ch['share_code']}",
            link="#/challenges",
            icon="⚔",
        )
    except Exception:
        pass
    return get_challenge_by_id(ch["id"])


def cancel_challenge(challenger_user_id, challenge_id):
    """Cancela un challenge abierto (sin acceptante). Refund."""
    ch = get_challenge_by_id(challenge_id)
    if not ch or ch["status"] != "open" or ch["challenger_user_id"] != challenger_user_id:
        return None
    _exec("UPDATE challenges SET status='cancelled' WHERE id=?", (challenge_id,))
    add_currency(challenger_user_id, ch["amount"], f"challenge cancelled refund · {ch['share_code']}")
    return ch


def submit_challenge_match(user_id, share_code, match_id, value):
    """Submit el match jugado por uno de los participantes. Si ambos han enviado, resuelve.

    `value` es la stat ya extraída del match (kills/deaths/etc) — el caller (main.py) la
    calcula tras un riot_get del match.
    """
    ch = get_challenge_by_code(share_code)
    if not ch:
        return "Challenge no encontrado"
    if ch["status"] != "accepted":
        return f"Challenge en estado {ch['status']}, no se puede submit"

    if user_id == ch["challenger_user_id"]:
        if ch["challenger_match_id"]:
            return "Ya enviaste tu partida para este challenge"
        _exec(
            "UPDATE challenges SET challenger_match_id=?, challenger_value=? WHERE id=?",
            (match_id, float(value), ch["id"]),
        )
    elif user_id == ch["challenged_user_id"]:
        if ch["challenged_match_id"]:
            return "Ya enviaste tu partida para este challenge"
        _exec(
            "UPDATE challenges SET challenged_match_id=?, challenged_value=? WHERE id=?",
            (match_id, float(value), ch["id"]),
        )
    else:
        return "No formas parte de este challenge"

    # Refresh + comprobar resolución
    ch = get_challenge_by_id(ch["id"])
    if ch["challenger_value"] is not None and ch["challenged_value"] is not None:
        _resolve_challenge(ch)
    return get_challenge_by_id(ch["id"])


def _resolve_challenge(ch):
    """Determina ganador y paga. Empate → push (refund a ambos)."""
    cv = ch["challenger_value"]
    dv = ch["challenged_value"]
    higher = ch["comparison"] == "higher_wins"
    winner = None
    if cv > dv:
        winner = ch["challenger_user_id"] if higher else ch["challenged_user_id"]
    elif cv < dv:
        winner = ch["challenged_user_id"] if higher else ch["challenger_user_id"]
    # else: tie → push

    if winner is None:
        # Refund ambos
        _exec(
            "UPDATE challenges SET status='resolved', resolved_at=? WHERE id=?",
            (time.time(), ch["id"]),
        )
        add_currency(ch["challenger_user_id"], ch["amount"], f"challenge push refund · {ch['share_code']}")
        add_currency(ch["challenged_user_id"], ch["amount"], f"challenge push refund · {ch['share_code']}")
        return
    payout = ch["amount"] * 2
    add_currency(winner, payout, f"challenge won · {ch['share_code']}")
    loser = ch["challenged_user_id"] if winner == ch["challenger_user_id"] else ch["challenger_user_id"]
    _exec(
        "UPDATE challenges SET status='resolved', winner_user_id=?, resolved_at=? WHERE id=?",
        (winner, time.time(), ch["id"]),
    )
    try:
        push_notification(
            user_id=winner, notif_type="challenge_won",
            title=f"Ganaste challenge · +{payout} TC",
            body=f"{ch['stat_type']}: {cv if winner == ch['challenger_user_id'] else dv} vs {dv if winner == ch['challenger_user_id'] else cv}",
            link="#/challenges", icon="🏆",
        )
        push_notification(
            user_id=loser, notif_type="challenge_lost",
            title=f"Perdiste challenge · -{ch['amount']} TC",
            body=f"{ch['share_code']}",
            link="#/challenges", icon="❌",
        )
    except Exception:
        pass


def get_challenge_by_id(cid):
    cur = _exec(f"SELECT {_CHALLENGE_COLS} FROM challenges WHERE id=?", (cid,))
    return _row_to_challenge(cur.fetchone())


def get_challenge_by_code(code):
    cur = _exec(f"SELECT {_CHALLENGE_COLS} FROM challenges WHERE share_code=?", (code,))
    return _row_to_challenge(cur.fetchone())


def list_open_challenges(limit=50):
    cur = _exec(
        f"SELECT {_CHALLENGE_COLS} FROM challenges WHERE status='open' ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    return [_row_to_challenge(r) for r in cur.fetchall()]


def list_user_challenges(user_id, limit=50):
    cur = _exec(
        f"""SELECT {_CHALLENGE_COLS} FROM challenges
            WHERE challenger_user_id=? OR challenged_user_id=?
            ORDER BY created_at DESC LIMIT ?""",
        (user_id, user_id, limit),
    )
    return [_row_to_challenge(r) for r in cur.fetchall()]


def get_bet_by_id(bet_id):
    cur = _exec(
        f"SELECT {_BET_COLS} FROM bets WHERE id=?",
        (bet_id,),
    )
    row = cur.fetchone()
    return _row_to_bet(row) if row else None


def get_bet_by_code(share_code):
    cur = _exec(
        f"SELECT {_BET_COLS} FROM bets WHERE share_code=?",
        (share_code,),
    )
    row = cur.fetchone()
    return _row_to_bet(row) if row else None


def list_open_bets(limit=50):
    """Bets abiertas que cualquiera puede aceptar. Las más recientes primero."""
    cur = _exec(
        f"SELECT {_BET_COLS} FROM bets WHERE status='open' ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    return [_row_to_bet(r) for r in rows]


# ---------------------------------------------------------------------------
# Leaderboards
# ---------------------------------------------------------------------------

def leaderboard_top_currency(limit=20):
    cur = _exec(
        """SELECT id, discord_id, discord_username, discord_avatar, currency, riot_id
           FROM users
           ORDER BY currency DESC LIMIT ?""",
        (limit,),
    )
    rows = cur.fetchall()
    return [{"user_id": r[0], "discord_id": r[1], "username": r[2], "avatar": r[3], "currency": r[4], "riot_id": r[5]} for r in rows]


def leaderboard_top_bet_winners(limit=20):
    """Top users por bets ganadas."""
    cur = _exec(
        """SELECT u.id, u.discord_id, u.discord_username, u.discord_avatar, u.currency,
                  COUNT(*) AS won_count,
                  SUM(b.amount) AS net_won
           FROM bets b
           JOIN users u ON u.id = (
                CASE WHEN b.creator_side = b.winner_side THEN b.creator_user_id ELSE b.taker_user_id END
           )
           WHERE b.status = 'resolved'
           GROUP BY u.id, u.discord_id, u.discord_username, u.discord_avatar, u.currency
           ORDER BY won_count DESC, net_won DESC
           LIMIT ?""",
        (limit,),
    )
    rows = cur.fetchall()
    return [{
        "user_id": r[0], "discord_id": r[1], "username": r[2], "avatar": r[3], "currency": r[4],
        "won_count": r[5], "net_won": r[6],
    } for r in rows]


def get_user_bets(user_id, limit=50):
    cur = _exec(
        f"""SELECT {_BET_COLS}
           FROM bets
           WHERE creator_user_id=? OR taker_user_id=?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, user_id, limit),
    )
    rows = cur.fetchall()
    return [_row_to_bet(r) for r in rows]


_BET_COLS = (
    "id, share_code, match_id, game_id, creator_user_id, creator_side, "
    "amount, taker_user_id, status, winner_side, resolved_at, created_at, "
    "bet_kind, target_puuid, target_name, stat_type, threshold, stat_actual"
)


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
        "bet_kind": row[12] if len(row) > 12 else "match",
        "target_puuid": row[13] if len(row) > 13 else None,
        "target_name": row[14] if len(row) > 14 else None,
        "stat_type": row[15] if len(row) > 15 else None,
        "threshold": row[16] if len(row) > 16 else None,
        "stat_actual": row[17] if len(row) > 17 else None,
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
