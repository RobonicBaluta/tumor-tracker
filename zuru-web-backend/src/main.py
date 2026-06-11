import json
import os
import threading
import time
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from config import (
    headers, ACCOUNT_BY_RIOT_ID_URL, MATCHES_BY_PUUID_URL,
    MATCH_DETAILS_URL, MATCHES_COUNT, QUEUE_RANKED_SOLO, QUEUE_RANKED_FLEX,
    RANKED_QUEUES, BETTING_ALLOWED_QUEUES, WORST_KDA_THRESHOLD,
    LEAGUE_ENTRIES_BY_PUUID_URL, ACTIVE_GAME_URL, RIOT_BASE_URL, CHAMPION_MASTERY_URL,
    RIOT_PLATFORM_URL, PLATFORM_HOSTS, platform_url_for,
    league_url, spectator_url, mastery_url,
    queue_name, is_ranked_queue, allows_betting,
)
from riot_infra import riot_get as _riot_get, cache_stats
from tumor_engine import (
    compute_match_tumor_from_stats as _engine_match_score,
    compute_match_tumor as _engine_match_score_from_participant,
    compute_prior_tumor as _engine_prior,
    compute_team_tumor as _engine_team,
    predict_team_outcome as _engine_predict,
)
import auth as _auth
import users_db as _users
import bravery_engine as _bravery
from flask import redirect


def riot_get(url, max_retries=4):
    return _riot_get(url, headers=headers, max_retries=max_retries)


def detect_platform(puuid):
    """Auto-detecta la plataforma del jugador mirando el prefijo de su último match ID.
    Devuelve la URL base de la plataforma (e.g. https://eun1.api.riotgames.com).
    Fallback a EUW si no se puede determinar."""
    ids_res = riot_get(f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count=1")
    if ids_res.status_code == 200:
        ids = ids_res.json()
        if ids:
            prefix = ids[0].split("_")[0].upper()
            host = PLATFORM_HOSTS.get(prefix)
            if host:
                return host
    return RIOT_PLATFORM_URL


import uuid

# Progress store para jobs async (liveGame, backtest, analytics)
_jobs = {}
_jobs_lock = threading.Lock()


def job_create():
    jid = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[jid] = {
            "status": "running",
            "step": "Iniciando...",
            "progress": 0,
            "total": 1,
            "result": None,
            "error": None,
            "ts": time.time(),
        }
    return jid


def job_update(jid, **kwargs):
    with _jobs_lock:
        if jid in _jobs:
            _jobs[jid].update(kwargs)
            _jobs[jid]["ts"] = time.time()


def job_get(jid):
    with _jobs_lock:
        return dict(_jobs.get(jid) or {})


def job_cleanup():
    """Quita jobs viejos del store (>10 min)."""
    cutoff = time.time() - 600
    with _jobs_lock:
        for jid in list(_jobs.keys()):
            if _jobs[jid]["ts"] < cutoff:
                del _jobs[jid]


# Background prefetcher: guardia para no lanzar N threads por el mismo puuid
_prefetch_in_progress = set()
_prefetch_lock = threading.Lock()


def warmup_prefetch(puuid, count=30):
    """Lanza un thread en background que cachea los últimos `count` match details
    del jugador. Silencioso, pasa por el token bucket del riot_get."""
    with _prefetch_lock:
        if puuid in _prefetch_in_progress:
            return
        _prefetch_in_progress.add(puuid)

    def _worker():
        try:
            ids_res = riot_get(f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count={count}&queue={QUEUE_RANKED_SOLO}")
            if ids_res.status_code != 200:
                return
            for mid in ids_res.json() or []:
                riot_get(f"{MATCH_DETAILS_URL}/{mid}")  # cache hit si ya existe
        except Exception:
            pass
        finally:
            with _prefetch_lock:
                _prefetch_in_progress.discard(puuid)

    threading.Thread(target=_worker, daemon=True).start()


def _extract_perks(perks):
    """Extrae las runas principales (keystone + primary/secondary tree) del spec."""
    if not perks or not isinstance(perks, dict):
        return None
    styles = perks.get("perkStyles") or []
    ids = perks.get("perkIds") or []
    keystone = ids[0] if ids else None
    primary = next((s.get("style") for s in styles if s.get("description") == "primaryStyle"), None)
    secondary = next((s.get("style") for s in styles if s.get("description") == "subStyle"), None)
    return {"keystone": keystone, "primary": primary, "secondary": secondary}


_champ_id_name_cache = {}

def champ_id_to_name(champ_id):
    """Resuelve championId → 'Yasuo' usando DDragon (cacheado en memoria)."""
    if not champ_id:
        return ""
    if not _champ_id_name_cache:
        try:
            v_res = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=5)
            version = v_res.json()[0] if v_res.status_code == 200 else "15.1.1"
            c_res = requests.get(
                f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json",
                timeout=5,
            )
            if c_res.status_code == 200:
                for key, info in c_res.json()["data"].items():
                    _champ_id_name_cache[int(info["key"])] = key
        except Exception:
            pass
    return _champ_id_name_cache.get(int(champ_id), "")

app = Flask(__name__)
# CORS restringible vía CORS_ORIGINS env var ("*" por defecto en dev).
_cors_origins = os.getenv("CORS_ORIGINS", "*")
if _cors_origins == "*":
    CORS(app)
else:
    CORS(app, origins=[o.strip() for o in _cors_origins.split(",") if o.strip()])

# Healthcheck para Render.
@app.route("/healthz")
def healthz():
    return {"ok": True}


@app.route("/healthz/redis")
def healthz_redis():
    """Devuelve estado del cliente Redis. 200 incluso si está caído (no-op fallback)."""
    try:
        from redis_client import is_enabled, r
    except Exception:
        return {"enabled": False, "available": False, "error": "import_failed"}
    if not is_enabled() or r is None:
        return {"enabled": False, "available": False}
    try:
        pong = r.ping()
        return {"enabled": True, "available": bool(pong)}
    except Exception as exc:
        return {"enabled": True, "available": False, "error": str(exc)[:120]}

# Directorio de datos: en Render se monta /var/data, en dev usa src/.
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
LIVE_CACHE_FILE = os.path.join(DATA_DIR, "live_game_cache.json")
LIVE_CACHE_TTL = 6 * 3600  # 6 horas para éxitos
LIVE_CACHE_TTL_FAIL = 30 * 60  # 30 min para fallos (rate limit, etc)
LIVE_CACHE_SCHEMA_VERSION = 4  # bumped tras rewrite del tumor_engine


def load_live_cache():
    if not os.path.exists(LIVE_CACHE_FILE):
        return {}
    try:
        with open(LIVE_CACHE_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        meta = data.get("__meta__") or {}
        if meta.get("version") != LIVE_CACHE_SCHEMA_VERSION:
            return {"__meta__": {"version": LIVE_CACHE_SCHEMA_VERSION}}
        return data
    except Exception:
        return {"__meta__": {"version": LIVE_CACHE_SCHEMA_VERSION}}


def save_live_cache(cache):
    try:
        if "__meta__" not in cache:
            cache["__meta__"] = {"version": LIVE_CACHE_SCHEMA_VERSION}
        with open(LIVE_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass


RECENT_FILE = os.path.join(DATA_DIR, "recent_summoners.json")
LEADERBOARD_FILE = os.path.join(DATA_DIR, "leaderboard.json")
SAVED_ACCOUNTS_FILE = os.path.join(DATA_DIR, "saved_accounts.json")
WATCH_LIST_FILE = os.path.join(DATA_DIR, "watch_list.json")
PREDICTIONS_FILE = os.path.join(DATA_DIR, "predictions.json")
BLACKLIST_FILE = os.path.join(DATA_DIR, "champion_blacklist.json")


def load_blacklist():
    if not os.path.exists(BLACKLIST_FILE):
        return {}
    try:
        with open(BLACKLIST_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_blacklist(data):
    with open(BLACKLIST_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False)


import sqlite3 as _sqlite3
_PRED_DB_PATH = os.path.join(DATA_DIR, "predictions.db")
_pred_conn = None


def _pred_db():
    global _pred_conn
    if _pred_conn is None:
        _pred_conn = _sqlite3.connect(_PRED_DB_PATH, check_same_thread=False, isolation_level=None)
        _pred_conn.execute("PRAGMA journal_mode=WAL")
        _pred_conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                match_id TEXT NOT NULL,
                viewer_puuid TEXT NOT NULL,
                viewer_name TEXT,
                viewer_team TEXT,
                blue_sum REAL, red_sum REAL,
                blue_score REAL, red_score REAL,
                predicted_winner TEXT,
                confidence INTEGER,
                created_at REAL,
                resolved INTEGER DEFAULT 0,
                actual_winner TEXT,
                correct INTEGER,
                PRIMARY KEY (match_id, viewer_puuid)
            )
        """)
        if os.path.exists(PREDICTIONS_FILE):
            try:
                with open(PREDICTIONS_FILE, "r") as f:
                    old = json.load(f)
                for p in old:
                    _pred_conn.execute(
                        """INSERT OR IGNORE INTO predictions
                        (match_id, viewer_puuid, viewer_name, viewer_team,
                         blue_sum, red_sum, blue_score, red_score,
                         predicted_winner, confidence, created_at,
                         resolved, actual_winner, correct)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            p.get("match_id"), p.get("viewer_puuid"),
                            p.get("viewer_name"), p.get("viewer_team"),
                            p.get("blue_sum"), p.get("red_sum"),
                            p.get("blue_sum"), p.get("red_sum"),
                            p.get("predicted_winner"), p.get("confidence", 0),
                            p.get("created_at", 0),
                            1 if p.get("resolved") else 0,
                            p.get("actual_winner"),
                            1 if p.get("correct") else (0 if p.get("correct") is False else None),
                        ),
                    )
                os.rename(PREDICTIONS_FILE, PREDICTIONS_FILE + ".migrated")
            except Exception:
                pass
    # Limpieza one-shot al inicio: borrar predicciones que tienen scores en la
    # escala vieja (negativos o > 100). Tras el rewrite del tumor_engine ya no
    # son comparables con las nuevas. Se ejecuta cada vez que se abre la DB,
    # es idempotente.
    try:
        _pred_conn.execute(
            "DELETE FROM predictions WHERE blue_score < 0 OR red_score < 0"
        )
    except Exception:
        pass
    # Tabla para guardar snapshots del live: cuando miras una partida en vivo,
    # se persisten los priors + predicción para no recalcular en matchDetail.
    _pred_conn.execute("""
        CREATE TABLE IF NOT EXISTS live_snapshots (
            match_id TEXT PRIMARY KEY,
            snapshot TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    # Tabla de logs detallados por predicción: se usa para auditar y afinar
    # empíricamente el modelo (mediante /tuningReport).
    # Cache de priors por jugador — independiente del champion. Se rellena
    # al procesar live games / backtests / overview, y se reutiliza siempre
    # que no esté expirado. TTL más largo que el live cache porque el prior
    # depende del histórico, no del champ actual.
    _pred_conn.execute("""
        CREATE TABLE IF NOT EXISTS player_priors_cache (
            puuid TEXT PRIMARY KEY,
            tier TEXT,
            prior_tumor INTEGER,
            sample_size INTEGER,
            recent_avg INTEGER,
            recent_losses INTEGER,
            recent_wins INTEGER,
            is_tilted INTEGER DEFAULT 0,
            is_hotstreak INTEGER DEFAULT 0,
            likely_role TEXT,
            cached_at REAL NOT NULL
        )
    """)
    # Backtest histórico — cada partida replayed se persiste para acumular
    # datos empíricos. Deduplicado por (match_id, viewer_puuid).
    _pred_conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_logs (
            match_id TEXT NOT NULL,
            viewer_puuid TEXT NOT NULL,
            viewer_name TEXT,
            created_at REAL NOT NULL,
            predicted_winner TEXT,
            actual_winner TEXT,
            correct INTEGER,
            confidence INTEGER,
            median_diff REAL,
            sum_diff REAL,
            blue_team_tumor REAL,
            red_team_tumor REAL,
            blue_team_sum REAL,
            red_team_sum REAL,
            used_sum_tiebreaker INTEGER DEFAULT 0,
            blue_priors TEXT,
            red_priors TEXT,
            blue_roles TEXT,
            red_roles TEXT,
            PRIMARY KEY (match_id, viewer_puuid)
        )
    """)
    _pred_conn.execute("""
        CREATE TABLE IF NOT EXISTS prediction_logs (
            match_id TEXT NOT NULL,
            viewer_puuid TEXT NOT NULL,
            created_at REAL NOT NULL,
            -- Predicción
            predicted_winner TEXT,
            confidence INTEGER,
            blue_team_tumor REAL,
            red_team_tumor REAL,
            blue_team_sum REAL,
            red_team_sum REAL,
            median_diff REAL,
            sum_diff REAL,
            used_sum_tiebreaker INTEGER DEFAULT 0,
            -- Composición de cada equipo (priors individuales)
            blue_priors TEXT,      -- JSON array de ints
            red_priors TEXT,
            blue_roles TEXT,       -- JSON array de strings
            red_roles TEXT,
            blue_streamers INTEGER DEFAULT 0,
            red_streamers INTEGER DEFAULT 0,
            -- Resolución
            resolved INTEGER DEFAULT 0,
            actual_winner TEXT,
            correct INTEGER,
            resolved_at REAL,
            PRIMARY KEY (match_id, viewer_puuid)
        )
    """)
    return _pred_conn


def log_prediction(entry):
    """Graba una predicción con todo su detalle (priors por jugador, roles, sumas)."""
    db = _pred_db()
    db.execute(
        """INSERT OR REPLACE INTO prediction_logs (
            match_id, viewer_puuid, created_at,
            predicted_winner, confidence,
            blue_team_tumor, red_team_tumor, blue_team_sum, red_team_sum,
            median_diff, sum_diff, used_sum_tiebreaker,
            blue_priors, red_priors, blue_roles, red_roles,
            blue_streamers, red_streamers,
            resolved
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
        (
            entry["match_id"], entry["viewer_puuid"], entry.get("created_at", time.time()),
            entry.get("predicted_winner"), entry.get("confidence", 0),
            entry.get("blue_team_tumor"), entry.get("red_team_tumor"),
            entry.get("blue_team_sum"), entry.get("red_team_sum"),
            entry.get("median_diff"), entry.get("sum_diff"),
            1 if entry.get("used_sum_tiebreaker") else 0,
            json.dumps(entry.get("blue_priors") or []),
            json.dumps(entry.get("red_priors") or []),
            json.dumps(entry.get("blue_roles") or []),
            json.dumps(entry.get("red_roles") or []),
            entry.get("blue_streamers", 0),
            entry.get("red_streamers", 0),
        ),
    )


PRIOR_CACHE_TTL = 30 * 60  # 30 minutos: prior cambia poco entre partidas


def get_cached_prior(puuid):
    """Recupera prior cacheado del jugador si está fresco. Devuelve dict o None."""
    db = _pred_db()
    row = db.execute(
        """SELECT tier, prior_tumor, sample_size, recent_avg, recent_losses, recent_wins,
                  is_tilted, is_hotstreak, likely_role, cached_at
           FROM player_priors_cache WHERE puuid = ?""",
        (puuid,),
    ).fetchone()
    if not row:
        return None
    if time.time() - (row[9] or 0) > PRIOR_CACHE_TTL:
        return None
    return {
        "tier": row[0],
        "score": row[1],
        "champion_total_sample": row[2] or 0,
        "recent_avg_tumor": row[3] or 0,
        "recent_losses": row[4] or 0,
        "recent_wins": row[5] or 0,
        "is_tilted": bool(row[6]),
        "is_hotstreak": bool(row[7]),
        "likely_role": row[8] or "",
    }


def save_cached_prior(puuid, profile, tier):
    """Guarda el prior calculado para reutilización rápida."""
    db = _pred_db()
    db.execute(
        """INSERT OR REPLACE INTO player_priors_cache (
            puuid, tier, prior_tumor, sample_size, recent_avg,
            recent_losses, recent_wins, is_tilted, is_hotstreak, likely_role, cached_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            puuid, tier or "",
            profile.get("score"),
            profile.get("champion_total_sample", 0),
            profile.get("recent_avg_tumor", 0),
            profile.get("recent_losses", 0),
            profile.get("recent_wins", 0),
            1 if profile.get("is_tilted") else 0,
            1 if profile.get("is_hotstreak") else 0,
            profile.get("likely_role") or "",
            time.time(),
        ),
    )


def log_backtest_match(entry):
    """Guarda una fila de backtest (una partida replayed)."""
    db = _pred_db()
    db.execute(
        """INSERT OR REPLACE INTO backtest_logs (
            match_id, viewer_puuid, viewer_name, created_at,
            predicted_winner, actual_winner, correct, confidence,
            median_diff, sum_diff,
            blue_team_tumor, red_team_tumor, blue_team_sum, red_team_sum,
            used_sum_tiebreaker,
            blue_priors, red_priors, blue_roles, red_roles
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            entry["match_id"], entry["viewer_puuid"], entry.get("viewer_name"),
            entry.get("created_at", time.time()),
            entry.get("predicted_winner"), entry.get("actual_winner"),
            1 if entry.get("correct") else (0 if entry.get("correct") is False else None),
            entry.get("confidence", 0),
            entry.get("median_diff"), entry.get("sum_diff"),
            entry.get("blue_team_tumor"), entry.get("red_team_tumor"),
            entry.get("blue_team_sum"), entry.get("red_team_sum"),
            1 if entry.get("used_sum_tiebreaker") else 0,
            json.dumps(entry.get("blue_priors") or []),
            json.dumps(entry.get("red_priors") or []),
            json.dumps(entry.get("blue_roles") or []),
            json.dumps(entry.get("red_roles") or []),
        ),
    )


def log_resolve(match_id, viewer_puuid, actual_winner, correct):
    db = _pred_db()
    db.execute(
        """UPDATE prediction_logs
           SET resolved=1, actual_winner=?, correct=?, resolved_at=?
           WHERE match_id=? AND viewer_puuid=?""",
        (actual_winner, 1 if correct else 0, time.time(), match_id, viewer_puuid),
    )


def save_live_snapshot(match_id, snapshot_data):
    """Guarda el snapshot completo del live (players + prediction) para reutilizar en matchDetail."""
    db = _pred_db()
    db.execute(
        "INSERT OR REPLACE INTO live_snapshots (match_id, snapshot, created_at) VALUES (?, ?, ?)",
        (match_id, json.dumps(snapshot_data), time.time()),
    )


def get_live_snapshot(match_id):
    """Recupera un snapshot guardado. Devuelve None si no existe."""
    db = _pred_db()
    row = db.execute("SELECT snapshot FROM live_snapshots WHERE match_id=?", (match_id,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def predictions_add(entry):
    db = _pred_db()
    db.execute(
        """INSERT OR IGNORE INTO predictions
        (match_id, viewer_puuid, viewer_name, viewer_team,
         blue_sum, red_sum, blue_score, red_score,
         predicted_winner, confidence, created_at, resolved)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,0)""",
        (
            entry["match_id"], entry["viewer_puuid"],
            entry.get("viewer_name"), entry.get("viewer_team"),
            entry.get("blue_sum"), entry.get("red_sum"),
            entry.get("blue_score"), entry.get("red_score"),
            entry.get("predicted_winner"), entry.get("confidence", 0),
            entry.get("created_at", time.time()),
        ),
    )


def predictions_all():
    db = _pred_db()
    cur = db.execute("SELECT * FROM predictions")
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def predictions_mark_resolved(match_id, viewer_puuid, actual_winner, predicted_winner):
    db = _pred_db()
    correct = 1 if predicted_winner and predicted_winner == actual_winner else (0 if predicted_winner else None)
    db.execute(
        "UPDATE predictions SET resolved=1, actual_winner=?, correct=? WHERE match_id=? AND viewer_puuid=?",
        (actual_winner, correct, match_id, viewer_puuid),
    )
    # Log detallado: refleja la resolución en prediction_logs
    try:
        if predicted_winner:
            log_resolve(match_id, viewer_puuid, actual_winner, predicted_winner == actual_winner)
    except Exception:
        pass


def load_predictions():
    return predictions_all()


def save_predictions(_):
    pass


MAX_RECENT = 10


def load_recent():
    if not os.path.exists(RECENT_FILE):
        return []
    with open(RECENT_FILE, "r") as f:
        return json.load(f)


def save_recent(summoner: str):
    recent = load_recent()
    recent = [s for s in recent if s != summoner]
    recent.insert(0, summoner)
    with open(RECENT_FILE, "w") as f:
        json.dump(recent[:MAX_RECENT], f)


def load_saved_accounts():
    if not os.path.exists(SAVED_ACCOUNTS_FILE):
        return []
    with open(SAVED_ACCOUNTS_FILE) as f:
        return json.load(f)


def load_watch_list():
    if not os.path.exists(WATCH_LIST_FILE):
        return {}
    with open(WATCH_LIST_FILE) as f:
        return json.load(f)


def save_watch_list(data):
    with open(WATCH_LIST_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False)


def load_leaderboard():
    if not os.path.exists(LEADERBOARD_FILE):
        return {}
    with open(LEADERBOARD_FILE, "r") as f:
        return json.load(f)


def update_leaderboard(matches_overview):
    lb = load_leaderboard()
    for match in matches_overview:
        if match["game_duration"] < 300:
            continue
        w = match.get("worst")
        if not w:  # non-ranked queues no tienen worst player
            continue
        nombre = w["nombre"]
        if nombre not in lb:
            lb[nombre] = {"nombre": nombre, "apariciones": 0, "champion_counts": {},
                          "total_kills": 0, "total_deaths": 0, "total_assists": 0}
        e = lb[nombre]
        e["apariciones"] += 1
        e["total_kills"] += w["kills"]
        e["total_deaths"] += w["deaths"]
        e["total_assists"] += w["assists"]
        e["champion_counts"][w["campeon"]] = e["champion_counts"].get(w["campeon"], 0) + 1
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(lb, f)


@app.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    lb = load_leaderboard()
    entries = sorted(lb.values(), key=lambda e: e["apariciones"], reverse=True)[:20]
    result = []
    for i, e in enumerate(entries):
        campeon = max(e["champion_counts"], key=lambda c: e["champion_counts"][c])
        kda = round((e["total_kills"] + e["total_assists"]) / max(1, e["total_deaths"]), 2)
        result.append({
            "position": i + 1,
            "nombre": e["nombre"],
            "apariciones": e["apariciones"],
            "campeon": campeon,
            "total_kills": e["total_kills"],
            "total_deaths": e["total_deaths"],
            "total_assists": e["total_assists"],
            "avg_kda": kda,
        })
    return jsonify(result)


@app.route("/recentSummoners", methods=["GET"])
def get_recent_summoners():
    return jsonify(load_recent())


@app.route("/recentSummoners", methods=["POST"])
def post_recent_summoner():
    summoner = request.json.get("summoner")
    if summoner:
        save_recent(summoner)
    return jsonify({"ok": True})


@app.route("/savedAccounts", methods=["GET"])
def get_saved_accounts():
    return jsonify(load_saved_accounts())


@app.route("/savedAccounts", methods=["POST"])
def add_saved_account():
    summoner = (request.json or {}).get("summoner", "").strip()
    if not summoner:
        return jsonify({"error": "Summoner requerido"}), 400
    accounts = load_saved_accounts()
    accounts = [a for a in accounts if a != summoner]
    accounts.insert(0, summoner)
    with open(SAVED_ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, ensure_ascii=False)
    return jsonify(accounts)


@app.route("/savedAccounts", methods=["DELETE"])
def remove_saved_account():
    summoner = (request.json or {}).get("summoner", "").strip()
    accounts = [a for a in load_saved_accounts() if a != summoner]
    with open(SAVED_ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, ensure_ascii=False)
    return jsonify(accounts)


@app.route("/watchList", methods=["GET"])
def get_watch_list_ep():
    summoner = request.args.get("summoner", "")
    return jsonify(load_watch_list().get(summoner, []))


@app.route("/watchList", methods=["POST"])
def add_to_watch_list():
    data = request.json or {}
    summoner = data.get("summoner", "")
    tumor = data.get("tumor", "")
    watch = load_watch_list()
    if summoner not in watch:
        watch[summoner] = []
    if tumor not in watch[summoner]:
        watch[summoner].append(tumor)
    save_watch_list(watch)
    return jsonify(watch[summoner])


@app.route("/watchList", methods=["DELETE"])
def remove_from_watch_list():
    data = request.json or {}
    summoner = data.get("summoner", "")
    tumor = data.get("tumor", "")
    watch = load_watch_list()
    if summoner in watch:
        watch[summoner] = [t for t in watch[summoner] if t != tumor]
    save_watch_list(watch)
    return jsonify(watch.get(summoner, []))


def calculate_kda(kills, deaths, assists):
    """Calcula el KDA de un jugador"""
    return (kills + assists) / max(1, deaths)


# Umbrales mínimos aceptables por rango.
# Por debajo del umbral = contribuye al tumor score.
RANK_THRESHOLDS = {
    "IRON":        {"kda": 0.5, "cs_per_min": 2.5, "dmg_per_min": 300, "vision_per_min": 0.4},
    "BRONZE":      {"kda": 0.6, "cs_per_min": 3.0, "dmg_per_min": 400, "vision_per_min": 0.5},
    "SILVER":      {"kda": 0.7, "cs_per_min": 3.5, "dmg_per_min": 500, "vision_per_min": 0.6},
    "GOLD":        {"kda": 0.8, "cs_per_min": 4.0, "dmg_per_min": 650, "vision_per_min": 0.8},
    "PLATINUM":    {"kda": 1.0, "cs_per_min": 5.0, "dmg_per_min": 800, "vision_per_min": 1.0},
    "EMERALD":     {"kda": 1.1, "cs_per_min": 5.5, "dmg_per_min": 950, "vision_per_min": 1.1},
    "DIAMOND":     {"kda": 1.2, "cs_per_min": 6.5, "dmg_per_min": 1100, "vision_per_min": 1.2},
    "MASTER":      {"kda": 1.4, "cs_per_min": 7.5, "dmg_per_min": 1300, "vision_per_min": 1.4},
    "GRANDMASTER": {"kda": 1.5, "cs_per_min": 8.0, "dmg_per_min": 1400, "vision_per_min": 1.5},
    "CHALLENGER":  {"kda": 1.6, "cs_per_min": 8.5, "dmg_per_min": 1500, "vision_per_min": 1.6},
}


def get_player_rank(puuid, platform_host=None):
    """Obtiene el tier SoloQ actual del jugador (e.g. 'GOLD')."""
    url = f"{league_url(platform_host or RIOT_PLATFORM_URL)}/{puuid}"
    entries_res = riot_get(url)
    if entries_res.status_code != 200:
        return "GOLD", "IV"  # fallback

    for entry in entries_res.json():
        if entry["queueType"] == "RANKED_SOLO_5x5":
            return entry["tier"], entry["rank"]

    return "UNRANKED", ""


def predict_team_outcome(players):
    """Wrapper. La lógica vive en tumor_engine.predict_team_outcome.

    Acepta el shape histórico (`avg_tumor_score`) de los callers de main.py
    y lo traduce al formato que espera el engine (`prior_tumor`).
    """
    translated = []
    for p in players:
        translated.append({
            "team_id": p.get("team_id"),
            "puuid": p.get("puuid"),
            "name": p.get("nombre") or p.get("name"),
            "role": p.get("role"),
            "prior_tumor": p.get("avg_tumor_score"),
            "is_tilted": p.get("is_tilted", False),
            "is_hotstreak": p.get("is_hotstreak", False),
        })
    return _engine_predict(translated)


def calculate_tumor_score(player, game_duration, tier="GOLD", role="DEFAULT"):
    """Wrapper retrocompatible. Toda la lógica vive en tumor_engine.py."""
    return _engine_match_score(player, game_duration, tier, role)


def find_player_in_participants(participants, puuid, game_name=None, tag_line=None):
    """Encuentra al jugador en participants. Primero por puuid; si Riot ha rotado
    el puuid (matches viejos tienen el puuid antiguo), fallback a Riot ID."""
    p = next((x for x in participants if x.get("puuid") == puuid), None)
    if p is not None:
        return p
    if game_name and tag_line:
        gn_l = game_name.lower()
        tl_l = tag_line.lower()
        p = next((x for x in participants
                  if (x.get("riotIdGameName") or "").lower() == gn_l
                  and (x.get("riotIdTagline") or "").lower() == tl_l), None)
        return p
    return None


def get_worst_player_in_match(participants, puuid, game_name=None, tag_line=None,
                              game_duration=None, tier=None):
    """Encuentra el peor aliado en una partida.

    Si se proveen game_duration + tier, selecciona por TUMOR SCORE MÁS ALTO
    (coherente con lo que la UI muestra como "tumor score" del peor). Sin esos
    params, fallback a KDA MÁS BAJO (comportamiento legacy, p.ej. getTurboCancer
    que filtra por KDA<1 explícitamente).

    Devuelve None si el jugador no está en la partida.
    """
    my_player = find_player_in_participants(participants, puuid, game_name, tag_line)
    if my_player is None:
        return None
    my_team_id = my_player["teamId"]

    use_tumor = (game_duration is not None and tier is not None)

    if not use_tumor:
        worst_player = None
        worst_kda = float("inf")
        for p in participants:
            if p["teamId"] != my_team_id:
                continue
            kda = calculate_kda(p["kills"], p["deaths"], p["assists"])
            p["kda"] = kda
            if kda < worst_kda:
                worst_kda = kda
                worst_player = p
        return worst_player

    # Selección por tumor_score: el peor = el de mayor puntuación de tumor,
    # coherente con la métrica mostrada en la UI.
    worst_player = None
    worst_tumor = -1
    for p in participants:
        if p["teamId"] != my_team_id:
            continue
        # Pre-calcular KDA para downstream
        p["kda"] = calculate_kda(p["kills"], p["deaths"], p["assists"])
        role = p.get("teamPosition") or p.get("individualPosition") or ""
        try:
            # compute_match_tumor devuelve (score, components)
            result = _engine_match_score_from_participant(p, game_duration, tier, role)
            t_score = result[0] if isinstance(result, tuple) else result
        except Exception:
            t_score = 0
        if t_score > worst_tumor:
            worst_tumor = t_score
            worst_player = p
    return worst_player


def get_compare(game_name1, tag_line1, game_name2, tag_line2):
    """Busca partidas comunes entre dos jugadores y compara sus stats."""
    try:
        acc1_res = riot_get(f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name1}/{tag_line1}")
        if acc1_res.status_code != 200:
            return {"error": f"Error cuenta 1: {acc1_res.text}"}, 400
        acc1 = acc1_res.json()
        puuid1 = acc1["puuid"]

        acc2_res = riot_get(f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name2}/{tag_line2}")
        if acc2_res.status_code != 200:
            return {"error": f"Error cuenta 2: {acc2_res.text}"}, 400
        acc2 = acc2_res.json()
        puuid2 = acc2["puuid"]

        ids1_res = riot_get(f"{MATCHES_BY_PUUID_URL}/{puuid1}/ids?start=0&count=30&queue={QUEUE_RANKED_SOLO}")
        ids2_res = riot_get(f"{MATCHES_BY_PUUID_URL}/{puuid2}/ids?start=0&count=30&queue={QUEUE_RANKED_SOLO}")

        ids1 = set(ids1_res.json() if ids1_res.status_code == 200 else [])
        ids2 = set(ids2_res.json() if ids2_res.status_code == 200 else [])
        common = ids1 & ids2

        matches = []
        score1, score2 = 0, 0  # who was worse more often

        for match_id in common:
            match_res = riot_get(f"{MATCH_DETAILS_URL}/{match_id}")
            if match_res.status_code != 200:
                continue

            data = match_res.json()
            participants = data["info"]["participants"]
            game_duration = data["info"]["gameDuration"]

            p1 = next((p for p in participants if p["puuid"] == puuid1), None)
            p2 = next((p for p in participants if p["puuid"] == puuid2), None)
            if not p1 or not p2:
                continue

            kda1 = calculate_kda(p1["kills"], p1["deaths"], p1["assists"])
            kda2 = calculate_kda(p2["kills"], p2["deaths"], p2["assists"])
            worse = 1 if kda1 < kda2 else (2 if kda2 < kda1 else 0)
            if worse == 1:
                score1 += 1
            elif worse == 2:
                score2 += 1

            matches.append({
                "match_id": match_id,
                "game_duration": game_duration,
                "same_team": p1["teamId"] == p2["teamId"],
                "worse_player": worse,
                "player1": {
                    "campeon": p1["championName"],
                    "kills": p1["kills"], "deaths": p1["deaths"], "assists": p1["assists"],
                    "kda": round(kda1, 2),
                    "cs": p1["totalMinionsKilled"] + p1["neutralMinionsKilled"],
                    "damage": p1["totalDamageDealtToChampions"],
                    "win": p1["win"],
                },
                "player2": {
                    "campeon": p2["championName"],
                    "kills": p2["kills"], "deaths": p2["deaths"], "assists": p2["assists"],
                    "kda": round(kda2, 2),
                    "cs": p2["totalMinionsKilled"] + p2["neutralMinionsKilled"],
                    "damage": p2["totalDamageDealtToChampions"],
                    "win": p2["win"],
                },
            })

        return {
            "player1_name": f"{acc1['gameName']}#{acc1['tagLine']}",
            "player2_name": f"{acc2['gameName']}#{acc2['tagLine']}",
            "common_matches": len(matches),
            "score1": score1,
            "score2": score2,
            "matches": matches,
        }
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/compare", methods=["GET"])
def compare_endpoint():
    gn1 = request.args.get("game_name1")
    tl1 = request.args.get("tag_line1")
    gn2 = request.args.get("game_name2")
    tl2 = request.args.get("tag_line2")
    if not all([gn1, tl1, gn2, tl2]):
        return jsonify({"error": "Faltan parámetros"}), 400
    result = get_compare(gn1, tl1, gn2, tl2)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result)


def get_el_peor(game_name, tag_line):
    """Obtiene el peor jugador aliado de las últimas rankeds"""
    try:
        # 1. Obtener PUUID
        account_url = f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name}/{tag_line}"
        account_res = riot_get(account_url)

        if account_res.status_code != 200:
            return {"error": f"Error obteniendo cuenta: {account_res.text}"}, 400

        puuid = account_res.json()["puuid"]

        # 2. Obtener últimas rankeds (SoloQ)
        matches_url = f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count={MATCHES_COUNT}&queue={QUEUE_RANKED_SOLO}"
        matches_res = riot_get(matches_url)

        if matches_res.status_code != 200:
            return {"error": f"Error obteniendo partidas: {matches_res.text}"}, 400

        match_ids = matches_res.json()
        worst_players = []

        # 3. Fetch en paralelo (8 workers) + procesar en orden
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as _ex:
            _responses = list(_ex.map(
                lambda mid: riot_get(f"{MATCH_DETAILS_URL}/{mid}"),
                match_ids,
            ))
        for match_res in _responses:
            if match_res.status_code != 200:
                continue
            data = match_res.json()
            participants = data["info"]["participants"]
            worst_player = get_worst_player_in_match(participants, puuid)
            if worst_player:
                worst_players.append(worst_player)

        # 4. Encontrar el peor jugador con KDA < 1 y más muertes
        turbocancer = max(
            (p for p in worst_players if p['kda'] < WORST_KDA_THRESHOLD),
            key=lambda p: p['deaths'],
            default=None
        )

        if turbocancer is None:
            return {"error": "No se encontró un peor jugador con KDA < 1"}, 404

        return {
            "nombre": f"{turbocancer['riotIdGameName']}#{turbocancer['riotIdTagline']}",
            "campeon": turbocancer['championName'],
            "kills": turbocancer['kills'],
            "deaths": turbocancer['deaths'],
            "assists": turbocancer['assists'],
            "kda": round(turbocancer['kda'], 2)
        }

    except Exception as e:
        return {"error": str(e)}, 500


def get_overview(game_name, tag_line, start=0, tier_override=None, queue=None):
    """Obtiene el peor aliado por cada una de las últimas partidas del queue dado.

    queue: None (default) → SoloQ. 0 / 'all' → todos los queues (sin filtro).
    Para queues no-ranked (no en RANKED_QUEUES), se devuelve match raw stats sin
    tumor score / lane diff / priors.
    """
    try:
        # Normaliza queue
        if queue in (None, '', 'soloq'):
            queue_int = QUEUE_RANKED_SOLO
        elif queue == 'flex':
            queue_int = QUEUE_RANKED_FLEX
        elif queue == 'all' or queue == 0 or queue == '0':
            queue_int = None  # sin filtro
        else:
            try:
                queue_int = int(queue)
            except (TypeError, ValueError):
                queue_int = QUEUE_RANKED_SOLO
        ranked_mode = is_ranked_queue(queue_int) if queue_int is not None else False

        # 1. Obtener PUUID
        account_url = f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name}/{tag_line}"
        account_res = riot_get(account_url)

        if account_res.status_code != 200:
            return {"error": f"Error obteniendo cuenta: {account_res.text}"}, 400

        account = account_res.json()
        puuid = account["puuid"]

        # Auto-detectar plataforma del jugador
        platform_host = detect_platform(puuid)

        # Warmup silencioso: cachea match details en background para acelerar analytics
        if start == 0:
            warmup_prefetch(puuid, count=30)

        # 2. Obtener rango (solo en la primera carga; en "load more" se reutiliza).
        # Para queues no-ranked igual lo pedimos (es info útil del jugador), pero el
        # tumor score solo se aplica a queues ranked.
        if tier_override:
            tier, division = tier_override, ""
        else:
            tier, division = get_player_rank(puuid, platform_host)

        # 3. Obtener partidas del queue solicitado desde el offset pedido
        queue_param = f"&queue={queue_int}" if queue_int is not None else ""
        matches_url = f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start={start}&count={MATCHES_COUNT}{queue_param}"
        matches_res = riot_get(matches_url)

        if matches_res.status_code != 200:
            return {"error": f"Error obteniendo partidas: {matches_res.text}"}, 400

        match_ids = matches_res.json()
        matches_overview = []

        # 4. Fetch de Match v5 en paralelo (8 workers). Antes era secuencial: 20 calls × ~200ms
        # cold cache = 4s sólo en network. riot_get tiene su propio rate limiter + cache,
        # thread-safe. El procesamiento de cada respuesta se hace en serie porque es CPU-bound rápido.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as _ex:
            _match_responses = list(_ex.map(
                lambda mid: riot_get(f"{MATCH_DETAILS_URL}/{mid}"),
                match_ids,
            ))

        # 5. Procesar cada partida (respeta el orden original de match_ids)
        for match_id, match_res in zip(match_ids, _match_responses):
            if match_res.status_code != 200:
                continue

            data = match_res.json()
            info = data.get("info", {})
            participants = info.get("participants", []) or []
            game_duration = info.get("gameDuration", 0)
            match_queue_id = info.get("queueId", 0)
            match_is_ranked = is_ranked_queue(match_queue_id)

            # Datos del propio jugador (fallback a riot id por puuid rotation)
            my_data = find_player_in_participants(participants, puuid, game_name, tag_line)
            if my_data is None:
                continue
            my_kda = calculate_kda(my_data["kills"], my_data["deaths"], my_data["assists"])
            my_cs = my_data["totalMinionsKilled"] + my_data["neutralMinionsKilled"]

            # Para queues no-ranked (ARAM, Arena, normales, URF...) emitimos un
            # match en modo "raw stats": sin tumor score, sin lane diff, sin
            # peor jugador. Mostramos solo las stats del propio jugador.
            if not match_is_ranked:
                matches_overview.append({
                    "match_id": match_id,
                    "queue_id": match_queue_id,
                    "queue_name": queue_name(match_queue_id),
                    "is_ranked": False,
                    "tumor_compatible": False,
                    "game_duration": game_duration,
                    "game_date": info.get("gameCreation", 0),
                    "win": my_data["win"],
                    "best_and_lost": False,
                    "worst_is_me": False,
                    "my_champion": my_data["championName"],
                    "my_kills": my_data["kills"],
                    "my_deaths": my_data["deaths"],
                    "my_assists": my_data["assists"],
                    "my_kda": round(my_kda, 2),
                    "my_cs": my_cs,
                    "my_damage": my_data["totalDamageDealtToChampions"],
                    "my_gold": my_data.get("goldEarned", 0),
                    "my_vision": my_data.get("visionScore", 0),
                    "worst": None,  # raw mode: no worst player
                })
                continue

            # === Path normal (queue ranked): tumor + worst player ===
            # Pasamos game_duration + tier para que el peor se seleccione por
            # TUMOR SCORE (coherente con el número mostrado en la card), no por KDA.
            worst_player = get_worst_player_in_match(
                participants, puuid, game_name, tag_line,
                game_duration=game_duration, tier=tier,
            )
            if not worst_player:
                continue

            # Equipo aliado
            team = [p for p in participants if p["teamId"] == my_data["teamId"]]
            team_kdas = [calculate_kda(p["kills"], p["deaths"], p["assists"]) for p in team]

            # ¿Eres el mejor de tu equipo y aun así perdiste?
            best_and_lost = not my_data["win"] and my_kda == max(team_kdas)
            # worst_is_me: compara via puuid (current); fallback a Riot ID por puuid rotation
            worst_is_me = (worst_player.get("puuid") == my_data.get("puuid"))

            # Medias del equipo (para comparativa)
            def team_avg(field):
                vals = [p[field] for p in team]
                return round(sum(vals) / len(vals), 1) if vals else 0

            def team_avg_cs():
                vals = [p["totalMinionsKilled"] + p["neutralMinionsKilled"] for p in team]
                return round(sum(vals) / len(vals), 1) if vals else 0

            worst_cs    = worst_player["totalMinionsKilled"] + worst_player["neutralMinionsKilled"]
            worst_dmg   = worst_player["totalDamageDealtToChampions"]
            worst_vs    = worst_player["visionScore"]
            worst_gold  = worst_player["goldEarned"]
            worst_dead  = worst_player["totalTimeSpentDead"]
            worst_level = worst_player["champLevel"]
            worst_wards = worst_player["wardsPlaced"]

            worst_dict = {
                "nombre": f"{worst_player['riotIdGameName']}#{worst_player['riotIdTagline']}",
                "campeon": worst_player["championName"],
                "kills": worst_player["kills"],
                "deaths": worst_player["deaths"],
                "assists": worst_player["assists"],
                "kda": round(worst_player["kda"], 2),
                "cs": worst_cs,
                "damage": worst_dmg,
                "vision_score": worst_vs,
                "gold": worst_gold,
                "time_dead": worst_dead,
                "champ_level": worst_level,
                "wards_placed": worst_wards,
                # Medias del equipo
                "team_avg": {
                    "kda":    round(sum(team_kdas) / len(team_kdas), 2),
                    "cs":     team_avg_cs(),
                    "damage": team_avg("totalDamageDealtToChampions"),
                    "vision": team_avg("visionScore"),
                    "gold":   team_avg("goldEarned"),
                },
            }
            worst_role = worst_player.get("teamPosition") or "DEFAULT"
            worst_dict["tumor_score"] = calculate_tumor_score(worst_dict, game_duration, tier, worst_role)

            matches_overview.append({
                "match_id": match_id,
                "queue_id": match_queue_id,
                "queue_name": queue_name(match_queue_id),
                "is_ranked": True,
                "tumor_compatible": True,
                "game_duration": game_duration,
                "game_date": info.get("gameCreation", 0),
                "win": my_data["win"],
                "best_and_lost": best_and_lost,
                "worst_is_me": worst_is_me,
                "my_champion": my_data["championName"],
                "my_kills": my_data["kills"],
                "my_deaths": my_data["deaths"],
                "my_assists": my_data["assists"],
                "my_kda": round(my_kda, 2),
                "my_cs": my_cs,
                "my_damage": my_data["totalDamageDealtToChampions"],
                "worst": worst_dict,
            })

        summoner_key = f"{account['gameName']}#{account['tagLine']}"

        alerts = []
        if start == 0:
            update_leaderboard(matches_overview)
            watched = set(load_watch_list().get(summoner_key, []))
            if watched:
                seen = set()
                for m in matches_overview:
                    nombre = m["worst"]["nombre"]
                    if nombre in watched and nombre not in seen:
                        seen.add(nombre)
                        alerts.append({"nombre": nombre, "campeon": m["worst"]["campeon"]})

        return {
            "summoner": summoner_key,
            "tier": tier,
            "division": division,
            "matches": matches_overview,
            "has_more": len(match_ids) == MATCHES_COUNT,
            "alerts": alerts,
        }

    except Exception as e:
        import traceback
        return {"error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()}, 500


def compute_player_profile(puuid, tier="GOLD", num_matches=8, current_champion_id=None):
    """Tumor score + estadísticas del campeón actual basadas en últimas N partidas (ranked solo o cualquiera)."""
    try:
        ids_res = riot_get(f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count={num_matches}&queue={QUEUE_RANKED_SOLO}")
        match_ids = ids_res.json() if ids_res.status_code == 200 else []
        if not match_ids:
            ids_res = riot_get(f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count={num_matches}")
            if ids_res.status_code != 200:
                return None
            match_ids = ids_res.json()
        if not match_ids:
            return None

        scores = []
        total_games = 0
        champion_games = 0
        champion_wins = 0
        role_counts = {}         # rol en TODAS las partidas recientes (fallback)
        champ_role_counts = {}   # rol solo en partidas del champ actual (preferente)
        recent_tumors = []  # últimos 3 tumor scores (para streak)
        recent_wins = []    # últimos 3 wins (para tilt)
        recent_match_puuids = []  # por partida: lista de (match_id, teammates_puuids)

        # Match IDs vienen ordenados: más recientes primero.
        for idx, mid in enumerate(match_ids):
            mres = riot_get(f"{MATCH_DETAILS_URL}/{mid}")
            if mres.status_code != 200:
                continue
            data = mres.json()
            game_duration = data["info"]["gameDuration"]
            if game_duration < 300:
                continue
            p = next((x for x in data["info"]["participants"] if x["puuid"] == puuid), None)
            if not p:
                continue

            total_games += 1
            match_role = p.get("teamPosition") or ""
            if match_role:
                role_counts[match_role] = role_counts.get(match_role, 0) + 1

            if current_champion_id is not None and p.get("championId") == current_champion_id:
                champion_games += 1
                if p.get("win"):
                    champion_wins += 1
                if match_role:
                    champ_role_counts[match_role] = champ_role_counts.get(match_role, 0) + 1

            stats = {
                "kda": calculate_kda(p["kills"], p["deaths"], p["assists"]),
                "cs": p["totalMinionsKilled"] + p["neutralMinionsKilled"],
                "damage": p["totalDamageDealtToChampions"],
                "vision_score": p["visionScore"],
                "time_dead": p["totalTimeSpentDead"],
            }
            role = p.get("teamPosition") or "DEFAULT"
            score = calculate_tumor_score(stats, game_duration, tier, role)
            scores.append(score)

            if len(recent_tumors) < 3:
                recent_tumors.append(score)
                recent_wins.append(bool(p.get("win")))

            # para duo detection: compañeros de equipo del puuid en esta partida
            tm = [x["puuid"] for x in data["info"]["participants"]
                  if x["teamId"] == p["teamId"] and x["puuid"] != puuid]
            recent_match_puuids.append(tm)

        if not scores:
            return None

        champ_pct = round(champion_games / total_games * 100) if total_games else 0
        champ_wr = round(champion_wins / champion_games * 100) if champion_games else None
        if champ_role_counts:
            likely_role = max(champ_role_counts, key=champ_role_counts.get)
        elif role_counts:
            likely_role = max(role_counts, key=role_counts.get)
        else:
            likely_role = ""

        # Streak / tilt detection
        # Tilt requiere que hayas jugado mal recientemente. Perder solo no cuenta.
        recent_losses = sum(1 for w in recent_wins if not w)
        recent_wins_count = sum(1 for w in recent_wins if w)
        avg_recent_tumor = sum(recent_tumors) / len(recent_tumors) if recent_tumors else 0
        enough = len(recent_tumors) >= 3
        is_tilted = enough and (
            avg_recent_tumor >= 50
            or (recent_losses >= 3 and avg_recent_tumor >= 30)
        )
        # Hotstreak = 3+ wins seguidas con tumor decente
        is_hotstreak = enough and recent_wins_count >= 3 and avg_recent_tumor <= 40

        base_score = round(sum(scores) / len(scores))
        # Si tiltado, añadir penalización al score predicho
        adjusted_score = base_score
        if is_tilted:
            adjusted_score = min(100, base_score + 15)

        result = {
            "score": adjusted_score,
            "base_score": base_score,
            "is_tilted": is_tilted,
            "is_hotstreak": is_hotstreak,
            "recent_losses": recent_losses,
            "recent_wins": recent_wins_count,
            "recent_avg_tumor": round(avg_recent_tumor),
            "likely_role": likely_role,
            "champion_games": champion_games,
            "champion_wins": champion_wins,
            "champion_total_sample": total_games,
            "champion_pct": champ_pct,
            "champion_winrate": champ_wr,
            "is_main": False,  # se recalcula en el live endpoint con mastery
            "teammate_history": recent_match_puuids,
        }
        # Persistir prior global del jugador (sin info per-champ)
        try:
            save_cached_prior(puuid, result, tier)
        except Exception:
            pass
        return result
    except Exception:
        return None


def _compute_live_game(game_name, tag_line, job_id=None, force_refresh=False):
    """Extrae la lógica del endpoint /liveGame para poder reutilizarla en modo async.

    Si se pasa job_id, va publicando progreso en el job store.
    Devuelve (response_dict, status_code).
    """
    def step(msg, progress=None, total=None):
        if job_id:
            kw = {"step": msg}
            if progress is not None:
                kw["progress"] = progress
            if total is not None:
                kw["total"] = total
            job_update(job_id, **kw)

    step("Resolviendo cuenta...")
    acc_res = riot_get(f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name}/{tag_line}")
    if acc_res.status_code != 200:
        return {"error": "No se pudo obtener la cuenta"}, 400
    me_puuid = acc_res.json()["puuid"]

    # Auto-detectar plataforma del jugador (EUW, EUNE, NA, etc)
    step("Detectando región...")
    platform_host = detect_platform(me_puuid)

    step("Buscando partida activa...")
    spec_res = riot_get(f"{spectator_url(platform_host)}/{me_puuid}")
    if spec_res.status_code == 404:
        return {"error": "El jugador no está en partida ahora mismo"}, 404
    if spec_res.status_code in (502, 503, 504):
        return {"error": "Riot está caído (502/503). Espera unos segundos e intenta otra vez."}, 503
    if spec_res.status_code == 429:
        return {"error": "Rate limit. Espera 1-2 minutos."}, 429
    if spec_res.status_code != 200:
        body = (spec_res.text or "")[:200].replace("\n", " ")
        return {"error": f"Spectator error {spec_res.status_code}: {body}"}, 502

    game = spec_res.json()
    participants = game.get("participants", []) or []
    players = []
    cache = load_live_cache()
    cache_dirty = False
    now = time.time()

    # Watch list + blacklist del viewer
    viewer_key = f"{game_name}#{tag_line}"
    watched = set(load_watch_list().get(viewer_key, []))
    blacklist = set(load_blacklist().get(viewer_key, []))

    total_players = len(participants)
    step(f"Analizando 0/{total_players} jugadores...", progress=0, total=total_players)

    # Lock para escritura concurrente al cache JSON
    cache_lock = threading.Lock()
    progress_counter = {"done": 0}
    progress_lock = threading.Lock()

    def _looks_censored(rid: str) -> bool:
        if not rid:
            return True
        if "#" not in rid:
            return True
        name_part = rid.split("#", 1)[0].strip()
        return name_part == "" or name_part in ("?", "-", "Hidden", "hidden")

    def _process_player(p):
        """Procesa un jugador. Devuelve el entry_out listo para añadir a players."""
        nonlocal cache_dirty
        p_puuid = p.get("puuid")
        if not p_puuid:
            champ_id_fallback = p.get("championId")
            champ_name_fb = champ_id_to_name(champ_id_fallback)
            return {
                "puuid": "", "nombre": "🥷 Anónimo",
                "champion_id": champ_id_fallback, "champion_name": champ_name_fb,
                "team_id": p.get("teamId"), "role": "",
                "tier": "UNRANKED", "division": "",
                "avg_tumor_score": None, "champion_games": 0, "champion_total_sample": 0,
                "champion_pct": 0, "champion_winrate": None, "is_main": False,
                "is_tilted": False, "recent_losses": 0, "recent_avg_tumor": 0,
                "mastery_points": 0, "mastery_level": 0, "estimated_games": 0,
                "streamer_mode": True, "is_me": False,
                "is_watched": False, "is_blacklisted": champ_name_fb in blacklist,
                "_teammate_history": [],
            }

        champ_id = p.get("championId")
        cache_key = f"{p_puuid}:{champ_id}"
        with cache_lock:
            cached = cache.get(cache_key)
        if not force_refresh and cached and cached["data"].get("avg_tumor_score") is not None and (now - cached.get("ts", 0)) < LIVE_CACHE_TTL:
            entry = dict(cached["data"])
            entry["team_id"] = p.get("teamId")
            entry["champion_id"] = champ_id
            entry["spell1_id"] = p.get("spell1Id")
            entry["spell2_id"] = p.get("spell2Id")
            entry["perks"] = _extract_perks(p.get("perks"))
            entry["is_me"] = p_puuid == me_puuid
            entry["is_watched"] = entry.get("nombre") in watched
            champ_name = champ_id_to_name(champ_id)
            entry["is_blacklisted"] = champ_name in blacklist
            entry["champion_name"] = champ_name
            nombre = entry.get("nombre") or ""
            name_part = nombre.split("#", 1)[0].strip() if "#" in nombre else nombre.strip()
            if not entry.get("streamer_mode") and (
                not name_part or name_part in ("?", "-", "Hidden", "🥷 Anónimo")
            ):
                entry["streamer_mode"] = True
                entry["nombre"] = "🥷 Anónimo"
            mp = entry.get("mastery_points", 0) or 0
            ml = entry.get("mastery_level", 0) or 0
            cg = entry.get("champion_games", 0) or 0
            entry["is_main"] = (
                (mp >= 50000 and cg >= 1)
                or mp >= 150000
                or ml >= 7
            )
            entry["smurf_signals"] = _detect_smurf_signals(entry)
            return entry

        # Cache miss → fetch fresco. Las llamadas a riot_get ya están serializadas
        # por el token bucket, así que la concurrencia es segura.
        tier, division = get_player_rank(p_puuid, platform_host)

        raw_riot_id = p.get("riotId", "") or ""
        streamer_mode = False

        if _looks_censored(raw_riot_id):
            acc2 = riot_get(f"{RIOT_BASE_URL}/riot/account/v1/accounts/by-puuid/{p_puuid}")
            if acc2.status_code == 200:
                try:
                    a = acc2.json()
                except Exception:
                    a = {}
                gname = (a.get("gameName") or "").strip()
                tline = (a.get("tagLine") or "").strip()
                if gname and tline:
                    riot_id = f"{gname}#{tline}"
                else:
                    riot_id = "🥷 Anónimo"
                    streamer_mode = True
            else:
                riot_id = "🥷 Anónimo"
                streamer_mode = True
        else:
            riot_id = raw_riot_id

        profile = compute_player_profile(p_puuid, tier, num_matches=7, current_champion_id=champ_id)

        mastery_points = 0
        mastery_level = 0
        try:
            m_res = riot_get(f"{mastery_url(platform_host)}/{p_puuid}/by-champion/{champ_id}")
            if m_res.status_code == 200:
                m = m_res.json()
                mastery_points = m.get("championPoints", 0)
                mastery_level = m.get("championLevel", 0)
        except Exception:
            pass

        entry = {
            "puuid": p_puuid,
            "nombre": riot_id,
            "champion_id": champ_id,
            "team_id": p.get("teamId"),
            # Arena: 8 duos identificados por playerSubteamId (1-8). Para 5v5 esto es None.
            "subteam_id": p.get("playerSubteamId"),
            "role": (profile.get("likely_role") if profile else "") or (
                "JUNGLE" if p.get("spell1Id") == 11 or p.get("spell2Id") == 11 else ""
            ),
            "tier": tier,
            "division": division,
            "avg_tumor_score": profile["score"] if profile else None,
            "champion_games": profile["champion_games"] if profile else 0,
            "champion_total_sample": profile["champion_total_sample"] if profile else 0,
            "champion_pct": profile["champion_pct"] if profile else 0,
            "champion_winrate": profile["champion_winrate"] if profile else None,
            "is_main": (
                (mastery_points >= 50000 and (profile and profile.get("champion_games", 0) >= 1))
                or mastery_points >= 150000
                or mastery_level >= 7
            ),
            "is_tilted": profile["is_tilted"] if profile else False,
            "is_hotstreak": profile.get("is_hotstreak", False) if profile else False,
            "recent_losses": profile["recent_losses"] if profile else 0,
            "recent_wins": profile.get("recent_wins", 0) if profile else 0,
            "recent_avg_tumor": profile["recent_avg_tumor"] if profile else 0,
            "mastery_points": mastery_points,
            "mastery_level": mastery_level,
            "estimated_games": round(mastery_points / 1900) if mastery_points else 0,
            "streamer_mode": streamer_mode,
            "spell1_id": p.get("spell1Id"),
            "spell2_id": p.get("spell2Id"),
            "perks": _extract_perks(p.get("perks")),
            "_teammate_history": profile.get("teammate_history", []) if profile else [],
        }
        if entry["avg_tumor_score"] is not None:
            with cache_lock:
                cache[cache_key] = {"ts": now, "data": entry}
                cache_dirty = True

        champ_name = champ_id_to_name(champ_id)
        entry["champion_name"] = champ_name

        entry_out = dict(entry)
        entry_out["is_me"] = p_puuid == me_puuid
        entry_out["is_watched"] = riot_id in watched
        entry_out["is_blacklisted"] = champ_name in blacklist
        entry_out["smurf_signals"] = _detect_smurf_signals(entry_out)
        return entry_out

    def _process_with_progress(p):
        result = _process_player(p)
        with progress_lock:
            progress_counter["done"] += 1
            done = progress_counter["done"]
        step(f"Analizando {done}/{total_players} jugadores...", progress=done, total=total_players)
        return result

    # Procesamiento paralelo: 6 workers son suficientes (Riot rate limit
    # serializa las llamadas, los threads se turnan en el token bucket)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as executor:
        # map() preserva el orden de participants → players queda en orden
        for entry_out in executor.map(_process_with_progress, participants):
            players.append(entry_out)

    if cache_dirty:
        save_live_cache(cache)

    # Notificar al user logueado si algún jugador en watchlist aparece en partida.
    # Solo se hace una vez por (match_id, watched_name) gracias al ID estable.
    try:
        watched_in_game = [p for p in players if p.get("is_watched") and p.get("nombre") in watched]
        if watched_in_game:
            cur = _users._exec("SELECT id FROM users WHERE riot_puuid=?", (me_puuid,))
            urow = cur.fetchone()
            if urow:
                user_id = urow[0]
                for w in watched_in_game:
                    nid = f"watch-{game.get('gameId')}-{w['nombre']}"
                    _users.push_notification(
                        user_id,
                        notif_type="watchlist_alert",
                        title=f"☢ {w['nombre']} en tu partida",
                        body=f"juega {w.get('champion_name', '?')} ({'azul' if w.get('team_id') == 100 else 'rojo'})",
                        link="#/", icon="☢",
                    )
    except Exception:
        pass

    # Duo detection: para cada equipo, cruza los teammate_history.
    # Si el puuid de A aparece en la historia de B >=2 veces (y viceversa), son duo.
    duo_groups = {}  # team_id -> list of sets of puuids
    for team_id in (100, 200):
        team_players = [p for p in players if p["team_id"] == team_id]
        pairs = {}
        for a in team_players:
            a_hist = a.get("_teammate_history", [])
            a_puuid = a["puuid"]
            for b in team_players:
                if a["puuid"] >= b["puuid"]:
                    continue
                b_puuid = b["puuid"]
                # contar en cuántas partidas de A aparece B
                matches_together = sum(1 for tm in a_hist if b_puuid in tm)
                if matches_together >= 2:
                    pairs[(a_puuid, b_puuid)] = matches_together
        duo_groups[team_id] = pairs

    # Asignar etiqueta "duo_group" A/B/C a cada pareja detectada
    for team_id, pairs in duo_groups.items():
        groups = []  # lista de sets
        for (a, b) in pairs:
            placed = False
            for g in groups:
                if a in g or b in g:
                    g.add(a); g.add(b)
                    placed = True
                    break
            if not placed:
                groups.append({a, b})
        labels = ["α", "β", "γ", "δ"]
        for idx, g in enumerate(groups):
            label = labels[idx] if idx < len(labels) else f"#{idx+1}"
            for p in players:
                if p["puuid"] in g and p["team_id"] == team_id:
                    p["duo_group"] = label
                    p["duo_size"] = len(g)

    # Streamer mode / null score fallback: media del equipo
    for team_id in (100, 200):
        team = [p for p in players if p["team_id"] == team_id]
        valid = [p["avg_tumor_score"] for p in team if p.get("avg_tumor_score") is not None]
        if not valid:
            continue
        avg = round(sum(valid) / len(valid))
        for p in team:
            if p.get("avg_tumor_score") is None:
                p["avg_tumor_score"] = avg
                p["score_is_team_avg"] = True

    # limpia campos internos antes de devolver
    for p in players:
        p.pop("_teammate_history", None)

    # Bans del game spec
    bans = []
    for b in game.get("bannedChampions", []) or []:
        cid = b.get("championId", 0)
        if cid and cid > 0:
            bans.append({
                "team_id": b.get("teamId"),
                "champion_id": cid,
                "champion_name": champ_id_to_name(cid),
                "pick_turn": b.get("pickTurn"),
            })

    game_id = game.get("gameId")
    queue_id = game.get("gameQueueConfigId")

    # Predicción 5v5 solo aplica a SoloQ + Flex. En ARAM (450) y Arena (1700)
    # el motor de tumor con role-weights + medianas no tiene sentido.
    is_predictable_5v5 = is_ranked_queue(queue_id)
    if is_predictable_5v5:
        prediction = predict_team_outcome(players)
    else:
        prediction = None

    # Arena (queue 1700): agrupa players por playerSubteamId para que el frontend
    # pueda renderizar 8 duos de 2.
    arena_subteams = None
    if queue_id == 1700:
        groups = {}
        for p in players:
            sid = p.get("subteam_id") or 0
            groups.setdefault(sid, []).append(p)
        arena_subteams = []
        for sid in sorted(groups.keys()):
            members = groups[sid]
            priors = [m.get("avg_tumor_score") for m in members if m.get("avg_tumor_score") is not None]
            avg_prior = round(sum(priors) / len(priors), 1) if priors else None
            arena_subteams.append({
                "subteam_id": sid,
                "members": members,
                "avg_prior": avg_prior,
                "any_tilted": any(m.get("is_tilted") for m in members),
                "any_hotstreak": any(m.get("is_hotstreak") for m in members),
            })
    # Derivar platform ID del host detectado (e.g. "https://eun1.api..." → "EUN1")
    platform = game.get("platformId") or ""
    if not platform:
        for pid, host in PLATFORM_HOSTS.items():
            if host == platform_host:
                platform = pid
                break
        if not platform:
            platform = "EUW1"
    match_id = f"{platform}_{game_id}"

    me = next((p for p in players if p["is_me"]), None)
    viewer_team = "blue" if (me and me["team_id"] == 100) else "red" if me else None

    # Logging de predicción solo aplica cuando hay predicción (5v5 ranked)
    if prediction is not None:
        try:
            predictions_add({
                "match_id": match_id,
                "game_id": game_id,
                "viewer_puuid": me_puuid,
                "viewer_name": f"{game_name}#{tag_line}",
                "viewer_team": viewer_team,
                "blue_sum": prediction["blue_team_tumor"],
                "red_sum": prediction["red_team_tumor"],
                "blue_score": prediction["blue_team_tumor"],
                "red_score": prediction["red_team_tumor"],
                "predicted_winner": prediction["winner"] if prediction["winner"] != "tie" else None,
                "confidence": prediction["confidence"],
                "created_at": now,
            })
        except Exception:
            pass

    # Log detallado para afinación empírica (solo 5v5)
    if prediction is not None:
        try:
            blue_players = [p for p in players if p.get("team_id") == 100]
            red_players  = [p for p in players if p.get("team_id") == 200]
            blue_priors = [p.get("avg_tumor_score") for p in blue_players]
            red_priors  = [p.get("avg_tumor_score") for p in red_players]
            median_diff = (prediction.get("red_team_tumor", 0) or 0) - (prediction.get("blue_team_tumor", 0) or 0)
            sum_diff_raw = (prediction.get("red_team_sum", 0) or 0) - (prediction.get("blue_team_sum", 0) or 0)
            log_prediction({
                "match_id": match_id,
                "viewer_puuid": me_puuid,
                "created_at": now,
                "predicted_winner": prediction["winner"] if prediction["winner"] != "tie" else None,
                "confidence": prediction["confidence"],
                "blue_team_tumor": prediction["blue_team_tumor"],
                "red_team_tumor":  prediction["red_team_tumor"],
                "blue_team_sum":   prediction.get("blue_team_sum"),
                "red_team_sum":    prediction.get("red_team_sum"),
                "median_diff":     median_diff,
                "sum_diff":        sum_diff_raw,
                "used_sum_tiebreaker": abs(median_diff) < 4 and prediction["winner"] != "tie",
                "blue_priors": blue_priors,
                "red_priors":  red_priors,
                "blue_roles":  [p.get("role") or "" for p in blue_players],
                "red_roles":   [p.get("role") or "" for p in red_players],
                "blue_streamers": sum(1 for p in blue_players if p.get("streamer_mode")),
                "red_streamers":  sum(1 for p in red_players  if p.get("streamer_mode")),
            })
        except Exception:
            pass

    step("Listo", progress=total_players, total=total_players)

    result = {
        "game_id": game_id,
        "match_id": match_id,
        "queue_id": queue_id,
        "viewer_puuid": me_puuid,
        "players": players,
        "bans": bans,
        "prediction": prediction,
        "is_predictable_5v5": is_predictable_5v5,
        "arena_subteams": arena_subteams,
    }

    # Persistir snapshot: priors + predicción para reutilizar en matchDetail.
    try:
        # Spectator devuelve gameStartTime en ms (epoch). 0 cuando aún no empezó (loading screen).
        gst_ms = game.get("gameStartTime") or 0
        game_start_ts = (gst_ms / 1000.0) if gst_ms else None
        snapshot = {
            "prediction": prediction,
            "game_start_ts": game_start_ts,
            "player_priors": {
                p["puuid"]: {
                    "prior_tumor": p.get("avg_tumor_score"),
                    "role": p.get("role"),
                    "tier": p.get("tier"),
                    "is_tilted": p.get("is_tilted"),
                    "is_hotstreak": p.get("is_hotstreak"),
                }
                for p in players if p.get("puuid")
            },
        }
        save_live_snapshot(match_id, snapshot)
    except Exception:
        pass

    return result, 200


@app.route('/liveGame', methods=['GET'])
def live_game_endpoint():
    game_name = request.args.get('game_name')
    tag_line = request.args.get('tag_line')
    if not game_name or not tag_line:
        return jsonify({"error": "Falta game_name y/o tag_line"}), 400
    result, status = _compute_live_game(game_name, tag_line)
    return jsonify(result), status


@app.route('/liveGame/start', methods=['POST'])
def live_game_start():
    data = request.get_json() or {}
    game_name = data.get("game_name")
    tag_line = data.get("tag_line")
    force_refresh = bool(data.get("force_refresh", False))
    if not game_name or not tag_line:
        return jsonify({"error": "Falta game_name y/o tag_line"}), 400
    job_cleanup()
    jid = job_create()

    def _worker():
        try:
            result, status = _compute_live_game(game_name, tag_line, job_id=jid, force_refresh=force_refresh)
            if status == 200:
                job_update(jid, status="done", result=result, progress=1, total=1)
            else:
                job_update(jid, status="error", error=result.get("error", "Error"), progress=1, total=1)
        except Exception as e:
            job_update(jid, status="error", error=str(e))

    threading.Thread(target=_worker, daemon=True).start()
    return jsonify({"job_id": jid})


@app.route('/liveGame/progress/<jid>', methods=['GET'])
def live_game_progress(jid):
    job = job_get(jid)
    if not job:
        return jsonify({"error": "Job no encontrado o expirado"}), 404
    return jsonify(job)


@app.route('/playerAnalytics', methods=['GET'])
def player_analytics_endpoint():
    import datetime
    game_name = request.args.get('game_name')
    tag_line = request.args.get('tag_line')
    count = int(request.args.get('count', 30))
    if not game_name or not tag_line:
        return jsonify({"error": "Falta game_name y/o tag_line"}), 400

    acc_res = riot_get(f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name}/{tag_line}")
    if acc_res.status_code != 200:
        return jsonify({"error": "No se pudo obtener la cuenta"}), 400
    puuid = acc_res.json()["puuid"]
    tier, _ = get_player_rank(puuid)

    ids_res = riot_get(f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count={count}&queue={QUEUE_RANKED_SOLO}")
    if ids_res.status_code != 200:
        return jsonify({"error": "No se pudieron obtener partidas"}), 400
    match_ids = ids_res.json()

    # Filtros opcionales
    filter_champion = request.args.get('champion')
    filter_role = request.args.get('role')
    filter_result = request.args.get('result')  # 'win' | 'loss'
    filter_from = request.args.get('from_ts')   # epoch seconds
    filter_to = request.args.get('to_ts')
    filter_from = float(filter_from) if filter_from else None
    filter_to = float(filter_to) if filter_to else None

    evolution = []
    hour_stats = {}
    week_buckets = {"this": {"games": 0, "wins": 0, "tumor_sum": 0},
                    "last": {"games": 0, "wins": 0, "tumor_sum": 0}}
    role_combo_stats = {}
    duo_stats = {}
    champion_pool = {}  # championName -> {games, wins, tumor_sum}
    lane_diff_stats = {"games": 0, "won_lane": 0, "cs_diff_sum": 0, "dmg_diff_sum": 0, "kda_diff_sum": 0}

    now_ts = time.time()
    this_week_start = now_ts - 7 * 86400
    last_week_start = now_ts - 14 * 86400

    for mid in match_ids:
        mres = riot_get(f"{MATCH_DETAILS_URL}/{mid}")
        if mres.status_code != 200:
            continue
        data = mres.json()
        info = data.get("info", {})
        if info.get("gameDuration", 0) < 300:
            continue

        me = next((p for p in info["participants"] if p["puuid"] == puuid), None)
        if not me:
            continue

        game_date = info.get("gameCreation", 0) / 1000
        win = bool(me.get("win"))
        role = me.get("teamPosition") or "DEFAULT"
        champion = me["championName"]

        # Aplicar filtros
        if filter_champion and champion != filter_champion:
            continue
        if filter_role and role != filter_role:
            continue
        if filter_result == "win" and not win:
            continue
        if filter_result == "loss" and win:
            continue
        if filter_from and game_date < filter_from:
            continue
        if filter_to and game_date > filter_to:
            continue

        stats = {
            "kda": calculate_kda(me["kills"], me["deaths"], me["assists"]),
            "cs": me["totalMinionsKilled"] + me["neutralMinionsKilled"],
            "damage": me["totalDamageDealtToChampions"],
            "vision_score": me["visionScore"],
            "time_dead": me["totalTimeSpentDead"],
        }
        tumor = calculate_tumor_score(stats, info["gameDuration"], tier, role)

        evolution.append({
            "date": game_date,
            "tumor": tumor,
            "win": win,
            "champion": champion,
            "kda": round(stats["kda"], 2),
        })

        # Champion pool
        cp = champion_pool.setdefault(champion, {"games": 0, "wins": 0, "tumor_sum": 0})
        cp["games"] += 1
        cp["wins"] += int(win)
        cp["tumor_sum"] += tumor

        hour = datetime.datetime.fromtimestamp(game_date).hour
        h = hour_stats.setdefault(hour, {"games": 0, "wins": 0, "tumor_sum": 0})
        h["games"] += 1
        h["wins"] += int(win)
        h["tumor_sum"] += tumor

        if game_date >= this_week_start:
            wkey = "this"
        elif game_date >= last_week_start:
            wkey = "last"
        else:
            wkey = None
        if wkey:
            w = week_buckets[wkey]
            w["games"] += 1
            w["wins"] += int(win)
            w["tumor_sum"] += tumor

        teammates = [p for p in info["participants"]
                     if p["teamId"] == me["teamId"] and p["puuid"] != puuid]

        for t in teammates:
            name = f"{t.get('riotIdGameName','?')}#{t.get('riotIdTagline','?')}"
            d = duo_stats.setdefault(t["puuid"], {
                "name": name, "games": 0, "wins": 0,
                "champion_counts": {},
                "my_tumor_sum": 0.0,
                "their_tumor_sum": 0.0,
            })
            d["games"] += 1
            d["wins"] += int(win)
            ch = t.get("championName", "?")
            d["champion_counts"][ch] = d["champion_counts"].get(ch, 0) + 1
            # Tumor del usuario en esta partida (ya calculado arriba como `tumor`)
            d["my_tumor_sum"] += tumor
            # Tumor del compañero en la misma partida
            try:
                t_role = t.get("teamPosition") or t.get("individualPosition") or role
                t_stats = {
                    "kda": calculate_kda(t["kills"], t["deaths"], t["assists"]),
                    "cs": t["totalMinionsKilled"] + t["neutralMinionsKilled"],
                    "damage": t["totalDamageDealtToChampions"],
                    "vision_score": t["visionScore"],
                    "time_dead": t["totalTimeSpentDead"],
                }
                t_tumor = calculate_tumor_score(t_stats, info["gameDuration"], tier, t_role)
                d["their_tumor_sum"] += t_tumor
            except Exception:
                # Si falla, contamos solo el tuyo y la media will be off-by-1; aceptable
                pass

        if role != "DEFAULT":
            for t in teammates:
                other = t.get("teamPosition") or ""
                if not other:
                    continue
                key = f"{role}|{other}"
                rc = role_combo_stats.setdefault(key, {"games": 0, "wins": 0})
                rc["games"] += 1
                rc["wins"] += int(win)

        # Lane diff: compara stats con tu oponente en la misma posición del equipo enemigo
        if role and role != "DEFAULT":
            opponent = next(
                (p for p in info["participants"]
                 if p["teamId"] != me["teamId"] and (p.get("teamPosition") or "") == role),
                None,
            )
            if opponent:
                my_cs = me["totalMinionsKilled"] + me["neutralMinionsKilled"]
                op_cs = opponent["totalMinionsKilled"] + opponent["neutralMinionsKilled"]
                my_dmg = me["totalDamageDealtToChampions"]
                op_dmg = opponent["totalDamageDealtToChampions"]
                my_kda = (me["kills"] + me["assists"]) / max(1, me["deaths"])
                op_kda = (opponent["kills"] + opponent["assists"]) / max(1, opponent["deaths"])
                lane_diff_stats["games"] += 1
                # "ganaste tu lane" si superaste a tu rival en al menos 2 de 3 métricas
                wins_in_lane = sum([my_cs > op_cs, my_dmg > op_dmg, my_kda > op_kda])
                if wins_in_lane >= 2:
                    lane_diff_stats["won_lane"] += 1
                lane_diff_stats["cs_diff_sum"] += (my_cs - op_cs)
                lane_diff_stats["dmg_diff_sum"] += (my_dmg - op_dmg)
                lane_diff_stats["kda_diff_sum"] += (my_kda - op_kda)

    def pack_week(w):
        if not w or not w["games"]:
            return None
        return {
            "games": w["games"],
            "wins": w["wins"],
            "winrate": round(w["wins"] / w["games"] * 100),
            "avg_tumor": round(w["tumor_sum"] / w["games"]),
        }

    duo_out = []
    for pp, v in duo_stats.items():
        if v["games"] < 2:
            continue
        top_champ = max(v["champion_counts"], key=lambda c: v["champion_counts"][c])
        my_avg = round(v["my_tumor_sum"] / v["games"], 1) if v["games"] else 0
        their_avg = round(v["their_tumor_sum"] / v["games"], 1) if v["games"] else 0
        combined_avg = round((my_avg + their_avg) / 2.0, 1)
        duo_out.append({
            "puuid": pp,
            "nombre": v["name"],
            "games": v["games"],
            "wins": v["wins"],
            "winrate": round(v["wins"] / v["games"] * 100),
            "top_champion": top_champ,
            "my_avg_tumor": my_avg,
            "their_avg_tumor": their_avg,
            "combined_avg_tumor": combined_avg,
        })
    duo_out.sort(key=lambda d: (d["games"], d["winrate"]), reverse=True)

    # Best teammates: ordenar por WR + volumen
    best_teammates = sorted(
        [d for d in duo_out if d["games"] >= 2],
        key=lambda d: (d["winrate"], d["games"]),
        reverse=True,
    )[:5]

    # Worst nemesis: jugador concreto con el que tienes peor WR
    worst_nemesis = sorted(
        [d for d in duo_out if d["games"] >= 2],
        key=lambda d: (d["winrate"], -d["games"]),
    )[:5]

    # Champion pool: top 10 por volumen
    champion_pool_out = [
        {
            "champion": c,
            "games": v["games"],
            "wins": v["wins"],
            "winrate": round(v["wins"] / v["games"] * 100),
            "avg_tumor": round(v["tumor_sum"] / v["games"]),
        }
        for c, v in champion_pool.items()
    ]
    champion_pool_out.sort(key=lambda x: x["games"], reverse=True)

    role_combo_out = []
    for k, v in role_combo_stats.items():
        if v["games"] < 2:
            continue
        my_r, other_r = k.split("|")
        role_combo_out.append({
            "my_role": my_r,
            "other_role": other_r,
            "games": v["games"],
            "wins": v["wins"],
            "winrate": round(v["wins"] / v["games"] * 100),
        })

    hour_out = [
        {
            "hour": h,
            "games": v["games"],
            "winrate": round(v["wins"] / v["games"] * 100) if v["games"] else 0,
            "avg_tumor": round(v["tumor_sum"] / v["games"]) if v["games"] else 0,
        }
        for h, v in sorted(hour_stats.items())
    ]

    # Tilt forecast: probabilidad heurística de que tiltees si juegas otra ahora
    # Combina: hora actual vs horario tóxico, % de losses recientes, racha actual
    tilt_score = 0
    tilt_reasons = []
    now_hour = datetime.datetime.now().hour
    hour_data = next((h for h in hour_out if h["hour"] == now_hour), None)
    if hour_data and hour_data["games"] >= 3 and hour_data["winrate"] < 40:
        tilt_score += 30
        tilt_reasons.append(f"a las {now_hour:02d}h tu WR es solo {hour_data['winrate']}%")
    # Racha de losses
    last_5 = sorted(evolution, key=lambda e: e["date"], reverse=True)[:5]
    losses_last_5 = sum(1 for m in last_5 if not m["win"])
    if losses_last_5 >= 3:
        tilt_score += 25
        tilt_reasons.append(f"{losses_last_5}/5 losses recientes")
    # Tumor reciente alto
    if last_5:
        avg_recent = sum(m["tumor"] for m in last_5) / len(last_5)
        if avg_recent >= 50:
            tilt_score += 25
            tilt_reasons.append(f"tumor medio reciente {round(avg_recent)} (alto)")
    # Sesión muy larga (más de 4 partidas en las últimas 4 horas)
    cutoff_4h = now_ts - 4 * 3600
    recent_session = [m for m in evolution if m["date"] >= cutoff_4h]
    if len(recent_session) >= 4:
        tilt_score += 20
        tilt_reasons.append(f"{len(recent_session)} partidas en 4h (sesión larga)")
    tilt_score = min(100, tilt_score)
    tilt_forecast = {
        "score": tilt_score,
        "level": "alto" if tilt_score >= 60 else "medio" if tilt_score >= 30 else "bajo",
        "reasons": tilt_reasons,
        "advice": (
            "Para. Hidratate. Vuelve mañana." if tilt_score >= 60
            else "Cuidado. Una más y descansa." if tilt_score >= 30
            else "Estás fresco, sigue."
        ),
    }

    # Lane diff: cómo te va contra el oponente directo de tu lane
    lane_out = None
    if lane_diff_stats["games"] > 0:
        n = lane_diff_stats["games"]
        lane_out = {
            "games": n,
            "win_lane_rate": round(lane_diff_stats["won_lane"] / n * 100),
            "avg_cs_diff": round(lane_diff_stats["cs_diff_sum"] / n, 1),
            "avg_dmg_diff": round(lane_diff_stats["dmg_diff_sum"] / n),
            "avg_kda_diff": round(lane_diff_stats["kda_diff_sum"] / n, 2),
        }

    return jsonify({
        "summoner": f"{game_name}#{tag_line}",
        "tier": tier,
        "total_matches": len(evolution),
        "evolution": sorted(evolution, key=lambda e: e["date"]),
        "hour_stats": hour_out,
        "week_stats": {
            "this": pack_week(week_buckets["this"]),
            "last": pack_week(week_buckets["last"]),
        },
        "duo_stats": duo_out[:10],
        "role_combo_stats": role_combo_out,
        "champion_pool": champion_pool_out[:10],
        "best_teammates": best_teammates,
        "worst_nemesis": worst_nemesis,
        "tilt_forecast": tilt_forecast,
        "lane_diff": lane_out,
    })


def _kmeans(points, k, max_iter=40, seed=42):
    """Pure-Python k-means. points: list of float vectors. Returns (labels, centroids)."""
    if not points or k <= 0:
        return [], []
    n = len(points)
    if n <= k:
        return list(range(n)), [list(p) for p in points]
    dim = len(points[0])
    # Deterministic init: pick k points spread across the dataset by index
    rng_state = seed & 0xffffffff
    def _rng():
        nonlocal rng_state
        rng_state = (rng_state * 1103515245 + 12345) & 0x7fffffff
        return rng_state
    centroids = [list(points[(_rng() % n)]) for _ in range(k)]
    labels = [0] * n
    for _ in range(max_iter):
        # Assign
        changed = False
        for i, p in enumerate(points):
            best, best_d = 0, float('inf')
            for ci, c in enumerate(centroids):
                d = sum((p[j] - c[j]) ** 2 for j in range(dim))
                if d < best_d:
                    best_d, best = d, ci
            if labels[i] != best:
                changed = True
                labels[i] = best
        # Update
        sums = [[0.0] * dim for _ in range(k)]
        counts = [0] * k
        for i, p in enumerate(points):
            l = labels[i]
            counts[l] += 1
            for j in range(dim):
                sums[l][j] += p[j]
        for ci in range(k):
            if counts[ci] > 0:
                centroids[ci] = [sums[ci][j] / counts[ci] for j in range(dim)]
        if not changed:
            break
    return labels, centroids


# ---------------------------------------------------------------------------
# Death heatmap: agrega posiciones de muerte del jugador en sus últimas matches
# ---------------------------------------------------------------------------

# Summoner's Rift es ~ 14820 × 14881 unidades de juego. Lo normalizamos a [0,1].
SR_MAP_SIZE = 14820.0


def _get_timeline(match_id):
    """Fetch match-v5 timeline con caché en Redis (7d TTL — timelines son inmutables)."""
    try:
        from redis_client import r_get_json, r_set_json
        cached = r_get_json(f"timeline:{match_id}")
        if cached is not None:
            return cached
    except Exception:
        pass
    res = riot_get(f"{MATCH_DETAILS_URL}/{match_id}/timeline")
    if res.status_code != 200:
        return None
    data = res.json()
    try:
        from redis_client import r_set_json
        r_set_json(f"timeline:{match_id}", data, ttl=7 * 24 * 3600)
    except Exception:
        pass
    return data


@app.route('/analytics/death-heatmap', methods=['GET'])
def analytics_death_heatmap():
    """Agrega las posiciones de muerte del usuario en sus últimas N partidas
    ranked (SR, mapa 11). Devuelve coords normalizadas [0,1].

    Query params:
      - game_name, tag_line: requeridos
      - count: max 10 (default 10) — cada match consume 1 timeline call (Riot)
      - queue: 420|440 (default 420)
    """
    game_name = request.args.get('game_name')
    tag_line = request.args.get('tag_line')
    if not game_name or not tag_line:
        return jsonify({"error": "game_name + tag_line requeridos"}), 400
    try:
        count = max(1, min(10, int(request.args.get('count', 10))))
    except Exception:
        count = 10
    queue = request.args.get('queue', '420')
    try:
        queue_int = int(queue)
    except Exception:
        queue_int = 420
    if queue_int not in RANKED_QUEUES:
        return jsonify({"error": "Heatmap solo en SoloQ/Flex"}), 400

    acc = riot_get(f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name}/{tag_line}")
    if acc.status_code != 200:
        return jsonify({"error": "Cuenta no encontrada"}), 404
    puuid = acc.json()["puuid"]

    ids_res = riot_get(f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count={count}&queue={queue_int}")
    if ids_res.status_code != 200:
        return jsonify({"error": "No se pudieron listar partidas"}), 502
    match_ids = ids_res.json() or []

    deaths = []
    matches_processed = 0
    for mid in match_ids:
        # Match details para resolver participantId del user
        mres = riot_get(f"{MATCH_DETAILS_URL}/{mid}")
        if mres.status_code != 200:
            continue
        info = mres.json().get("info", {})
        if int(info.get("mapId", 0)) != 11:  # solo SR
            continue
        parts = info.get("participants", []) or []
        # find user via puuid o riot_id (puuid rotation)
        me = find_player_in_participants(parts, puuid, game_name, tag_line)
        if not me:
            continue
        my_pid = me.get("participantId")
        if not my_pid:
            continue

        timeline = _get_timeline(mid)
        if not timeline:
            continue
        frames = timeline.get("info", {}).get("frames", []) or []
        for frame in frames:
            for ev in frame.get("events", []) or []:
                if ev.get("type") != "CHAMPION_KILL":
                    continue
                if ev.get("victimId") != my_pid:
                    continue
                pos = ev.get("position") or {}
                x = pos.get("x", 0)
                y = pos.get("y", 0)
                deaths.append({
                    "x": round(x / SR_MAP_SIZE, 4),
                    "y": round(y / SR_MAP_SIZE, 4),
                    "match_id": mid,
                    "timestamp_ms": ev.get("timestamp"),
                    "killer_id": ev.get("killerId"),
                })
        matches_processed += 1

    return jsonify({
        "puuid": puuid,
        "matches_processed": matches_processed,
        "queue": queue_int,
        "deaths": deaths,
        "total_deaths": len(deaths),
    })


@app.route('/analytics/clusters', methods=['GET'])
def analytics_clusters():
    """Cluster jugadores por estilo usando k-means sobre prior_tumor, recent_avg, win_rate, tilt/streak.

    Query params:
      - k: número de clusters (default 4, max 8)
      - limit: máx jugadores a procesar (default 500)
    """
    try:
        k = max(2, min(8, int(request.args.get('k', 4))))
    except Exception:
        k = 4
    try:
        limit = max(20, min(2000, int(request.args.get('limit', 500))))
    except Exception:
        limit = 500

    db = _pred_db()
    rows = db.execute(
        """SELECT puuid, tier, prior_tumor, sample_size, recent_avg,
                  recent_losses, recent_wins, is_tilted, is_hotstreak, likely_role
           FROM player_priors_cache
           WHERE sample_size >= 3
           ORDER BY cached_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()

    if not rows or len(rows) < k:
        return jsonify({"clusters": [], "n": len(rows), "k": k, "message": "Not enough player data"})

    points = []
    meta = []
    for r in rows:
        puuid, tier, prior, sample, recent_avg, losses, wins, tilted, streak, role = r
        wl = (wins or 0) + (losses or 0)
        win_rate = (wins / wl) if wl else 0.5
        # Feature vector normalized to roughly [0, 1]
        vec = [
            (prior or 50) / 100.0,
            (recent_avg or 50) / 100.0,
            win_rate,
            1.0 if tilted else 0.0,
            1.0 if streak else 0.0,
        ]
        points.append(vec)
        meta.append({
            "puuid": puuid,
            "tier": tier or "UNRANKED",
            "prior_tumor": prior or 0,
            "recent_avg": recent_avg or 0,
            "win_rate": round(win_rate * 100, 1),
            "wins": wins or 0,
            "losses": losses or 0,
            "is_tilted": bool(tilted),
            "is_hotstreak": bool(streak),
            "role": role or "",
        })

    labels, centroids = _kmeans(points, k)

    # ------------------------------------------------------------------
    # Archetype classifier — orden de prioridad, primero que matchea gana.
    # Cada uno: (key, predicate(centroid_dict), info dict)
    # info: name, emoji, color (hex), description, sort_dir
    #   sort_dir = -1: peor primero (tumor); +1: mejor primero (carry/limpios)
    # ------------------------------------------------------------------
    # NOTA: el centroid_summary tiene valores ya escalados a [0, 100]
    # (avg_prior, avg_recent, win_rate, tilt_frac, streak_frac). Los predicados
    # comparan en esa escala — no en [0, 1].
    ARCHETYPES = [
        ("tumor_cronico", lambda c: c["avg_prior"] > 65, {
            "name": "Tumor Crónico",
            "emoji": "💀",
            "color": "#dc2626",  # red-600
            "description": "Históricamente tóxicos. Tumor alto + winrate bajo. Si los ves, sufre.",
            "sort_dir": -1,
        }),
        ("hot_streak", lambda c: c["streak_frac"] > 40, {
            "name": "Hot Streak",
            "emoji": "🔥",
            "color": "#f97316",  # orange-500
            "description": "En racha caliente últimos días. Cuidado: están on fire.",
            "sort_dir": +1,
        }),
        ("en_tilt", lambda c: c["tilt_frac"] > 40, {
            "name": "En Tilt",
            "emoji": "🌋",
            "color": "#ea580c",  # orange-600
            "description": "Acaban de tener mala racha. Probable que sigan flojos.",
            "sort_dir": -1,
        }),
        ("carry_estable", lambda c: c["avg_prior"] < 35 and c["win_rate"] > 55, {
            "name": "Carry Estable",
            "emoji": "👑",
            "color": "#facc15",  # yellow-400
            "description": "Tumor bajo + winrate alto. Los buenos de verdad.",
            "sort_dir": +1,
        }),
        ("inestable", lambda c: abs(c["avg_prior"] - c["avg_recent"]) > 20, {
            "name": "Inestable",
            "emoji": "⚡",
            "color": "#a855f7",  # purple-500
            "description": "Su rendimiento varía mucho. Pueden hacer cualquier cosa.",
            "sort_dir": -1,
        }),
        ("solido", lambda c: c["avg_prior"] < 45 and c["win_rate"] > 50, {
            "name": "Sólido",
            "emoji": "🛡",
            "color": "#22c55e",  # green-500
            "description": "Decente sin destacar. Reliable.",
            "sort_dir": +1,
        }),
        ("bajon", lambda c: c["avg_recent"] > 55 and c["avg_prior"] < 50, {
            "name": "En Bajón",
            "emoji": "📉",
            "color": "#0891b2",  # cyan-600
            "description": "Prior medio pero últimas partidas malas. Quizás pase.",
            "sort_dir": -1,
        }),
        ("victima", lambda c: c["avg_prior"] < 35 and c["win_rate"] < 45, {
            "name": "Víctima",
            "emoji": "😢",
            "color": "#64748b",  # slate-500
            "description": "Tumor bajo pero pierden mucho. Carry sin equipo.",
            "sort_dir": +1,
        }),
        ("promedio", lambda c: True, {  # catch-all
            "name": "Promedio",
            "emoji": "⚖",
            "color": "#94a3b8",  # slate-400
            "description": "Sin nada llamativo. Ni para bien ni para mal.",
            "sort_dir": -1,
        }),
    ]

    clusters = []
    for ci in range(k):
        members = [meta[i] for i in range(len(meta)) if labels[i] == ci]
        if not members:
            continue
        c = centroids[ci]
        prior_norm, recent_norm, win_rate, tilt_frac, streak_frac = c
        avg_prior = prior_norm * 100
        avg_recent = recent_norm * 100
        centroid_summary = {
            "avg_prior": round(avg_prior, 1),
            "avg_recent": round(avg_recent, 1),
            "win_rate": round(win_rate * 100, 1),
            "tilt_frac": round(tilt_frac * 100, 1),
            "streak_frac": round(streak_frac * 100, 1),
        }
        # Encuentra archetype
        archetype = next(
            (info for key, predicate, info in ARCHETYPES if predicate(centroid_summary)),
            ARCHETYPES[-1][2],  # fallback Promedio
        )
        # Ordena samples según el archetype: si es bueno (sort_dir=+1) muestra
        # los mejores primero, si es malo (sort_dir=-1) muestra los peores primero
        members.sort(key=lambda m: (-m["prior_tumor"] if archetype["sort_dir"] == -1
                                    else m["prior_tumor"]))
        clusters.append({
            "id": ci,
            "name": archetype["name"],
            "emoji": archetype["emoji"],
            "color": archetype["color"],
            "description": archetype["description"],
            "size": len(members),
            "centroid": centroid_summary,
            "samples": members[:6],
        })

    # Orden de visualización: peores primero (más alto avg_prior arriba)
    clusters.sort(key=lambda c: -c["centroid"]["avg_prior"])
    return jsonify({"clusters": clusters, "n": len(rows), "k": k})


@app.route('/tuningReport', methods=['GET'])
def tuning_report_endpoint():
    """Reporte empírico para afinar el modelo.

    Devuelve accuracy segmentada por:
      - Banda de confianza (low/medium/high)
      - Magnitud de median_diff (cerca del tie / claro)
      - Si se usó el tiebreaker por suma o no
      - Por número de streamers en cada equipo
      - Por rol predominante del equipo (si los hay)
      - Sesgo blue vs red (¿el modelo favorece una lado?)
      - Errores destacados (más recientes)

    Se puede invocar manualmente; también sirve para que un agent lea el JSON
    y proponga cambios en pesos/umbrales del engine.
    """
    db = _pred_db()
    source = request.args.get("source", "all")  # "live" | "backtest" | "all"

    live_rows = db.execute("""
        SELECT match_id, predicted_winner, actual_winner, correct, confidence,
               blue_team_tumor, red_team_tumor, blue_team_sum, red_team_sum,
               median_diff, sum_diff, used_sum_tiebreaker,
               blue_priors, red_priors, blue_roles, red_roles,
               blue_streamers, red_streamers, created_at, resolved
        FROM prediction_logs
        WHERE resolved = 1 AND predicted_winner IS NOT NULL
    """).fetchall() if source in ("live", "all") else []

    backtest_rows = db.execute("""
        SELECT match_id, predicted_winner, actual_winner, correct, confidence,
               blue_team_tumor, red_team_tumor, blue_team_sum, red_team_sum,
               median_diff, sum_diff, used_sum_tiebreaker,
               blue_priors, red_priors, blue_roles, red_roles,
               0 AS blue_streamers, 0 AS red_streamers, created_at, 1 AS resolved
        FROM backtest_logs
        WHERE predicted_winner IS NOT NULL
    """).fetchall() if source in ("backtest", "all") else []

    rows = list(live_rows) + list(backtest_rows)

    if not rows:
        return jsonify({
            "total_resolved": 0,
            "message": "Aún no hay predicciones resueltas para analizar. Juega y comprueba algunas."
        })

    def pct(n, d):
        return round(n / d * 100, 1) if d else 0.0

    def bucket_by(key_fn):
        buckets = {}
        for r in rows:
            k = key_fn(r)
            b = buckets.setdefault(k, {"n": 0, "hits": 0})
            b["n"] += 1
            if r[3]:
                b["hits"] += 1
        return {
            k: {"n": v["n"], "correct": v["hits"], "accuracy": pct(v["hits"], v["n"])}
            for k, v in buckets.items()
        }

    total = len(rows)
    correct = sum(1 for r in rows if r[3])
    accuracy = pct(correct, total)

    # Confianza
    def conf_band(r):
        c = r[4] or 0
        if c < 30:  return "low (<30)"
        if c < 60:  return "med (30-59)"
        return "high (60+)"
    by_confidence = bucket_by(conf_band)

    # Magnitud de diferencia de medianas
    def med_band(r):
        d = abs(r[9] or 0)
        if d < 5:    return "very close (0-4)"
        if d < 10:   return "close (5-9)"
        if d < 20:   return "clear (10-19)"
        return "obvious (20+)"
    by_median_gap = bucket_by(med_band)

    # Si el tiebreaker por suma se usó
    by_tiebreaker = bucket_by(lambda r: "sum_tiebreaker" if r[11] else "median_only")

    # Sesgo blue vs red
    blue_wins = sum(1 for r in rows if r[1] == "blue")
    red_wins  = sum(1 for r in rows if r[1] == "red")
    blue_correct = sum(1 for r in rows if r[1] == "blue" and r[3])
    red_correct  = sum(1 for r in rows if r[1] == "red"  and r[3])
    side_bias = {
        "predicted_blue":  {"n": blue_wins, "correct": blue_correct, "accuracy": pct(blue_correct, blue_wins)},
        "predicted_red":   {"n": red_wins,  "correct": red_correct,  "accuracy": pct(red_correct,  red_wins)},
    }

    # Streamers en los equipos
    def streamer_band(r):
        total_streamers = (r[16] or 0) + (r[17] or 0)
        if total_streamers == 0: return "no streamers"
        if total_streamers == 1: return "1 streamer"
        return "2+ streamers"
    by_streamers = bucket_by(streamer_band)

    # Casos de fallo reciente (para inspección manual)
    misses = [r for r in rows if not r[3]]
    misses_recent = sorted(misses, key=lambda r: r[18] or 0, reverse=True)[:10]
    def miss_summary(r):
        return {
            "match_id": r[0],
            "predicted": r[1],
            "actual": r[2],
            "confidence": r[4],
            "blue_tumor": r[5],
            "red_tumor": r[6],
            "median_diff": r[9],
            "sum_diff": r[10],
            "used_sum_tiebreaker": bool(r[11]),
            "blue_priors": json.loads(r[12] or "[]"),
            "red_priors":  json.loads(r[13] or "[]"),
            "blue_roles": json.loads(r[14] or "[]"),
            "red_roles":  json.loads(r[15] or "[]"),
            "streamers": (r[16] or 0) + (r[17] or 0),
        }

    return jsonify({
        "generated_at": time.time(),
        "source": source,
        "total_resolved": total,
        "total_correct": correct,
        "accuracy_overall": accuracy,
        "sources_breakdown": {
            "live_predictions": len(live_rows),
            "backtest_replays": len(backtest_rows),
        },
        "by_confidence_band": by_confidence,
        "by_median_gap": by_median_gap,
        "by_tiebreaker": by_tiebreaker,
        "side_bias": side_bias,
        "by_streamer_count": by_streamers,
        "misses_recent_10": [miss_summary(r) for r in misses_recent],
        "suggestions_hints": _tuning_suggestions(by_confidence, by_median_gap, by_tiebreaker, side_bias, accuracy),
    })


def _tuning_suggestions(by_conf, by_med, by_tie, side_bias, overall):
    """Reglas heurísticas que devuelven hints para humanos o agents."""
    hints = []
    if overall < 55:
        hints.append(f"Accuracy overall {overall}% es bajo (<55). El modelo casi tira moneda, revisar pesos de ejes.")
    # Confidence que no correlaciona con accuracy
    high = by_conf.get("high (60+)", {})
    low  = by_conf.get("low (<30)", {})
    if high and low and high.get("accuracy", 0) < low.get("accuracy", 0) + 5:
        hints.append("High-confidence no mejora mucho sobre low-confidence. La escala de confidence está mal calibrada — bajar confidence_scale o subir tie_threshold.")
    # Sesgo blue/red
    b = side_bias["predicted_blue"]["accuracy"]
    r = side_bias["predicted_red"]["accuracy"]
    if abs(b - r) > 10:
        hints.append(f"Sesgo detectado: predicciones blue tienen {b}% acierto y red {r}%. Desequilibrio, revisar si algo depende del team_id.")
    # Very close casos que sí aciertan mucho
    vc = by_med.get("very close (0-4)", {})
    if vc and vc.get("accuracy", 0) > 55:
        hints.append("Las predicciones 'very close' aciertan decentemente — considerar bajar tie_threshold para cubrir más casos.")
    # Tiebreaker útil o no
    st = by_tie.get("sum_tiebreaker", {})
    mo = by_tie.get("median_only", {})
    if st and mo:
        d = st.get("accuracy", 0) - mo.get("accuracy", 0)
        if d < -5:
            hints.append("El tiebreaker por suma acierta peor que las predicciones por mediana. Reconsiderar el tiebreaker.")
        elif d > 5:
            hints.append("El tiebreaker por suma mejora accuracy. Mantenerlo.")
    if not hints:
        hints.append("Nada obvio que tocar. Sigue acumulando datos.")
    return hints


# ============================================================================
# AUTH + CURRENCY (Tumor Coins)
# ============================================================================

def _current_user():
    """Lee el JWT del header Authorization y devuelve el user dict, o None."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    payload = _auth.verify_jwt(token)
    if not payload:
        return None
    user_id = payload.get("user_id")
    if not user_id:
        return None
    return _users.get_user_by_id(user_id)


@app.route('/auth/discord/login', methods=['GET'])
def auth_discord_login():
    """Redirige al user a Discord para que autorice."""
    return redirect(_auth.discord_auth_redirect_url())


@app.route('/auth/discord/callback', methods=['GET'])
def auth_discord_callback():
    """Callback de Discord. Canjea code → access_token → user info → JWT.
    Redirige al frontend con ?token=JWT."""
    code = request.args.get("code")
    if not code:
        return redirect(f"{_auth.FRONTEND_URL}?auth_error=no_code")
    token_data = _auth.discord_exchange_code(code)
    if not token_data or "access_token" not in token_data:
        return redirect(f"{_auth.FRONTEND_URL}?auth_error=token_exchange_failed")
    user_info = _auth.discord_fetch_user(token_data["access_token"])
    if not user_info or "id" not in user_info:
        return redirect(f"{_auth.FRONTEND_URL}?auth_error=user_fetch_failed")

    user = _users.upsert_user_from_discord(
        discord_id=user_info["id"],
        username=user_info.get("username", "unknown"),
        avatar_hash=user_info.get("avatar"),
    )
    jwt = _auth.issue_jwt({"user_id": user["id"], "discord_id": user["discord_id"]})
    return redirect(f"{_auth.FRONTEND_URL}?token={jwt}")


@app.route('/auth/rso/login', methods=['GET'])
def auth_rso_login():
    """RSO login. Solo activo si tienes credenciales de Riot."""
    url = _auth.rso_auth_redirect_url()
    if not url:
        return jsonify({"error": "RSO no está configurado. Pide approval a Riot."}), 503
    return redirect(url)


@app.route('/auth/rso/callback', methods=['GET'])
def auth_rso_callback():
    """RSO callback: vincula el Riot account al user logueado por Discord.
    Si no hay sesión activa, crea un user nuevo basado en el sub de RSO."""
    code = request.args.get("code")
    if not code:
        return redirect(f"{_auth.FRONTEND_URL}?auth_error=no_code")
    token_data = _auth.rso_exchange_code(code)
    if not token_data or "access_token" not in token_data:
        return redirect(f"{_auth.FRONTEND_URL}?auth_error=rso_token_failed")
    info = _auth.rso_fetch_user(token_data["access_token"])
    if not info or "sub" not in info:
        return redirect(f"{_auth.FRONTEND_URL}?auth_error=rso_userinfo_failed")
    # info["sub"] es el puuid de Riot
    puuid = info["sub"]
    # Recuperar gameName/tagLine vía account-v1
    acc_res = riot_get(f"{RIOT_BASE_URL}/riot/account/v1/accounts/by-puuid/{puuid}")
    if acc_res.status_code != 200:
        return redirect(f"{_auth.FRONTEND_URL}?auth_error=riot_account_failed")
    acc = acc_res.json()
    riot_id = f"{acc.get('gameName', '?')}#{acc.get('tagLine', '?')}"

    # Si hay JWT en query → vincula al user existente. Si no, crea uno con discord_id=riot_puuid
    existing_token = request.args.get("state")  # opcional: pasaríamos jwt como state
    if existing_token:
        payload = _auth.verify_jwt(existing_token)
        if payload and payload.get("user_id"):
            _users.link_riot_account(payload["user_id"], puuid, riot_id)
            return redirect(f"{_auth.FRONTEND_URL}?riot_linked=1")
    # Sin sesión: usa puuid como discord_id ficticio (workaround si solo usa RSO)
    user = _users.upsert_user_from_discord(
        discord_id=f"rso_{puuid[:16]}",
        username=acc.get("gameName", "RiotUser"),
        avatar_hash=None,
    )
    _users.link_riot_account(user["id"], puuid, riot_id)
    jwt = _auth.issue_jwt({"user_id": user["id"], "discord_id": user["discord_id"]})
    return redirect(f"{_auth.FRONTEND_URL}?token={jwt}")


@app.route('/auth/me', methods=['GET'])
def auth_me():
    """Devuelve el user actual basado en el JWT."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    daily = _users.daily_status(user["id"])
    user["can_claim_daily"] = daily["can_claim"]
    user["daily"] = daily   # {amount, can_claim, next_claim_at, last_claim_at}
    return jsonify(user)


@app.route('/auth/link-riot', methods=['POST'])
def auth_link_riot():
    """Vincula un Riot ID al user actual."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    game_name = data.get("game_name")
    tag_line = data.get("tag_line")
    if not game_name or not tag_line:
        return jsonify({"error": "Falta game_name/tag_line"}), 400

    acc_res = riot_get(f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name}/{tag_line}")
    if acc_res.status_code == 404:
        return jsonify({"error": "Riot ID no encontrado"}), 404
    if acc_res.status_code != 200:
        return jsonify({"error": f"Riot API error {acc_res.status_code}"}), 502
    puuid = acc_res.json()["puuid"]
    riot_id = f"{game_name}#{tag_line}"
    _users.link_riot_account(user["id"], puuid, riot_id)
    return jsonify(_users.get_user_by_id(user["id"]))


@app.route('/auth/unlink-riot', methods=['POST'])
def auth_unlink_riot():
    """Desvincula el Riot ID del user actual."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    _users.unlink_riot_account(user["id"])
    return jsonify(_users.get_user_by_id(user["id"]))


@app.route('/currency/balance', methods=['GET'])
def currency_balance():
    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    txs = _users.get_recent_transactions(user["id"], limit=20)
    daily = _users.daily_status(user["id"])
    return jsonify({
        "currency": user["currency"],
        "can_claim_daily": daily["can_claim"],
        "daily": daily,
        "recent_transactions": txs,
    })


@app.route('/currency/daily', methods=['POST'])
def currency_daily():
    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    awarded = _users.DAILY_REWARD_AMOUNT
    new_balance = _users.claim_daily(user["id"])
    if new_balance is None:
        return jsonify({"error": "Aún no puedes reclamar el daily reward"}), 429
    return jsonify({"currency": new_balance, "awarded": awarded, "daily": _users.daily_status(user["id"])})


# ============================================================================
# ML MODEL (regresión logística sobre prediction_logs históricos)
# ============================================================================

@app.route('/ml/train', methods=['POST'])
def ml_train():
    """Entrena el modelo ML con todos los logs disponibles."""
    import ml_predictor
    db = _pred_db()
    rows = []
    try:
        cur = db.execute("SELECT * FROM prediction_logs WHERE resolved=1 AND predicted_winner IS NOT NULL AND actual_winner IS NOT NULL")
        cols = [c[0] for c in cur.description]
        rows.extend(dict(zip(cols, r)) for r in cur.fetchall())
    except Exception:
        pass
    try:
        cur = db.execute("SELECT * FROM backtest_logs WHERE predicted_winner IS NOT NULL AND actual_winner IS NOT NULL")
        cols = [c[0] for c in cur.description]
        rows.extend(dict(zip(cols, r)) for r in cur.fetchall())
    except Exception:
        pass

    if len(rows) < 20:
        return jsonify({"error": f"Solo {len(rows)} muestras. Necesitas al menos 20 para entrenar."}), 400
    split = int(len(rows) * 0.8)
    train, test = rows[:split], rows[split:]
    weights = ml_predictor.train_logistic_regression(train)
    train_eval = ml_predictor.evaluate(train, weights)
    test_eval = ml_predictor.evaluate(test, weights)
    ml_predictor.save_model(weights, meta={"train_eval": train_eval, "test_eval": test_eval, "n_train": len(train)})
    return jsonify({
        "ok": True,
        "n_total": len(rows),
        "n_train": len(train),
        "n_test": len(test),
        "train_accuracy": train_eval["accuracy"],
        "test_accuracy": test_eval["accuracy"],
    })


@app.route('/ml/info', methods=['GET'])
def ml_info():
    """Info del modelo entrenado."""
    import ml_predictor
    model = ml_predictor.load_model()
    if not model:
        return jsonify({"trained": False})
    return jsonify({"trained": True, "meta": model.get("meta", {})})


# ============================================================================
# ACHIEVEMENTS
# ============================================================================

@app.route('/achievements', methods=['GET'])
def achievements_mine():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    _users.evaluate_achievements(user["id"])
    return jsonify(_users.list_achievements(user["id"]))


# ============================================================================
# SETTINGS
# ============================================================================

@app.route('/settings', methods=['GET'])
def settings_get():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    return jsonify(_users.get_settings(user["id"]))


@app.route('/settings', methods=['POST'])
def settings_save():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    data = request.get_json() or {}
    saved = _users.save_settings(user["id"], **data)
    return jsonify(saved)


# ============================================================================
# PUBLIC PROFILE
# ============================================================================

@app.route('/profile/<path:riot_id>', methods=['GET'])
def public_profile(riot_id):
    """Vista pública del perfil. Solo si tiene public_profile=1."""
    profile = _users.find_user_by_riot_id_public(riot_id)
    if not profile:
        return jsonify({"error": "Perfil no encontrado o privado"}), 404
    achievements = _users.list_achievements(profile["id"])
    unlocked = [a for a in achievements if a["unlocked"]]
    return jsonify({
        "user": profile,
        "achievements_unlocked": unlocked,
        "achievement_count": len(unlocked),
        "total_achievements": len(achievements),
    })


# ============================================================================
# SMURF / SUSPICIOUS DETECTION
# ============================================================================

def _detect_smurf_signals(player):
    """Heurística simple para detectar smurfs/cuentas raras en live game.
    Devuelve lista de razones (vacía si nada raro)."""
    signals = []
    tier = (player.get("tier") or "").upper()
    avg = player.get("avg_tumor_score") or 50
    games = player.get("estimated_games") or 0
    mp = player.get("mastery_points") or 0
    sample = player.get("champion_total_sample") or 0

    # Tumor muy bajo en elo bajo
    if tier in ("IRON", "BRONZE", "SILVER") and avg <= 15 and sample >= 3:
        signals.append("🥷 stats demasiado buenas para su elo")
    # Cuenta nueva (poca mastery total) jugando ranked solo
    if mp < 5000 and tier in ("GOLD", "PLATINUM", "EMERALD", "DIAMOND") and sample >= 3:
        signals.append("🆕 cuenta muy nueva en su elo")
    # Streak ganadora muy alta
    if (player.get("recent_wins") or 0) >= 7 and avg <= 25:
        signals.append("📈 winstreak +7 con stats sólidas")
    return signals


# ============================================================================
# NOTIFICATIONS (per-user, polled)
# ============================================================================

@app.route('/notifications', methods=['GET'])
def get_notifications():
    user = _current_user()
    if not user:
        return jsonify([])
    return jsonify(_users.get_unread_notifications(user["id"]))


@app.route('/notifications/read', methods=['POST'])
def mark_read():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    data = request.get_json() or {}
    ids = data.get("ids")
    _users.mark_notifications_read(user["id"], ids)
    return jsonify({"ok": True})


# ============================================================================
# LEADERBOARDS
# ============================================================================

@app.route('/leaderboards/<kind>', methods=['GET'])
def leaderboards(kind):
    if kind == "currency":
        return jsonify(_users.leaderboard_top_currency(limit=20))
    if kind == "bets":
        return jsonify(_users.leaderboard_top_bet_winners(limit=20))
    if kind == "accuracy":
        # Top users por accuracy de predicciones live
        # Combina prediction_logs por viewer_puuid → users
        db = _pred_db()
        rows = db.execute("""
            SELECT viewer_puuid, COUNT(*) AS total,
                   SUM(CASE WHEN correct=1 THEN 1 ELSE 0 END) AS hits
            FROM prediction_logs
            WHERE resolved=1 AND predicted_winner IS NOT NULL
            GROUP BY viewer_puuid
            HAVING COUNT(*) >= 5
        """).fetchall()
        result = []
        for puuid, total, hits in rows:
            cur = _users._exec("SELECT id, discord_id, discord_username, discord_avatar, currency, riot_id FROM users WHERE riot_puuid=?", (puuid,))
            urow = cur.fetchone()
            if not urow:
                continue
            accuracy = round((hits or 0) / total * 100, 1)
            result.append({
                "user_id": urow[0], "discord_id": urow[1], "username": urow[2], "avatar": urow[3],
                "currency": urow[4], "riot_id": urow[5],
                "total": total, "hits": hits, "accuracy": accuracy,
            })
        result.sort(key=lambda x: (x["accuracy"], x["total"]), reverse=True)
        return jsonify(result[:20])
    return jsonify({"error": "Tipo desconocido. Usa: currency | bets | accuracy"}), 400


# ============================================================================
# FRIENDS
# ============================================================================

@app.route('/friends', methods=['GET'])
def friends_list():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    return jsonify(_users.list_friends(user["id"]))


@app.route('/friends/add', methods=['POST'])
def friends_add():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    data = request.get_json() or {}
    riot_id = data.get("riot_id", "").strip()
    if "#" not in riot_id:
        return jsonify({"error": "Formato: Nombre#TAG"}), 400
    target_id = _users.find_user_by_riot_id(riot_id)
    if not target_id:
        return jsonify({"error": "Ese Riot ID no está registrado en Tumor Tracker"}), 404
    result = _users.send_friend_request(user["id"], target_id)
    if not result:
        return jsonify({"error": "No puedes añadirte a ti mismo"}), 400
    # Notificar al target si es nueva
    if result.get("status") == "pending":
        try:
            _users.push_notification(
                user_id=target_id,
                notif_type="friend_request",
                title="Nueva solicitud de amistad",
                body=f"{user['username']} quiere ser tu amigo",
                link="#/friends", icon="👋",
            )
        except Exception:
            pass
    return jsonify(result)


@app.route('/friends/<int:friendship_id>/accept', methods=['POST'])
def friends_accept(friendship_id):
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    if not _users.accept_friend(user["id"], friendship_id):
        return jsonify({"error": "No se pudo aceptar"}), 400
    return jsonify({"ok": True})


@app.route('/friends/<int:friendship_id>/reject', methods=['POST'])
def friends_reject(friendship_id):
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    _users.reject_friend(user["id"], friendship_id)
    return jsonify({"ok": True})


# ============================================================================
# COMPARISON ROOMS
# ============================================================================

@app.route('/rooms/create', methods=['POST'])
def rooms_create():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    data = request.get_json() or {}
    name = data.get("name", "").strip()[:80]
    room = _users.create_room(user["id"], name)
    if not room:
        return jsonify({"error": "No se pudo crear la sala"}), 500
    # Owner se añade auto si tiene riot_id
    if user.get("riot_id"):
        _users.add_room_member(room["id"], user["riot_id"])
        room = _users.get_room_by_id(room["id"])
    return jsonify(room)


@app.route('/rooms/<code>', methods=['GET'])
def rooms_get(code):
    room = _users.get_room_by_code(code)
    if not room:
        return jsonify({"error": "Sala no encontrada"}), 404
    return jsonify(room)


@app.route('/rooms/<code>/join', methods=['POST'])
def rooms_join(code):
    """Una user con su Riot ID a la sala. Acepta riot_id en body o usa el del user logueado."""
    room = _users.get_room_by_code(code)
    if not room:
        return jsonify({"error": "Sala no encontrada"}), 404
    data = request.get_json() or {}
    riot_id = data.get("riot_id", "").strip()
    if not riot_id:
        user = _current_user()
        if user and user.get("riot_id"):
            riot_id = user["riot_id"]
    if not riot_id or "#" not in riot_id:
        return jsonify({"error": "Riot ID requerido (formato Nombre#TAG)"}), 400
    if len(room["members"]) >= 8:
        return jsonify({"error": "Sala llena (máximo 8 miembros)"}), 400
    _users.add_room_member(room["id"], riot_id)
    return jsonify(_users.get_room_by_id(room["id"]))


@app.route('/rooms/<code>/leave', methods=['POST'])
def rooms_leave(code):
    """Sale de la sala. Usa el riot_id del user logueado (body opcional)."""
    room = _users.get_room_by_code(code)
    if not room:
        return jsonify({"error": "Sala no encontrada"}), 404
    user = _current_user()
    data = request.get_json(silent=True) or {}
    riot_id = (data.get("riot_id") or "").strip()
    if not riot_id and user and user.get("riot_id"):
        riot_id = user["riot_id"]
    if not riot_id:
        return jsonify({"error": "riot_id requerido"}), 400
    _users.remove_room_member(room["id"], riot_id)
    return jsonify({"ok": True})


@app.route('/rooms/mine', methods=['GET'])
def rooms_mine():
    """Lista salas donde el user es owner o miembro."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    rooms = _users.list_rooms_for_user(user["id"], user.get("riot_id"))
    return jsonify(rooms)


@app.route('/rooms/<code>', methods=['DELETE'])
def rooms_delete(code):
    """Sólo el owner puede borrar la sala completa."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    room = _users.get_room_by_code(code)
    if not room:
        return jsonify({"error": "Sala no encontrada"}), 404
    ok = _users.delete_room(room["id"], user["id"])
    if not ok:
        return jsonify({"error": "Solo el dueño puede borrar la sala"}), 403
    return jsonify({"ok": True})


@app.route('/rooms/<code>/bravery/toggle', methods=['POST'])
def rooms_bravery_toggle(code):
    """Owner only: activa/desactiva el modo Bravery de la sala.

    Cuando bravery_active=True, todos los miembros pueden lockear su setup
    con dimensiones (champ + lane + items) compartiendo room_code.
    Cuando =False, el modo Bravery de la sala está cerrado.
    """
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    room = _users.get_room_by_code(code)
    if not room:
        return jsonify({"error": "Sala no encontrada"}), 404
    if room["owner_user_id"] != user["id"]:
        return jsonify({"error": "Sólo el dueño puede activar Bravery"}), 403
    data = request.get_json(silent=True) or {}
    target = bool(data.get("active", not room["bravery_active"]))
    updated = _users.set_room_bravery(room["id"], target)
    # Notificar a miembros si se activa
    if target and not room["bravery_active"]:
        for m in (updated.get("members") or []):
            try:
                # Buscamos el user por riot_id
                cur = _users._exec(
                    "SELECT id FROM users WHERE riot_id=?", (m["riot_id"],)
                )
                row = cur.fetchone()
                if row and row[0] != user["id"]:
                    _users.push_notification(
                        user_id=row[0], notif_type="room_bravery_started",
                        title=f"🎲 Bravery activo en {room.get('name') or room['code']}",
                        body="Entra y lockea tu setup",
                        link="#/social", icon="🎲",
                    )
            except Exception:
                pass
    return jsonify(updated)


# ============================================================================
# BETS P2P
# ============================================================================

def _augment_bet(bet):
    """Añade nombres de usuarios al dict de bet para que la UI no haga lookups extra."""
    if not bet:
        return None
    user_ids = [bet.get("creator_user_id"), bet.get("taker_user_id")]
    briefs = _users.get_users_brief(user_ids)
    bet["creator"] = briefs.get(bet.get("creator_user_id"))
    bet["taker"] = briefs.get(bet.get("taker_user_id")) if bet.get("taker_user_id") else None
    return bet


def _resolve_match_queue_id(match_id):
    """Resuelve el queueId de un match. Devuelve int o None si no se puede.

    Order: live cache (partidas en curso) → Match v5 (terminadas).
    """
    try:
        cache = load_live_cache()
        snap = cache.get(match_id)
        if snap:
            data = snap.get("data") or {}
            qid = data.get("queue_id") or data.get("queueId")
            if qid is not None:
                return int(qid)
    except Exception:
        pass
    try:
        mres = riot_get(f"{MATCH_DETAILS_URL}/{match_id}")
        if mres.status_code == 200:
            return int(mres.json().get("info", {}).get("queueId", 0))
    except Exception:
        pass
    return None


TIER_MULTIPLIER = {
    # Cuanto más alto el tier del jugador, más multiplicador da la apuesta de
    # que será el peor (más sorprendente). Cuanto más bajo, menos paga porque
    # es esperable que un Iron sea sus.
    "IRON": 1.20, "BRONZE": 1.50, "SILVER": 1.80,
    "GOLD": 2.20, "PLATINUM": 2.60, "EMERALD": 3.00,
    "DIAMOND": 3.50, "MASTER": 4.00, "GRANDMASTER": 4.50, "CHALLENGER": 5.00,
    "UNRANKED": 2.20, "": 2.20,
}


def _compute_player_bet_multiplier(target_puuid, match_id):
    """Multiplicador para una apuesta house de "X será sus en este match".

    Heurística:
      base = TIER_MULTIPLIER[player_tier] (mejor rango → más payout, porque es
        más sorprendente que el favorito caiga)
      ajuste por prior: si el prior es bajo (<35) sube el multi (improbable),
        si es alto (>65) baja (esperado).

    Lee de `live_snapshots` (SQLite) — guarda player_priors[puuid] al hacer
    /liveGame.
    """
    try:
        snap = get_live_snapshot(match_id)
        priors = (snap or {}).get("player_priors") or {}
        target = priors.get(target_puuid)
        if not target:
            return 2.0
        tier = (target.get("tier") or "UNRANKED").upper()
        base = TIER_MULTIPLIER.get(tier, 2.2)
        prior = target.get("prior_tumor")
        if prior is None:
            return round(max(1.05, min(6.0, base)), 2)
        # Prior < 35 (jugador "limpio"): bonus +0.8 al multi (improbable que sea sus)
        # Prior 35-65: neutral
        # Prior > 65 (ya tumor): -0.5 (esperado, paga menos)
        if prior < 35:
            base += 0.8
        elif prior > 65:
            base -= 0.5
        # Decay temporal (mismo modelo que match bets)
        base *= _payout_decay_factor(_live_elapsed_seconds(match_id))
        return round(max(1.05, min(6.0, base)), 2)
    except Exception:
        return 2.0


UNDERDOG_BONUS = 1.15  # bonus contra la predicción; sólo aplica con confidence alta
UNDERDOG_BONUS_MIN_CONFIDENCE = 25  # por debajo de este conf el "underdog" es ruido, no aplicar bonus

# Ventana de apuestas en una partida live.
# Una SoloQ típica dura ~28-32 min; cerramos a los 25 min de gametime para evitar
# apuestas "con foresight" muy cerca del final.
BET_CLOSE_AT_ELAPSED = 25 * 60  # 1500s
# El payout decae linealmente entre min 5 y BET_CLOSE_AT_ELAPSED hasta el floor.
PAYOUT_DECAY_START   = 5 * 60   # antes de min 5 no hay decay
PAYOUT_DECAY_END     = 25 * 60  # a 25 min queda el floor
PAYOUT_DECAY_FLOOR   = 0.55     # multiplier no cae por debajo de 55% del nominal


def _live_elapsed_seconds(match_id):
    """Segundos transcurridos desde el inicio real de la partida live.
    Devuelve None si no hay snapshot o no se conoce gameStartTime aún (loading screen).
    """
    snap = get_live_snapshot(match_id)
    if not snap:
        return None
    g0 = snap.get("game_start_ts")
    if not g0:
        return None
    return max(0.0, time.time() - float(g0))


def _payout_decay_factor(elapsed):
    """Factor multiplicativo [PAYOUT_DECAY_FLOOR..1.0] aplicado al multiplier.

    Antes de PAYOUT_DECAY_START → 1.0 (sin decay).
    Entre START..END → decae linealmente hasta PAYOUT_DECAY_FLOOR.
    Después de END → PAYOUT_DECAY_FLOOR (pero igualmente apuestas estarán cerradas).
    """
    if elapsed is None or elapsed <= PAYOUT_DECAY_START:
        return 1.0
    if elapsed >= PAYOUT_DECAY_END:
        return PAYOUT_DECAY_FLOOR
    frac = (elapsed - PAYOUT_DECAY_START) / (PAYOUT_DECAY_END - PAYOUT_DECAY_START)
    return 1.0 - frac * (1.0 - PAYOUT_DECAY_FLOOR)


def _is_betting_closed(match_id):
    """True si la ventana de apuestas ya cerró por tiempo de juego elapsed.
    Si no podemos determinar elapsed (sin snapshot), permitimos apostar.
    """
    elapsed = _live_elapsed_seconds(match_id)
    return elapsed is not None and elapsed >= BET_CLOSE_AT_ELAPSED


def _get_match_prediction(match_id):
    """Devuelve la predicción 5v5 guardada del match (winner, confidence) o None.

    Fuente única de verdad: SQLite `live_snapshots` (escrita al final del
    flujo de /liveGame). El JSON `live_game_cache.json` es para priors POR
    jugador, no por match.
    """
    snap = get_live_snapshot(match_id)
    if not snap:
        return None
    pred = snap.get("prediction") or {}
    winner = pred.get("winner")
    if winner not in ("blue", "red"):
        return None
    try:
        confidence = float(pred.get("confidence") or 0)
    except Exception:
        confidence = 0.0
    return {"winner": winner, "confidence": confidence}


def _compute_house_multiplier(match_id, side):
    """Multiplicador dinámico para house bets en partida live.

    Modelo de odds:
      - Probabilidad del side derivada de la confidence de la predicción 5v5.
      - Multiplier base = 0.95 / prob(side)  (5% de house edge).
      - Si apuestas CONTRA el lado predicho como ganador Y la prediction tiene
        confidence ≥ UNDERDOG_BONUS_MIN_CONFIDENCE, bonus extra (UNDERDOG_BONUS).
        Si la confidence es baja, el "underdog" no es un underdog real (es ~50/50),
        así que el bonus daría EV+ injustificado al lado contrario.
      - Cap final: [1.05, 6.5].

    Si no hay snapshot (raro), devuelve 2.0 (fair odds).
    """
    try:
        pred = _get_match_prediction(match_id)
        if not pred:
            return 2.0
        # Confidence → probabilidad del winner side. confidence=0 → 0.5,
        # confidence=100 → 0.92 (cap para que el multi nunca colapse a ~1.0).
        prob_winner = min(0.92, 0.5 + 0.42 * (pred["confidence"] / 100.0))
        is_against = (side != pred["winner"])
        prob_side = prob_winner if not is_against else (1 - prob_winner)
        mult = 0.95 / max(0.08, prob_side)
        # Underdog bonus sólo si la predicción es razonablemente confiada.
        # Con conf < 25 la prediction es ~50/50; aplicar bonus = regalar EV+.
        if is_against and pred["confidence"] >= UNDERDOG_BONUS_MIN_CONFIDENCE:
            mult *= UNDERDOG_BONUS
        # Decay temporal: cuanto más avanzada la partida cuando apuestas,
        # peor payout (cada vez sabes "más" del resultado).
        mult *= _payout_decay_factor(_live_elapsed_seconds(match_id))
        return max(1.05, min(6.5, round(mult, 2)))
    except Exception:
        return 2.0


@app.route('/bets/preview-multiplier', methods=['GET'])
def bets_preview_multiplier():
    """Devuelve el multiplicador que se aplicaría a una house bet en este match
    para el side dado. Útil para que el frontend lo muestre antes de confirmar.
    Body params: match_id, side ('blue'|'red')."""
    match_id = request.args.get('match_id')
    side = request.args.get('side')
    if not match_id or side not in ('blue', 'red'):
        return jsonify({"error": "match_id y side ('blue'|'red') requeridos"}), 400
    queue_id = _resolve_match_queue_id(match_id)
    if queue_id is not None and not allows_betting(queue_id):
        return jsonify({"error": f"Apuestas solo en SoloQ/Flex (queue: {queue_name(queue_id)})"}), 400
    elapsed = _live_elapsed_seconds(match_id)
    closed = elapsed is not None and elapsed >= BET_CLOSE_AT_ELAPSED
    mult = _compute_house_multiplier(match_id, side)
    pred = _get_match_prediction(match_id)
    # Sólo es "underdog real" si va contra una predicción razonablemente confiada
    is_underdog = bool(
        pred
        and side != pred["winner"]
        and pred["confidence"] >= UNDERDOG_BONUS_MIN_CONFIDENCE
    )
    return jsonify({
        "multiplier": mult,
        "is_underdog": is_underdog,
        "underdog_bonus": UNDERDOG_BONUS if is_underdog else 1.0,
        "predicted_winner": pred["winner"] if pred else None,
        "predicted_confidence": pred["confidence"] if pred else None,
        "elapsed_seconds": elapsed,
        "betting_closed": closed,
        "close_at_elapsed": BET_CLOSE_AT_ELAPSED,
        "decay_factor": round(_payout_decay_factor(elapsed), 3) if elapsed is not None else 1.0,
    })


@app.route('/bets/create', methods=['POST'])
def bets_create():
    """Crea una apuesta. Body:
      Match bet P2P:   { match_id, game_id, side: 'blue'|'red', amount }
      Match bet HOUSE: { match_id, game_id, side: 'blue'|'red', amount, is_house: true }
        → contra el sistema, con multiplicador dinámico calculado del estado live.
      Stat bet:   { match_id, game_id, side: 'over'|'under', amount,
                    bet_kind: 'stat', target_puuid, target_name, stat_type, threshold }
    """
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    data = request.get_json() or {}
    match_id = data.get("match_id")
    game_id = data.get("game_id")
    side = data.get("side")
    amount = int(data.get("amount", 0))
    bet_kind = data.get("bet_kind") or "match"
    is_house = bool(data.get("is_house"))

    if not match_id or amount <= 0:
        return jsonify({"error": "Faltan campos o son inválidos"}), 400
    if amount > user["currency"]:
        return jsonify({"error": "Saldo insuficiente"}), 400

    # Gate: solo SoloQ + Flex permiten apuestas. Resolvemos el queue:
    # - Live game: viene del live cache (game ya iniciado, queue conocido)
    # - Match terminado: lo leemos del Match v5
    queue_id = _resolve_match_queue_id(match_id)
    if queue_id is not None and not allows_betting(queue_id):
        return jsonify({
            "error": f"Apuestas solo permitidas en SoloQ y Flex (queue actual: {queue_name(queue_id)})"
        }), 400

    # Gate temporal: bets cerradas pasados BET_CLOSE_AT_ELAPSED segundos de partida.
    if _is_betting_closed(match_id):
        return jsonify({
            "error": "Ventana de apuestas cerrada — la partida lleva demasiado tiempo (>25 min). Próxima partida será otra cosa."
        }), 400

    if bet_kind == "match":
        if side not in ("blue", "red"):
            return jsonify({"error": "side debe ser blue|red"}), 400
        if is_house:
            mult = _compute_house_multiplier(match_id, side)
            bet = _users.create_bet(
                user["id"], match_id, game_id, side, amount,
                is_house=True, payout_multiplier=mult,
            )
        else:
            bet = _users.create_bet(user["id"], match_id, game_id, side, amount)
    elif bet_kind == "stat":
        if side not in ("over", "under"):
            return jsonify({"error": "side debe ser over|under"}), 400
        target_puuid = data.get("target_puuid")
        target_name = data.get("target_name")
        stat_type = data.get("stat_type")
        try:
            threshold = float(data.get("threshold"))
        except Exception:
            return jsonify({"error": "threshold inválido"}), 400
        if not target_puuid or stat_type not in _users.VALID_STAT_TYPES:
            return jsonify({"error": "stat_type inválido o falta target_puuid"}), 400
        # No puedes apostar sobre ti mismo
        if user.get("riot_puuid") and target_puuid == user["riot_puuid"]:
            return jsonify({"error": "No puedes apostar sobre ti mismo"}), 400
        mult = _compute_player_bet_multiplier(target_puuid, match_id) if is_house else 2.0
        bet = _users.create_bet(
            user["id"], match_id, game_id, side, amount,
            bet_kind="stat", target_puuid=target_puuid, target_name=target_name,
            stat_type=stat_type, threshold=threshold,
            is_house=is_house, payout_multiplier=mult,
        )
    else:
        return jsonify({"error": "bet_kind inválido"}), 400

    if not bet:
        return jsonify({"error": "No se pudo crear la apuesta"}), 500
    return jsonify(_augment_bet(bet))


@app.route('/bets/player', methods=['POST'])
def bets_player():
    """Apuesta simple "este jugador será sus" — house mode, multiplicador
    automático por tier + prior. Body: { match_id, target_puuid, target_name, amount }.

    Restricciones:
      - Solo en SoloQ/Flex (gating compartido).
      - No puedes apostar sobre ti mismo.
      - Solo 1 player-bet por match.
    """
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    data = request.get_json() or {}
    match_id = data.get("match_id")
    target_puuid = data.get("target_puuid")
    target_name = data.get("target_name") or ""
    try:
        amount = int(data.get("amount", 0))
    except Exception:
        return jsonify({"error": "amount inválido"}), 400
    if not match_id or not target_puuid or amount <= 0:
        return jsonify({"error": "Faltan campos"}), 400
    if amount > user["currency"]:
        return jsonify({"error": "Saldo insuficiente"}), 400

    queue_id = _resolve_match_queue_id(match_id)
    if queue_id is not None and not allows_betting(queue_id):
        return jsonify({"error": "Apuestas solo permitidas en SoloQ y Flex"}), 400

    if user.get("riot_puuid") and target_puuid == user["riot_puuid"]:
        return jsonify({"error": "No puedes apostar sobre ti mismo"}), 400

    # 1 player-bet por match: ya existe stat bet de este user en este match?
    existing = _users._exec(
        """SELECT id FROM bets
           WHERE creator_user_id=? AND match_id=? AND bet_kind='stat'
           AND status IN ('open', 'matched')""",
        (user["id"], match_id),
    ).fetchone()
    if existing:
        return jsonify({"error": "Ya tienes una apuesta activa de jugador en este match"}), 400

    # Multiplicador y threshold automáticos.
    # Threshold = 60 (tumor score sus). Side = 'over'.
    # El multiplicador escala con tier + prior (ver _compute_player_bet_multiplier).
    mult = _compute_player_bet_multiplier(target_puuid, match_id)
    bet = _users.create_bet(
        user["id"], match_id, None, "over", amount,
        bet_kind="stat", target_puuid=target_puuid, target_name=target_name,
        stat_type="tumor_score", threshold=60.0,
        is_house=True, payout_multiplier=mult,
    )
    if not bet:
        return jsonify({"error": "No se pudo crear la apuesta"}), 500
    return jsonify(_augment_bet(bet))


@app.route('/bets/<share_code>', methods=['GET'])
def bets_get(share_code):
    """Detalle público de una apuesta. No requiere auth (útil para previewar antes de aceptar)."""
    bet = _users.get_bet_by_code(share_code)
    if not bet:
        return jsonify({"error": "Apuesta no encontrada"}), 404
    return jsonify(_augment_bet(bet))


@app.route('/bets/resolve-mine', methods=['POST'])
def bets_resolve_mine():
    """Escanea las bets matched del user actual y resuelve las que correspondan
    a partidas que ya han terminado.

    Idempotente: una bet ya resuelta no se toca. Devuelve {checked, resolved,
    refunded}."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401

    # Bets matched del user (creator o taker), agrupadas por match_id
    cur = _users._exec(
        f"""SELECT {_users._BET_COLS} FROM bets
            WHERE status='matched' AND (creator_user_id=? OR taker_user_id=?)
            ORDER BY created_at ASC""",
        (user["id"], user["id"]),
    )
    bets = [_users._row_to_bet(r) for r in cur.fetchall()]
    if not bets:
        return jsonify({"checked": 0, "resolved": 0, "refunded": 0})

    by_match = {}
    for b in bets:
        by_match.setdefault(b["match_id"], []).append(b)

    resolved_count = 0
    refunded_count = 0
    checked_matches = 0

    for match_id, bets_in_match in by_match.items():
        checked_matches += 1
        # Match v5 — solo resolvemos si la partida YA acabó (200 OK con info completa)
        mres = riot_get(f"{MATCH_DETAILS_URL}/{match_id}")
        if mres.status_code != 200:
            continue
        info = mres.json().get("info", {})
        parts = info.get("participants", []) or []
        if not parts:
            continue
        # Decide ganador (lado azul = 100, rojo = 200)
        blue_win = next((p["win"] for p in parts if p["teamId"] == 100), False)
        actual = "blue" if blue_win else "red"

        # game_end_ts para refund window
        game_end_ts = None
        try:
            end_ms = info.get("gameEndTimestamp")
            if end_ms:
                game_end_ts = float(end_ms) / 1000.0
            else:
                start_ms = info.get("gameStartTimestamp")
                dur = info.get("gameDuration", 0) or 0
                if start_ms:
                    game_end_ts = (float(start_ms) / 1000.0) + float(dur)
        except Exception:
            pass

        # Resolver match bets (P2P + house) + stat bets de este match
        for b in bets_in_match:
            try:
                if b["bet_kind"] == "match":
                    res = _users.resolve_bet(b["id"], actual, game_end_ts=game_end_ts)
                    if res:
                        if res.get("status") == "refunded":
                            refunded_count += 1
                        elif res.get("status") == "resolved":
                            resolved_count += 1
                elif b["bet_kind"] == "stat":
                    val = _extract_player_stat(mres.json(), b.get("target_puuid"), b.get("stat_type"))
                    if val is None:
                        continue
                    res = _users.resolve_stat_bet(b["id"], val, game_end_ts=game_end_ts)
                    if res:
                        if res.get("status") == "refunded":
                            refunded_count += 1
                        elif res.get("status") == "resolved":
                            resolved_count += 1
            except Exception:
                pass

    return jsonify({
        "checked": checked_matches,
        "resolved": resolved_count,
        "refunded": refunded_count,
    })


@app.route('/bets/<share_code>/accept', methods=['POST'])
def bets_accept(share_code):
    """Acepta la apuesta tomando el lado contrario."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    result = _users.accept_bet(user["id"], share_code)
    if isinstance(result, str):
        return jsonify({"error": result}), 400
    if not result:
        return jsonify({"error": "No se pudo aceptar la apuesta"}), 500
    return jsonify(_augment_bet(result))


@app.route('/bets/<share_code>/cancel', methods=['POST'])
def bets_cancel(share_code):
    """El creator cancela su propia apuesta abierta."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    bet = _users.get_bet_by_code(share_code)
    if not bet:
        return jsonify({"error": "Apuesta no encontrada"}), 404
    cancelled = _users.cancel_bet(user["id"], bet["id"])
    if not cancelled:
        return jsonify({"error": "No se pudo cancelar (¿no eres el creador o ya está aceptada?)"}), 400
    return jsonify(_augment_bet(_users.get_bet_by_id(bet["id"])))


@app.route('/bets/open', methods=['GET'])
def bets_open_feed():
    """Feed público de apuestas abiertas. Usado en la vista 'Hot Bets'."""
    bets = _users.list_open_bets(limit=50)
    return jsonify([_augment_bet(b) for b in bets])


@app.route('/bets/mine', methods=['GET'])
def bets_mine():
    """Lista de apuestas del user actual (creadas o aceptadas)."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    bets = _users.get_user_bets(user["id"])
    return jsonify([_augment_bet(b) for b in bets])


# ---------------------------------------------------------------------------
# 1v1 Challenges: cada user juega su partida, se comparan stats
# ---------------------------------------------------------------------------

def _augment_challenge(ch):
    if not ch:
        return None
    briefs = _users.get_users_brief([ch.get("challenger_user_id"), ch.get("challenged_user_id")])
    ch["challenger"] = briefs.get(ch.get("challenger_user_id"))
    ch["challenged"] = briefs.get(ch.get("challenged_user_id")) if ch.get("challenged_user_id") else None
    return ch


def _extract_player_stat(match_info, puuid, stat_type):
    """Extrae la stat del participante con `puuid` del JSON de match-v5."""
    info = (match_info or {}).get("info", {})
    parts = info.get("participants", []) or []
    p = next((x for x in parts if x.get("puuid") == puuid), None)
    if not p:
        return None
    k = p.get("kills", 0) or 0
    d = p.get("deaths", 0) or 0
    a = p.get("assists", 0) or 0
    if stat_type == "kills":   return float(k)
    if stat_type == "deaths":  return float(d)
    if stat_type == "assists": return float(a)
    if stat_type == "kda":     return (k + a) / max(d, 1)
    if stat_type == "cs":      return float((p.get("totalMinionsKilled", 0) or 0) + (p.get("neutralMinionsKilled", 0) or 0))
    if stat_type == "gold":    return float(p.get("goldEarned", 0) or 0)
    if stat_type == "damage":  return float(p.get("totalDamageDealtToChampions", 0) or 0)
    if stat_type == "tumor_score":
        # Tumor score del jugador en este match.
        # BUG histórico fixed: antes pasaba `gameDuration/60` (minutos) a la
        # función que espera SEGUNDOS, así que el engine dividía por 60 otra
        # vez y saturaba cs/min y dmg/min → todas las stat-bets de tumor_score
        # resolvían con valores corruptos.
        try:
            game_duration_s = float(info.get("gameDuration", 0))
            if game_duration_s < 1:
                return None
            tier = (p.get("tier") or "").upper() or "UNRANKED"
            role = p.get("teamPosition") or p.get("individualPosition") or ""
            # _engine_match_score_from_participant = compute_match_tumor:
            # acepta el participant raw + duration en segundos. Devuelve (score, components).
            result = _engine_match_score_from_participant(p, game_duration_s, tier=tier, role=role)
            if isinstance(result, tuple):
                return float(result[0])
            return float(result)
        except Exception:
            return None
    return None


@app.route('/challenges/create', methods=['POST'])
def challenges_create():
    """Body: { stat_type, amount, comparison?, format? } — challenger debe tener riot_id vinculado.

    format: 'single' (default, legacy) | 'bo3' | 'bo5' | 'bo10'
      Para bo*, el stat_type es ignorado para determinar ganador (se usa win/loss
      de partidas ranked solo); el stat_type sigue usándose como tiebreaker
      implícito vía tumor score acumulado.
    """
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    if not user.get("riot_puuid"):
        return jsonify({"error": "Vincula tu Riot ID antes de crear challenges"}), 400
    data = request.get_json() or {}
    stat_type = data.get("stat_type")
    fmt = data.get("format") or "single"
    try:
        amount = int(data.get("amount", 0))
    except Exception:
        return jsonify({"error": "amount inválido"}), 400
    comparison = data.get("comparison") or ("lower_wins" if stat_type == "deaths" else "higher_wins")
    if amount <= 0 or stat_type not in _users.VALID_CHALLENGE_STATS:
        return jsonify({"error": "stat_type/amount inválidos"}), 400
    if fmt not in _users.CHALLENGE_FORMATS:
        return jsonify({"error": "format debe ser single|bo3|tumor_race|streak"}), 400
    if amount > user["currency"]:
        return jsonify({"error": "Saldo insuficiente"}), 400
    target_user_id = data.get("challenged_user_id")
    try:
        target_user_id = int(target_user_id) if target_user_id else None
    except Exception:
        target_user_id = None
    ch = _users.create_challenge(user["id"], stat_type, amount, comparison, fmt=fmt, target_user_id=target_user_id)
    if not ch:
        return jsonify({"error": "No se pudo crear el challenge"}), 500
    return jsonify(_augment_challenge(ch))


# ---------------------------------------------------------------------------
# Best-of-N challenge poller (item #3)
# ---------------------------------------------------------------------------

def _matches_after_accepted(puuid, accepted_ts_sec):
    """Lista match_ids ranked (SoloQ + Flex) jugados tras accepted_ts_sec.
    Mantiene orden de Riot (más reciente primero por id)."""
    ids = []
    for q in sorted(RANKED_QUEUES):
        url = (f"{RIOT_BASE_URL}/lol/match/v5/matches/by-puuid/{puuid}/ids"
               f"?queue={q}&start=0&count=20&startTime={int(accepted_ts_sec)}")
        res = riot_get(url)
        if res.status_code == 200:
            ids.extend(res.json() or [])
    seen = set()
    return [m for m in ids if not (m in seen or seen.add(m))]


def _enriched_matches_for_player(puuid, match_ids):
    """Devuelve [(game_creation_ts, match_id, won, tumor_score)] orden ascendente."""
    enriched = []
    for mid in match_ids:
        mres = riot_get(f"{MATCH_DETAILS_URL}/{mid}")
        if mres.status_code != 200:
            continue
        info_full = mres.json()
        info = info_full.get("info", {})
        parts = info.get("participants", []) or []
        p = next((x for x in parts if x.get("puuid") == puuid), None)
        if not p:
            continue
        won = bool(p.get("win"))
        ts = _extract_player_stat(info_full, puuid, "tumor_score") or 0
        enriched.append((info.get("gameCreation", 0), mid, won, float(ts)))
    enriched.sort(key=lambda x: x[0])  # oldest first
    return enriched


def _poll_one_challenge(ch):
    """Procesa un challenge no-single aceptado. Format-aware:
       - bo3:       primero en 2 wins
       - tumor_race: cada uno juega 1 match; menor tumor gana
       - streak:    primer jugador en lograr 2 wins seguidas
    """
    accepted_ts_ms = int((ch.get("accepted_at") or 0) * 1000)
    if accepted_ts_ms == 0:
        return None
    challenger_puuid = ch["challenger_puuid"]
    challenged_puuid = ch["challenged_puuid"]
    if not challenged_puuid:
        return None

    fmt = ch.get("format") or "bo3"
    accepted_ts_sec = accepted_ts_ms // 1000

    ch_matches = _matches_after_accepted(challenger_puuid, accepted_ts_sec)
    dh_matches = _matches_after_accepted(challenged_puuid, accepted_ts_sec)
    ch_enriched = _enriched_matches_for_player(challenger_puuid, ch_matches)
    dh_enriched = _enriched_matches_for_player(challenged_puuid, dh_matches)

    expired = (ch.get("expires_at") or 0) > 0 and time.time() > ch["expires_at"]

    # === Format: BO3 — primer en alcanzar 2 wins ===
    if fmt == "bo3":
        cw = sum(1 for _, _, won, _ in ch_enriched if won)
        dw = sum(1 for _, _, won, _ in dh_enriched if won)
        ct = sum(t for _, _, _, t in ch_enriched)
        dt = sum(t for _, _, _, t in dh_enriched)
        _users.update_challenge_progress(ch["id"], cw, dw, ct, dt)
        needed = ch["matches_required"]
        if cw >= needed and cw > dw:
            return _users.resolve_bestofn_challenge(ch["id"], ch["challenger_user_id"], reason=f"{cw}-{dw}")
        if dw >= needed and dw > cw:
            return _users.resolve_bestofn_challenge(ch["id"], ch["challenged_user_id"], reason=f"{cw}-{dw}")
        if expired:
            if cw > dw:
                return _users.resolve_bestofn_challenge(ch["id"], ch["challenger_user_id"], reason=f"expired {cw}-{dw}")
            if dw > cw:
                return _users.resolve_bestofn_challenge(ch["id"], ch["challenged_user_id"], reason=f"expired {cw}-{dw}")
            # Tiebreak por tumor (menor gana)
            if ct == dt:
                _users.push_challenge_refund(ch["id"], reason="tie_no_data")
            elif ct < dt:
                _users.resolve_bestofn_challenge(ch["id"], ch["challenger_user_id"],
                                                 reason=f"tiebreak tumor {ct:.0f}<{dt:.0f}")
            else:
                _users.resolve_bestofn_challenge(ch["id"], ch["challenged_user_id"],
                                                 reason=f"tiebreak tumor {dt:.0f}<{ct:.0f}")
            return _users.get_challenge_by_id(ch["id"])
        return None

    # === Format: TUMOR RACE — cada uno juega 1 match, menor tumor gana ===
    if fmt == "tumor_race":
        # Tomamos el PRIMER match cronológico de cada uno (oldest first)
        c_first = ch_enriched[0] if ch_enriched else None
        d_first = dh_enriched[0] if dh_enriched else None
        # Almacenamos progreso usando los campos existentes
        c_tumor = c_first[3] if c_first else 0.0
        d_tumor = d_first[3] if d_first else 0.0
        c_games = 1 if c_first else 0
        d_games = 1 if d_first else 0
        _users.update_challenge_progress(ch["id"], c_games, d_games, c_tumor, d_tumor)

        if c_first and d_first:
            if c_tumor < d_tumor:
                return _users.resolve_bestofn_challenge(ch["id"], ch["challenger_user_id"],
                    reason=f"tumor race {c_tumor:.0f}<{d_tumor:.0f}")
            if d_tumor < c_tumor:
                return _users.resolve_bestofn_challenge(ch["id"], ch["challenged_user_id"],
                    reason=f"tumor race {d_tumor:.0f}<{c_tumor:.0f}")
            # Empate exacto → tiebreak por quién ganó la partida (los wins valen)
            c_won = c_first[2]; d_won = d_first[2]
            if c_won and not d_won:
                return _users.resolve_bestofn_challenge(ch["id"], ch["challenger_user_id"],
                    reason="tumor tie, you won")
            if d_won and not c_won:
                return _users.resolve_bestofn_challenge(ch["id"], ch["challenged_user_id"],
                    reason="tumor tie, you won")
            _users.push_challenge_refund(ch["id"], reason="tumor tie + both lost/won")
            return _users.get_challenge_by_id(ch["id"])

        if expired:
            # Alguien no jugó: el que SÍ jugó gana por walkover; si ninguno, refund
            if c_first and not d_first:
                return _users.resolve_bestofn_challenge(ch["id"], ch["challenger_user_id"], reason="walkover")
            if d_first and not c_first:
                return _users.resolve_bestofn_challenge(ch["id"], ch["challenged_user_id"], reason="walkover")
            _users.push_challenge_refund(ch["id"], reason="nobody played")
            return _users.get_challenge_by_id(ch["id"])
        return None

    # === Format: STREAK — primero en 2 wins seguidas (cronológicamente) ===
    if fmt == "streak":
        required = ch["matches_required"] or 2

        def _find_streak_completion(enriched, n):
            """Devuelve (game_creation_ts, current_streak, max_streak).
            game_creation_ts es el timestamp donde el jugador alcanzó la streak
            (None si nunca). current_streak es la racha actual al final."""
            streak = 0
            max_streak = 0
            reached_ts = None
            for ts, _mid, won, _tumor in enriched:
                if won:
                    streak += 1
                    if streak > max_streak:
                        max_streak = streak
                    if streak >= n and reached_ts is None:
                        reached_ts = ts
                else:
                    streak = 0
            return reached_ts, streak, max_streak

        c_reach, c_curr, c_max = _find_streak_completion(ch_enriched, required)
        d_reach, d_curr, d_max = _find_streak_completion(dh_enriched, required)

        # Guardamos current_streak en challenger_wins / challenged_wins (display).
        # tumor_total guarda el max_streak alcanzado por si lo queremos mostrar.
        _users.update_challenge_progress(ch["id"], c_curr, d_curr, float(c_max), float(d_max))

        if c_reach and d_reach:
            # Ambos llegaron → el primero cronológicamente gana
            winner_id = ch["challenger_user_id"] if c_reach <= d_reach else ch["challenged_user_id"]
            return _users.resolve_bestofn_challenge(ch["id"], winner_id, reason=f"streak {required}")
        if c_reach:
            return _users.resolve_bestofn_challenge(ch["id"], ch["challenger_user_id"], reason=f"streak {required}")
        if d_reach:
            return _users.resolve_bestofn_challenge(ch["id"], ch["challenged_user_id"], reason=f"streak {required}")

        if expired:
            if c_max > d_max:
                return _users.resolve_bestofn_challenge(ch["id"], ch["challenger_user_id"],
                    reason=f"expired max streak {c_max}>{d_max}")
            if d_max > c_max:
                return _users.resolve_bestofn_challenge(ch["id"], ch["challenged_user_id"],
                    reason=f"expired max streak {d_max}>{c_max}")
            _users.push_challenge_refund(ch["id"], reason="streak tied")
            return _users.get_challenge_by_id(ch["id"])
        return None

    # Format desconocido (legacy bo5/bo10 sin migrar) — refund a ambos
    if expired:
        _users.push_challenge_refund(ch["id"], reason=f"unknown_format:{fmt}")
        return _users.get_challenge_by_id(ch["id"])
    return None


@app.route('/challenges/poll', methods=['POST'])
def challenges_poll():
    """Trigger manual del poller de best-of-N challenges.

    Idempotente: procesa hasta 50 challenges aceptados y devuelve resumen.
    Sin auth para que se pueda llamar desde un cron externo (cron-job.org, etc).
    """
    chs = _users.list_pollable_challenges()
    processed = 0
    resolved = 0
    for ch in chs:
        try:
            res = _poll_one_challenge(ch)
            processed += 1
            if res and res.get("status") in ("resolved", "expired"):
                resolved += 1
        except Exception:
            pass
    return jsonify({"processed": processed, "resolved": resolved, "candidates": len(chs)})


@app.route('/challenges/<share_code>/accept', methods=['POST'])
def challenges_accept(share_code):
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    res = _users.accept_challenge(user["id"], share_code)
    if isinstance(res, str):
        return jsonify({"error": res}), 400
    return jsonify(_augment_challenge(res))


@app.route('/challenges/<share_code>/cancel', methods=['POST'])
def challenges_cancel(share_code):
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    ch = _users.get_challenge_by_code(share_code)
    if not ch:
        return jsonify({"error": "No encontrado"}), 404
    res = _users.cancel_challenge(user["id"], ch["id"])
    if not res:
        return jsonify({"error": "No se pudo cancelar"}), 400
    return jsonify({"ok": True})


@app.route('/challenges/<share_code>/submit', methods=['POST'])
def challenges_submit(share_code):
    """Body: { match_id }. Backend pulls Match v5 y extrae la stat del puuid del user."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    if not user.get("riot_puuid"):
        return jsonify({"error": "Vincula tu Riot ID"}), 400
    data = request.get_json() or {}
    match_id = data.get("match_id")
    if not match_id:
        return jsonify({"error": "match_id requerido"}), 400
    ch = _users.get_challenge_by_code(share_code)
    if not ch:
        return jsonify({"error": "Challenge no encontrado"}), 404
    if ch["status"] != "accepted":
        return jsonify({"error": f"Challenge en estado {ch['status']}"}), 400
    if user["id"] not in (ch["challenger_user_id"], ch["challenged_user_id"]):
        return jsonify({"error": "No participas en este challenge"}), 403

    mres = riot_get(f"{MATCH_DETAILS_URL}/{match_id}")
    if mres.status_code != 200:
        return jsonify({"error": f"Match no disponible (riot {mres.status_code})"}), 502
    info = mres.json()
    val = _extract_player_stat(info, user["riot_puuid"], ch["stat_type"])
    if val is None:
        return jsonify({"error": "No participaste en ese match o stat no extraíble"}), 400
    res = _users.submit_challenge_match(user["id"], share_code, match_id, val)
    if isinstance(res, str):
        return jsonify({"error": res}), 400
    return jsonify(_augment_challenge(res))


@app.route('/challenges/open', methods=['GET'])
def challenges_open_feed():
    user = _current_user()
    viewer_id = user["id"] if user else None
    return jsonify([
        _augment_challenge(c)
        for c in _users.list_open_challenges(viewer_user_id=viewer_id, limit=50)
    ])


@app.route('/challenges/mine', methods=['GET'])
def challenges_mine():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    return jsonify([_augment_challenge(c) for c in _users.list_user_challenges(user["id"])])


@app.route('/challenges/<share_code>', methods=['GET'])
def challenges_get(share_code):
    ch = _users.get_challenge_by_code(share_code)
    if not ch:
        return jsonify({"error": "No encontrado"}), 404
    return jsonify(_augment_challenge(ch))


# ---------------------------------------------------------------------------
# Item #4: Room bets — pool de sala, resuelve por win/loss + tumor tiebreaker
# ---------------------------------------------------------------------------

def _augment_room_bet(rb):
    if not rb:
        return None
    rb["participants"] = []
    for p in _users.list_room_bet_participants(rb["id"]):
        u = _users.get_user_by_id(p["user_id"])
        if u:
            p["username"] = u["username"]
            p["avatar"] = u.get("avatar")
            p["riot_id"] = u.get("riot_id")
        rb["participants"].append(p)
    return rb


@app.route('/rooms/<code>/bets/create', methods=['POST'])
def room_bet_create(code):
    """Body: { stake, ttl_hours? }"""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    if not user.get("riot_puuid"):
        return jsonify({"error": "Vincula tu Riot ID"}), 400
    room = _users.get_room_by_code(code)
    if not room:
        return jsonify({"error": "Sala no encontrada"}), 404
    if room["owner_user_id"] != user["id"]:
        return jsonify({"error": "Solo el owner de la sala crea room bets"}), 403
    data = request.get_json() or {}
    try:
        stake = int(data.get("stake", 0))
    except Exception:
        return jsonify({"error": "stake inválido"}), 400
    if stake <= 0 or stake > user["currency"]:
        return jsonify({"error": "stake inválido o saldo insuficiente"}), 400
    ttl = int(data.get("ttl_hours", 24)) * 3600
    rb = _users.create_room_bet(room["id"], user["id"], stake, ttl_seconds=ttl)
    if not rb:
        return jsonify({"error": "No se pudo crear"}), 500
    return jsonify(_augment_room_bet(rb))


@app.route('/rooms/<code>/bets/<int:rbid>/join', methods=['POST'])
def room_bet_join(code, rbid):
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    res = _users.join_room_bet(rbid, user["id"])
    if isinstance(res, str):
        return jsonify({"error": res}), 400
    return jsonify(_augment_room_bet(res))


@app.route('/rooms/<code>/bets/<int:rbid>/start', methods=['POST'])
def room_bet_start(code, rbid):
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    res = _users.start_room_bet(rbid, user["id"])
    if not res:
        return jsonify({"error": "No se pudo arrancar"}), 400
    return jsonify(_augment_room_bet(res))


@app.route('/rooms/<code>/bets/<int:rbid>/cancel', methods=['POST'])
def room_bet_cancel(code, rbid):
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    res = _users.cancel_room_bet(rbid, user["id"])
    if not res:
        return jsonify({"error": "No se pudo cancelar"}), 400
    return jsonify(_augment_room_bet(res))


@app.route('/rooms/<code>/bets', methods=['GET'])
def room_bet_list(code):
    room = _users.get_room_by_code(code)
    if not room:
        return jsonify({"error": "Sala no encontrada"}), 404
    bets = _users.list_room_bets_for_room(room["id"])
    return jsonify([_augment_room_bet(rb) for rb in bets])


def _resolve_one_room_bet(rb):
    """Resolución de un room bet active:
    1. Para cada participante, busca su próxima ranked solo después de started_at.
    2. Marca won/lost + tumor_score.
    3. Si hay winners → se reparten el pot de los losers proporcionalmente al stake.
       Los winners recuperan stake + share del pot de los losers.
    4. Si no hay winners (todos perdieron) → entre quienes coincidieron en el
       mismo match, los de menor tumor reciben un bonus (10% del stake del
       compañero con mayor tumor); el resto del stake se refunda a su dueño.
    """
    rbid = rb["id"]
    if rb["status"] != "active":
        return None
    started_ms = int((rb.get("started_at") or 0) * 1000)
    if started_ms == 0:
        return None

    parts = _users.list_room_bet_participants(rbid)
    # Step 1+2: find each participant's first ranked match (solo o flex) after started_at
    for p in parts:
        if p.get("match_id"):
            continue  # ya procesado
        ids = []
        for q in sorted(RANKED_QUEUES):
            url = (f"{RIOT_BASE_URL}/lol/match/v5/matches/by-puuid/{p['puuid']}/ids"
                   f"?queue={q}&start=0&count=10&startTime={started_ms // 1000}")
            res = riot_get(url)
            if res.status_code == 200:
                ids.extend(res.json() or [])
        if not ids:
            continue
        # tomamos la más antigua después de started_at
        match_id = ids[-1]
        mres = riot_get(f"{MATCH_DETAILS_URL}/{match_id}")
        if mres.status_code != 200:
            continue
        info = mres.json()
        parts_in = info.get("info", {}).get("participants", []) or []
        target = next((x for x in parts_in if x.get("puuid") == p["puuid"]), None)
        if not target:
            continue
        won = bool(target.get("win"))
        ts = _extract_player_stat(info, p["puuid"], "tumor_score")
        _users.update_room_bet_participant(rbid, p["user_id"],
                                           match_id=match_id, won=won, tumor_score=ts)

    # Refresh
    parts = _users.list_room_bet_participants(rbid)
    # Si aún hay participantes sin match_id y no hemos pasado el deadline → vuelve más tarde
    pending = [p for p in parts if not p.get("match_id")]
    if pending and time.time() < (rb.get("resolves_at") or 0):
        return None
    # Si llegamos al deadline con pendings, los refundamos
    for p in pending:
        _users.add_currency(p["user_id"], p["staked"], f"room bet refund (no game) · #{rbid}")
        _users.update_room_bet_participant(rbid, p["user_id"], payout=p["staked"])

    completed = [p for p in parts if p.get("match_id")]
    winners = [p for p in completed if p.get("won")]
    losers = [p for p in completed if p.get("won") is False]

    if winners:
        # Pot from losers (their stakes go to winners proportionally)
        loser_pot = sum(p["staked"] for p in losers)
        winner_pot_each = loser_pot // max(len(winners), 1)
        for w in winners:
            payout = w["staked"] + winner_pot_each
            _users.add_currency(w["user_id"], payout, f"room bet won · #{rbid}")
            _users.update_room_bet_participant(rbid, w["user_id"], payout=payout)
        for l in losers:
            _users.update_room_bet_participant(rbid, l["user_id"], payout=0)
    else:
        # Todos perdieron → tiebreaker tumor entre los que coincidieron en el mismo match
        bonus_pct = 0.10
        # Group por match_id
        by_match = {}
        for p in completed:
            by_match.setdefault(p["match_id"], []).append(p)
        # En cada grupo de >=2, el de menor tumor cobra del de mayor
        bonuses = {p["user_id"]: 0 for p in completed}
        penalties = {p["user_id"]: 0 for p in completed}
        for mid, group in by_match.items():
            if len(group) < 2:
                continue
            sorted_g = sorted(group, key=lambda x: x.get("tumor_score") or 99999)
            best = sorted_g[0]
            for worse in sorted_g[1:]:
                bonus = int(worse["staked"] * bonus_pct)
                bonuses[best["user_id"]] += bonus
                penalties[worse["user_id"]] += bonus
        # Pay out: each player gets back stake - penalty + bonus
        for p in completed:
            net = p["staked"] - penalties[p["user_id"]] + bonuses[p["user_id"]]
            net = max(0, net)
            _users.add_currency(p["user_id"], net, f"room bet refund · #{rbid}")
            _users.update_room_bet_participant(rbid, p["user_id"], payout=net)

    _users.finalize_room_bet(rbid)
    return _users.get_room_bet(rbid)


@app.route('/rooms/bets/poll', methods=['POST'])
def room_bet_poll():
    """Procesa todos los room bets active (igual que /challenges/poll)."""
    ids = _users.list_active_room_bets()
    processed = 0
    resolved = 0
    for rbid in ids:
        try:
            rb = _users.get_room_bet(rbid)
            res = _resolve_one_room_bet(rb)
            processed += 1
            if res and res.get("status") == "resolved":
                resolved += 1
        except Exception:
            pass
    return jsonify({"processed": processed, "resolved": resolved, "candidates": len(ids)})


@app.route('/backtestHistory', methods=['GET'])
def backtest_history_endpoint():
    """Estadísticas acumuladas del histórico de backtests."""
    db = _pred_db()
    rows = db.execute("""
        SELECT predicted_winner, actual_winner, correct, confidence, created_at
        FROM backtest_logs
    """).fetchall()

    decided = [r for r in rows if r[0]]
    correct = sum(1 for r in decided if r[2])
    ties = sum(1 for r in rows if not r[0])

    # Últimos 30 días
    import time as _time
    cutoff_30d = _time.time() - 30 * 86400
    recent = [r for r in decided if (r[4] or 0) >= cutoff_30d]
    recent_correct = sum(1 for r in recent if r[2])

    return jsonify({
        "total_backtested": len(rows),
        "decided": len(decided),
        "ties_excluded": ties,
        "correct": correct,
        "accuracy_all_time": round(correct / len(decided) * 100, 1) if decided else 0.0,
        "last_30_days": {
            "decided": len(recent),
            "correct": recent_correct,
            "accuracy": round(recent_correct / len(recent) * 100, 1) if recent else 0.0,
        },
    })


@app.route('/cacheStats', methods=['GET'])
def cache_stats_endpoint():
    return jsonify(cache_stats())


@app.route('/backtest', methods=['GET'])
def backtest_endpoint():
    """Re-ejecuta el modelo sobre partidas históricas y devuelve acierto real.

    Para cada una de las últimas N rankeds del summoner solicitado:
      1. Calcula el prior_tumor_score de los 10 jugadores ANTES de esa partida.
      2. Predice ganador con el modelo actual.
      3. Compara con el resultado real.
    """
    game_name = request.args.get('game_name')
    tag_line = request.args.get('tag_line')
    count = int(request.args.get('count', 20))
    if not game_name or not tag_line:
        return jsonify({"error": "Falta game_name y/o tag_line"}), 400

    acc_res = riot_get(f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name}/{tag_line}")
    if acc_res.status_code != 200:
        return jsonify({"error": "No se pudo obtener la cuenta"}), 400
    puuid = acc_res.json()["puuid"]
    tier, _div = get_player_rank(puuid)

    ids_res = riot_get(f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count={count}&queue={QUEUE_RANKED_SOLO}")
    if ids_res.status_code != 200:
        return jsonify({"error": "No se pudieron obtener partidas"}), 400
    match_ids = ids_res.json()

    payload = _run_backtest(puuid, tier, match_ids, game_name, tag_line)
    return jsonify(payload)


def _run_backtest(puuid, tier, match_ids, game_name, tag_line, job_id=None):
    """Ejecuta el backtest sobre `match_ids`. Si se pasa job_id, publica progreso."""
    results = []
    correct = 0
    total = 0
    pending = 0
    n = len(match_ids)
    for i, mid in enumerate(match_ids):
        if job_id:
            job_update(job_id, step=f"Procesando partida {i+1}/{n}...", progress=i, total=n)
        mres = riot_get(f"{MATCH_DETAILS_URL}/{mid}")
        if mres.status_code != 200:
            continue
        info = mres.json().get("info", {})
        parts = info.get("participants", [])
        if not parts or info.get("gameDuration", 0) < 300:
            continue

        game_creation = info.get("gameCreation", 0)
        synthetic_players = []
        for p in parts:
            prior = compute_prior_tumor_score(p["puuid"], tier, game_creation, num=5)
            synthetic_players.append({
                "team_id": p["teamId"],
                "avg_tumor_score": prior,
                "tier": tier,
                "role": p.get("teamPosition") or "",
                "champion_total_sample": 5 if prior is not None else 0,
            })
        prediction = predict_team_outcome(synthetic_players)
        actual = "blue" if next((x["win"] for x in parts if x["teamId"] == 100), False) else "red"
        if prediction["winner"] == "tie":
            pending += 1
            hit = None
        else:
            hit = prediction["winner"] == actual
            total += 1
            if hit:
                correct += 1
        results.append({
            "match_id": mid,
            "predicted": prediction["winner"],
            "actual": actual,
            "correct": hit,
            "confidence": prediction["confidence"],
            "diff": prediction["diff"],
        })

        # Persistir backtest para acumular datos empíricos
        try:
            blue_players = [x for x in parts if x["teamId"] == 100]
            red_players  = [x for x in parts if x["teamId"] == 200]
            blue_priors = [sp.get("avg_tumor_score") for sp in synthetic_players if sp["team_id"] == 100]
            red_priors  = [sp.get("avg_tumor_score") for sp in synthetic_players if sp["team_id"] == 200]
            median_diff = (prediction.get("red_team_tumor", 0) or 0) - (prediction.get("blue_team_tumor", 0) or 0)
            sum_diff_raw = (prediction.get("red_team_sum", 0) or 0) - (prediction.get("blue_team_sum", 0) or 0)
            log_backtest_match({
                "match_id": mid,
                "viewer_puuid": puuid,
                "viewer_name": f"{game_name}#{tag_line}",
                "predicted_winner": prediction["winner"] if prediction["winner"] != "tie" else None,
                "actual_winner": actual,
                "correct": hit,
                "confidence": prediction["confidence"],
                "median_diff": median_diff,
                "sum_diff": sum_diff_raw,
                "blue_team_tumor": prediction["blue_team_tumor"],
                "red_team_tumor": prediction["red_team_tumor"],
                "blue_team_sum": prediction.get("blue_team_sum"),
                "red_team_sum": prediction.get("red_team_sum"),
                "used_sum_tiebreaker": abs(median_diff) < 4 and prediction["winner"] != "tie",
                "blue_priors": blue_priors,
                "red_priors": red_priors,
                "blue_roles": [p.get("teamPosition") or "" for p in blue_players],
                "red_roles":  [p.get("teamPosition") or "" for p in red_players],
            })
        except Exception:
            pass
    if job_id:
        job_update(job_id, step="Listo", progress=n, total=n)

    return {
        "summoner": f"{game_name}#{tag_line}",
        "sample_size": len(results),
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total * 100) if total else 0,
        "ties": pending,
        "results": results,
    }


@app.route('/backtest/start', methods=['POST'])
def backtest_start():
    data = request.get_json() or {}
    game_name = data.get("game_name")
    tag_line = data.get("tag_line")
    count = int(data.get("count", 20))
    if not game_name or not tag_line:
        return jsonify({"error": "Falta game_name y/o tag_line"}), 400

    acc_res = riot_get(f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name}/{tag_line}")
    if acc_res.status_code != 200:
        return jsonify({"error": "No se pudo obtener la cuenta"}), 400
    puuid = acc_res.json()["puuid"]
    tier, _ = get_player_rank(puuid)

    ids_res = riot_get(f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count={count}&queue={QUEUE_RANKED_SOLO}")
    if ids_res.status_code != 200:
        return jsonify({"error": "No se pudieron obtener partidas"}), 400
    match_ids = ids_res.json() or []

    job_cleanup()
    jid = job_create()
    job_update(jid, step="Iniciando backtest...", progress=0, total=len(match_ids))

    def _worker():
        try:
            payload = _run_backtest(puuid, tier, match_ids, game_name, tag_line, job_id=jid)
            job_update(jid, status="done", result=payload)
        except Exception as e:
            job_update(jid, status="error", error=str(e))

    threading.Thread(target=_worker, daemon=True).start()
    return jsonify({"job_id": jid, "total": len(match_ids)})


@app.route('/backtest/progress/<jid>', methods=['GET'])
def backtest_progress(jid):
    job = job_get(jid)
    if not job:
        return jsonify({"error": "Job no encontrado"}), 404
    return jsonify(job)


@app.route('/championBlacklist', methods=['GET'])
def get_blacklist():
    summoner = request.args.get('summoner', '')
    return jsonify(load_blacklist().get(summoner, []))


@app.route('/championBlacklist', methods=['POST'])
def add_blacklist():
    data = request.get_json() or {}
    summoner = data.get('summoner')
    champion = data.get('champion')
    if not summoner or not champion:
        return jsonify({"error": "summoner y champion requeridos"}), 400
    bl = load_blacklist()
    lst = bl.setdefault(summoner, [])
    if champion not in lst:
        lst.append(champion)
    save_blacklist(bl)
    return jsonify(lst)


@app.route('/championBlacklist', methods=['DELETE'])
def remove_blacklist():
    data = request.get_json() or {}
    summoner = data.get('summoner')
    champion = data.get('champion')
    bl = load_blacklist()
    if summoner in bl:
        bl[summoner] = [c for c in bl[summoner] if c != champion]
    save_blacklist(bl)
    return jsonify(bl.get(summoner, []))


def _resolve_pending_predictions(limit=None):
    """Resuelve predicciones sin resolver consultando el match detail real.
    También dispara la resolución de TODAS las bets matched de ese match_id
    (match bets P2P + house, y stat bets) para que no haga falta abrir
    MyBetsModal para que se resuelvan."""
    db = _pred_db()
    q = "SELECT match_id, viewer_puuid, predicted_winner FROM predictions WHERE resolved=0"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = db.execute(q).fetchall()
    # Agrupar por match_id para una sola llamada Match v5 por partida
    by_match = {}
    for match_id, viewer_puuid, predicted in rows:
        by_match.setdefault(match_id, []).append((viewer_puuid, predicted))

    for match_id, viewers in by_match.items():
        # Si no quedan viewers con predicted, marca todos resolved sin Riot fetch
        if all(predicted is None for _, predicted in viewers):
            for viewer_puuid, _ in viewers:
                db.execute(
                    "UPDATE predictions SET resolved=1 WHERE match_id=? AND viewer_puuid=?",
                    (match_id, viewer_puuid),
                )
            continue
        mres = riot_get(f"{MATCH_DETAILS_URL}/{match_id}")
        if mres.status_code != 200:
            continue
        info = mres.json().get("info", {})
        parts = info.get("participants", []) or []
        if not parts:
            continue
        blue_win = next((p["win"] for p in parts if p["teamId"] == 100), False)
        actual = "blue" if blue_win else "red"

        # game_end_ts para refund window
        game_end_ts = None
        try:
            end_ms = info.get("gameEndTimestamp")
            if end_ms:
                game_end_ts = float(end_ms) / 1000.0
            else:
                start_ms = info.get("gameStartTimestamp")
                dur = info.get("gameDuration", 0) or 0
                if start_ms:
                    game_end_ts = (float(start_ms) / 1000.0) + float(dur)
        except Exception:
            pass

        # Marcar predicciones resueltas
        for viewer_puuid, predicted in viewers:
            if predicted is None:
                db.execute(
                    "UPDATE predictions SET resolved=1 WHERE match_id=? AND viewer_puuid=?",
                    (match_id, viewer_puuid),
                )
            else:
                predictions_mark_resolved(match_id, viewer_puuid, actual, predicted)

        # Auto-resolver match bets (P2P + house) — idempotente, sólo toca status='matched'
        try:
            _users.resolve_bets_for_match(match_id, actual, game_end_ts=game_end_ts)
        except Exception:
            pass

        # Auto-resolver stat bets de ese match
        try:
            stat_bets = _users.list_stat_bets_for_match(match_id)
            for sb in (stat_bets or []):
                tp = sb.get("target_puuid")
                stype = sb.get("stat_type")
                if not tp or not stype:
                    continue
                actual_val = _extract_player_stat(mres.json(), tp, stype)
                if actual_val is None:
                    continue
                _users.resolve_stat_bet(sb["id"], actual_val, game_end_ts=game_end_ts)
        except Exception:
            pass


def _auto_resolve_orphan_bets(max_matches=20):
    """Sweep para bets matched cuyo match_id NO está en `predictions`.
    Esto cubre apuestas hechas sobre matches que el viewer no haya predicho
    (e.g. apostó en partida ajena). Por throttling, limita a max_matches calls
    a Riot por invocación.

    Filtra match_ids ya cubiertos por `_resolve_pending_predictions` mirando
    si todavía quedan bets matched de ese match (lo cual significa que la
    función anterior no las resolvió → probable: sin row en `predictions`).
    """
    try:
        match_ids = _users.list_pending_match_ids(min_age_seconds=180, limit=max_matches)
    except Exception:
        return
    for match_id in match_ids:
        mres = riot_get(f"{MATCH_DETAILS_URL}/{match_id}")
        if mres.status_code != 200:
            continue
        info = mres.json().get("info", {})
        parts = info.get("participants", []) or []
        if not parts:
            continue
        blue_win = next((p["win"] for p in parts if p["teamId"] == 100), False)
        actual = "blue" if blue_win else "red"
        game_end_ts = None
        try:
            end_ms = info.get("gameEndTimestamp")
            if end_ms:
                game_end_ts = float(end_ms) / 1000.0
            else:
                start_ms = info.get("gameStartTimestamp")
                dur = info.get("gameDuration", 0) or 0
                if start_ms:
                    game_end_ts = (float(start_ms) / 1000.0) + float(dur)
        except Exception:
            pass
        try:
            _users.resolve_bets_for_match(match_id, actual, game_end_ts=game_end_ts)
        except Exception:
            pass
        try:
            stat_bets = _users.list_stat_bets_for_match(match_id)
            for sb in (stat_bets or []):
                tp = sb.get("target_puuid")
                stype = sb.get("stat_type")
                if not tp or not stype:
                    continue
                actual_val = _extract_player_stat(mres.json(), tp, stype)
                if actual_val is None:
                    continue
                _users.resolve_stat_bet(sb["id"], actual_val, game_end_ts=game_end_ts)
        except Exception:
            pass


_PREDSTATS_SWEEP_LOCK = threading.Lock()
_PREDSTATS_LAST_SWEEP = {"ts": 0.0}
PREDSTATS_SWEEP_INTERVAL = 30.0  # segundos entre sweeps globales


@app.route('/predictionStats', methods=['GET'])
def prediction_stats_endpoint():
    """Devuelve el acierto global de predicciones.
    Dispara el sweep de auto-resolución de bets matched a lo más cada
    PREDSTATS_SWEEP_INTERVAL segundos — antes esto se ejecutaba en cada call,
    así que N tabs abiertas hacían N sweeps en paralelo.
    """
    now = time.time()
    do_sweep = False
    with _PREDSTATS_SWEEP_LOCK:
        if (now - _PREDSTATS_LAST_SWEEP["ts"]) >= PREDSTATS_SWEEP_INTERVAL:
            _PREDSTATS_LAST_SWEEP["ts"] = now
            do_sweep = True
    if do_sweep:
        try:
            _resolve_pending_predictions()
        except Exception:
            pass
        try:
            _auto_resolve_orphan_bets(max_matches=15)
        except Exception:
            pass

    preds = predictions_all()
    resolved = [p for p in preds if p.get("resolved") and p.get("predicted_winner")]
    total = len(resolved)
    correct = sum(1 for p in resolved if p.get("correct"))
    pending = sum(1 for p in preds if not p.get("resolved"))
    pct = round(correct / total * 100) if total else 0

    return jsonify({
        "total": total,
        "correct": correct,
        "accuracy": pct,
        "pending": pending,
        "recent": sorted(resolved, key=lambda x: x.get("created_at", 0), reverse=True)[:10],
    })


@app.route('/resolvePrediction', methods=['POST'])
def resolve_prediction_endpoint():
    """Resuelve una predicción concreta al instante (botón "Comprobar resultado")."""
    data = request.get_json() or {}
    match_id = data.get("match_id")
    viewer_puuid = data.get("viewer_puuid")
    if not match_id or not viewer_puuid:
        return jsonify({"error": "match_id y viewer_puuid requeridos"}), 400

    db = _pred_db()
    row = db.execute(
        "SELECT predicted_winner, resolved, actual_winner, correct FROM predictions WHERE match_id=? AND viewer_puuid=?",
        (match_id, viewer_puuid),
    ).fetchone()
    if not row:
        return jsonify({"error": "Predicción no encontrada"}), 404

    predicted, resolved, actual, correct = row
    if resolved:
        return jsonify({"resolved": True, "actual_winner": actual, "correct": bool(correct), "predicted_winner": predicted})

    mres = riot_get(f"{MATCH_DETAILS_URL}/{match_id}")
    if mres.status_code != 200:
        return jsonify({"resolved": False, "error": "La partida aún no ha terminado"}), 202
    info = mres.json().get("info", {})
    parts = info.get("participants", []) or []
    if not parts:
        return jsonify({"resolved": False, "error": "Aún no hay datos"}), 202
    blue_win = next((p["win"] for p in parts if p["teamId"] == 100), False)
    actual = "blue" if blue_win else "red"
    predictions_mark_resolved(match_id, viewer_puuid, actual, predicted)

    # game_end_ts (segundos epoch) para refund window de item #1
    game_end_ts = None
    try:
        # Match v5 da gameEndTimestamp en ms; algunos juegos viejos solo gameStartTimestamp + gameDuration
        end_ms = info.get("gameEndTimestamp")
        if end_ms:
            game_end_ts = float(end_ms) / 1000.0
        else:
            start_ms = info.get("gameStartTimestamp")
            dur = info.get("gameDuration", 0) or 0
            if start_ms:
                game_end_ts = (float(start_ms) / 1000.0) + float(dur)
    except Exception:
        game_end_ts = None

    # Auto-resolver match bets (P2P + house) con refund window
    try:
        _users.resolve_bets_for_match(match_id, actual, game_end_ts=game_end_ts)
    except Exception:
        pass
    # Stat bets: usa _extract_player_stat (que ya maneja tumor_score)
    try:
        stat_bets = _users.list_stat_bets_for_match(match_id)
        if stat_bets:
            for sb in stat_bets:
                tp = sb.get("target_puuid")
                stype = sb.get("stat_type")
                if not tp or not stype:
                    continue
                actual_val = _extract_player_stat(mres.json(), tp, stype)
                if actual_val is None:
                    continue
                _users.resolve_stat_bet(sb["id"], actual_val, game_end_ts=game_end_ts)
    except Exception:
        pass

    # Premiar Tumor Coins si la predicción acertó y el viewer está logueado
    is_correct = bool(predicted and predicted == actual)
    coins_awarded = 0
    new_balance = None
    if is_correct:
        try:
            cur2 = _users._exec("SELECT id FROM users WHERE riot_puuid=?", (viewer_puuid,))
            urow = cur2.fetchone()
            if urow:
                user_id = urow[0]
                # Award basado en confianza (mejor predicción = más coins)
                conf = 0
                try:
                    crow = _pred_db().execute(
                        "SELECT confidence FROM predictions WHERE match_id=? AND viewer_puuid=?",
                        (match_id, viewer_puuid),
                    ).fetchone()
                    conf = (crow[0] if crow else 0) or 0
                except Exception:
                    pass
                # 20 base + bonus por confianza alta (max 50 total)
                coins_awarded = min(50, 20 + conf // 4)
                new_balance = _users.add_currency(user_id, coins_awarded, f"prediction hit · {match_id}")
        except Exception:
            pass

    return jsonify({
        "resolved": True,
        "actual_winner": actual,
        "correct": is_correct,
        "predicted_winner": predicted,
        "coins_awarded": coins_awarded,
        "new_balance": new_balance,
    })


@app.route('/getOverview', methods=['GET'])
def get_overview_endpoint():
    game_name = request.args.get('game_name')
    tag_line = request.args.get('tag_line')
    start = int(request.args.get('start', 0))
    tier_override = request.args.get('tier') or None
    queue = request.args.get('queue') or None

    if not game_name or not tag_line:
        return jsonify({"error": "Falta game_name y/o tag_line como query params"}), 400

    result = get_overview(game_name, tag_line, start=start, tier_override=tier_override, queue=queue)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result)


def compute_prior_tumor_score(puuid, tier, before_ms, num=5):
    """Tumor score promedio del jugador en sus últimas N rankeds ANTES de `before_ms`.
    Misma lógica que el live, pero filtrado por endTime.

    Usa player_priors_cache cuando before_ms es reciente (<1h del ahora).
    Para backtests sobre partidas viejas, no se cachea porque el "antes de X"
    cambia según la partida que estés analizando.
    """
    # Si el corte temporal es muy reciente, podemos usar el cache global
    now_ms = time.time() * 1000
    if abs(now_ms - before_ms) < 3600 * 1000:  # < 1h
        cached = get_cached_prior(puuid)
        if cached is not None and cached.get("score") is not None:
            return cached["score"]
    try:
        end_sec = int(before_ms / 1000) - 1
        ids_res = riot_get(
            f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count={num}&endTime={end_sec}&queue={QUEUE_RANKED_SOLO}"
        )
        ids = ids_res.json() if ids_res.status_code == 200 else []
        if not ids:
            ids_res = riot_get(
                f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count={num}&endTime={end_sec}"
            )
            if ids_res.status_code != 200:
                return None
            ids = ids_res.json()
        if not ids:
            return None
        scores = []
        for mid in ids:
            mres = riot_get(f"{MATCH_DETAILS_URL}/{mid}")
            if mres.status_code != 200:
                continue
            d = mres.json()["info"]
            if d["gameDuration"] < 300:
                continue
            pp = next((x for x in d["participants"] if x["puuid"] == puuid), None)
            if not pp:
                continue
            stats = {
                "kda": calculate_kda(pp["kills"], pp["deaths"], pp["assists"]),
                "cs": pp["totalMinionsKilled"] + pp["neutralMinionsKilled"],
                "damage": pp["totalDamageDealtToChampions"],
                "vision_score": pp["visionScore"],
                "time_dead": pp["totalTimeSpentDead"],
            }
            role = pp.get("teamPosition") or "DEFAULT"
            scores.append(calculate_tumor_score(stats, d["gameDuration"], tier, role))
        if not scores:
            return None
        return round(sum(scores) / len(scores))
    except Exception:
        return None


@app.route('/matchDetail/<match_id>', methods=['GET'])
def match_detail_endpoint(match_id):
    res = riot_get(f"{MATCH_DETAILS_URL}/{match_id}")
    if res.status_code != 200:
        return jsonify({"error": "No se pudo obtener la partida"}), res.status_code

    info = res.json()["info"]
    participants = info["participants"]
    game_duration = info["gameDuration"]
    game_creation = info.get("gameCreation", 0)
    viewer_tier = request.args.get("viewer_tier", "GOLD") or "GOLD"

    # Intentar recuperar snapshot del live (si este match se vio en directo)
    snapshot = get_live_snapshot(match_id)
    snapshot_priors = snapshot.get("player_priors", {}) if snapshot else {}
    cached_prediction = snapshot.get("prediction") if snapshot else None

    def summarize(p):
        kda = calculate_kda(p["kills"], p["deaths"], p["assists"])
        cs = p["totalMinionsKilled"] + p["neutralMinionsKilled"]
        stats = {
            "kda": kda,
            "cs": cs,
            "damage": p["totalDamageDealtToChampions"],
            "vision_score": p["visionScore"],
            "time_dead": p["totalTimeSpentDead"],
        }
        role = p.get("teamPosition") or "DEFAULT"
        match_tumor = calculate_tumor_score(stats, game_duration, viewer_tier, role)

        # Reutilizar prior del snapshot si existe; si no, calcular fresco
        sp = snapshot_priors.get(p["puuid"])
        if sp is not None:
            prior_tumor = sp.get("prior_tumor")
        else:
            prior_tumor = compute_prior_tumor_score(p["puuid"], viewer_tier, game_creation, num=5)

        return {
            "puuid": p["puuid"],
            "nombre": f"{p['riotIdGameName']}#{p['riotIdTagline']}",
            "campeon": p["championName"],
            "kills": p["kills"], "deaths": p["deaths"], "assists": p["assists"],
            "kda": round(kda, 2),
            "cs": cs,
            "damage": p["totalDamageDealtToChampions"],
            "gold": p["goldEarned"],
            "vision_score": p["visionScore"],
            "wards_placed": p["wardsPlaced"],
            "champ_level": p["champLevel"],
            "time_dead": p["totalTimeSpentDead"],
            "win": p["win"],
            "tumor_score": match_tumor,
            "prior_tumor_score": prior_tumor,
        }

    team_blue = [summarize(p) for p in participants if p["teamId"] == 100]
    team_red  = [summarize(p) for p in participants if p["teamId"] == 200]

    # Usar predicción cacheada del live si existe; si no, calcular con priors
    if cached_prediction:
        prediction = cached_prediction
    else:
        synthetic_players = []
        for p, summary in zip(
            [pp for pp in participants if pp["teamId"] == 100],
            team_blue,
        ):
            synthetic_players.append({
                "team_id": 100,
                "avg_tumor_score": summary["prior_tumor_score"],
                "tier": viewer_tier,
                "role": p.get("teamPosition") or "",
            })
        for p, summary in zip(
            [pp for pp in participants if pp["teamId"] == 200],
            team_red,
        ):
            synthetic_players.append({
                "team_id": 200,
                "avg_tumor_score": summary["prior_tumor_score"],
                "tier": viewer_tier,
                "role": p.get("teamPosition") or "",
            })
        prediction = predict_team_outcome(synthetic_players)

    return jsonify({
        "match_id": match_id,
        "game_duration": info["gameDuration"],
        "game_date": info.get("gameCreation", 0),
        "blue_win": team_blue[0]["win"] if team_blue else False,
        "team_blue": team_blue,
        "team_red": team_red,
        "prediction": prediction,
        "from_live_snapshot": bool(snapshot),
    })


@app.route('/getElPeor', methods=['GET'])
def get_el_peor_endpoint():
    """Endpoint GET que devuelve el peor jugador
    Query params:
        - game_name: Nombre del jugador
        - tag_line: Etiqueta del jugador
    """
    game_name = request.args.get('game_name')
    tag_line = request.args.get('tag_line')

    if not game_name or not tag_line:
        return jsonify({"error": "Falta game_name y/o tag_line como query params"}), 400

    result = get_el_peor(game_name, tag_line)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result)


# ---------------------------------------------------------------------------
# Bravery endpoints — randomize champion/lane/items, lock in, resolve post-match
# ---------------------------------------------------------------------------

@app.route('/bravery/data', methods=['GET'])
def bravery_data():
    """Devuelve {version, champions, items} de Data Dragon (cacheado 24h).
    items son finales (>=2000g, no upgradeable, sin componentes ni consumibles)."""
    data = _bravery.get_data()
    if not data:
        return jsonify({"error": "Data Dragon no disponible"}), 503
    return jsonify(data)


@app.route('/bravery/roll', methods=['POST'])
def bravery_roll():
    """Genera un roll de bravery sin lockearlo aún.
    Body: {dimensions: ['champion','lane'?,'items'?], room_code?, item_count?}

    Reglas:
      - 'lane' SÓLO permitida si room_code está set (en SoloQ no eliges lane,
        sólo tiene sentido en bravery de sala donde 5 personas coordinan comp).
    """
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    data = request.get_json() or {}
    dims = list(data.get("dimensions") or ["champion"])
    if "champion" not in dims:
        dims = ["champion"] + dims
    room_code = data.get("room_code")
    # Gate: lane sólo permitida en bravery de sala
    if "lane" in dims and not room_code:
        dims = [d for d in dims if d != "lane"]
    try:
        item_count = int(data.get("item_count", 5))
    except Exception:
        item_count = 5
    item_count = max(3, min(6, item_count))
    rolled = _bravery.roll(dims, item_count=item_count)
    if not rolled:
        return jsonify({"error": "Data Dragon no disponible"}), 503
    return jsonify(rolled)


@app.route('/bravery/lock', methods=['POST'])
def bravery_lock():
    """Lockea un roll. Escrowa el stake.
    Body: {champion_id, champion_name, lane?, items?, dimensions, stake, room_code?}
    items es lista de {id, name, gold}."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    if not user.get("riot_puuid"):
        return jsonify({"error": "Vincula tu Riot ID antes de bravery"}), 400
    data = request.get_json() or {}
    try:
        champion_id = int(data.get("champion_id"))
        stake = int(data.get("stake"))
    except Exception:
        return jsonify({"error": "champion_id/stake inválidos"}), 400
    champion_name = data.get("champion_name") or ""
    if not champion_name:
        return jsonify({"error": "champion_name requerido"}), 400
    if stake <= 0 or stake > user["currency"]:
        return jsonify({"error": "Stake inválido o saldo insuficiente"}), 400
    if _users.user_has_pending_bravery(user["id"]):
        return jsonify({"error": "Ya tienes un bravery pending. Cancélalo o juega antes de crear otro."}), 400

    items = data.get("items")
    if items is not None:
        if not isinstance(items, list) or not all(
            isinstance(it, dict) and "id" in it and "name" in it for it in items
        ):
            return jsonify({"error": "items debe ser lista de {id, name}"}), 400

    room_code = data.get("room_code") or None

    # En sala: validar bravery_active del owner + claim lane random del pool
    lane = None
    if room_code:
        room = _users.get_room_by_code(room_code)
        if not room:
            return jsonify({"error": "Sala no encontrada"}), 404
        if not room["bravery_active"]:
            return jsonify({"error": "El host aún no ha activado Bravery en esta sala"}), 400
        # Claim lane: pool de 5, excluye las ya tomadas por otros locks pending
        claimed = _users.claimed_lanes_in_room(room_code)
        available = [l for l in _bravery.VALID_LANES if l not in claimed]
        if not available:
            return jsonify({"error": "Sala llena: las 5 lanes están ocupadas"}), 400
        import random as _rnd
        lane = _rnd.choice(available)

    dims = set(["champion"])
    if lane: dims.add("lane")
    if items: dims.add("items")
    style_mult = _bravery.style_mult_for_dims(dims)

    # Capturar tier actual del user para que el resolver use thresholds correctos
    # (antes se hardcodeaba UNRANKED, lo que inflaba payouts en Diamond+).
    tier_now = None
    try:
        tier_now, _div = get_player_rank(user["riot_puuid"])
    except Exception:
        tier_now = None

    lock = _users.create_bravery_lock(
        user_id=user["id"],
        puuid=user["riot_puuid"],
        champion_id=champion_id,
        champion_name=champion_name,
        lane=lane,
        items=items,
        dimensions=len(dims),
        style_mult=style_mult,
        stake=stake,
        room_code=room_code,
        tier=tier_now,
    )
    if not lock:
        return jsonify({"error": "No se pudo crear el lock"}), 500
    return jsonify(lock)


@app.route('/bravery/<int:lid>/reroll', methods=['POST'])
def bravery_reroll(lid):
    """Re-rolea un bravery lock pending (1 vez por lock). Cambia champion,
    items (si la dim items estaba activa) y lane (si en sala — toma del pool
    excluyendo las ya tomadas por otros).

    Body opcional: {item_count?: int}
    """
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    lock = _users.get_bravery_lock_by_id(lid)
    if not lock or lock["user_id"] != user["id"]:
        return jsonify({"error": "Lock no encontrado"}), 404
    if lock["status"] != "pending":
        return jsonify({"error": "Sólo se puede rerollear un lock pending"}), 400
    if lock["reroll_used"]:
        return jsonify({"error": "Ya usaste tu reroll en este lock"}), 400

    data = request.get_json(silent=True) or {}
    try:
        item_count = int(data.get("item_count", len(lock.get("items") or []) or 5))
    except Exception:
        item_count = 5
    item_count = max(3, min(6, item_count))

    had_items = bool(lock.get("items"))
    dims_in = ["champion"] + (["items"] if had_items else [])
    new_roll = _bravery.roll(dims_in, item_count=item_count)
    if not new_roll:
        return jsonify({"error": "Data Dragon no disponible"}), 503

    # Si está en sala con lane: claim NUEVA lane del pool (excluye otros pending
    # excepto el propio lock — su lane "actual" cuenta como disponible para él)
    new_lane = None
    if lock["room_code"] and lock["lane"]:
        claimed = _users.claimed_lanes_in_room(lock["room_code"], exclude_lock_id=lid)
        available = [l for l in _bravery.VALID_LANES if l not in claimed]
        if not available:
            return jsonify({"error": "Sala llena al rerollear, lane no disponible"}), 400
        import random as _rnd
        new_lane = _rnd.choice(available)

    dims = set(["champion"])
    if new_lane: dims.add("lane")
    if had_items: dims.add("items")
    new_style_mult = _bravery.style_mult_for_dims(dims)

    updated = _users.update_bravery_lock_roll(
        lid=lid,
        champion_id=new_roll["champion"]["id"],
        champion_name=new_roll["champion"]["name"],
        lane=new_lane,
        items=new_roll.get("items"),
        style_mult=new_style_mult,
        dimensions=len(dims),
    )
    if not updated:
        return jsonify({"error": "No se pudo rerollear"}), 500
    return jsonify(updated)


@app.route('/bravery/<int:lid>/cancel', methods=['POST'])
def bravery_cancel(lid):
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    res = _users.cancel_bravery_lock(user["id"], lid)
    if not res:
        return jsonify({"error": "Lock no cancelable"}), 400
    return jsonify(res)


@app.route('/bravery/mine', methods=['GET'])
def bravery_mine():
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    return jsonify(_users.list_user_bravery_locks(user["id"]))


@app.route('/bravery/room/<code>', methods=['GET'])
def bravery_room_locks(code):
    """Locks de bravery de una sala (para verlos junto a los miembros)."""
    return jsonify(_users.list_room_bravery_locks(code))


def _resolve_one_bravery(lock):
    """Resuelve un bravery lock pendiente buscando la primera partida del
    user posterior al lock. Devuelve dict {status, payout?, match_id?, error?}."""
    now = time.time()
    # Expiración: si pasaron BRAVERY_REFUND_AFTER, refund automático
    if lock.get("created_at") and (now - lock["created_at"]) > _users.BRAVERY_REFUND_AFTER:
        _users.refund_bravery_lock(lock["id"], reason="expired_no_match")
        return {"status": "refunded", "reason": "expired"}

    # Buscar matches posteriores al lock (ranked + normal + aram acepta)
    start_time = int(lock["created_at"])
    url = (f"{RIOT_BASE_URL}/lol/match/v5/matches/by-puuid/{lock['puuid']}/ids"
           f"?start=0&count=5&startTime={start_time}")
    res = riot_get(url)
    if res.status_code != 200:
        return {"status": "skipped", "reason": "match_list_unavailable"}
    match_ids = res.json() or []
    # Tomamos el match más antiguo posterior al lock (Riot devuelve en orden DESC)
    if not match_ids:
        return {"status": "skipped", "reason": "no_matches_yet"}
    target_id = match_ids[-1]

    mres = riot_get(f"{MATCH_DETAILS_URL}/{target_id}")
    if mres.status_code != 200:
        return {"status": "skipped", "reason": "match_details_unavailable"}
    info = mres.json().get("info", {})
    parts = info.get("participants", []) or []
    me = next((p for p in parts if p.get("puuid") == lock["puuid"]), None)
    if not me:
        return {"status": "skipped", "reason": "participant_not_found"}

    # Compute tumor. El tier se captura al hacer lock (mejor approx que UNRANKED).
    queue_id = info.get("queueId")
    game_duration = info.get("gameDuration") or 0
    tier_for_scoring = lock.get("tier") or "UNRANKED"
    role = me.get("teamPosition") or me.get("individualPosition") or ""
    try:
        result = _engine_match_score_from_participant(me, game_duration, tier=tier_for_scoring, role=role)
        tumor_score = float(result[0] if isinstance(result, tuple) else result)
    except Exception:
        tumor_score = 50.0

    compliance = _bravery.compute_compliance(lock, me)
    payout = _bravery.compute_payout(lock["stake"], tumor_score, compliance)
    _users.resolve_bravery_lock(
        lid=lock["id"],
        match_id=target_id,
        tumor_score=tumor_score,
        compliance=compliance,
        payout=payout,
    )
    # Notificación
    try:
        if payout >= lock["stake"]:
            push_notification(
                user_id=lock["user_id"], notif_type="bravery_won",
                title=f"☢ Bravery +{payout - lock['stake']} TC",
                body=f"{lock['champion_name']} tumor {round(tumor_score)} · x{compliance['effective_mult']}",
                link="#/social", icon="🎲",
            )
        else:
            push_notification(
                user_id=lock["user_id"], notif_type="bravery_lost",
                title=f"☢ Bravery -{lock['stake'] - payout} TC",
                body=f"{lock['champion_name']} no cumplió · pagó {payout} TC",
                link="#/social", icon="💀",
            )
    except Exception:
        pass
    return {"status": "resolved", "payout": payout, "match_id": target_id,
            "tumor_score": tumor_score, "compliance": compliance}


@app.route('/bravery/resolve-mine', methods=['POST'])
def bravery_resolve_mine():
    """Escanea bravery locks pending del user y los resuelve si ya hay partida."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    cur = _users._exec(
        f"SELECT {_users._BRAVERY_COLS} FROM bravery_locks WHERE user_id=? AND status='pending' ORDER BY created_at ASC",
        (user["id"],),
    )
    locks = [_users._row_to_bravery(r) for r in cur.fetchall()]
    out = []
    for lk in locks:
        try:
            out.append(_resolve_one_bravery(lk))
        except Exception as e:
            out.append({"status": "skipped", "reason": str(e)})
    # Si algo se resolvió/refundó, refresh balance del frontend
    return jsonify({"checked": len(locks), "results": out})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)