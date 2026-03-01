"""Tests for the Performance Ceiling Model (math/ceiling.py)."""

from __future__ import annotations

from datetime import date

import pytest

from science_engine.math.ceiling import (
    CeilingEstimate,
    _pct_vo2max_at_duration,
    _velocity_from_vo2,
    athlete_specific_pct_cs,
    estimate_ceiling,
    format_ceiling_range,
    format_marathon_time,
    marathon_time_from_cs,
    marathon_time_from_vo2max,
    project_vo2max,
)
from science_engine.models.enums import (
    CEILING_CS_PCT_ELITE,
    CEILING_CS_PCT_MIDPACK,
    CEILING_CS_PCT_NOVICE,
    CEILING_VO2MAX_ELITE,
    CEILING_VO2MAX_MIDPACK,
    CEILING_VO2MAX_NOVICE,
    MARATHON_DISTANCE_M,
)


# =========================================================================
# TestAthleteSpecificPctCS
# =========================================================================


class TestAthleteSpecificPctCS:
    """Tests for athlete_specific_pct_cs interpolation."""

    def test_novice_floor(self):
        """VO2max at or below novice threshold returns novice %CS."""
        assert athlete_specific_pct_cs(CEILING_VO2MAX_NOVICE) == CEILING_CS_PCT_NOVICE
        assert athlete_specific_pct_cs(20.0) == CEILING_CS_PCT_NOVICE

    def test_elite_ceiling(self):
        """VO2max at or above elite threshold returns elite %CS."""
        assert athlete_specific_pct_cs(CEILING_VO2MAX_ELITE) == CEILING_CS_PCT_ELITE
        assert athlete_specific_pct_cs(80.0) == CEILING_CS_PCT_ELITE

    def test_midpack_exact(self):
        """VO2max at midpack threshold returns midpack %CS."""
        assert athlete_specific_pct_cs(CEILING_VO2MAX_MIDPACK) == pytest.approx(
            CEILING_CS_PCT_MIDPACK
        )

    def test_interpolation_novice_to_midpack(self):
        """Value between novice and midpack is interpolated."""
        mid_vo2 = (CEILING_VO2MAX_NOVICE + CEILING_VO2MAX_MIDPACK) / 2
        result = athlete_specific_pct_cs(mid_vo2)
        expected = (CEILING_CS_PCT_NOVICE + CEILING_CS_PCT_MIDPACK) / 2
        assert result == pytest.approx(expected)

    def test_interpolation_midpack_to_elite(self):
        """Value between midpack and elite is interpolated."""
        mid_vo2 = (CEILING_VO2MAX_MIDPACK + CEILING_VO2MAX_ELITE) / 2
        result = athlete_specific_pct_cs(mid_vo2)
        expected = (CEILING_CS_PCT_MIDPACK + CEILING_CS_PCT_ELITE) / 2
        assert result == pytest.approx(expected)

    def test_monotonically_increasing(self):
        """Higher VO2max → higher %CS (monotonicity)."""
        vo2_values = [30.0, 40.0, 50.0, 55.0, 60.0, 65.0, 70.0]
        pct_values = [athlete_specific_pct_cs(v) for v in vo2_values]
        for i in range(len(pct_values) - 1):
            assert pct_values[i] <= pct_values[i + 1]

    def test_range_bounds(self):
        """All values stay within [NOVICE, ELITE] range."""
        for vo2 in [10.0, 35.0, 42.0, 50.0, 57.0, 65.0, 90.0]:
            result = athlete_specific_pct_cs(vo2)
            assert CEILING_CS_PCT_NOVICE <= result <= CEILING_CS_PCT_ELITE

    def test_slightly_above_novice(self):
        """Just above novice threshold interpolates slightly above novice %CS."""
        result = athlete_specific_pct_cs(CEILING_VO2MAX_NOVICE + 1.0)
        assert result > CEILING_CS_PCT_NOVICE
        assert result < CEILING_CS_PCT_MIDPACK


# =========================================================================
# TestMarathonTimeFromCS
# =========================================================================


class TestMarathonTimeFromCS:
    """Tests for marathon_time_from_cs."""

    def test_known_value_midpack(self):
        """4.2 m/s CS at 84.8% → known marathon time."""
        time_s = marathon_time_from_cs(4.2, CEILING_CS_PCT_MIDPACK)
        # 42195 / (4.2 * 0.848) = 42195 / 3.5616 ≈ 11847.4 s ≈ 3:17:27
        assert time_s == pytest.approx(MARATHON_DISTANCE_M / (4.2 * 0.848), rel=1e-6)

    def test_known_value_elite(self):
        """5.5 m/s CS at 93% → sub-2:30 marathon."""
        time_s = marathon_time_from_cs(5.5, CEILING_CS_PCT_ELITE)
        # 42195 / (5.5 * 0.93) = 42195 / 5.115 ≈ 8248.5 s ≈ 2:17:29
        assert time_s < 2.5 * 3600  # under 2:30

    def test_zero_cs_raises(self):
        """CS of zero raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            marathon_time_from_cs(0.0, 0.848)

    def test_negative_cs_raises(self):
        """Negative CS raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            marathon_time_from_cs(-1.0, 0.848)

    def test_pct_cs_out_of_range_raises(self):
        """pct_cs > 1 or <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="pct_cs"):
            marathon_time_from_cs(4.0, 1.1)
        with pytest.raises(ValueError, match="pct_cs"):
            marathon_time_from_cs(4.0, 0.0)

    def test_higher_cs_faster_time(self):
        """Higher CS → faster marathon time."""
        t1 = marathon_time_from_cs(3.5, 0.848)
        t2 = marathon_time_from_cs(4.5, 0.848)
        assert t2 < t1


# =========================================================================
# TestMarathonTimeFromVO2max
# =========================================================================


class TestMarathonTimeFromVO2max:
    """Tests for marathon_time_from_vo2max (Daniels solver)."""

    def test_elite_vo2max(self):
        """VO2max 70 → sub-2:30 marathon (known from VDOT tables)."""
        time_s = marathon_time_from_vo2max(70.0)
        assert time_s < 2.5 * 3600  # under 2:30:00

    def test_intermediate_vo2max(self):
        """VO2max 48 → ~3:20-3:40 marathon (known from VDOT tables)."""
        time_s = marathon_time_from_vo2max(48.0)
        assert 3.0 * 3600 < time_s < 4.0 * 3600  # between 3:00 and 4:00

    def test_beginner_vo2max(self):
        """VO2max 35 → 4:30+ marathon."""
        time_s = marathon_time_from_vo2max(35.0)
        assert time_s > 4.0 * 3600  # over 4:00

    def test_higher_vo2max_faster(self):
        """Higher VO2max → faster marathon time (monotonic)."""
        t35 = marathon_time_from_vo2max(35.0)
        t48 = marathon_time_from_vo2max(48.0)
        t65 = marathon_time_from_vo2max(65.0)
        assert t65 < t48 < t35

    def test_zero_vo2max_raises(self):
        """VO2max 0 raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            marathon_time_from_vo2max(0.0)

    def test_negative_vo2max_raises(self):
        """Negative VO2max raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            marathon_time_from_vo2max(-5.0)


# =========================================================================
# TestDanielsHelpers
# =========================================================================


class TestDanielsHelpers:
    """Tests for the internal Daniels-Gilbert helper functions."""

    def test_pct_vo2max_at_short_duration(self):
        """%VO2max at 10 min should be close to 1.0 (Daniels curve can slightly exceed 1.0)."""
        pct = _pct_vo2max_at_duration(10.0)
        assert 0.95 < pct < 1.05

    def test_pct_vo2max_at_marathon_duration(self):
        """%VO2max at ~180 min should be ~0.75-0.85."""
        pct = _pct_vo2max_at_duration(180.0)
        assert 0.75 < pct < 0.86

    def test_pct_vo2max_decreases_with_duration(self):
        """Longer duration → lower %VO2max."""
        p10 = _pct_vo2max_at_duration(10.0)
        p60 = _pct_vo2max_at_duration(60.0)
        p180 = _pct_vo2max_at_duration(180.0)
        assert p10 > p60 > p180

    def test_velocity_from_vo2_positive(self):
        """Valid VO2 → positive velocity."""
        v = _velocity_from_vo2(48.0)
        assert v > 0

    def test_velocity_increases_with_vo2(self):
        """Higher VO2 → higher velocity."""
        v40 = _velocity_from_vo2(40.0)
        v60 = _velocity_from_vo2(60.0)
        assert v60 > v40


# =========================================================================
# TestProjectVO2max
# =========================================================================


class TestProjectVO2max:
    """Tests for project_vo2max."""

    def test_insufficient_data(self):
        """Fewer than 3 points returns (None, None)."""
        history = (("2026-01-01", 45.0), ("2026-02-01", 46.0))
        proj, trend = project_vo2max(history, date(2026, 6, 15), date(2026, 3, 1))
        assert proj is None
        assert trend is None

    def test_positive_trend(self):
        """Improving VO2max → positive trend and higher projection."""
        history = (
            ("2025-10-01", 45.0),
            ("2025-11-01", 46.0),
            ("2025-12-01", 47.0),
            ("2026-01-01", 48.0),
            ("2026-02-01", 49.0),
        )
        proj, trend = project_vo2max(history, date(2026, 6, 15), date(2026, 2, 15))
        assert trend is not None
        assert trend > 0
        assert proj is not None
        assert proj > 49.0

    def test_negative_trend(self):
        """Declining VO2max → negative trend."""
        history = (
            ("2026-01-01", 50.0),
            ("2026-01-15", 49.0),
            ("2026-02-01", 48.0),
        )
        proj, trend = project_vo2max(history, date(2026, 6, 15), date(2026, 2, 15))
        assert trend is not None
        assert trend < 0

    def test_flat_trend(self):
        """Stable VO2max → near-zero trend."""
        history = (
            ("2026-01-01", 48.0),
            ("2026-01-15", 48.0),
            ("2026-02-01", 48.0),
        )
        proj, trend = project_vo2max(history, date(2026, 6, 15), date(2026, 2, 15))
        assert trend is not None
        assert abs(trend) < 0.01
        assert proj is not None
        assert proj == pytest.approx(48.0, abs=0.5)

    def test_capped_improvement_rate(self):
        """Unrealistically fast improvement gets capped."""
        # 5 ml/kg/min per week is unrealistic
        history = (
            ("2026-01-01", 40.0),
            ("2026-01-08", 45.0),
            ("2026-01-15", 50.0),
        )
        proj, trend = project_vo2max(history, date(2026, 6, 15), date(2026, 1, 20))
        assert trend is not None
        assert trend <= 0.5  # Capped at VO2MAX_MAX_WEEKLY_IMPROVEMENT

    def test_projection_clamped_to_range(self):
        """Projected value stays within physiological bounds (20-90)."""
        # Very low declining trend
        history = (
            ("2026-01-01", 25.0),
            ("2026-01-15", 23.0),
            ("2026-02-01", 21.0),
        )
        proj, _ = project_vo2max(history, date(2027, 6, 15), date(2026, 2, 15))
        assert proj is not None
        assert proj >= 20.0

    def test_projection_max_weeks_limit(self):
        """Projection doesn't extend beyond VO2MAX_PROJECTION_MAX_WEEKS."""
        history = (
            ("2025-01-01", 45.0),
            ("2025-06-01", 47.0),
            ("2025-12-01", 49.0),
        )
        # Race date very far in the future
        proj_far, _ = project_vo2max(history, date(2028, 1, 1), date(2026, 2, 1))
        proj_near, _ = project_vo2max(history, date(2026, 8, 1), date(2026, 2, 1))
        assert proj_far is not None
        assert proj_near is not None
        # Far projection should be capped, not wildly higher than near
        assert proj_far <= proj_near + 15  # Reasonable bound


# =========================================================================
# TestEstimateCeiling
# =========================================================================


class TestEstimateCeiling:
    """Tests for the main estimate_ceiling function."""

    def test_insufficient_no_data(self):
        """No CS, no VO2max → INSUFFICIENT."""
        est = estimate_ceiling()
        assert est.data_quality == "INSUFFICIENT"
        assert est.signal_count == 0
        assert est.marathon_time_s == 0.0

    def test_cs_only_low_quality(self):
        """CS without VO2max → LOW quality."""
        est = estimate_ceiling(cs=4.2)
        assert est.data_quality == "LOW"
        assert est.signal_count == 1
        assert est.cs_estimate_s is not None
        assert est.vo2max_estimate_s is None
        assert est.marathon_time_s > 0
        assert "CS-only" not in est.warnings[0] or "VO2max" in est.warnings[0]

    def test_vo2max_only_low_quality(self):
        """VO2max without CS → LOW quality."""
        est = estimate_ceiling(vo2max=48.0)
        assert est.data_quality == "LOW"
        assert est.signal_count == 1
        assert est.vo2max_estimate_s is not None
        assert est.cs_estimate_s is None

    def test_both_signals_moderate(self):
        """CS + VO2max without trajectory → MODERATE quality."""
        est = estimate_ceiling(cs=4.2, vo2max=48.0)
        assert est.data_quality == "MODERATE"
        assert est.signal_count == 2
        assert est.cs_estimate_s is not None
        assert est.vo2max_estimate_s is not None
        assert len(est.warnings) == 0

    def test_both_signals_with_trajectory_high(self):
        """CS + VO2max + trajectory → HIGH quality."""
        history = (
            ("2025-10-01", 45.0),
            ("2025-11-01", 46.0),
            ("2025-12-01", 47.0),
            ("2026-01-01", 48.0),
            ("2026-02-01", 49.0),
        )
        est = estimate_ceiling(
            cs=4.2,
            vo2max=48.0,
            vo2max_history=history,
            race_date=date(2026, 6, 15),
            current_date=date(2026, 2, 15),
        )
        assert est.data_quality == "HIGH"
        assert est.signal_count == 3
        assert est.vo2max_projected is not None
        assert est.vo2max_weekly_trend is not None

    def test_weighted_average_between_signals(self):
        """Central estimate is between CS and VO2max estimates."""
        est = estimate_ceiling(cs=4.2, vo2max=48.0)
        assert min(est.cs_estimate_s, est.vo2max_estimate_s) <= est.marathon_time_s
        assert est.marathon_time_s <= max(est.cs_estimate_s, est.vo2max_estimate_s)

    def test_ci_contains_central(self):
        """Confidence interval brackets the central estimate."""
        est = estimate_ceiling(cs=4.2, vo2max=48.0)
        assert est.marathon_time_low_s < est.marathon_time_s
        assert est.marathon_time_s < est.marathon_time_high_s

    def test_ci_wider_without_trajectory(self):
        """CI is wider when trajectory data is missing."""
        history = (
            ("2025-10-01", 45.0),
            ("2025-11-01", 46.0),
            ("2025-12-01", 47.0),
            ("2026-01-01", 48.0),
            ("2026-02-01", 49.0),
        )
        est_no_traj = estimate_ceiling(cs=4.2, vo2max=48.0)
        est_with_traj = estimate_ceiling(
            cs=4.2,
            vo2max=48.0,
            vo2max_history=history,
            race_date=date(2026, 6, 15),
            current_date=date(2026, 2, 15),
        )
        width_no = est_no_traj.marathon_time_high_s - est_no_traj.marathon_time_low_s
        width_with = est_with_traj.marathon_time_high_s - est_with_traj.marathon_time_low_s
        assert width_no > width_with

    def test_ci_wider_when_signals_disagree(self):
        """CI is wider when CS and VO2max estimates are far apart."""
        # Mismatched: fast CS + slow VO2max
        est_disagree = estimate_ceiling(cs=5.0, vo2max=38.0)
        # Matched: moderate CS + moderate VO2max
        est_agree = estimate_ceiling(cs=4.2, vo2max=48.0)
        width_disagree = (
            est_disagree.marathon_time_high_s - est_disagree.marathon_time_low_s
        )
        width_agree = est_agree.marathon_time_high_s - est_agree.marathon_time_low_s
        assert width_disagree > width_agree

    def test_se_cs_widens_ci(self):
        """Standard error on CS widens the confidence interval."""
        est_no_se = estimate_ceiling(cs=4.2, vo2max=48.0, se_cs=0.0)
        est_se = estimate_ceiling(cs=4.2, vo2max=48.0, se_cs=0.2)
        width_no_se = est_no_se.marathon_time_high_s - est_no_se.marathon_time_low_s
        width_se = est_se.marathon_time_high_s - est_se.marathon_time_low_s
        assert width_se > width_no_se

    def test_pace_consistent_with_time(self):
        """Marathon pace should equal time / distance-in-km."""
        est = estimate_ceiling(cs=4.2, vo2max=48.0)
        expected_pace = est.marathon_time_s / (MARATHON_DISTANCE_M / 1000.0)
        assert est.marathon_pace_s_per_km == pytest.approx(expected_pace)

    def test_pct_cs_set_when_cs_available(self):
        """pct_cs_used is set when CS signal is available."""
        est = estimate_ceiling(cs=4.2, vo2max=48.0)
        assert est.pct_cs_used > 0

    def test_pct_cs_zero_when_no_cs(self):
        """pct_cs_used is 0 when no CS data."""
        est = estimate_ceiling(vo2max=48.0)
        assert est.pct_cs_used == 0.0

    def test_cs_only_uses_default_vo2max_for_pct(self):
        """CS-only estimate uses a default VO2max (45) for %CS interpolation."""
        est = estimate_ceiling(cs=4.2)
        expected_pct = athlete_specific_pct_cs(45.0)
        assert est.pct_cs_used == pytest.approx(expected_pct)

    def test_zero_cs_treated_as_unavailable(self):
        """CS = 0 is treated as unavailable."""
        est = estimate_ceiling(cs=0.0, vo2max=48.0)
        assert est.cs_estimate_s is None
        assert est.data_quality == "LOW"


# =========================================================================
# TestFormatting
# =========================================================================


class TestFormatting:
    """Tests for format_marathon_time and format_ceiling_range."""

    def test_format_sub_3(self):
        """2:52:30 formats correctly."""
        assert format_marathon_time(2 * 3600 + 52 * 60 + 30) == "2:52:30"

    def test_format_3_hours_exact(self):
        """3:00:00 formats correctly."""
        assert format_marathon_time(3 * 3600) == "3:00:00"

    def test_format_zero(self):
        """0 seconds → '0:00:00'."""
        assert format_marathon_time(0) == "0:00:00"

    def test_format_range_insufficient(self):
        """INSUFFICIENT estimate → descriptive message."""
        est = estimate_ceiling()
        result = format_ceiling_range(est)
        assert "Insufficient" in result

    def test_format_range_with_data(self):
        """Valid estimate → range with confidence."""
        est = estimate_ceiling(cs=4.2, vo2max=48.0)
        result = format_ceiling_range(est)
        assert "ceiling" in result.lower()
        assert "85%" in result
        assert "-" in result
