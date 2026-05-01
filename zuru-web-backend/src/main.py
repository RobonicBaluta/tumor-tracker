import json
import os
import threading
import time
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from config import (
    headers, ACCOUNT_BY_RIOT_ID_URL, MATCHES_BY_PUUID_URL,
    MATCH_DETAILS_URL, MATCHES_COUNT, QUEUE_RANKED_SOLO, WORST_KDA_THRESHOLD,
    LEAGUE_ENTRIES_BY_PUUID_URL, ACTIVE_GAME_URL, RIOT_BASE_URL, CHAMPION_MASTERY_URL,
    RIOT_PLATFORM_URL, PLATFORM_HOSTS, platform_url_for,
    league_url, spectator_url, mastery_url,
)
from riot_infra import riot_get as _riot_get, cache_stats
from tumor_engine import (
    compute_match_tumor_from_stats as _engine_match_score,
    compute_prior_tumor as _engine_prior,
    compute_team_tumor as _engine_team,
    predict_team_outcome as _engine_predict,
)
import auth as _auth
import users_db as _users
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
        w = match["worst"]
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


def get_worst_player_in_match(participants, puuid):
    """Encuentra el peor aliado en una partida.
    Devuelve None si el jugador no está en la partida (caso raro: cambio de
    region, match corrupto, etc)."""
    my_player = next((p for p in participants if p["puuid"] == puuid), None)
    if my_player is None:
        return None
    my_team_id = my_player["teamId"]

    worst_player = None
    worst_kda = float("inf")

    for p in participants:
        # Solo aliados (incluyéndote a ti)
        if p["teamId"] != my_team_id:
            continue

        kda = calculate_kda(p["kills"], p["deaths"], p["assists"])
        p["kda"] = kda

        if kda < worst_kda:
            worst_kda = kda
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

        # 3. Procesar cada partida
        for match_id in match_ids:
            match_url = f"{MATCH_DETAILS_URL}/{match_id}"
            match_res = riot_get(match_url)

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


def get_overview(game_name, tag_line, start=0, tier_override=None):
    """Obtiene el peor aliado por cada una de las últimas rankeds"""
    try:
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

        # 2. Obtener rango (solo en la primera carga; en "load more" se reutiliza)
        if tier_override:
            tier, division = tier_override, ""
        else:
            tier, division = get_player_rank(puuid, platform_host)

        # 3. Obtener rankeds (SoloQ) desde el offset pedido
        matches_url = f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start={start}&count={MATCHES_COUNT}&queue={QUEUE_RANKED_SOLO}"
        matches_res = riot_get(matches_url)

        if matches_res.status_code != 200:
            return {"error": f"Error obteniendo partidas: {matches_res.text}"}, 400

        match_ids = matches_res.json()
        matches_overview = []

        # 4. Procesar cada partida
        for match_id in match_ids:
            match_url = f"{MATCH_DETAILS_URL}/{match_id}"
            match_res = riot_get(match_url)

            if match_res.status_code != 200:
                continue

            data = match_res.json()
            participants = data["info"]["participants"]
            game_duration = data["info"]["gameDuration"]

            worst_player = get_worst_player_in_match(participants, puuid)
            if not worst_player:
                continue

            # Datos del propio jugador en esa partida
            my_data = next((p for p in participants if p["puuid"] == puuid), None)
            if my_data is None:
                continue
            my_kda = calculate_kda(my_data["kills"], my_data["deaths"], my_data["assists"])
            my_cs = my_data["totalMinionsKilled"] + my_data["neutralMinionsKilled"]

            # Equipo aliado
            team = [p for p in participants if p["teamId"] == my_data["teamId"]]
            team_kdas = [calculate_kda(p["kills"], p["deaths"], p["assists"]) for p in team]

            # ¿Eres el mejor de tu equipo y aun así perdiste?
            best_and_lost = not my_data["win"] and my_kda == max(team_kdas)
            worst_is_me = worst_player["puuid"] == puuid

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
                "game_duration": game_duration,
                "game_date": data["info"].get("gameCreation", 0),
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

    # Nueva predicción (role-weighted + volume-weighted + elo-normalized)
    prediction = predict_team_outcome(players)

    game_id = game.get("gameId")
    queue_id = game.get("gameQueueConfigId")
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

    # Log detallado para afinación empírica
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
    }

    # Persistir snapshot: priors + predicción para reutilizar en matchDetail.
    try:
        snapshot = {
            "prediction": prediction,
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
            d = duo_stats.setdefault(t["puuid"], {"name": name, "games": 0, "wins": 0,
                                                  "champion_counts": {}})
            d["games"] += 1
            d["wins"] += int(win)
            ch = t.get("championName", "?")
            d["champion_counts"][ch] = d["champion_counts"].get(ch, 0) + 1

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
        duo_out.append({
            "puuid": pp,
            "nombre": v["name"],
            "games": v["games"],
            "wins": v["wins"],
            "winrate": round(v["wins"] / v["games"] * 100),
            "top_champion": top_champ,
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

    # Group + label clusters by their dominant trait
    clusters = []
    for ci in range(k):
        members = [meta[i] for i in range(len(meta)) if labels[i] == ci]
        if not members:
            continue
        c = centroids[ci]
        prior_norm, recent_norm, win_rate, tilt_frac, streak_frac = c
        # Heuristic naming
        avg_prior = prior_norm * 100
        avg_recent = recent_norm * 100
        if avg_prior > 65:
            name = "Tumores Crónicos"
            emoji = "💀"
        elif avg_prior < 35 and win_rate > 0.55:
            name = "Carries Funcionales"
            emoji = "🔥"
        elif streak_frac > 0.4:
            name = "Hot Streak"
            emoji = "📈"
        elif tilt_frac > 0.4:
            name = "Tilteados"
            emoji = "🌋"
        elif avg_recent > 60:
            name = "Bajón reciente"
            emoji = "📉"
        else:
            name = "Promedio"
            emoji = "·"
        # Sort members by prior (worst first for tumor clusters, best first otherwise)
        members.sort(key=lambda m: -m["prior_tumor"] if avg_prior > 50 else m["prior_tumor"])
        clusters.append({
            "id": ci,
            "name": name,
            "emoji": emoji,
            "size": len(members),
            "centroid": {
                "avg_prior": round(avg_prior, 1),
                "avg_recent": round(avg_recent, 1),
                "win_rate": round(win_rate * 100, 1),
                "tilt_frac": round(tilt_frac * 100, 1),
                "streak_frac": round(streak_frac * 100, 1),
            },
            "samples": members[:6],  # top 6 per cluster
        })

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
    user["can_claim_daily"] = _users.can_claim_daily(user["id"])
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
    if acc_res.status_code != 200:
        return jsonify({"error": "No se pudo obtener la cuenta de Riot"}), 400
    puuid = acc_res.json()["puuid"]
    riot_id = f"{game_name}#{tag_line}"
    _users.link_riot_account(user["id"], puuid, riot_id)
    return jsonify(_users.get_user_by_id(user["id"]))


@app.route('/currency/balance', methods=['GET'])
def currency_balance():
    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    txs = _users.get_recent_transactions(user["id"], limit=20)
    return jsonify({
        "currency": user["currency"],
        "can_claim_daily": _users.can_claim_daily(user["id"]),
        "recent_transactions": txs,
    })


@app.route('/currency/daily', methods=['POST'])
def currency_daily():
    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    new_balance = _users.claim_daily(user["id"], amount=100)
    if new_balance is None:
        return jsonify({"error": "Ya has reclamado el daily reward hoy"}), 429
    return jsonify({"currency": new_balance, "awarded": 100})


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
    room = _users.get_room_by_code(code)
    if not room:
        return jsonify({"error": "Sala no encontrada"}), 404
    data = request.get_json() or {}
    riot_id = data.get("riot_id", "").strip()
    if not riot_id:
        return jsonify({"error": "riot_id requerido"}), 400
    _users.remove_room_member(room["id"], riot_id)
    return jsonify({"ok": True})


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


@app.route('/bets/create', methods=['POST'])
def bets_create():
    """Crea una apuesta. Body:
      Match bet:  { match_id, game_id, side: 'blue'|'red', amount }
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

    if not match_id or amount <= 0:
        return jsonify({"error": "Faltan campos o son inválidos"}), 400
    if amount > user["currency"]:
        return jsonify({"error": "Saldo insuficiente"}), 400

    if bet_kind == "match":
        if side not in ("blue", "red"):
            return jsonify({"error": "side debe ser blue|red"}), 400
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
        bet = _users.create_bet(
            user["id"], match_id, game_id, side, amount,
            bet_kind="stat", target_puuid=target_puuid, target_name=target_name,
            stat_type=stat_type, threshold=threshold,
        )
    else:
        return jsonify({"error": "bet_kind inválido"}), 400

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
    parts = (match_info or {}).get("info", {}).get("participants", []) or []
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
    return None


@app.route('/challenges/create', methods=['POST'])
def challenges_create():
    """Body: { stat_type, amount, comparison? } — challenger debe tener riot_id vinculado."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Login requerido"}), 401
    if not user.get("riot_puuid"):
        return jsonify({"error": "Vincula tu Riot ID antes de crear challenges"}), 400
    data = request.get_json() or {}
    stat_type = data.get("stat_type")
    try:
        amount = int(data.get("amount", 0))
    except Exception:
        return jsonify({"error": "amount inválido"}), 400
    comparison = data.get("comparison") or ("lower_wins" if stat_type == "deaths" else "higher_wins")
    if amount <= 0 or stat_type not in _users.VALID_CHALLENGE_STATS:
        return jsonify({"error": "stat_type/amount inválidos"}), 400
    if amount > user["currency"]:
        return jsonify({"error": "Saldo insuficiente"}), 400
    ch = _users.create_challenge(user["id"], stat_type, amount, comparison)
    if not ch:
        return jsonify({"error": "No se pudo crear el challenge"}), 500
    return jsonify(_augment_challenge(ch))


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
    return jsonify([_augment_challenge(c) for c in _users.list_open_challenges(limit=50)])


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
    """Resuelve predicciones sin resolver consultando el match detail real."""
    db = _pred_db()
    q = "SELECT match_id, viewer_puuid, predicted_winner FROM predictions WHERE resolved=0"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = db.execute(q).fetchall()
    for match_id, viewer_puuid, predicted in rows:
        if predicted is None:
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
        predictions_mark_resolved(match_id, viewer_puuid, actual, predicted)


@app.route('/predictionStats', methods=['GET'])
def prediction_stats_endpoint():
    """Resuelve predicciones pendientes y devuelve el acierto global."""
    _resolve_pending_predictions()
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

    # Auto-resolver apuestas P2P de este match (match bets + stat bets)
    try:
        _users.resolve_bets_for_match(match_id, actual)
    except Exception:
        pass
    try:
        stat_bets = _users.list_stat_bets_for_match(match_id)
        if stat_bets:
            # Indexa participantes por puuid para lookup O(1)
            by_puuid = {p.get("puuid"): p for p in parts if p.get("puuid")}
            for sb in stat_bets:
                tp = sb.get("target_puuid")
                stype = sb.get("stat_type")
                p = by_puuid.get(tp)
                if not p or not stype:
                    continue
                k = p.get("kills", 0) or 0
                d = p.get("deaths", 0) or 0
                a = p.get("assists", 0) or 0
                if stype == "kills":
                    actual_val = float(k)
                elif stype == "deaths":
                    actual_val = float(d)
                elif stype == "assists":
                    actual_val = float(a)
                elif stype == "kda":
                    actual_val = (k + a) / max(d, 1)
                else:
                    continue
                _users.resolve_stat_bet(sb["id"], actual_val)
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

    if not game_name or not tag_line:
        return jsonify({"error": "Falta game_name y/o tag_line como query params"}), 400

    result = get_overview(game_name, tag_line, start=start, tier_override=tier_override)
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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)