"""Tests for weather-based pace adjustment math."""

from __future__ import annotations

import pytest

from science_engine.math.weather import heat_risk_category, pace_adjustment_factor


class TestPaceAdjustmentFactor:
    """Tests for pace_adjustment_factor()."""

    def test_no_adjustment_below_15c(self) -> None:
        """Below reference temperature, no adjustment."""
        assert pace_adjustment_factor(10.0, vo2max=50.0) == 1.0

    def test_no_adjustment_at_15c(self) -> None:
        """At exactly the reference temperature, no adjustment."""
        assert pace_adjustment_factor(15.0, vo2max=50.0) == 1.0

    def test_no_adjustment_none(self) -> None:
        """None temperature returns 1.0."""
        assert pace_adjustment_factor(None) == 1.0

    def test_basic_midpack_adjustment(self) -> None:
        """25°C, no humidity, VO2max 50 → factor ~1.03 (10°C * 0.3%)."""
        factor = pace_adjustment_factor(25.0, vo2max=50.0)
        assert factor == pytest.approx(1.03, abs=0.001)

    def test_elite_adjusts_less(self) -> None:
        """Elite runner (VO2max 70) adjusts less than midpack at same temp."""
        elite = pace_adjustment_factor(25.0, vo2max=70.0)
        midpack = pace_adjustment_factor(25.0, vo2max=50.0)
        assert elite < midpack

    def test_elite_rate(self) -> None:
        """VO2max >= 65 uses elite rate: 0.18% per °C."""
        factor = pace_adjustment_factor(25.0, vo2max=70.0)
        # 10°C * 0.0018 = 0.018 → factor = 1.018
        assert factor == pytest.approx(1.018, abs=0.001)

    def test_back_of_pack_adjusts_more(self) -> None:
        """Back-of-pack (VO2max 35) adjusts more than midpack."""
        bop = pace_adjustment_factor(25.0, vo2max=35.0)
        midpack = pace_adjustment_factor(25.0, vo2max=50.0)
        assert bop > midpack

    def test_back_of_pack_rate(self) -> None:
        """VO2max <= 35 uses back-of-pack rate: 0.64% per °C."""
        factor = pace_adjustment_factor(25.0, vo2max=30.0)
        # 10°C * 0.0064 = 0.064 → factor = 1.064
        assert factor == pytest.approx(1.064, abs=0.001)

    def test_humidity_adds_correction(self) -> None:
        """80% humidity adds correction above temperature-only factor."""
        temp_only = pace_adjustment_factor(25.0, humidity_pct=None, vo2max=50.0)
        with_humidity = pace_adjustment_factor(25.0, humidity_pct=80.0, vo2max=50.0)
        assert with_humidity > temp_only
        # 80 - 60 = 20% above threshold * 0.002 = 0.04 extra
        expected_extra = 20.0 * 0.002
        assert with_humidity - temp_only == pytest.approx(expected_extra, abs=0.001)

    def test_humidity_below_threshold_no_effect(self) -> None:
        """50% humidity (below 60% threshold) has no effect."""
        temp_only = pace_adjustment_factor(25.0, humidity_pct=None, vo2max=50.0)
        with_low_humidity = pace_adjustment_factor(25.0, humidity_pct=50.0, vo2max=50.0)
        assert with_low_humidity == temp_only

    def test_humidity_at_threshold_no_effect(self) -> None:
        """At exactly 60% humidity, no correction applied."""
        temp_only = pace_adjustment_factor(25.0, humidity_pct=None, vo2max=50.0)
        at_threshold = pace_adjustment_factor(25.0, humidity_pct=60.0, vo2max=50.0)
        assert at_threshold == temp_only

    def test_extreme_heat_large_factor(self) -> None:
        """40°C produces a large factor (>1.06 for midpack)."""
        factor = pace_adjustment_factor(40.0, vo2max=50.0)
        # 25°C above reference * 0.003 = 0.075 → factor = 1.075
        assert factor > 1.06

    def test_default_vo2max_uses_midpack(self) -> None:
        """When vo2max is None, uses midpack degradation rate."""
        with_none = pace_adjustment_factor(25.0, vo2max=None)
        with_midpack = pace_adjustment_factor(25.0, vo2max=50.0)
        assert with_none == with_midpack

    def test_interpolation_between_midpack_and_elite(self) -> None:
        """VO2max 57.5 (midpoint) produces rate between midpack and elite."""
        midpack = pace_adjustment_factor(25.0, vo2max=50.0)
        elite = pace_adjustment_factor(25.0, vo2max=65.0)
        mid = pace_adjustment_factor(25.0, vo2max=57.5)
        assert midpack > mid > elite

    def test_factor_always_ge_one(self) -> None:
        """Factor is always >= 1.0 regardless of inputs."""
        assert pace_adjustment_factor(-10.0) >= 1.0
        assert pace_adjustment_factor(0.0) >= 1.0
        assert pace_adjustment_factor(50.0, humidity_pct=100.0, vo2max=30.0) >= 1.0


class TestHeatRiskCategory:
    """Tests for heat_risk_category()."""

    def test_none_is_low(self) -> None:
        assert heat_risk_category(None) == "LOW"

    def test_cool_is_low(self) -> None:
        assert heat_risk_category(15.0) == "LOW"

    def test_moderate(self) -> None:
        assert heat_risk_category(23.0) == "MODERATE"

    def test_high(self) -> None:
        assert heat_risk_category(30.0) == "HIGH"

    def test_extreme(self) -> None:
        assert heat_risk_category(38.0) == "EXTREME"

    def test_boundary_20c_is_moderate(self) -> None:
        assert heat_risk_category(20.0) == "MODERATE"

    def test_boundary_27c_is_high(self) -> None:
        assert heat_risk_category(27.0) == "HIGH"

    def test_boundary_35c_is_extreme(self) -> None:
        assert heat_risk_category(35.0) == "EXTREME"

    def test_humidity_bumps_category(self) -> None:
        """High humidity (>70%) bumps risk up one tier."""
        without = heat_risk_category(23.0, humidity_pct=50.0)
        with_humid = heat_risk_category(23.0, humidity_pct=80.0)
        assert without == "MODERATE"
        assert with_humid == "HIGH"

    def test_humidity_cap_at_extreme(self) -> None:
        """Already EXTREME doesn't go higher with humidity."""
        assert heat_risk_category(38.0, humidity_pct=90.0) == "EXTREME"

    def test_humidity_bumps_low_to_moderate(self) -> None:
        """Low risk + high humidity → moderate."""
        assert heat_risk_category(18.0, humidity_pct=80.0) == "MODERATE"
