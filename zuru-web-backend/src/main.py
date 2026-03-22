import json
import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from config import (
    headers, ACCOUNT_BY_RIOT_ID_URL, MATCHES_BY_PUUID_URL,
    MATCH_DETAILS_URL, MATCHES_COUNT, QUEUE_RANKED_SOLO, WORST_KDA_THRESHOLD,
    LEAGUE_ENTRIES_BY_PUUID_URL
)

app = Flask(__name__)
CORS(app)

RECENT_FILE = os.path.join(os.path.dirname(__file__), "recent_summoners.json")
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


@app.route("/recentSummoners", methods=["GET"])
def get_recent_summoners():
    return jsonify(load_recent())


@app.route("/recentSummoners", methods=["POST"])
def post_recent_summoner():
    summoner = request.json.get("summoner")
    if summoner:
        save_recent(summoner)
    return jsonify({"ok": True})


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
    entries_res = requests.get(f"{LEAGUE_ENTRIES_BY_PUUID_URL}/{puuid}", headers=headers)
    if entries_res.status_code != 200:
        return "GOLD", "IV"  # fallback

    for entry in entries_res.json():
        if entry["queueType"] == "RANKED_SOLO_5x5":
            return entry["tier"], entry["rank"]

    return "UNRANKED", ""


def calculate_tumor_score(player, game_duration, tier="GOLD"):
    """
    Score 0-100 que mide lo malo que fue un jugador relativo a su rango.
    Los umbrales se ajustan según el tier: en Diamond se exige mucho más que en Bronze.
    """
    thresholds = RANK_THRESHOLDS.get(tier, RANK_THRESHOLDS["GOLD"])
    mins = max(game_duration / 60, 1)

    def pct_below(value, threshold, max_pts):
        """Cuánto por debajo del umbral estás, en puntos."""
        if threshold == 0:
            return 0.0
        return max(0.0, min(float(max_pts), (threshold - value) / threshold * max_pts))

    # KDA (0-30 pts)
    kda_pts = pct_below(player["kda"], thresholds["kda"], 30)

    # CS/min (0-25 pts)
    cs_pts = pct_below(player["cs"] / mins, thresholds["cs_per_min"], 25)

    # Daño/min (0-20 pts)
    dmg_pts = pct_below(player["damage"] / mins, thresholds["dmg_per_min"], 20)

    # Tiempo muerto % (0-15 pts) — igual en todos los rangos
    dead_pct = player["time_dead"] / max(game_duration, 1)
    dead_pts = min(15.0, dead_pct * 37.5)

    # Visión/min (0-10 pts)
    vision_pts = pct_below(player["vision_score"] / mins, thresholds["vision_per_min"], 10)

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


def get_el_peor(game_name, tag_line):
    """Obtiene el peor jugador aliado de las últimas rankeds"""
    try:
        # 1. Obtener PUUID
        account_url = f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name}/{tag_line}"
        account_res = requests.get(account_url, headers=headers)

        if account_res.status_code != 200:
            return {"error": f"Error obteniendo cuenta: {account_res.text}"}, 400

        puuid = account_res.json()["puuid"]

        # 2. Obtener últimas rankeds (SoloQ)
        matches_url = f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count={MATCHES_COUNT}&queue={QUEUE_RANKED_SOLO}"
        matches_res = requests.get(matches_url, headers=headers)

        if matches_res.status_code != 200:
            return {"error": f"Error obteniendo partidas: {matches_res.text}"}, 400

        match_ids = matches_res.json()
        worst_players = []

        # 3. Procesar cada partida
        for match_id in match_ids:
            match_url = f"{MATCH_DETAILS_URL}/{match_id}"
            match_res = requests.get(match_url, headers=headers)

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
        account_res = requests.get(account_url, headers=headers)

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
        matches_res = requests.get(matches_url, headers=headers)

        if matches_res.status_code != 200:
            return {"error": f"Error obteniendo partidas: {matches_res.text}"}, 400

        match_ids = matches_res.json()
        matches_overview = []

        # 4. Procesar cada partida
        for match_id in match_ids:
            match_url = f"{MATCH_DETAILS_URL}/{match_id}"
            match_res = requests.get(match_url, headers=headers)

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
            worst_dict["tumor_score"] = calculate_tumor_score(worst_dict, game_duration, tier)

            matches_overview.append({
                "match_id": match_id,
                "game_duration": game_duration,
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

        return {
            "summoner": f"{account['gameName']}#{account['tagLine']}",
            "tier": tier,
            "division": division,
            "matches": matches_overview,
            "has_more": len(match_ids) == MATCHES_COUNT,
        }

    except Exception as e:
        return {"error": str(e)}, 500


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