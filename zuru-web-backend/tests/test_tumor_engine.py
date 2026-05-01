"""
Tests de invariantes del tumor_engine.

Lo que estos tests garantizan:
  - match_tumor está siempre en [0, 100]
  - team_tumor (mediana) está siempre dentro de [min, max] de los priors
  - Si todos los priors son X, team_tumor es X exactamente
  - Streamer mode (prior=None) no afecta al cálculo
  - Predicción es coherente: equipo con menor team_tumor gana
  - Tiebreaker por suma funciona cuando medianas son iguales
  - Empate solo si mediana Y suma son iguales
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import tumor_engine as te


class TestBadScore:
    def test_at_threshold_returns_zero(self):
        assert te.bad_score(10, 10) == 0.0

    def test_above_threshold_returns_zero(self):
        assert te.bad_score(20, 10) == 0.0

    def test_zero_value_returns_100(self):
        assert te.bad_score(0, 10) == 100.0

    def test_half_threshold_returns_50(self):
        assert te.bad_score(5, 10) == 50.0


class TestMatchTumor:
    def _good_player(self):
        return {
            "kills": 10, "deaths": 3, "assists": 8,
            "totalMinionsKilled": 200, "neutralMinionsKilled": 10,
            "totalDamageDealtToChampions": 30000,
            "visionScore": 25, "totalTimeSpentDead": 80,
        }

    def _bad_player(self):
        return {
            "kills": 1, "deaths": 12, "assists": 2,
            "totalMinionsKilled": 50, "neutralMinionsKilled": 0,
            "totalDamageDealtToChampions": 5000,
            "visionScore": 5, "totalTimeSpentDead": 400,
        }

    def test_score_range(self):
        for tier in ["IRON", "GOLD", "DIAMOND", "CHALLENGER"]:
            for role in ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]:
                score, _ = te.compute_match_tumor(self._good_player(), 1800, tier, role)
                assert 0 <= score <= 100, f"out of range: tier={tier} role={role} score={score}"

    def test_good_mid_low_score(self):
        score, _ = te.compute_match_tumor(self._good_player(), 1800, "GOLD", "MIDDLE")
        assert score < 30, f"good mid should be < 30, got {score}"

    def test_bad_adc_high_score(self):
        score, _ = te.compute_match_tumor(self._bad_player(), 1800, "GOLD", "BOTTOM")
        assert score > 50, f"bad ADC should be > 50, got {score}"

    def test_support_with_zero_cs_not_punished(self):
        sup = {
            "kills": 2, "deaths": 3, "assists": 18,
            "totalMinionsKilled": 0, "neutralMinionsKilled": 0,
            "totalDamageDealtToChampions": 9000,
            "visionScore": 80, "totalTimeSpentDead": 120,
        }
        score, _ = te.compute_match_tumor(sup, 1800, "GOLD", "UTILITY")
        # Support con 0 cs pero buena visión y kda → no debería pasar de 30
        assert score < 30, f"support with 0 cs but good vision/kda should be < 30, got {score}"


class TestTeamTumor:
    def test_all_same_returns_same(self):
        for x in [0, 30, 50, 70, 100]:
            result = te.compute_team_tumor([x, x, x, x, x])
            assert result == x, f"all={x} should give {x}, got {result}"

    def test_within_min_max(self):
        priors = [10, 30, 50, 70, 90]
        result = te.compute_team_tumor(priors)
        assert min(priors) <= result <= max(priors)

    def test_median_of_5(self):
        # Mediana de [10, 30, 50, 70, 90] = 50
        assert te.compute_team_tumor([10, 30, 50, 70, 90]) == 50

    def test_median_of_4_averages_middle_two(self):
        # 4 valores → promedio de los dos del medio
        assert te.compute_team_tumor([10, 30, 70, 90]) == 50

    def test_streamer_mode_skipped(self):
        # Con un None, mediana sobre los 4 válidos
        result = te.compute_team_tumor([10, 30, None, 50, 70])
        assert result == 40  # mediana de [10, 30, 50, 70] = 40

    def test_all_none_default_50(self):
        assert te.compute_team_tumor([None, None, None, None, None]) == 50

    def test_outlier_doesnt_dominate(self):
        # Una persona terrible no destruye al equipo
        normal = te.compute_team_tumor([20, 25, 30, 35, 40])
        with_troll = te.compute_team_tumor([20, 25, 30, 35, 99])
        # Mediana protege contra outliers
        assert with_troll == 30  # sigue siendo 30 (mediana del medio)
        assert normal == 30


class TestPredictTeamOutcome:
    def _player(self, team_id, prior, role="TOP"):
        return {"team_id": team_id, "prior_tumor": prior, "role": role}

    def test_lower_tumor_wins(self):
        players = [self._player(100, 30) for _ in range(5)] + [self._player(200, 60) for _ in range(5)]
        result = te.predict_team_outcome(players)
        assert result["winner"] == "blue"
        assert result["blue_team_tumor"] == 30
        assert result["red_team_tumor"] == 60

    def test_higher_tumor_loses(self):
        players = [self._player(100, 60) for _ in range(5)] + [self._player(200, 30) for _ in range(5)]
        result = te.predict_team_outcome(players)
        assert result["winner"] == "red"

    def test_exact_tie_returns_tie(self):
        players = [self._player(100, 50) for _ in range(5)] + [self._player(200, 50) for _ in range(5)]
        result = te.predict_team_outcome(players)
        assert result["winner"] == "tie"

    def test_sum_tiebreaker_when_medians_equal(self):
        # Mediana 50 ambos, pero blue suma menos
        blue = [self._player(100, x) for x in [20, 30, 50, 70, 80]]   # mediana 50, sum 250
        red  = [self._player(200, x) for x in [40, 45, 50, 80, 100]]  # mediana 50, sum 315
        result = te.predict_team_outcome(blue + red)
        # Mediana igual, blue suma menos → gana blue
        assert result["winner"] == "blue"

    def test_streamer_mode_player_excluded(self):
        # Un streamer en blue no afecta al resultado del equipo
        blue = [self._player(100, x) for x in [30, 30, 30, 30]] + [self._player(100, None)]
        red  = [self._player(200, x) for x in [60, 60, 60, 60, 60]]
        result = te.predict_team_outcome(blue + red)
        assert result["winner"] == "blue"
        assert result["blue_team_tumor"] == 30
        assert result["red_team_tumor"] == 60

    def test_confidence_scales_with_diff(self):
        small_diff = te.predict_team_outcome(
            [self._player(100, 45) for _ in range(5)] +
            [self._player(200, 50) for _ in range(5)]
        )
        big_diff = te.predict_team_outcome(
            [self._player(100, 20) for _ in range(5)] +
            [self._player(200, 80) for _ in range(5)]
        )
        assert big_diff["confidence"] > small_diff["confidence"]


class TestStreakModifiers:
    def test_tilt_adds_penalty(self):
        original = 30
        tilted = te.apply_streak_modifier(original, is_tilted=True)
        assert tilted == original + te.TILT_PENALTY

    def test_hotstreak_subtracts_bonus(self):
        original = 50
        hot = te.apply_streak_modifier(original, is_hotstreak=True)
        assert hot == original - te.HOTSTREAK_BONUS

    def test_capped_to_100(self):
        result = te.apply_streak_modifier(95, is_tilted=True)
        assert result == 100  # not 105

    def test_capped_to_0(self):
        result = te.apply_streak_modifier(5, is_hotstreak=True)
        assert result == 0  # not -3
