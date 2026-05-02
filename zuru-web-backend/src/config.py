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

# Riot API URLs — regionales (match v5, account v1)
RIOT_BASE_URL = "https://europe.api.riotgames.com"
ACCOUNT_BY_RIOT_ID_URL = f"{RIOT_BASE_URL}/riot/account/v1/accounts/by-riot-id"
MATCHES_BY_PUUID_URL = f"{RIOT_BASE_URL}/lol/match/v5/matches/by-puuid"
MATCH_DETAILS_URL = f"{RIOT_BASE_URL}/lol/match/v5/matches"

# Platform URLs — se auto-detectan por región del jugador.
# El default es EUW pero se sobrescribe en runtime.
RIOT_PLATFORM_URL = "https://euw1.api.riotgames.com"

# Mapa de plataformas conocidas (match ID prefix → platform host)
PLATFORM_HOSTS = {
    "EUW1": "https://euw1.api.riotgames.com",
    "EUN1": "https://eun1.api.riotgames.com",
    "NA1":  "https://na1.api.riotgames.com",
    "KR":   "https://kr.api.riotgames.com",
    "JP1":  "https://jp1.api.riotgames.com",
    "BR1":  "https://br1.api.riotgames.com",
    "LA1":  "https://la1.api.riotgames.com",
    "LA2":  "https://la2.api.riotgames.com",
    "OC1":  "https://oc1.api.riotgames.com",
    "TR1":  "https://tr1.api.riotgames.com",
    "RU":   "https://ru.api.riotgames.com",
    "PH2":  "https://ph2.api.riotgames.com",
    "SG2":  "https://sg2.api.riotgames.com",
    "TH2":  "https://th2.api.riotgames.com",
    "TW2":  "https://tw2.api.riotgames.com",
    "VN2":  "https://vn2.api.riotgames.com",
}


def platform_url_for(platform_id):
    """Devuelve la URL base de la plataforma. Fallback a EUW."""
    return PLATFORM_HOSTS.get(platform_id.upper(), RIOT_PLATFORM_URL)


def league_url(platform_host):
    return f"{platform_host}/lol/league/v4/entries/by-puuid"


def spectator_url(platform_host):
    return f"{platform_host}/lol/spectator/v5/active-games/by-summoner"


def mastery_url(platform_host):
    return f"{platform_host}/lol/champion-mastery/v4/champion-masteries/by-puuid"


# Retrocompat: URLs con la plataforma default (EUW). Los callers deberían usar
# las funciones de arriba con platform_host detectado dinámicamente.
LEAGUE_ENTRIES_BY_PUUID_URL = f"{RIOT_PLATFORM_URL}/lol/league/v4/entries/by-puuid"
ACTIVE_GAME_URL = f"{RIOT_PLATFORM_URL}/lol/spectator/v5/active-games/by-summoner"
CHAMPION_MASTERY_URL = f"{RIOT_PLATFORM_URL}/lol/champion-mastery/v4/champion-masteries/by-puuid"

# Configuración de query
MATCHES_COUNT = 20
QUEUE_RANKED_SOLO = 420
QUEUE_RANKED_FLEX = 440
WORST_KDA_THRESHOLD = 1.0

# Queues que admiten tumor scoring (5v5 con roles + tier MMR-based).
# El resto cae al modo "raw stats" — sin tumor score, sin lane diff, sin priors.
RANKED_QUEUES = {QUEUE_RANKED_SOLO, QUEUE_RANKED_FLEX}
TUMOR_COMPATIBLE_QUEUES = RANKED_QUEUES  # mismo set por ahora

# Queues donde se permiten apuestas (P2P + house) y challenges.
BETTING_ALLOWED_QUEUES = RANKED_QUEUES

# Display names (es) — el frontend tiene su propio i18n pero el backend
# manda el queue_id y el front lo traduce. Aquí solo lo usamos para logs.
QUEUE_DISPLAY = {
    420: "SoloQ",
    440: "Flex",
    450: "ARAM",
    400: "Normal Draft",
    430: "Normal Blind",
    700: "Clash",
    830: "Co-op vs IA",
    900: "URF",
    1700: "Arena",
    1900: "URF",
    0: "Custom",
}


def queue_name(queue_id):
    return QUEUE_DISPLAY.get(int(queue_id) if queue_id is not None else 0, f"Queue {queue_id}")


def is_ranked_queue(queue_id):
    try:
        return int(queue_id) in RANKED_QUEUES
    except Exception:
        return False


def allows_betting(queue_id):
    try:
        return int(queue_id) in BETTING_ALLOWED_QUEUES
    except Exception:
        return False
