import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(dotenv_path=".env")

# Obtener API key desde variable de entorno
API_KEY = os.getenv("RIOT_API_TOKEN")
print(f"API_KEY: {API_KEY}")  # Debug: Verificar que se cargó la API key correctamente

if not API_KEY:
    raise ValueError("No se encontró la variable de entorno RIOT_API_TOKEN")

# Headers
headers = {
    "X-Riot-Token": API_KEY
}

# Riot API URLs
RIOT_BASE_URL = "https://europe.api.riotgames.com"
RIOT_PLATFORM_URL = "https://euw1.api.riotgames.com"
ACCOUNT_BY_RIOT_ID_URL = f"{RIOT_BASE_URL}/riot/account/v1/accounts/by-riot-id"
MATCHES_BY_PUUID_URL = f"{RIOT_BASE_URL}/lol/match/v5/matches/by-puuid"
MATCH_DETAILS_URL = f"{RIOT_BASE_URL}/lol/match/v5/matches"
LEAGUE_ENTRIES_BY_PUUID_URL = f"{RIOT_PLATFORM_URL}/lol/league/v4/entries/by-puuid"
ACTIVE_GAME_URL = f"{RIOT_PLATFORM_URL}/lol/spectator/v5/active-games/by-summoner"
CHAMPION_MASTERY_URL = f"{RIOT_PLATFORM_URL}/lol/champion-mastery/v4/champion-masteries/by-puuid"

# Configuración de query
MATCHES_COUNT = 20
QUEUE_RANKED_SOLO = 420
WORST_KDA_THRESHOLD = 1.0
