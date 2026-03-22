import json
import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from config import (
    headers, ACCOUNT_BY_RIOT_ID_URL, MATCHES_BY_PUUID_URL,
    MATCH_DETAILS_URL, MATCHES_COUNT, QUEUE_RANKED_SOLO, WORST_KDA_THRESHOLD
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


def calculate_tumor_score(player, game_duration):
    """
    Score 0-100 que mide lo malo que fue un jugador.
    100 = nuclear tumor, 0 = jugador decente.
    """
    mins = max(game_duration / 60, 1)

    # KDA (0-30 pts): KDA 0 = 30, KDA 1+ = 0
    kda_pts = max(0.0, min(30.0, (1.0 - player["kda"]) * 30))

    # CS/min (0-25 pts): 0 cs/min = 25, 4+ cs/min = 0
    cs_per_min = player["cs"] / mins
    cs_pts = max(0.0, min(25.0, (4.0 - cs_per_min) / 4.0 * 25))

    # Daño/min (0-20 pts): 0 = 20, 800+ dm/min = 0
    dmg_per_min = player["damage"] / mins
    dmg_pts = max(0.0, min(20.0, (800 - dmg_per_min) / 800 * 20))

    # Tiempo muerto % (0-15 pts): >40% del tiempo muerto = 15 pts
    dead_pct = player["time_dead"] / max(game_duration, 1)
    dead_pts = min(15.0, dead_pct * 37.5)

    # Visión/min (0-10 pts): 0 vs/min = 10, 2+ vs/min = 0
    vision_per_min = player["vision_score"] / mins
    vision_pts = max(0.0, min(10.0, (2.0 - vision_per_min) / 2.0 * 10))

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


def get_overview(game_name, tag_line):
    """Obtiene el peor aliado por cada una de las últimas rankeds"""
    try:
        # 1. Obtener PUUID
        account_url = f"{ACCOUNT_BY_RIOT_ID_URL}/{game_name}/{tag_line}"
        account_res = requests.get(account_url, headers=headers)

        if account_res.status_code != 200:
            return {"error": f"Error obteniendo cuenta: {account_res.text}"}, 400

        account = account_res.json()
        puuid = account["puuid"]

        # 2. Obtener últimas rankeds (SoloQ)
        matches_url = f"{MATCHES_BY_PUUID_URL}/{puuid}/ids?start=0&count={MATCHES_COUNT}&queue={QUEUE_RANKED_SOLO}"
        matches_res = requests.get(matches_url, headers=headers)

        if matches_res.status_code != 200:
            return {"error": f"Error obteniendo partidas: {matches_res.text}"}, 400

        match_ids = matches_res.json()
        matches_overview = []

        # 3. Procesar cada partida
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
            worst_dict["tumor_score"] = calculate_tumor_score(worst_dict, game_duration)

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

        # 4. Encontrar el top tumor (el que más veces apareció como el peor)
        from collections import Counter
        appearances = Counter(m["worst"]["nombre"] for m in matches_overview)
        top_nombre = appearances.most_common(1)[0][0] if appearances else None

        top_tumor = None
        if top_nombre:
            top_matches = [m["worst"] for m in matches_overview if m["worst"]["nombre"] == top_nombre]
            total_kills   = sum(p["kills"]   for p in top_matches)
            total_deaths  = sum(p["deaths"]  for p in top_matches)
            total_assists = sum(p["assists"] for p in top_matches)
            avg_kda = round(calculate_kda(total_kills, total_deaths, total_assists), 2)
            # Campeón más jugado por este tumor
            champion = Counter(p["campeon"] for p in top_matches).most_common(1)[0][0]
            top_tumor = {
                "nombre": top_nombre,
                "apariciones": appearances[top_nombre],
                "campeon": champion,
                "total_kills": total_kills,
                "total_deaths": total_deaths,
                "total_assists": total_assists,
                "avg_kda": avg_kda
            }

        # 5. Estadísticas personales (solo partidas no remake)
        valid = [m for m in matches_overview if m["game_duration"] >= 300]
        total = len(valid)
        wins_count = sum(1 for m in valid if m["win"])
        personal_stats = {
            "total_matches": total,
            "wins": wins_count,
            "losses": total - wins_count,
            "win_rate": round(wins_count / total * 100) if total else 0,
            "times_worst": sum(1 for m in valid if m["worst_is_me"]),
            "times_best_and_lost": sum(1 for m in valid if m["best_and_lost"]),
            "avg_kda": round(sum(m["my_kda"] for m in valid) / total, 2) if total else 0,
            "avg_cs": round(sum(m["my_cs"] for m in valid) / total, 1) if total else 0,
            "avg_damage": round(sum(m["my_damage"] for m in valid) / total) if total else 0,
        }

        return {
            "summoner": f"{account['gameName']}#{account['tagLine']}",
            "matches": matches_overview,
            "top_tumor": top_tumor,
            "personal_stats": personal_stats,
        }

    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/getOverview', methods=['GET'])
def get_overview_endpoint():
    game_name = request.args.get('game_name')
    tag_line = request.args.get('tag_line')

    if not game_name or not tag_line:
        return jsonify({"error": "Falta game_name y/o tag_line como query params"}), 400

    result = get_overview(game_name, tag_line)
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