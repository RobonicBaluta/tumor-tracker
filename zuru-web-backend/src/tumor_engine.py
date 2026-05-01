"""
Tumor scoring engine — pipeline limpia y unificada.

Una sola escala 0-100 para todo. 0 = inmaculado, 100 = catastrófico.

Pipeline:
  1. Datos crudos por participante (Capa 1)
  2. 5 ejes de medida (Capa 2): KDA, CS/min, DMG/min, % vivo, Visión/min
  3. Ponderación final por rol (Capa 3)
  4. match_tumor → prior_tumor (media histórica) → team_tumor (media equipo)
  5. predict_team_outcome basado en team_tumor

Garantías:
  - Todos los scores devueltos son enteros 0-100 sin negativos
  - team_tumor está siempre en [min(prior_team), max(prior_team)]
  - Si todos los priors son X, team_tumor = X exactamente
"""

# ---------------------------------------------------------------------------
# Capa 2 + 3 — Tablas
# ---------------------------------------------------------------------------

# Multiplicador del threshold base por rango. Más alto = se exige más.
TIER_MULTIPLIER = {
    "IRON":        0.65,
    "BRONZE":      0.75,
    "SILVER":      0.85,
    "GOLD":        1.00,
    "PLATINUM":    1.10,
    "EMERALD":     1.18,
    "DIAMOND":     1.27,
    "MASTER":      1.38,
    "GRANDMASTER": 1.48,
    "CHALLENGER":  1.55,
    "UNRANKED":    0.95,  # asume algo ligeramente por debajo de gold
    "":            0.95,
}

# KDA threshold por rango (no por rol). KDA = (K+A)/max(1,D)
KDA_THRESHOLD = {
    "IRON":        1.6,
    "BRONZE":      1.8,
    "SILVER":      2.0,
    "GOLD":        2.2,
    "PLATINUM":    2.4,
    "EMERALD":     2.6,
    "DIAMOND":     2.8,
    "MASTER":      3.0,
    "GRANDMASTER": 3.2,
    "CHALLENGER":  3.5,
    "UNRANKED":    2.1,
    "":            2.1,
}

# Thresholds base @ Gold por rol. Se multiplican por TIER_MULTIPLIER[tier].
ROLE_BASE = {
    "TOP":     {"cs_per_min": 6.0, "dmg_per_min": 550, "vision_per_min": 0.7},
    "JUNGLE":  {"cs_per_min": 4.5, "dmg_per_min": 600, "vision_per_min": 1.4},
    "MIDDLE":  {"cs_per_min": 6.5, "dmg_per_min": 700, "vision_per_min": 0.8},
    "BOTTOM":  {"cs_per_min": 7.5, "dmg_per_min": 750, "vision_per_min": 0.6},
    "UTILITY": {"cs_per_min": 1.5, "dmg_per_min": 280, "vision_per_min": 2.0},
    "DEFAULT": {"cs_per_min": 5.5, "dmg_per_min": 600, "vision_per_min": 0.9},
}

# Pesos por rol — suman 100. Define qué es "importante" en cada posición.
ROLE_WEIGHTS = {
    "TOP":     {"kda": 25, "cs": 25, "dmg": 20, "dead": 15, "vision": 15},
    "JUNGLE":  {"kda": 25, "cs": 15, "dmg": 20, "dead": 15, "vision": 25},
    "MIDDLE":  {"kda": 25, "cs": 25, "dmg": 25, "dead": 15, "vision": 10},
    "BOTTOM":  {"kda": 25, "cs": 30, "dmg": 25, "dead": 15, "vision":  5},
    "UTILITY": {"kda": 30, "cs":  5, "dmg": 15, "dead": 15, "vision": 35},
    "DEFAULT": {"kda": 25, "cs": 25, "dmg": 20, "dead": 15, "vision": 15},
}


def _normalize_tier(tier):
    if not tier:
        return ""
    return str(tier).upper().strip()


def _normalize_role(role):
    if not role:
        return "DEFAULT"
    r = str(role).upper().strip()
    return r if r in ROLE_BASE else "DEFAULT"


# ---------------------------------------------------------------------------
# Función central — bad_score
# ---------------------------------------------------------------------------

def bad_score(value, threshold):
    """
    Devuelve 0-100 donde:
      - value >= threshold ⇒ 0 (excelente, expectativa cumplida)
      - value == 0         ⇒ 100 (catastrófico)
      - lineal en medio
    """
    if threshold <= 0:
        return 0.0
    if value >= threshold:
        return 0.0
    return max(0.0, min(100.0, (1.0 - value / threshold) * 100.0))


# ---------------------------------------------------------------------------
# Capa 2 — match_tumor: 5 ejes para una sola partida
# ---------------------------------------------------------------------------

def compute_match_tumor_from_stats(stats, game_duration, tier="", role=""):
    """
    Variante que acepta el dict precomputado con campos kda, cs, damage,
    vision_score, time_dead. Útil para callers que ya hicieron las cuentas
    y no tienen el participant raw a mano.
    """
    if game_duration is None or game_duration < 1:
        return 0, {}

    tier = _normalize_tier(tier)
    role = _normalize_role(role)
    mins = max(game_duration / 60.0, 1.0)

    kda_value = stats.get("kda", 0) or 0
    cs = stats.get("cs", 0) or 0
    dmg = stats.get("damage", 0) or 0
    vs = stats.get("vision_score", 0) or 0
    dead = stats.get("time_dead", 0) or 0

    tier_mult = TIER_MULTIPLIER.get(tier, TIER_MULTIPLIER[""])
    kda_thr = KDA_THRESHOLD.get(tier, KDA_THRESHOLD[""])
    kda_raw = bad_score(kda_value, kda_thr)

    cs_pm_value = cs / mins
    cs_pm_thr = ROLE_BASE[role]["cs_per_min"] * tier_mult
    cs_pm_raw = bad_score(cs_pm_value, cs_pm_thr)

    dmg_pm_value = dmg / mins
    dmg_pm_thr = ROLE_BASE[role]["dmg_per_min"] * tier_mult
    dmg_pm_raw = bad_score(dmg_pm_value, dmg_pm_thr)

    alive_pct = max(0.0, 1.0 - (dead / max(game_duration, 1)))
    dead_raw = bad_score(alive_pct, 0.85)

    vs_pm_value = vs / mins
    vs_pm_thr = ROLE_BASE[role]["vision_per_min"] * tier_mult
    vs_pm_raw = bad_score(vs_pm_value, vs_pm_thr)

    w = ROLE_WEIGHTS[role]
    total_w = w["kda"] + w["cs"] + w["dmg"] + w["dead"] + w["vision"]
    weighted = (
        kda_raw   * w["kda"] +
        cs_pm_raw * w["cs"] +
        dmg_pm_raw * w["dmg"] +
        dead_raw  * w["dead"] +
        vs_pm_raw * w["vision"]
    ) / total_w
    return max(0, min(100, int(round(weighted))))


def compute_match_tumor(participant, game_duration, tier="", role=""):
    """
    Calcula el tumor 0-100 de un jugador en una partida concreta.

    Args:
      participant: dict con kills, deaths, assists, totalMinionsKilled,
                   neutralMinionsKilled, totalDamageDealtToChampions,
                   visionScore, totalTimeSpentDead.
      game_duration: segundos.
      tier: tier del jugador (cualquier capitalización, "" si UNRANKED).
      role: teamPosition del jugador.

    Returns:
      (score: int 0-100, components: dict con desglose por eje)
    """
    if game_duration is None or game_duration < 1:
        return 0, {}

    tier = _normalize_tier(tier)
    role = _normalize_role(role)

    mins = max(game_duration / 60.0, 1.0)

    # Datos crudos
    kills = participant.get("kills", 0) or 0
    deaths = participant.get("deaths", 0) or 0
    assists = participant.get("assists", 0) or 0
    cs = (participant.get("totalMinionsKilled", 0) or 0) + (participant.get("neutralMinionsKilled", 0) or 0)
    dmg = participant.get("totalDamageDealtToChampions", 0) or 0
    vs = participant.get("visionScore", 0) or 0
    dead = participant.get("totalTimeSpentDead", 0) or 0

    # ========================================================================
    # Eje 1 · KDA
    # ========================================================================
    kda_value = (kills + assists) / max(1, deaths)
    kda_thr = KDA_THRESHOLD.get(tier, KDA_THRESHOLD[""])
    kda_raw = bad_score(kda_value, kda_thr)

    # ========================================================================
    # Eje 2 · CS/min (rol + tier mult)
    # ========================================================================
    tier_mult = TIER_MULTIPLIER.get(tier, TIER_MULTIPLIER[""])
    cs_pm_value = cs / mins
    cs_pm_thr = ROLE_BASE[role]["cs_per_min"] * tier_mult
    cs_pm_raw = bad_score(cs_pm_value, cs_pm_thr)

    # ========================================================================
    # Eje 3 · DMG/min (rol + tier mult)
    # ========================================================================
    dmg_pm_value = dmg / mins
    dmg_pm_thr = ROLE_BASE[role]["dmg_per_min"] * tier_mult
    dmg_pm_raw = bad_score(dmg_pm_value, dmg_pm_thr)

    # ========================================================================
    # Eje 4 · Tiempo vivo (sin rol, sin tier — morir es morir)
    # ========================================================================
    alive_pct = max(0.0, 1.0 - (dead / max(game_duration, 1)))
    dead_raw = bad_score(alive_pct, 0.85)

    # ========================================================================
    # Eje 5 · Visión/min (rol + tier mult)
    # ========================================================================
    vs_pm_value = vs / mins
    vs_pm_thr = ROLE_BASE[role]["vision_per_min"] * tier_mult
    vs_pm_raw = bad_score(vs_pm_value, vs_pm_thr)

    # ========================================================================
    # Capa 3 — Ponderación final por rol
    # ========================================================================
    w = ROLE_WEIGHTS[role]
    total_w = w["kda"] + w["cs"] + w["dmg"] + w["dead"] + w["vision"]
    weighted = (
        kda_raw   * w["kda"] +
        cs_pm_raw * w["cs"] +
        dmg_pm_raw * w["dmg"] +
        dead_raw  * w["dead"] +
        vs_pm_raw * w["vision"]
    ) / total_w

    final = max(0, min(100, int(round(weighted))))

    components = {
        "kda": {
            "value": round(kda_value, 2),
            "threshold": round(kda_thr, 2),
            "raw_score": round(kda_raw, 1),
            "weight": w["kda"],
            "contribution": round(kda_raw * w["kda"] / total_w, 2),
        },
        "cs_per_min": {
            "value": round(cs_pm_value, 1),
            "threshold": round(cs_pm_thr, 1),
            "raw_score": round(cs_pm_raw, 1),
            "weight": w["cs"],
            "contribution": round(cs_pm_raw * w["cs"] / total_w, 2),
        },
        "dmg_per_min": {
            "value": round(dmg_pm_value, 0),
            "threshold": round(dmg_pm_thr, 0),
            "raw_score": round(dmg_pm_raw, 1),
            "weight": w["dmg"],
            "contribution": round(dmg_pm_raw * w["dmg"] / total_w, 2),
        },
        "time_dead": {
            "value": round(alive_pct * 100, 1),  # como % vivo
            "threshold": 85.0,
            "raw_score": round(dead_raw, 1),
            "weight": w["dead"],
            "contribution": round(dead_raw * w["dead"] / total_w, 2),
        },
        "vision": {
            "value": round(vs_pm_value, 2),
            "threshold": round(vs_pm_thr, 2),
            "raw_score": round(vs_pm_raw, 1),
            "weight": w["vision"],
            "contribution": round(vs_pm_raw * w["vision"] / total_w, 2),
        },
    }

    return final, components


# ---------------------------------------------------------------------------
# Capa 4 — prior_tumor: media histórica de los últimos N
# ---------------------------------------------------------------------------

def compute_prior_tumor(match_scores):
    """
    Args:
      match_scores: lista de match_tumor (int 0-100) ya filtrados (sin remakes).

    Returns:
      int 0-100 o None si la muestra es < 3
    """
    valid = [s for s in match_scores if s is not None]
    if len(valid) < 3:
        return None
    return max(0, min(100, int(round(sum(valid) / len(valid)))))


# ---------------------------------------------------------------------------
# Capa 4 — team_tumor: media de los priors del equipo
# ---------------------------------------------------------------------------

def compute_team_tumor(prior_scores):
    """
    Devuelve la MEDIANA de los priors válidos del equipo.

    Por qué mediana y no media:
      - Robusta a outliers: un jugador con tumor 95 no dispara el equipo entero
      - Neutra al modo streamer: los jugadores sin prior (None) se excluyen
        directamente, no se rellenan con la media (que sí afectaría)
      - 5 jugadores → siempre hay una mediana bien definida (el de la posición 3
        tras ordenar). Si hay pares (4 con prior), promedia los 2 del medio.

    Returns: int 0-100. Si no hay priors válidos devuelve 50.
    """
    valid = sorted(s for s in prior_scores if s is not None)
    if not valid:
        return 50
    n = len(valid)
    if n % 2 == 1:
        median = valid[n // 2]
    else:
        median = (valid[n // 2 - 1] + valid[n // 2]) / 2
    return max(0, min(100, int(round(median))))


# ---------------------------------------------------------------------------
# Capa 5 — predict_team_outcome
# ---------------------------------------------------------------------------

# Modificadores de tilt/hotstreak.
TILT_PENALTY = 10
HOTSTREAK_BONUS = 8


def apply_streak_modifier(prior, is_tilted=False, is_hotstreak=False):
    """Devuelve el prior ajustado según el estado del jugador."""
    if prior is None:
        return None
    if is_tilted:
        prior += TILT_PENALTY
    if is_hotstreak:
        prior -= HOTSTREAK_BONUS
    return max(0, min(100, prior))


def predict_team_outcome(players, tie_threshold=4, confidence_scale=6):
    """
    Calcula la predicción de la partida.

    Args:
      players: lista de dicts con al menos:
        - team_id (100|200)
        - prior_tumor (int 0-100, o None si no calculable)
        - role (opcional, para el breakdown)
        - puuid, name (opcional, para el breakdown)
        - is_tilted, is_hotstreak (opcionales)

    Returns:
      dict con blue_team_tumor, red_team_tumor, winner, confidence, diff,
      blue_breakdown, red_breakdown.
    """
    def player_row(p):
        prior = p.get("prior_tumor")
        adjusted = apply_streak_modifier(
            prior,
            is_tilted=bool(p.get("is_tilted")),
            is_hotstreak=bool(p.get("is_hotstreak")),
        )
        return {
            "puuid": p.get("puuid"),
            "name": p.get("name"),
            "role": _normalize_role(p.get("role")),
            "prior_tumor": prior,
            "adjusted_tumor": adjusted,
            "is_tilted": bool(p.get("is_tilted")),
            "is_hotstreak": bool(p.get("is_hotstreak")),
        }

    blue = [player_row(p) for p in players if p.get("team_id") == 100]
    red  = [player_row(p) for p in players if p.get("team_id") == 200]

    blue_priors = [r["adjusted_tumor"] for r in blue]
    red_priors  = [r["adjusted_tumor"] for r in red]

    # Streamers (prior=None) se EXCLUYEN del cálculo directamente. No se
    # rellenan. compute_team_tumor hace mediana de los válidos, así que
    # contribuyen 0 al resultado del equipo.
    blue_team_tumor = compute_team_tumor(blue_priors)
    red_team_tumor  = compute_team_tumor(red_priors)

    for r in blue:
        r["effective_tumor"] = r["adjusted_tumor"]
        r["contribution"] = r["adjusted_tumor"]
    for r in red:
        r["effective_tumor"] = r["adjusted_tumor"]
        r["contribution"] = r["adjusted_tumor"]

    diff = red_team_tumor - blue_team_tumor
    abs_diff = abs(diff)

    # Tiebreaker: si las medianas son iguales, usar suma total de priors.
    # Solo se declara "tie" (no hay predicción, no cuenta para accuracy) si
    # las medianas Y las sumas son EXACTAMENTE iguales.
    blue_sum = sum(p for p in blue_priors if p is not None)
    red_sum  = sum(p for p in red_priors  if p is not None)
    sum_diff = red_sum - blue_sum

    if abs_diff >= tie_threshold:
        winner = "blue" if blue_team_tumor < red_team_tumor else "red"
    elif abs_diff > 0 or abs(sum_diff) > 0:
        # Medianas cerca o iguales → desempata por suma (menos tumor total gana)
        if abs(sum_diff) > 0:
            winner = "blue" if blue_sum < red_sum else "red"
        else:
            winner = "blue" if blue_team_tumor < red_team_tumor else "red"
    else:
        # Absolutamente idénticos en mediana Y suma: no hay prediccion
        winner = "tie"

    confidence = min(99, abs_diff * confidence_scale)

    return {
        "blue_team_tumor": blue_team_tumor,
        "red_team_tumor":  red_team_tumor,
        "blue_team_sum":   blue_sum,
        "red_team_sum":    red_sum,
        "winner":          winner,
        "confidence":      confidence,
        "diff":            diff,
        "blue_breakdown":  blue,
        "red_breakdown":   red,
    }
