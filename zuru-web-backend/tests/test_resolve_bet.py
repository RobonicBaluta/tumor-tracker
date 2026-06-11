"""Tests para resolve_bet (match bets P2P y house).

Cubre los flujos de pago:
- P2P clásico: winner toma stake×2
- House: payout = stake × payout_multiplier si gana, 0 si pierde
- Refund window (anti-insider): bet creada <REFUND_WINDOW_SECONDS antes de
  game_end_ts → refund a ambos sin importar el resultado

Run: pytest tests/test_resolve_bet.py -v
"""
import os
import sys
import time
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """SQLite local en tmp_path por test."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import users_db
    importlib.reload(users_db)
    return users_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_user(udb, discord_id, username, extra_currency=0):
    u = udb.upsert_user_from_discord(discord_id, username, None)
    if extra_currency:
        udb.add_currency(u["id"], extra_currency, "test seed")
    return u


def _create_matched_match_bet(udb, side="blue", amount=50, is_house=False, payout_multiplier=2.0):
    """Crea 2 users + match bet matched (P2P si is_house=False, sino auto-matched)."""
    c = _seed_user(udb, "c-bet", "creator", 500)
    bet = udb.create_bet(
        c["id"], "EUW1_777", 777, side, amount,
        is_house=is_house, payout_multiplier=payout_multiplier,
    )
    if is_house:
        # House: ya pasa a 'matched' al crear
        assert bet["status"] == "matched"
        return {"bet_id": bet["id"], "c_id": c["id"], "t_id": None,
                "c_pre": udb.get_user_by_id(c["id"])["currency"] + amount,  # restablecemos por escrow
                "stake": amount}
    t = _seed_user(udb, "t-bet", "taker", 500)
    err = udb.accept_bet(t["id"], bet["share_code"])
    assert isinstance(err, dict), f"accept_bet falló: {err}"
    return {
        "bet_id": bet["id"], "c_id": c["id"], "t_id": t["id"],
        "stake": amount,
    }


def _backdate_bet_created(udb, bet_id, seconds_before_now):
    udb._exec("UPDATE bets SET created_at=? WHERE id=?", (time.time() - seconds_before_now, bet_id))


# ---------------------------------------------------------------------------
# P2P match bets
# ---------------------------------------------------------------------------

class TestP2PMatchBet:

    def test_creator_wins_gets_2x_stake(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_match_bet(udb, side="blue", amount=50)
        c_before = udb.get_user_by_id(ctx["c_id"])["currency"]
        # creator dijo "blue", actual=blue → creator gana
        result = udb.resolve_bet(ctx["bet_id"], "blue")
        assert result["status"] == "resolved"
        # winner cobra al menos 2×stake (achievements pueden añadir extra)
        c_after = udb.get_user_by_id(ctx["c_id"])["currency"]
        assert c_after - c_before >= 2 * ctx["stake"]

    def test_taker_wins_gets_2x_stake(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_match_bet(udb, side="blue", amount=50)
        t_before = udb.get_user_by_id(ctx["t_id"])["currency"]
        # creator dijo "blue", actual=red → taker gana
        result = udb.resolve_bet(ctx["bet_id"], "red")
        assert result["status"] == "resolved"
        t_after = udb.get_user_by_id(ctx["t_id"])["currency"]
        assert t_after - t_before >= 2 * ctx["stake"]

    def test_resolve_marks_winner_side(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_match_bet(udb)
        result = udb.resolve_bet(ctx["bet_id"], "red")
        assert result["winner_side"] == "red"

    def test_resolve_is_idempotent(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_match_bet(udb)
        udb.resolve_bet(ctx["bet_id"], "blue")
        # Segunda llamada no-op
        result = udb.resolve_bet(ctx["bet_id"], "blue")
        assert result is None


# ---------------------------------------------------------------------------
# House bets (vs sistema)
# ---------------------------------------------------------------------------

class TestHouseMatchBet:

    def test_creator_wins_gets_stake_times_multiplier(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_match_bet(udb, side="blue", amount=100,
                                         is_house=True, payout_multiplier=2.5)
        c_before = udb.get_user_by_id(ctx["c_id"])["currency"]
        result = udb.resolve_bet(ctx["bet_id"], "blue")
        assert result["status"] == "resolved"
        c_after = udb.get_user_by_id(ctx["c_id"])["currency"]
        # 100 × 2.5 = 250 al ganar (achievements pueden añadir extra)
        assert c_after - c_before >= 250

    def test_creator_loses_no_payout(self, isolated_db):
        """Al perder en house, NO debe haber pago del payout. evaluate_achievements
        puede añadir TC por unlocks colaterales, pero no debería superar el stake."""
        udb = isolated_db
        ctx = _create_matched_match_bet(udb, side="blue", amount=100,
                                         is_house=True, payout_multiplier=2.5)
        c_before = udb.get_user_by_id(ctx["c_id"])["currency"]
        result = udb.resolve_bet(ctx["bet_id"], "red")
        assert result["status"] == "resolved"
        c_after = udb.get_user_by_id(ctx["c_id"])["currency"]
        # Sin payout: el delta debe ser < el payout esperado al ganar (250).
        # Achievements pueden añadir hasta ~100 TC.
        assert c_after - c_before < 250

    def test_house_uses_payout_multiplier_in_message(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_match_bet(udb, side="blue", amount=100,
                                         is_house=True, payout_multiplier=3.5)
        c_before = udb.get_user_by_id(ctx["c_id"])["currency"]
        udb.resolve_bet(ctx["bet_id"], "blue")
        c_after = udb.get_user_by_id(ctx["c_id"])["currency"]
        # 100 × 3.5 = 350
        assert c_after - c_before >= 350


# ---------------------------------------------------------------------------
# Refund window
# ---------------------------------------------------------------------------

class TestRefundWindow:

    def test_no_game_end_ts_resolves_normally(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_match_bet(udb)
        c_before = udb.get_user_by_id(ctx["c_id"])["currency"]
        udb.resolve_bet(ctx["bet_id"], "blue")
        c_after = udb.get_user_by_id(ctx["c_id"])["currency"]
        assert c_after - c_before >= 2 * ctx["stake"]

    def test_bet_outside_refund_window_resolves(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_match_bet(udb)
        _backdate_bet_created(udb, ctx["bet_id"], 600)  # 10 min antes
        c_before = udb.get_user_by_id(ctx["c_id"])["currency"]
        result = udb.resolve_bet(ctx["bet_id"], "blue", game_end_ts=time.time())
        assert result["status"] == "resolved"
        c_after = udb.get_user_by_id(ctx["c_id"])["currency"]
        assert c_after - c_before >= 2 * ctx["stake"]

    def test_bet_inside_refund_window_refunds_both(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_match_bet(udb)
        _backdate_bet_created(udb, ctx["bet_id"], 10)  # 10s antes del fin → refund
        c_pre_resolve = udb.get_user_by_id(ctx["c_id"])["currency"]
        t_pre_resolve = udb.get_user_by_id(ctx["t_id"])["currency"]
        result = udb.resolve_bet(ctx["bet_id"], "blue", game_end_ts=time.time())
        assert result["status"] == "refunded"
        # Ambos recuperan su stake (escrow)
        assert udb.get_user_by_id(ctx["c_id"])["currency"] - c_pre_resolve == ctx["stake"]
        assert udb.get_user_by_id(ctx["t_id"])["currency"] - t_pre_resolve == ctx["stake"]

    def test_house_bet_also_refunds_within_window(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_match_bet(udb, is_house=True, payout_multiplier=2.5)
        _backdate_bet_created(udb, ctx["bet_id"], 10)
        c_pre = udb.get_user_by_id(ctx["c_id"])["currency"]
        result = udb.resolve_bet(ctx["bet_id"], "blue", game_end_ts=time.time())
        assert result["status"] == "refunded"
        # creator recupera el stake
        assert udb.get_user_by_id(ctx["c_id"])["currency"] - c_pre == ctx["stake"]

    def test_refund_window_boundary_resolves(self, isolated_db):
        """Justo en REFUND_WINDOW_SECONDS+5 antes del fin: resuelve normalmente."""
        udb = isolated_db
        ctx = _create_matched_match_bet(udb)
        _backdate_bet_created(udb, ctx["bet_id"], udb.REFUND_WINDOW_SECONDS + 5)
        result = udb.resolve_bet(ctx["bet_id"], "blue", game_end_ts=time.time())
        assert result["status"] == "resolved"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_unmatched_bet_does_not_resolve(self, isolated_db):
        """Una bet en status='open' (sin taker) no debe resolverse — sólo cancel o matched→resolved."""
        udb = isolated_db
        c = _seed_user(udb, "c-only", "creator", 500)
        bet = udb.create_bet(c["id"], "EUW1_888", 888, "blue", 50)
        assert bet["status"] == "open"
        result = udb.resolve_bet(bet["id"], "blue")
        assert result is None

    def test_winner_side_field_persists(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_match_bet(udb)
        udb.resolve_bet(ctx["bet_id"], "red")
        bet = udb.get_bet_by_id(ctx["bet_id"])
        assert bet["winner_side"] == "red"
