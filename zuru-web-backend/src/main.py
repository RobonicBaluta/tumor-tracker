import json
import os
import time
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from config import (
    headers, ACCOUNT_BY_RIOT_ID_URL, MATCHES_BY_PUUID_URL,
    MATCH_DETAILS_URL, MATCHES_COUNT, QUEUE_RANKED_SOLO, WORST_KDA_THRESHOLD,
    LEAGUE_ENTRIES_BY_PUUID_URL, ACTIVE_GAME_URL, RIOT_BASE_URL, CHAMPION_MASTERY_URL
)
from riot_infra import riot_get as _riot_get, cache_stats


def riot_get(url, max_retries=4):
    return _riot_get(url, headers=headers, max_retries=max_retries)


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
CORS(app)

LIVE_CACHE_FILE = os.path.join(os.path.dirname(__file__), "live_game_cache.json")
LIVE_CACHE_TTL = 6 * 3600  # 6 horas para éxitos
LIVE_CACHE_TTL_FAIL = 30 * 60  # 30 min para fallos (rate limit, etc)


def load_live_cache():
    if not os.path.exists(LIVE_CACHE_FILE):
        return {}
    try:
        with open(LIVE_CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_live_cache(cache):
    try:
        with open(LIVE_CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass


RECENT_FILE = os.path.join(os.path.dirname(__file__), "recent_summoners.json")
LEADERBOARD_FILE = os.path.join(os.path.dirname(__file__), "leaderboard.json")
SAVED_ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "saved_accounts.json")
WATCH_LIST_FILE = os.path.join(os.path.dirname(__file__), "watch_list.json")
PREDICTIONS_FILE = os.path.join(os.path.dirname(__file__), "predictions.json")
BLACKLIST_FILE = os.path.join(os.path.dirname(__file__), "champion_blacklist.json")


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


def load_predictions():
    if not os.path.exists(PREDICTIONS_FILE):
        return []
    try:
        with open(PREDICTIONS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_predictions(data):
    with open(PREDICTIONS_FILE, "w") as f:
        json.dump(data, f)
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


def get_player_rank(puuid):
    """Obtiene el tier SoloQ actual del jugador (e.g. 'GOLD')."""
    entries_res = riot_get(f"{LEAGUE_ENTRIES_BY_PUUID_URL}/{puuid}")
    if entries_res.status_code != 200:
        return "GOLD", "IV"  # fallback

    for entry in entries_res.json():
        if entry["queueType"] == "RANKED_SOLO_5x5":
            return entry["tier"], entry["rank"]

    return "UNRANKED", ""


ROLE_PROFILES = {
    # weights:  kda, cs, dmg, dead, vision        (suman 100)
    # mults:    multiplicador a aplicar al threshold base por rango
    "TOP":     {"weights": (28, 22, 22, 15, 13),  "cs_mult": 1.0,  "dmg_mult": 1.0,  "vision_mult": 0.7},
    "JUNGLE":  {"weights": (28, 18, 18, 15, 21),  "cs_mult": 0.7,  "dmg_mult": 1.0,  "vision_mult": 1.2},
    "MIDDLE":  {"weights": (28, 22, 25, 15, 10),  "cs_mult": 1.0,  "dmg_mult": 1.1,  "vision_mult": 0.7},
    "BOTTOM":  {"weights": (28, 25, 27, 15, 5),   "cs_mult": 1.1,  "dmg_mult": 1.2,  "vision_mult": 0.5},
    "UTILITY": {"weights": (30, 5,  10, 15, 40),  "cs_mult": 0.25, "dmg_mult": 0.45, "vision_mult": 2.5},
    # default si no se conoce el rol
    "DEFAULT": {"weights": (30, 25, 20, 15, 10),  "cs_mult": 1.0,  "dmg_mult": 1.0,  "vision_mult": 1.0},
}


def calculate_tumor_score(player, game_duration, tier="GOLD", role="DEFAULT"):
    """
    Score 0-100 que mide lo malo que fue un jugador relativo a su rango y rol.
    Los umbrales se ajustan por tier y rol: a un support se le exige visión,
    no farm; a un ADC daño y CS, no visión.
    """
    base = RANK_THRESHOLDS.get(tier, RANK_THRESHOLDS["GOLD"])
    profile = ROLE_PROFILES.get(role, ROLE_PROFILES["DEFAULT"])
    w_kda, w_cs, w_dmg, w_dead, w_vis = profile["weights"]

    cs_thr = base["cs_per_min"] * profile["cs_mult"]
    dmg_thr = base["dmg_per_min"] * profile["dmg_mult"]
    vis_thr = base["vision_per_min"] * profile["vision_mult"]

    mins = max(game_duration / 60, 1)

    def pct_below(value, threshold, max_pts):
        if threshold == 0:
            return 0.0
        return max(0.0, min(float(max_pts), (threshold - value) / threshold * max_pts))

    kda_pts = pct_below(player["kda"], base["kda"], w_kda)
    cs_pts = pct_below(player["cs"] / mins, cs_thr, w_cs)
    dmg_pts = pct_below(player["damage"] / mins, dmg_thr, w_dmg)
    dead_pct = player["time_dead"] / max(game_duration, 1)
    dead_pts = min(float(w_dead), dead_pct * (w_dead * 2.5))
    vision_pts = pct_below(player["vision_score"] / mins, vis_thr, w_vis)

    return round(kda_pts + cs_pts + dmg_pts + dead_pts + vision_pts)


def get_worst_player_in_match(participants, puuid):
    """Encuentra el peor aliado en una partida"""
    my_player = next(p for p in participants if p["puuid"] == puuid)
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

        # 2. Obtener rango (solo en la primera carga; en "load more" se reutiliza)
        if tier_override:
            tier, division = tier_override, ""
        else:
            tier, division = get_player_rank(puuid)

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
            my_data = next(p for p in participants if p["puuid"] == puuid)
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
        return {"error": str(e)}, 500


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
        role_counts = {}
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
            if current_champion_id is not None and p.get("championId") == current_champion_id:
                champion_games += 1
                if p.get("win"):
                    champion_wins += 1
                role_for_champ = p.get("teamPosition") or ""
                if role_for_champ:
                    role_counts[role_for_champ] = role_counts.get(role_for_champ, 0) + 1

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
        likely_role = max(role_counts, key=role_counts.get) if role_counts else ""

        # Streak / tilt detection
        # Tilt = últimas 3 partidas con tumor medio >= 50 o 3 losses seguidas
        recent_losses = sum(1 for w in recent_wins if not w)
        avg_recent_tumor = sum(recent_tumors) / len(recent_tumors) if recent_tumors else 0
        is_tilted = (recent_losses >= 3) or (avg_recent_tumor >= 50 and len(recent_tumors) >= 3)

        base_score = round(sum(scores) / len(scores))
        # Si tiltado, añadir penalización al score predicho
        adjusted_score = base_score
        if is_tilted:
            adjusted_score = min(100, base_score + 15)

        return {
            "score": adjusted_score,
            "base_score": base_score,
            "is_tilted": is_tilted,
            "recent_losses": recent_losses,
            "recent_avg_tumor": round(avg_recent_tumor),
            "likely_role": likely_role,
            "champion_games": champion_games,
            "champion_wins": champion_wins,
            "champion_total_sample": total_games,
            "champion_pct": champ_pct,
            "champion_winrate": champ_wr,
            "is_main": champ_pct >= 40,
            "teammate_history": recent_match_puuids,
        }
    except Exception:
        return None


@app.route('/liveGame', methods=['GET'])
def live_game_endpoint():
    game_name = request.args.get('game_name')
    tag_line = request.args.get('tag_line')
    if not game_name or not tag_line:
        return jsonify({"error": "Falta game_name y/o tag_line"}), 400

    acc_res = riot_get(f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name}/{tag_line}")
    if acc_res.status_code != 200:
        return jsonify({"error": "No se pudo obtener la cuenta"}), 400
    me_puuid = acc_res.json()["puuid"]

    spec_res = riot_get(f"{ACTIVE_GAME_URL}/{me_puuid}")
    if spec_res.status_code == 404:
        return jsonify({"error": "El jugador no está en partida ahora mismo"}), 404
    if spec_res.status_code != 200:
        return jsonify({"error": f"Error spectator: {spec_res.text}"}), 400

    game = spec_res.json()
    participants = game.get("participants", [])
    players = []
    cache = load_live_cache()
    cache_dirty = False
    now = time.time()

    # Watch list + blacklist del viewer
    viewer_key = f"{game_name}#{tag_line}"
    watched = set(load_watch_list().get(viewer_key, []))
    blacklist = set(load_blacklist().get(viewer_key, []))

    for p in participants:
        p_puuid = p.get("puuid")
        if not p_puuid:
            continue

        champ_id = p.get("championId")
        cache_key = f"{p_puuid}:{champ_id}"
        cached = cache.get(cache_key)
        if cached and cached["data"].get("avg_tumor_score") is not None and (now - cached.get("ts", 0)) < LIVE_CACHE_TTL:
            entry = dict(cached["data"])
            entry["is_me"] = p_puuid == me_puuid
            entry["is_watched"] = entry.get("nombre") in watched
            champ_name = champ_id_to_name(champ_id)
            entry["is_blacklisted"] = champ_name in blacklist
            entry["champion_name"] = champ_name
            players.append(entry)
            continue

        tier, division = get_player_rank(p_puuid)

        riot_id = p.get("riotId", "")
        if not riot_id:
            acc2 = riot_get(f"{RIOT_BASE_URL}/riot/account/v1/accounts/by-puuid/{p_puuid}")
            if acc2.status_code == 200:
                a = acc2.json()
                riot_id = f"{a.get('gameName', '?')}#{a.get('tagLine', '?')}"
            else:
                riot_id = "?"

        profile = compute_player_profile(p_puuid, tier, num_matches=7, current_champion_id=champ_id)

        mastery_points = 0
        mastery_level = 0
        try:
            m_res = riot_get(f"{CHAMPION_MASTERY_URL}/{p_puuid}/by-champion/{champ_id}")
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
            "is_main": profile["is_main"] if profile else False,
            "is_tilted": profile["is_tilted"] if profile else False,
            "recent_losses": profile["recent_losses"] if profile else 0,
            "recent_avg_tumor": profile["recent_avg_tumor"] if profile else 0,
            "mastery_points": mastery_points,
            "mastery_level": mastery_level,
            "estimated_games": round(mastery_points / 1900) if mastery_points else 0,
            "_teammate_history": profile.get("teammate_history", []) if profile else [],
        }
        if entry["avg_tumor_score"] is not None:
            cache[cache_key] = {"ts": now, "data": entry}
            cache_dirty = True

        champ_name = champ_id_to_name(champ_id)
        entry["champion_name"] = champ_name

        entry_out = dict(entry)
        entry_out["is_me"] = p_puuid == me_puuid
        entry_out["is_watched"] = riot_id in watched
        entry_out["is_blacklisted"] = champ_name in blacklist
        players.append(entry_out)

    if cache_dirty:
        save_live_cache(cache)

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

    # limpia campos internos antes de devolver
    for p in players:
        p.pop("_teammate_history", None)

    # Record prediction for later validation
    game_id = game.get("gameId")
    queue_id = game.get("gameQueueConfigId")
    platform = "EUW1"  # match ids use this prefix
    match_id = f"{platform}_{game_id}"

    blue_sum = sum(p["avg_tumor_score"] or 0 for p in players if p["team_id"] == 100)
    red_sum = sum(p["avg_tumor_score"] or 0 for p in players if p["team_id"] == 200)
    diff = abs(blue_sum - red_sum)
    predicted_winner = None
    if diff >= 5:
        predicted_winner = "blue" if blue_sum < red_sum else "red"

    me = next((p for p in players if p["is_me"]), None)
    viewer_team = "blue" if (me and me["team_id"] == 100) else "red" if me else None

    try:
        preds = load_predictions()
        if not any(p["match_id"] == match_id and p.get("viewer_puuid") == me_puuid for p in preds):
            preds.append({
                "match_id": match_id,
                "game_id": game_id,
                "viewer_puuid": me_puuid,
                "viewer_name": f"{game_name}#{tag_line}",
                "viewer_team": viewer_team,
                "blue_sum": blue_sum,
                "red_sum": red_sum,
                "predicted_winner": predicted_winner,
                "created_at": now,
                "resolved": False,
                "actual_winner": None,
                "correct": None,
            })
            save_predictions(preds)
    except Exception:
        pass

    return jsonify({
        "game_id": game_id,
        "match_id": match_id,
        "queue_id": queue_id,
        "players": players,
    })


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

    evolution = []
    hour_stats = {}
    week_buckets = {"this": {"games": 0, "wins": 0, "tumor_sum": 0},
                    "last": {"games": 0, "wins": 0, "tumor_sum": 0}}
    role_combo_stats = {}
    duo_stats = {}

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
            "champion": me["championName"],
            "kda": round(stats["kda"], 2),
        })

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
    })


@app.route('/cacheStats', methods=['GET'])
def cache_stats_endpoint():
    return jsonify(cache_stats())


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


@app.route('/predictionStats', methods=['GET'])
def prediction_stats_endpoint():
    """Resuelve predicciones pendientes y devuelve el acierto global."""
    preds = load_predictions()
    changed = False

    for pred in preds:
        if pred.get("resolved"):
            continue
        if pred.get("predicted_winner") is None:
            pred["resolved"] = True
            changed = True
            continue
        mres = riot_get(f"{MATCH_DETAILS_URL}/{pred['match_id']}")
        if mres.status_code != 200:
            continue
        info = mres.json().get("info", {})
        parts = info.get("participants", [])
        if not parts:
            continue
        # determinar ganador real
        blue_win = next((p["win"] for p in parts if p["teamId"] == 100), False)
        actual = "blue" if blue_win else "red"
        pred["actual_winner"] = actual
        pred["correct"] = (pred["predicted_winner"] == actual)
        pred["resolved"] = True
        changed = True

    if changed:
        save_predictions(preds)

    resolved = [p for p in preds if p.get("resolved") and p.get("predicted_winner") is not None]
    total = len(resolved)
    correct = sum(1 for p in resolved if p.get("correct"))
    pending = sum(1 for p in preds if not p.get("resolved"))
    pct = round(correct / total * 100) if total else 0

    return jsonify({
        "total": total,
        "correct": correct,
        "accuracy": pct,
        "pending": pending,
        "recent": sorted(
            [p for p in preds if p.get("resolved") and p.get("predicted_winner") is not None],
            key=lambda x: x.get("created_at", 0), reverse=True
        )[:10],
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


@app.route('/matchDetail/<match_id>', methods=['GET'])
def match_detail_endpoint(match_id):
    res = riot_get(f"{MATCH_DETAILS_URL}/{match_id}")
    if res.status_code != 200:
        return jsonify({"error": "No se pudo obtener la partida"}), res.status_code

    info = res.json()["info"]
    participants = info["participants"]
    game_duration = info["gameDuration"]
    viewer_tier = request.args.get("viewer_tier", "GOLD") or "GOLD"

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
        tumor_score = calculate_tumor_score(stats, game_duration, viewer_tier, role)
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
            "tumor_score": tumor_score,
        }

    team_blue = [summarize(p) for p in participants if p["teamId"] == 100]
    team_red  = [summarize(p) for p in participants if p["teamId"] == 200]

    return jsonify({
        "match_id": match_id,
        "game_duration": info["gameDuration"],
        "game_date": info.get("gameCreation", 0),
        "blue_win": team_blue[0]["win"] if team_blue else False,
        "team_blue": team_blue,
        "team_red": team_red,
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