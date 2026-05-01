"""
Auth helpers: Discord OAuth + JWT.

Variables de entorno necesarias en producción:
  - DISCORD_CLIENT_ID
  - DISCORD_CLIENT_SECRET
  - DISCORD_REDIRECT_URI  (e.g. https://tumor-tracker.vercel.app/auth/callback)
  - JWT_SECRET            (cualquier string largo random)
  - FRONTEND_URL          (para redireccionar tras login)

Flow:
  1. Frontend abre /auth/discord/login → backend redirige a Discord
  2. User autoriza → Discord redirige a /auth/discord/callback?code=XXX
  3. Backend canjea code por access_token, fetch info de usuario,
     upsert en DB, emite JWT, redirige al frontend con ?token=JWT
  4. Frontend guarda JWT en localStorage, lo manda en cada request
"""
import json
import os
import time
import urllib.parse

import requests

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:5000/auth/discord/callback")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"


def discord_auth_redirect_url():
    """URL a la que redirigir al user para que autorice con Discord."""
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
        "prompt": "none",
    }
    return f"{DISCORD_AUTH_URL}?{urllib.parse.urlencode(params)}"


def discord_exchange_code(code):
    """Intercambia el `code` recibido por un access_token. Devuelve el dict de Discord."""
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    res = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers, timeout=10)
    if res.status_code != 200:
        return None
    return res.json()


def discord_fetch_user(access_token):
    """Obtiene el perfil del user usando el access_token. Devuelve dict o None."""
    res = requests.get(
        DISCORD_USER_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if res.status_code != 200:
        return None
    return res.json()


# ---------------------------------------------------------------------------
# JWT (sin librería externa: HS256 manual con hmac+sha256)
# ---------------------------------------------------------------------------

import base64
import hashlib
import hmac


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def issue_jwt(payload: dict, ttl_seconds=30 * 86400):
    """Firma un JWT HS256. TTL por defecto: 30 días."""
    header = {"alg": "HS256", "typ": "JWT"}
    body = dict(payload)
    body["iat"] = int(time.time())
    body["exp"] = int(time.time()) + ttl_seconds

    h_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p_b64 = _b64url_encode(json.dumps(body, separators=(",", ":")).encode())
    signing_input = f"{h_b64}.{p_b64}".encode()
    sig = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    s_b64 = _b64url_encode(sig)
    return f"{h_b64}.{p_b64}.{s_b64}"


def verify_jwt(token: str):
    """Verifica firma + expiración. Devuelve el payload o None."""
    if not token or token.count(".") != 2:
        return None
    h_b64, p_b64, s_b64 = token.split(".")
    signing_input = f"{h_b64}.{p_b64}".encode()
    expected = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    received = _b64url_decode(s_b64)
    if not hmac.compare_digest(expected, received):
        return None
    try:
        payload = json.loads(_b64url_decode(p_b64))
    except Exception:
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload
