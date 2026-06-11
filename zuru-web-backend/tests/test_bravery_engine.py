"""Tests for bravery_engine.

Cubre la lógica que mueve TC: style_mult_for_dims, compute_compliance,
compute_payout, y el roll básico. Si rompes estas funciones, el sistema
mintea o quema TC mal.

Run: pytest tests/test_bravery_engine.py -v
"""
import sys
import os
import pytest

# Permite ejecutar el archivo de tests sin instalar el paquete.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import bravery_engine as be  # noqa: E402


# ---------------------------------------------------------------------------
# style_mult_for_dims
# ---------------------------------------------------------------------------

class TestStyleMult:
    def test_champion_only_is_one(self):
        assert be.style_mult_for_dims({"champion"}) == 1.0

    def test_champion_plus_lane_loses_10_percent(self):
        assert be.style_mult_for_dims({"champion", "lane"}) == 0.9

    def test_champion_plus_items_loses_25_percent(self):
        assert be.style_mult_for_dims({"champion", "items"}) == 0.75

    def test_champion_plus_all_loses_35_percent(self):
        # 1.0 - 0.10 - 0.25 = 0.65
        assert be.style_mult_for_dims({"champion", "lane", "items"}) == 0.65

    def test_without_champion_returns_one(self):
        # Gate: champion es obligatorio para que el modelo aplique
        assert be.style_mult_for_dims({"lane", "items"}) == 1.0

    def test_accepts_list_input(self):
        assert be.style_mult_for_dims(["champion", "items"]) == 0.75

    def test_empty_input_returns_one(self):
        assert be.style_mult_for_dims([]) == 1.0
        assert be.style_mult_for_dims(None) == 1.0

    def test_floor_never_below(self):
        # Si en el futuro se añaden más dims con penalty grande, el floor
        # protege contra mult negativo o cero.
        result = be.style_mult_for_dims({"champion", "lane", "items"})
        assert result >= be.STYLE_MULT_FLOOR


# ---------------------------------------------------------------------------
# compute_compliance
# ---------------------------------------------------------------------------

class TestCompliance:
    LOCK_BASE = {
        "champion_id": 266,  # Aatrox
        "lane": None,
        "items": None,
        "style_mult": 1.0,
    }

    def _lock(self, **overrides):
        d = dict(self.LOCK_BASE)
        d.update(overrides)
        return d

    def _participant(self, champ_id=266, team_pos="TOP", items=None):
        p = {"championId": champ_id, "teamPosition": team_pos}
        items = items or []
        for i in range(7):
            p[f"item{i}"] = items[i] if i < len(items) else 0
        return p

    def test_champion_match_true(self):
        r = be.compute_compliance(self._lock(), self._participant(champ_id=266))
        assert r["champion_match"] is True

    def test_champion_mismatch_false(self):
        r = be.compute_compliance(self._lock(), self._participant(champ_id=64))
        assert r["champion_match"] is False

    def test_lane_dim_inactive_returns_none(self):
        # Sin dim 'lane', lane_match es None (no aplica)
        r = be.compute_compliance(self._lock(), self._participant())
        assert r["lane_match"] is None

    def test_lane_match(self):
        r = be.compute_compliance(
            self._lock(lane="TOP", style_mult=0.9),
            self._participant(team_pos="TOP"),
        )
        assert r["lane_match"] is True
        # Lane cumplida: el effective_mult no baja
        assert r["effective_mult"] == 0.9

    def test_lane_mismatch_halves_mult(self):
        r = be.compute_compliance(
            self._lock(lane="TOP", style_mult=0.9),
            self._participant(team_pos="JUNGLE"),
        )
        assert r["lane_match"] is False
        # 0.9 × 0.5 = 0.45
        assert r["effective_mult"] == 0.45

    def test_items_dim_inactive_returns_none(self):
        r = be.compute_compliance(self._lock(), self._participant(items=[3157, 6655]))
        assert r["items_hit_rate"] is None

    def test_items_full_hit(self):
        rolled = [{"id": 3157}, {"id": 6655}, {"id": 3089}]
        r = be.compute_compliance(
            self._lock(items=rolled, style_mult=0.75),
            self._participant(items=[3157, 6655, 3089, 3145]),
        )
        assert r["items_hit_rate"] == 1.0
        # Full hit: 0.75 × (0.3 + 0.7×1.0) = 0.75 × 1.0 = 0.75
        assert r["effective_mult"] == 0.75

    def test_items_zero_hit_keeps_30pct_of_mult(self):
        rolled = [{"id": 3157}, {"id": 6655}]
        r = be.compute_compliance(
            self._lock(items=rolled, style_mult=0.75),
            self._participant(items=[1001, 1052]),
        )
        assert r["items_hit_rate"] == 0.0
        # 0 hit: 0.75 × (0.3 + 0) = 0.225
        assert r["effective_mult"] == pytest.approx(0.225)

    def test_items_partial_hit(self):
        rolled = [{"id": 3157}, {"id": 6655}, {"id": 3089}, {"id": 3145}, {"id": 6692}]
        # 2 de 5 = 0.4 hit rate
        r = be.compute_compliance(
            self._lock(items=rolled, style_mult=0.75),
            self._participant(items=[3157, 6655, 1001, 1052]),
        )
        assert r["items_hit_rate"] == pytest.approx(0.4)
        # 0.75 × (0.3 + 0.7×0.4) = 0.75 × 0.58 = 0.435
        assert r["effective_mult"] == pytest.approx(0.435, abs=1e-3)

    def test_lane_and_items_compose(self):
        rolled = [{"id": 3157}, {"id": 6655}]
        r = be.compute_compliance(
            self._lock(lane="MIDDLE", items=rolled, style_mult=0.65),
            self._participant(team_pos="MIDDLE", items=[3157, 6655]),
        )
        # 0.65 (no lane penalty extra) × 1.0 (full items) = 0.65
        assert r["effective_mult"] == 0.65

    def test_lane_mismatch_and_items_mismatch_compounds(self):
        rolled = [{"id": 3157}]
        r = be.compute_compliance(
            self._lock(lane="MIDDLE", items=rolled, style_mult=0.65),
            self._participant(team_pos="JUNGLE", items=[1001]),
        )
        # 0.65 × 0.5 (lane fail) × 0.3 (items 0 hit) = 0.0975
        assert r["effective_mult"] == pytest.approx(0.0975, abs=1e-3)

    def test_items_with_zeros_in_inventory(self):
        """Los slots vacíos del inventario tienen item_id=0; no deben contar."""
        rolled = [{"id": 3157}, {"id": 6655}]
        r = be.compute_compliance(
            self._lock(items=rolled),
            self._participant(items=[3157, 0, 0, 0, 0, 0]),
        )
        assert r["items_hit_rate"] == 0.5  # 1 de 2


# ---------------------------------------------------------------------------
# compute_payout
# ---------------------------------------------------------------------------

class TestPayout:
    GOOD_COMPLIANCE = {"champion_match": True, "lane_match": None, "items_hit_rate": None, "effective_mult": 1.0}

    def test_champion_mismatch_pays_zero(self):
        bad = dict(self.GOOD_COMPLIANCE, champion_match=False)
        assert be.compute_payout(100, 30, bad) == 0

    def test_tumor_none_pays_zero(self):
        assert be.compute_payout(100, None, self.GOOD_COMPLIANCE) == 0

    def test_sus_threshold_60_is_break_even(self):
        # Curva: perf = 1.0 + (60 - tumor)/40
        # Tumor 60 → perf = 1.0 → payout = stake
        assert be.compute_payout(100, 60, self.GOOD_COMPLIANCE) == 100

    def test_tumor_zero_capped_at_1_5x(self):
        assert be.compute_payout(100, 0, self.GOOD_COMPLIANCE) == 150

    def test_tumor_40_caps_at_1_5x(self):
        assert be.compute_payout(100, 40, self.GOOD_COMPLIANCE) == 150

    def test_tumor_100_pays_zero(self):
        assert be.compute_payout(100, 100, self.GOOD_COMPLIANCE) == 0

    def test_tumor_80_pays_half_stake(self):
        # perf = 1.0 + (60-80)/40 = 0.5 → 100 × 0.5 = 50
        assert be.compute_payout(100, 80, self.GOOD_COMPLIANCE) == 50

    def test_style_mult_compounds(self):
        # Tumor 60 (break-even) con effective_mult 0.65: payout = 100 × 1.0 × 0.65 = 65
        comp = dict(self.GOOD_COMPLIANCE, effective_mult=0.65)
        assert be.compute_payout(100, 60, comp) == 65

    def test_high_tumor_with_high_style_still_loses(self):
        # Tumor 90 (perf=0.25) con style 1.7 (hipotético): 100 × 0.25 × 1.7 = 42.5
        # En la realidad ahora max style es 1.0, pero el test verifica la matemática.
        comp = dict(self.GOOD_COMPLIANCE, effective_mult=1.7)
        assert be.compute_payout(100, 90, comp) in (42, 43)  # round half banker

    def test_below_sus_with_no_penalty_profits(self):
        # Tumor 30 con style 0.9: perf cap 1.5 × 0.9 = 1.35 → payout 135
        comp = dict(self.GOOD_COMPLIANCE, effective_mult=0.9)
        assert be.compute_payout(100, 30, comp) == 135

    def test_zero_stake_zero_payout(self):
        assert be.compute_payout(0, 50, self.GOOD_COMPLIANCE) == 0


# ---------------------------------------------------------------------------
# Invariantes
# ---------------------------------------------------------------------------

class TestInvariants:
    """Propiedades que deben mantenerse siempre. Si una de estas rompe, hay
    un agujero económico."""

    def test_payout_never_negative(self):
        comp = {"champion_match": True, "lane_match": True, "items_hit_rate": 1.0, "effective_mult": 1.7}
        for tumor in range(0, 101, 10):
            assert be.compute_payout(100, tumor, comp) >= 0, f"tumor={tumor} dio negativo"

    def test_break_even_point_is_sus_60(self):
        """La curva de payout siempre debe cruzar stake en tumor==SUS_TUMOR_THRESHOLD."""
        comp = {"champion_match": True, "lane_match": None, "items_hit_rate": None, "effective_mult": 1.0}
        assert be.compute_payout(1000, be.SUS_TUMOR_THRESHOLD, comp) == 1000

    def test_more_dimensions_means_less_or_equal_style_mult(self):
        """Más restricciones nunca deben dar más mult que menos restricciones."""
        a = be.style_mult_for_dims({"champion"})
        b = be.style_mult_for_dims({"champion", "lane"})
        c = be.style_mult_for_dims({"champion", "items"})
        d = be.style_mult_for_dims({"champion", "lane", "items"})
        assert a >= b >= d
        assert a >= c >= d

    def test_champion_match_false_zeros_payout_regardless_of_tumor(self):
        comp = {"champion_match": False, "lane_match": True, "items_hit_rate": 1.0, "effective_mult": 1.7}
        for tumor in [0, 30, 60, 90]:
            assert be.compute_payout(1000, tumor, comp) == 0


# ---------------------------------------------------------------------------
# roll (sólo si DDragon está disponible — skip si no hay red)
# ---------------------------------------------------------------------------

class TestRoll:
    def test_roll_returns_none_if_no_ddragon(self, monkeypatch):
        # Forzar cache vacía + bloquear refresh
        monkeypatch.setattr(be, "_CACHE", {"version": None, "champions": None, "items": None, "fetched_at": 0.0})
        monkeypatch.setattr(be, "_refresh_ddragon", lambda: None)
        assert be.roll(["champion"]) is None

    def test_roll_with_mock_data(self, monkeypatch):
        mock_cache = {
            "version": "14.1.1",
            "champions": [
                {"id": 266, "key": "Aatrox", "name": "Aatrox"},
                {"id": 103, "key": "Ahri", "name": "Ahri"},
            ],
            "items": [
                {"id": 3157, "name": "Zhonya's", "gold": 2600, "tags": ["SpellDamage"]},
                {"id": 6655, "name": "Luden's", "gold": 2900, "tags": ["SpellDamage"]},
                {"id": 3089, "name": "Rabadon's", "gold": 3600, "tags": ["SpellDamage"]},
            ],
            "fetched_at": 9999,
        }
        monkeypatch.setattr(be, "_CACHE", mock_cache)
        monkeypatch.setattr(be, "_refresh_ddragon", lambda: None)

        r = be.roll(["champion", "items"], item_count=3, seed=42)
        assert r is not None
        assert r["champion"]["name"] in ("Aatrox", "Ahri")
        assert r["lane"] is None  # no lane dim
        assert len(r["items"]) == 3
        assert r["style_mult"] == 0.75

    def test_roll_with_lane_dim(self, monkeypatch):
        mock_cache = {
            "version": "14.1.1",
            "champions": [{"id": 266, "key": "Aatrox", "name": "Aatrox"}],
            "items": [{"id": 3157, "name": "Zhonya's", "gold": 2600, "tags": []}],
            "fetched_at": 9999,
        }
        monkeypatch.setattr(be, "_CACHE", mock_cache)
        monkeypatch.setattr(be, "_refresh_ddragon", lambda: None)

        r = be.roll(["champion", "lane"], seed=1)
        assert r["lane"] in be.VALID_LANES
        assert r["items"] is None
        assert r["style_mult"] == 0.9

    def test_roll_forces_champion_dim(self, monkeypatch):
        mock_cache = {
            "version": "14.1.1",
            "champions": [{"id": 266, "key": "Aatrox", "name": "Aatrox"}],
            "items": [{"id": 3157, "name": "Z", "gold": 2600, "tags": []}],
            "fetched_at": 9999,
        }
        monkeypatch.setattr(be, "_CACHE", mock_cache)
        monkeypatch.setattr(be, "_refresh_ddragon", lambda: None)
        # Llamar sin 'champion' debe añadirla
        r = be.roll(["items"], seed=1)
        assert r is not None
        assert r["champion"] is not None
        assert "champion" in r["dimensions"]
