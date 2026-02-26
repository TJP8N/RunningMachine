"""Tests for the Critical Speed math module.

Uses synthetic data with known CS values to verify the linear fit recovers
the correct parameters. Also tests pace conversions, marathon pace
derivation, zone structure, and validation.
"""

from __future__ import annotations

import pytest

from science_engine.math.critical_speed import (
    CriticalSpeedResult,
    calculate_cs_zones,
    cs_to_pace_s_per_km,
    fit_critical_speed,
    marathon_pace_from_cs,
    validate_cs_result,
)
from science_engine.models.enums import CS_MARATHON_PCT_DEFAULT, CS_MIN_DATA_POINTS


# ---------------------------------------------------------------------------
# Synthetic data generation: D = CS * t + D'
# ---------------------------------------------------------------------------

# Known CS = 4.0 m/s, D' = 200 m
# Distances: 1500, 3000, 5000, 10000 m
_KNOWN_CS = 4.0
_KNOWN_D_PRIME = 200.0

def _make_pairs(cs: float, d_prime: float, distances: tuple[float, ...]) -> tuple[tuple[float, float], ...]:
    """Generate perfect distance-time pairs from known CS and D'."""
    return tuple((d, (d - d_prime) / cs) for d in distances)


_STANDARD_DISTANCES = (1500.0, 3000.0, 5000.0, 10000.0)
_PERFECT_PAIRS = _make_pairs(_KNOWN_CS, _KNOWN_D_PRIME, _STANDARD_DISTANCES)


class TestFitCriticalSpeed:
    def test_recovers_known_cs(self) -> None:
        """Perfect synthetic data should recover CS within 0.1%."""
        result = fit_critical_speed(_PERFECT_PAIRS)
        assert abs(result.critical_speed_m_per_s - _KNOWN_CS) / _KNOWN_CS < 0.001

    def test_recovers_known_d_prime(self) -> None:
        """Perfect data should recover D' within 0.1%."""
        result = fit_critical_speed(_PERFECT_PAIRS)
        assert abs(result.d_prime_meters - _KNOWN_D_PRIME) / _KNOWN_D_PRIME < 0.001

    def test_r_squared_perfect_data(self) -> None:
        """R² should be ~1.0 for perfect data."""
        result = fit_critical_speed(_PERFECT_PAIRS)
        assert result.r_squared > 0.999

    def test_minimum_data_points(self) -> None:
        """Exactly CS_MIN_DATA_POINTS pairs should work."""
        pairs = _PERFECT_PAIRS[:CS_MIN_DATA_POINTS]
        result = fit_critical_speed(pairs)
        assert abs(result.critical_speed_m_per_s - _KNOWN_CS) / _KNOWN_CS < 0.01

    def test_too_few_points_raises(self) -> None:
        """Fewer than CS_MIN_DATA_POINTS should raise ValueError."""
        pairs = _PERFECT_PAIRS[:CS_MIN_DATA_POINTS - 1]
        with pytest.raises(ValueError, match="at least"):
            fit_critical_speed(pairs)

    def test_negative_distance_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            fit_critical_speed([(-100.0, 300.0), (3000.0, 700.0), (5000.0, 1200.0)])

    def test_zero_time_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            fit_critical_speed([(1500.0, 0.0), (3000.0, 700.0), (5000.0, 1200.0)])

    def test_noisy_data_reasonable_fit(self) -> None:
        """With moderate noise, CS should still be within 5%."""
        import numpy as np
        rng = np.random.RandomState(42)
        noisy_pairs = []
        for d, t in _PERFECT_PAIRS:
            noisy_t = t + rng.normal(0, t * 0.01)  # 1% noise
            noisy_pairs.append((d, noisy_t))
        result = fit_critical_speed(noisy_pairs)
        assert abs(result.critical_speed_m_per_s - _KNOWN_CS) / _KNOWN_CS < 0.05

    def test_residuals_length(self) -> None:
        result = fit_critical_speed(_PERFECT_PAIRS)
        assert len(result.residuals) == len(_PERFECT_PAIRS)

    def test_standard_errors_populated(self) -> None:
        result = fit_critical_speed(_PERFECT_PAIRS)
        # Perfect data → near-zero SE, but they should be non-negative
        assert result.se_cs >= 0.0
        assert result.se_d_prime >= 0.0


class TestPaceConversion:
    def test_cs_to_pace(self) -> None:
        """4.0 m/s = 250 s/km = 4:10/km."""
        pace = cs_to_pace_s_per_km(4.0)
        assert pace == pytest.approx(250.0)

    def test_cs_to_pace_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            cs_to_pace_s_per_km(0.0)

    def test_marathon_pace_default(self) -> None:
        """4.0 m/s at 84.8% CS → marathon pace ~295 s/km."""
        pace = marathon_pace_from_cs(4.0)
        expected = 1000.0 / (4.0 * CS_MARATHON_PCT_DEFAULT)
        assert pace == pytest.approx(expected, rel=0.001)

    def test_marathon_pace_custom_pct(self) -> None:
        pace = marathon_pace_from_cs(4.0, pct_cs=0.80)
        expected = 1000.0 / (4.0 * 0.80)
        assert pace == pytest.approx(expected)

    def test_marathon_pace_invalid_pct(self) -> None:
        with pytest.raises(ValueError, match="pct_cs"):
            marathon_pace_from_cs(4.0, pct_cs=0.0)
        with pytest.raises(ValueError, match="pct_cs"):
            marathon_pace_from_cs(4.0, pct_cs=1.5)


class TestCSZones:
    def test_five_zones_returned(self) -> None:
        zones = calculate_cs_zones(4.0)
        assert len(zones) == 5

    def test_zones_ordered_by_pace(self) -> None:
        """Z1 (slowest) should have higher s/km than Z5 (fastest)."""
        zones = calculate_cs_zones(4.0)
        # Z1 upper (slowest) should be > Z5 lower (fastest)
        assert zones[0].upper > zones[-1].lower

    def test_zone_boundaries_no_gaps(self) -> None:
        """Each zone's lower bound should match the previous zone's upper."""
        zones = calculate_cs_zones(4.0)
        # Skip Z1 which has an artificial cap
        for i in range(2, len(zones)):
            assert zones[i].upper == pytest.approx(zones[i - 1].lower, rel=0.01)

    def test_invalid_cs_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            calculate_cs_zones(0.0)


class TestValidation:
    def test_perfect_result_no_warnings(self) -> None:
        result = fit_critical_speed(_PERFECT_PAIRS)
        warnings = validate_cs_result(result)
        assert warnings == []

    def test_low_r_squared_warning(self) -> None:
        result = CriticalSpeedResult(
            critical_speed_m_per_s=4.0,
            d_prime_meters=200.0,
            r_squared=0.80,
        )
        warnings = validate_cs_result(result)
        assert any("R²" in w for w in warnings)

    def test_cs_too_slow_warning(self) -> None:
        result = CriticalSpeedResult(
            critical_speed_m_per_s=2.0,
            d_prime_meters=200.0,
            r_squared=0.99,
        )
        warnings = validate_cs_result(result)
        assert any("slow" in w for w in warnings)

    def test_cs_too_fast_warning(self) -> None:
        result = CriticalSpeedResult(
            critical_speed_m_per_s=8.0,
            d_prime_meters=200.0,
            r_squared=0.99,
        )
        warnings = validate_cs_result(result)
        assert any("fast" in w for w in warnings)

    def test_negative_d_prime_warning(self) -> None:
        result = CriticalSpeedResult(
            critical_speed_m_per_s=4.0,
            d_prime_meters=-50.0,
            r_squared=0.99,
        )
        warnings = validate_cs_result(result)
        assert any("negative" in w for w in warnings)

    def test_d_prime_too_high_warning(self) -> None:
        result = CriticalSpeedResult(
            critical_speed_m_per_s=4.0,
            d_prime_meters=600.0,
            r_squared=0.99,
        )
        warnings = validate_cs_result(result)
        assert any("high" in w for w in warnings)
