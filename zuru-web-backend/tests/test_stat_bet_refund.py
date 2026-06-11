"""Tests para el refund window de stat-bets.

Verifica que `resolve_stat_bet(bet_id, value, game_end_ts=X)` refunda en
lugar de pagar cuando la bet se creó dentro de los últimos
REFUND_WINDOW_SECONDS antes del fin de partida (anti-insider). Sin esto,
un user podía apostar "tumor_score < 60" a minuto 27-29 con casi total
certeza.

Run: pytest tests/test_stat_bet_refund.py -v
"""
import os
import sys
import sqlite3
import time
import pytest

# Forzar SQLite local en memoria para los tests (no tocar prod)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Crea una users.db aislada por test, no toca la real."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # Reload users_db con el nuevo DATA_DIR
    import importlib
    import users_db
    importlib.reload(users_db)
    return users_db


def _create_matched_stat_bet(udb, created_at_offset_s_before_now=600):
    """Crea 2 users + stat bet matched. Devuelve dict con balances pre-escrow."""
    c = udb.upsert_user_from_discord("creator123", "creator", None)
    t = udb.upsert_user_from_discord("taker456", "taker", None)
    udb.add_currency(c["id"], 500, "test seed")
    udb.add_currency(t["id"], 500, "test seed")
    # Balance ANTES de crear la bet (incluye welcome bonus + seed)
    c_pre = udb.get_user_by_id(c["id"])["currency"]
    t_pre = udb.get_user_by_id(t["id"])["currency"]
    bet = udb.create_bet(
        c["id"], "EUW1_999", 999, "over", 50,
        bet_kind="stat",
        target_puuid="puuid_target", target_name="Target#EUW",
        stat_type="kda", threshold=2.0,
    )
    err = udb.accept_bet(t["id"], bet["share_code"])
    assert isinstance(err, dict), f"accept_bet falló: {err}"
    # Backdate created_at del bet para el test
    new_ts = time.time() - created_at_offset_s_before_now
    udb._exec("UPDATE bets SET created_at=? WHERE id=?", (new_ts, bet["id"]))
    return {
        "bet_id": bet["id"],
        "c_id": c["id"], "t_id": t["id"],
        # Balance ANTES de escrow. Tras escrow ambos tienen pre - 50.
        "c_pre": c_pre, "t_pre": t_pre,
        "stake": 50,
    }


class TestStatBetRefundWindow:

    def test_resolves_normally_without_game_end_ts(self, isolated_db):
        """Sin game_end_ts pasado, resuelve igual que antes (sin refund window)."""
        udb = isolated_db
        ctx = _create_matched_stat_bet(udb, created_at_offset_s_before_now=3600)
        c_before = udb.get_user_by_id(ctx["c_id"])["currency"]
        # creator dijo "over 2.0", actual=5.0 → creator gana, recibe 2×stake
        result = udb.resolve_stat_bet(ctx["bet_id"], 5.0)
        assert result is not None
        assert result["status"] == "resolved"
        # Winner cobra 2×stake (achievements pueden añadir; delta debe ser ≥)
        c_after = udb.get_user_by_id(ctx["c_id"])["currency"]
        assert c_after - c_before >= 2 * ctx["stake"]

    def test_resolves_normally_when_bet_outside_refund_window(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_stat_bet(udb, created_at_offset_s_before_now=600)
        c_before = udb.get_user_by_id(ctx["c_id"])["currency"]
        result = udb.resolve_stat_bet(ctx["bet_id"], 5.0, game_end_ts=time.time())
        assert result["status"] == "resolved"
        # creator ganó al menos 2×stake
        assert udb.get_user_by_id(ctx["c_id"])["currency"] - c_before >= 2 * ctx["stake"]

    def test_refunds_when_bet_inside_refund_window(self, isolated_db):
        """Insider gate: bet creada <60s antes del fin → refund AMBOS."""
        udb = isolated_db
        ctx = _create_matched_stat_bet(udb, created_at_offset_s_before_now=10)
        result = udb.resolve_stat_bet(ctx["bet_id"], 5.0, game_end_ts=time.time())
        assert result["status"] == "refunded"
        # Ambos vuelven a su balance pre-bet
        assert udb.get_user_by_id(ctx["c_id"])["currency"] == ctx["c_pre"]
        assert udb.get_user_by_id(ctx["t_id"])["currency"] == ctx["t_pre"]

    def test_refund_does_not_set_winner_side(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_stat_bet(udb, created_at_offset_s_before_now=20)
        result = udb.resolve_stat_bet(ctx["bet_id"], 5.0, game_end_ts=time.time())
        assert result["status"] == "refunded"
        assert result.get("winner_side") in (None, "")

    def test_already_resolved_bet_returns_none(self, isolated_db):
        udb = isolated_db
        ctx = _create_matched_stat_bet(udb, created_at_offset_s_before_now=600)
        udb.resolve_stat_bet(ctx["bet_id"], 5.0)
        result = udb.resolve_stat_bet(ctx["bet_id"], 5.0)
        assert result is None

    def test_refund_window_boundary_resolves_not_refunds(self, isolated_db):
        """Justo en el borde (creado a REFUND_WINDOW_SECONDS + 5s del fin): resuelve."""
        udb = isolated_db
        ctx = _create_matched_stat_bet(
            udb,
            created_at_offset_s_before_now=udb.REFUND_WINDOW_SECONDS + 5,
        )
        result = udb.resolve_stat_bet(ctx["bet_id"], 5.0, game_end_ts=time.time())
        assert result["status"] == "resolved"
