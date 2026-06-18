"""Daily / Weekly missions (#49).

Diseño minimalista: el catálogo es estático en este módulo, no en DB. Para
cada user y período (día UTC para daily, ISO-week para weekly), elegimos
un subset de N misiones de forma determinista vía hash(user_id, period,
kind) — así el mismo user ve las mismas misiones durante todo el período
sin necesidad de persistir la elección.

PROGRESS se computa SIEMPRE on-the-fly leyendo de las tablas existentes
(bets, daily_rewards, predictions). NO mantenemos contadores propios.
Cuando progress >= target, la UI muestra "Reclamar" → POST /missions/claim
→ se inserta una fila en `user_mission_claims` y se acredita el reward.

Beneficios:
  - 0 hooks en otros flujos. Si añades una nueva mission solo tocas
    MISSIONS abajo y la computación on-demand.
  - 1 sola tabla nueva, sin migraciones futuras al ajustar misiones.
  - El catálogo se puede tunear (texto, reward, target) sin perder claims.
"""

import time
import datetime as _dt
import hashlib


# Catálogo de misiones disponibles. Cada `key` debe ser estable porque
# los claims antiguos se referencian por key (si renombras una, los users
# con claim previo verán la nueva como reclamable de nuevo).
#
# `kind`: 'tumor' (la mission depende de partidas/tumor) o 'meta' (no
# requiere jugar partidas — UI/social/economy actions). Solo para que la
# UI agrupe visualmente o lo muestre como tag.
MISSIONS = {
    'daily': [
        # NOTA: reward bajo (5 TC) porque ya pagas el daily reward principal
        # al reclamar. La mission es más onboarding/discovery que economy.
        {'key': 'claim_daily',       'kind': 'meta',  'name': '🎁 Reclama tu daily',         'desc': 'Pulsa el botón 🎁 hoy',                 'target': 1, 'reward': 5},
        {'key': 'create_bet',        'kind': 'meta',  'name': '🎲 Crea 1 apuesta',           'desc': 'Lanza una bet P2P (cualquier monto)',   'target': 1, 'reward': 40},
        {'key': 'win_1_bet',         'kind': 'meta',  'name': '💰 Gana 1 apuesta',           'desc': 'Acierta 1 bet P2P hoy',                 'target': 1, 'reward': 80},
        {'key': 'predict_1_correct', 'kind': 'tumor', 'name': '🔮 Predice 1 partida bien',    'desc': 'Live prediction acertada hoy',          'target': 1, 'reward': 70},
        {'key': 'check_3_live',      'kind': 'tumor', 'name': '🟢 Comprueba 3 livs',          'desc': 'Mira el live game de 3 partidas',       'target': 3, 'reward': 50},
        # NOTA: 'tumor_below_40' eliminada del pool — no hay fuente de datos
        # implementada (helper devuelve 0). Volverla cuando hagamos join con
        # predictions.viewer_match_history.
    ],
    'weekly': [
        {'key': 'win_5_bets_week',   'kind': 'meta',  'name': '🏆 5 apuestas ganadas',       'desc': 'P2P, esta semana',                       'target': 5,  'reward': 250},
        {'key': 'predict_streak_3',  'kind': 'tumor', 'name': '🔥 Racha de 3 aciertos',      'desc': 'En tus predicciones live',               'target': 3,  'reward': 200},
        {'key': 'login_5_days',      'kind': 'meta',  'name': '📅 5 días conectado',         'desc': 'Daily claim en 5 días distintos',        'target': 5,  'reward': 300},
        {'key': 'predict_10_total',  'kind': 'tumor', 'name': '🎯 10 predicciones live',     'desc': 'Cualquier resultado, esta semana',       'target': 10, 'reward': 200},
    ],
}

# Cuántas misiones activas por período. Mantén pequeño para que cada una
# sea valiosa y no abrume al user.
ACTIVE_DAILY = 3
ACTIVE_WEEKLY = 2


def daily_period(tz_offset_minutes=0):
    """Período para una mission diaria: fecha LOCAL del user (YYYY-MM-DD)."""
    now = _dt.datetime.fromtimestamp(
        time.time() + int(tz_offset_minutes) * 60,
        tz=_dt.timezone.utc,
    )
    return now.date().isoformat()


def weekly_period(tz_offset_minutes=0):
    """Período para una mission semanal: ISO-week (YYYY-Www) en LOCAL del user.
    ISO weeks empiezan el lunes y son universalmente reconocidas."""
    now = _dt.datetime.fromtimestamp(
        time.time() + int(tz_offset_minutes) * 60,
        tz=_dt.timezone.utc,
    )
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def _pick_n(user_id, period, kind, pool, n):
    """Selección determinista: hash(user_id||period||kind) → seed → shuffle."""
    seed_str = f"{user_id}|{period}|{kind}"
    h = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
    indices = list(range(len(pool)))
    # Fisher-Yates con el hash como fuente de entropía.
    for i in range(len(indices) - 1, 0, -1):
        j = h % (i + 1)
        h //= (i + 1) or 1
        indices[i], indices[j] = indices[j], indices[i]
    return [pool[i] for i in indices[:n]]


def active_missions(user_id, tz_offset_minutes=0):
    """Devuelve las misiones activas (sin progreso) para este user en
    el período actual."""
    dp = daily_period(tz_offset_minutes)
    wp = weekly_period(tz_offset_minutes)
    daily = _pick_n(user_id, dp, 'daily', MISSIONS['daily'], ACTIVE_DAILY)
    weekly = _pick_n(user_id, wp, 'weekly', MISSIONS['weekly'], ACTIVE_WEEKLY)
    return {
        'daily':  {'period': dp, 'missions': daily},
        'weekly': {'period': wp, 'missions': weekly},
    }


def _period_start_end_utc(period_str, kind):
    """Convierte 'YYYY-MM-DD' (daily) o 'YYYY-Www' (weekly) en [start, end)
    epoch seconds UTC. Usado por las queries de progress para filtrar tx."""
    if kind == 'daily':
        d = _dt.datetime.strptime(period_str, '%Y-%m-%d').replace(tzinfo=_dt.timezone.utc)
        return d.timestamp(), (d + _dt.timedelta(days=1)).timestamp()
    else:
        # ISO week: 'YYYY-Www'.
        y, w = period_str.split('-W')
        # %G %V %u → year/week/day-of-week (1=Mon).
        start = _dt.datetime.strptime(f"{y} {int(w)} 1", '%G %V %u').replace(tzinfo=_dt.timezone.utc)
        return start.timestamp(), (start + _dt.timedelta(days=7)).timestamp()


def compute_progress(user_id, mission_key, kind, period, conn_helper, pred_db_helper=None):
    """Computa el progreso actual del user para esta mission.

    `conn_helper` es una función que ejecuta un SELECT en users_db
    (firma: (sql, params) -> cursor). Pasamos esto como callback para
    no acoplar al módulo users_db (evita import circular).
    `pred_db_helper` (opcional): mismo patrón pero para predictions.db.
    Si la mission necesita predictions y no se pasa, el progress es 0.

    Devuelve int en [0, target]; la UI clampa visualmente.
    """
    start, end = _period_start_end_utc(period, kind)

    # -- META missions (currency_transactions + bets + daily_rewards) --
    if mission_key == 'claim_daily':
        # Daily claim dentro del período. Una tx con reason='daily reward'.
        cur = conn_helper(
            "SELECT COUNT(*) FROM currency_transactions WHERE user_id=? AND reason=? AND created_at>=? AND created_at<?",
            (user_id, 'daily reward', start, end),
        )
        return int((cur.fetchone() or [0])[0] or 0)

    if mission_key == 'create_bet':
        cur = conn_helper(
            "SELECT COUNT(*) FROM bets WHERE creator_user_id=? AND created_at>=? AND created_at<?",
            (user_id, start, end),
        )
        return int((cur.fetchone() or [0])[0] or 0)

    if mission_key == 'win_1_bet':
        cur = conn_helper(
            """SELECT COUNT(*) FROM bets
               WHERE status='resolved' AND winner_side IS NOT NULL
               AND resolved_at>=? AND resolved_at<?
               AND ((creator_user_id=? AND creator_side=winner_side)
                    OR (taker_user_id=? AND creator_side<>winner_side))""",
            (start, end, user_id, user_id),
        )
        return int((cur.fetchone() or [0])[0] or 0)

    if mission_key == 'win_5_bets_week':
        cur = conn_helper(
            """SELECT COUNT(*) FROM bets
               WHERE status='resolved' AND winner_side IS NOT NULL
               AND resolved_at>=? AND resolved_at<?
               AND ((creator_user_id=? AND creator_side=winner_side)
                    OR (taker_user_id=? AND creator_side<>winner_side))""",
            (start, end, user_id, user_id),
        )
        return int((cur.fetchone() or [0])[0] or 0)

    if mission_key == 'login_5_days':
        # Días distintos con daily claim en la semana.
        cur = conn_helper(
            "SELECT created_at FROM currency_transactions WHERE user_id=? AND reason=? AND created_at>=? AND created_at<?",
            (user_id, 'daily reward', start, end),
        )
        ts_list = [r[0] for r in cur.fetchall() if r and r[0]]
        days = set()
        for ts in ts_list:
            days.add(_dt.datetime.fromtimestamp(float(ts), tz=_dt.timezone.utc).date())
        return len(days)

    # -- TUMOR missions (predictions.db) --
    # Necesitan el viewer_puuid del user para filtrar; ese contexto lo
    # añade el caller via pred_db_helper.
    if pred_db_helper is None:
        return 0

    if mission_key == 'predict_1_correct':
        return pred_db_helper('correct_count_in_period', start, end)
    if mission_key == 'check_3_live':
        return pred_db_helper('predictions_count_in_period', start, end)
    if mission_key == 'tumor_below_40':
        return pred_db_helper('low_tumor_matches_in_period', start, end, 40)
    if mission_key == 'predict_streak_3':
        return pred_db_helper('max_streak_in_period', start, end)
    if mission_key == 'predict_10_total':
        return pred_db_helper('predictions_count_in_period', start, end)

    return 0
