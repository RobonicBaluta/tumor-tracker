# 3. Procesar cada partida
# for match_id in match_ids:
#     match_url = f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}"
#     match_res = requests.get(match_url, headers=headers)

#     if match_res.status_code != 200:
#         print(f"Error match {match_id}")
#         continue

#     data = match_res.json()

#     # Buscar tu jugador
#     player_data = None
#     for p in data["info"]["participants"]:
#         if p["puuid"] == puuid:
#             player_data = p
#             break

#     if not player_data:
#         continue

#     kills = player_data["kills"] 
#     deaths = player_data["deaths"]
#     assists = player_data["assists"]
#     champion = player_data["championName"]
#     win = player_data["win"]

#     # Calcular KDA
#     kda = (kills + assists) / max(1, deaths)

#     result = "✅ WIN" if win else "❌ LOSE"

#     print(f"{result} | {champion} | {kills}/{deaths}/{assists} | KDA: {kda:.2f}")