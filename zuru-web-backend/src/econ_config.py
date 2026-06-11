"""Constantes de la economía y la lógica de juego de Tumor Tracker.

Centralizadas aquí para que tunearlas no requiera buscar magic numbers en
main.py / users_db.py / bravery_engine.py. Si tocas algo aquí, mira los
tests económicos (tests/test_bravery_engine.py, tests/test_tumor_engine.py)
y considera correrlos antes de deploy.

Reglas para añadir constantes:
  - SUS_* / PAYOUT_* / DECAY_* / WINDOW_* mantienen el prefijo del dominio.
  - Comentario corto al lado con la razón (no sólo "60 segundos" → "porque
    a partir de min 24 se puede inferir tumor_score con >90% certeza").
  - Si un test depende del valor, link al test en el comentario.
"""

# ---------------------------------------------------------------------------
# Tumor score thresholds
# ---------------------------------------------------------------------------

# Nivel "sus": el código habla de "tumor sus" en varios sitios (clusters,
# stat-bet threshold de tumor_score=60). En bravery es el break-even del payout.
# Ver: tests/test_bravery_engine.py::TestPayout::test_sus_threshold_60_is_break_even
SUS_TUMOR_THRESHOLD = 60.0


# ---------------------------------------------------------------------------
# House bet multiplier
# ---------------------------------------------------------------------------

# Bonus aplicado a bets contra la predicción. Antes era 1.30 sin gate, lo que
# daba EV+ silencioso en partidas con prediction de baja confianza (~50/50).
UNDERDOG_BONUS = 1.15
UNDERDOG_BONUS_MIN_CONFIDENCE = 25  # debajo no se aplica bonus

# Cap final del multiplier (después de decay y underdog). 1.05 es el min que
# garantiza payout > stake en cualquier escenario; 6.5 evita absurdos en bets
# contra equipos quasi-perdidos.
HOUSE_MULT_MIN = 1.05
HOUSE_MULT_MAX = 6.5


# ---------------------------------------------------------------------------
# Payout decay temporal (cuanto más avanzada la partida, peor payout)
# ---------------------------------------------------------------------------

# Antes de PAYOUT_DECAY_START no hay decay. Entre START y END decae lineal
# hasta PAYOUT_DECAY_FLOOR. Después de END está bloqueado (ver BET_CLOSE_AT_ELAPSED).
PAYOUT_DECAY_START = 5 * 60     # 300s
PAYOUT_DECAY_END = 25 * 60      # 1500s, coincide con cierre de ventana
PAYOUT_DECAY_FLOOR = 0.55       # mult nunca cae por debajo de 55% del nominal


# ---------------------------------------------------------------------------
# Ventana de apuestas
# ---------------------------------------------------------------------------

# Pasados N segundos de gametime, /bets/create rechaza. SoloQ típica dura
# 28-32min, así que 25 evita las apuestas "tengo nexus en mira".
BET_CLOSE_AT_ELAPSED = 25 * 60   # 1500s

# Red de seguridad: si una bet escapa de _is_betting_closed (clock skew, etc.)
# y se creó dentro de los últimos REFUND_WINDOW_SECONDS antes de game_end,
# resolve_bet la refunda. Aplica a match bets y stat bets.
REFUND_WINDOW_SECONDS = 60


# ---------------------------------------------------------------------------
# Daily reward
# ---------------------------------------------------------------------------

DAILY_REWARD_AMOUNT = 100
DAILY_REWARD_INTERVAL_SECONDS = 24 * 3600  # antes era 20h → +600 TC/mes/user de inflación


# ---------------------------------------------------------------------------
# Anti-sybil
# ---------------------------------------------------------------------------

LOGIN_RATE_MAX_PER_MINUTE = 3
LOGIN_RATE_MAX_PER_HOUR = 10
# Mínima edad de cuenta Discord para registrar (segundos)
MIN_DISCORD_ACCOUNT_AGE_SECONDS = 3 * 24 * 3600
# Snowflake epoch de Discord (constante de la API, no de nuestra app)
DISCORD_EPOCH_MS = 1420070400000


# ---------------------------------------------------------------------------
# Bravery
# ---------------------------------------------------------------------------

# TTL del lock pending: tras este tiempo la partida debe estar jugada.
BRAVERY_TTL_SECONDS = 3 * 60 * 60       # 3h
# Refund automático: si han pasado N horas sin partida, devolver stake.
BRAVERY_REFUND_AFTER = 6 * 60 * 60      # 6h
