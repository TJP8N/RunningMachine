"""Tests for Race-Pace Confidence Scoring (RPCS).

Covers each component scorer independently, composite weighting, warnings,
and edge cases (empty sessions, over target, recency weighting).
"""

from __future__ import annotations

import pytest

from science_engine.math.race_pace_confidence import (
    _recency_weight,
    _score_cumulative_mp,
    _score_longest_segment,
    _score_mp_under_fatigue,
    _score_pace_accuracy,
    calculate_race_pace_confidence,
)
from science_engine.models.enums import (
    RPCS_ACCURACY_DEFAULT_SCORE,
    RPCS_CUMULATIVE_TARGET_MIN,
    RPCS_FATIGUE_TARGET_MIN,
    RPCS_LONGEST_SEGMENT_FLOOR_MIN,
    RPCS_LONGEST_SEGMENT_TARGET_MIN,
    RPCS_RECENCY_HALF_LIFE_WEEKS,
)
from science_engine.models.mp_session_record import MPSessionRecord


# ---------------------------------------------------------------------------
# Helper: build MPSessionRecord quickly
# ---------------------------------------------------------------------------


def _mp(
    total: float = 20.0,
    longest: float = 15.0,
    fatigue: float = 0.0,
    long_run: bool = False,
    weeks_ago: float = 0.0,
    std_dev: float | None = None,
) -> MPSessionRecord:
    return MPSessionRecord(
        date="2026-01-15",
        total_mp_time_min=total,
        longest_continuous_mp_min=longest,
        mp_in_second_half_min=fatigue,
        was_long_run=long_run,
        weeks_ago=weeks_ago,
        pace_std_dev_s_per_km=std_dev,
    )


# ===================================================================
# Recency weighting
# ===================================================================


class TestRecencyWeight:
    def test_current_week_weight_is_one(self):
        assert _recency_weight(0.0) == pytest.approx(1.0)

    def test_half_life_gives_half_weight(self):
        w = _recency_weight(RPCS_RECENCY_HALF_LIFE_WEEKS)
        assert w == pytest.approx(0.5, abs=1e-6)

    def test_two_half_lives_gives_quarter_weight(self):
        w = _recency_weight(RPCS_RECENCY_HALF_LIFE_WEEKS * 2)
        assert w == pytest.approx(0.25, abs=1e-6)

    def test_weight_always_positive(self):
        assert _recency_weight(100.0) > 0


# ===================================================================
# Cumulative MP score
# ===================================================================


class TestCumulativeMPScore:
    def test_empty_sessions(self):
        score, total = _score_cumulative_mp([])
        assert score == 0.0
        assert total == 0.0

    def test_at_target(self):
        # Single session at exact target, weeks_ago=0 → weight=1.0
        s = _mp(total=RPCS_CUMULATIVE_TARGET_MIN, weeks_ago=0)
        score, _ = _score_cumulative_mp([s])
        assert score == 100.0

    def test_over_target_capped_at_100(self):
        s = _mp(total=200.0, weeks_ago=0)
        score, _ = _score_cumulative_mp([s])
        assert score == 100.0

    def test_partial_score(self):
        # Half the target, current week
        s = _mp(total=RPCS_CUMULATIVE_TARGET_MIN / 2, weeks_ago=0)
        score, _ = _score_cumulative_mp([s])
        assert score == pytest.approx(50.0, abs=0.5)

    def test_recency_reduces_contribution(self):
        # 120 min but 5 weeks ago → weighted to ~60 min → ~50%
        s = _mp(total=RPCS_CUMULATIVE_TARGET_MIN, weeks_ago=RPCS_RECENCY_HALF_LIFE_WEEKS)
        score, weighted = _score_cumulative_mp([s])
        assert weighted == pytest.approx(RPCS_CUMULATIVE_TARGET_MIN / 2, abs=1.0)
        assert score < 60.0

    def test_multiple_sessions_sum(self):
        sessions = [_mp(total=30.0, weeks_ago=0) for _ in range(4)]
        score, weighted = _score_cumulative_mp(sessions)
        assert weighted == pytest.approx(120.0, abs=0.1)
        assert score == 100.0


# ===================================================================
# Longest segment score
# ===================================================================


class TestLongestSegmentScore:
    def test_empty_sessions(self):
        score, longest = _score_longest_segment([])
        assert score == 0.0
        assert longest == 0.0

    def test_at_target(self):
        s = _mp(longest=RPCS_LONGEST_SEGMENT_TARGET_MIN)
        score, _ = _score_longest_segment([s])
        assert score == 100.0

    def test_at_floor(self):
        s = _mp(longest=RPCS_LONGEST_SEGMENT_FLOOR_MIN)
        score, _ = _score_longest_segment([s])
        assert score == 0.0

    def test_below_floor(self):
        s = _mp(longest=5.0)
        score, _ = _score_longest_segment([s])
        assert score == 0.0

    def test_midpoint(self):
        mid = (RPCS_LONGEST_SEGMENT_FLOOR_MIN + RPCS_LONGEST_SEGMENT_TARGET_MIN) / 2
        s = _mp(longest=mid)
        score, _ = _score_longest_segment([s])
        assert score == pytest.approx(50.0, abs=0.5)

    def test_takes_max_across_sessions(self):
        sessions = [_mp(longest=25.0), _mp(longest=45.0), _mp(longest=30.0)]
        score, longest = _score_longest_segment(sessions)
        assert longest == 45.0


# ===================================================================
# MP under fatigue score
# ===================================================================


class TestMPUnderFatigueScore:
    def test_empty_sessions(self):
        score, total = _score_mp_under_fatigue([])
        assert score == 0.0

    def test_non_long_run_ignored(self):
        s = _mp(fatigue=30.0, long_run=False)
        score, total = _score_mp_under_fatigue([s])
        assert total == 0.0
        assert score == 0.0

    def test_at_target(self):
        s = _mp(fatigue=RPCS_FATIGUE_TARGET_MIN, long_run=True)
        score, _ = _score_mp_under_fatigue([s])
        assert score == 100.0

    def test_below_minimum(self):
        s = _mp(fatigue=5.0, long_run=True)
        score, _ = _score_mp_under_fatigue([s])
        assert score == 0.0

    def test_multiple_long_runs_sum(self):
        sessions = [
            _mp(fatigue=15.0, long_run=True),
            _mp(fatigue=15.0, long_run=True),
            _mp(fatigue=15.0, long_run=True),
        ]
        score, total = _score_mp_under_fatigue(sessions)
        assert total == 45.0
        assert score == 100.0


# ===================================================================
# Pace accuracy score
# ===================================================================


class TestPaceAccuracyScore:
    def test_no_execution_data_returns_default(self):
        s = _mp()  # std_dev=None
        score, mean_std, has_exec = _score_pace_accuracy([s])
        assert score == RPCS_ACCURACY_DEFAULT_SCORE
        assert mean_std is None
        assert has_exec is False

    def test_excellent_accuracy(self):
        s = _mp(std_dev=2.0)
        score, _, has_exec = _score_pace_accuracy([s])
        assert score == 100.0
        assert has_exec is True

    def test_poor_accuracy(self):
        s = _mp(std_dev=20.0)
        score, _, _ = _score_pace_accuracy([s])
        assert score == 0.0

    def test_midpoint_accuracy(self):
        mid = (3.0 + 15.0) / 2  # 9 s/km
        s = _mp(std_dev=mid)
        score, _, _ = _score_pace_accuracy([s])
        assert score == pytest.approx(50.0, abs=0.5)

    def test_averages_multiple_sessions(self):
        sessions = [_mp(std_dev=3.0), _mp(std_dev=15.0)]
        score, mean_std, _ = _score_pace_accuracy(sessions)
        assert mean_std == pytest.approx(9.0, abs=0.1)
        assert score == pytest.approx(50.0, abs=0.5)


# ===================================================================
# Composite scoring
# ===================================================================


class TestCompositeScore:
    def test_empty_sessions_gives_zero_composite(self):
        result = calculate_race_pace_confidence([])
        assert result.composite_score == 0.0
        assert result.sessions_counted == 0
        assert "No marathon-pace sessions recorded" in result.warnings

    def test_perfect_scores_give_100(self):
        # Session that maxes out all components
        s = _mp(
            total=RPCS_CUMULATIVE_TARGET_MIN,
            longest=RPCS_LONGEST_SEGMENT_TARGET_MIN,
            fatigue=RPCS_FATIGUE_TARGET_MIN,
            long_run=True,
            weeks_ago=0,
            std_dev=2.0,
        )
        result = calculate_race_pace_confidence([s])
        assert result.composite_score == 100.0
        assert result.sessions_counted == 1
        assert result.has_execution_data is True

    def test_composite_respects_weights(self):
        # Only cumulative is at target, others at zero
        s = _mp(
            total=RPCS_CUMULATIVE_TARGET_MIN,
            longest=0.0,
            fatigue=0.0,
            long_run=False,
            weeks_ago=0,
        )
        result = calculate_race_pace_confidence([s])
        # Cumulative=100 * 0.30 + segment=0 * 0.20 + fatigue=0 * 0.30
        # + accuracy=50 (default) * 0.20 = 30 + 10 = 40
        assert result.composite_score == pytest.approx(40.0, abs=0.5)

    def test_warning_for_low_cumulative(self):
        s = _mp(total=10.0, weeks_ago=0)
        result = calculate_race_pace_confidence([s])
        assert any("low cumulative" in w.lower() for w in result.warnings)

    def test_warning_for_no_long_runs(self):
        s = _mp(total=30.0, long_run=False)
        result = calculate_race_pace_confidence([s])
        assert any("long run" in w.lower() for w in result.warnings)

    def test_warning_for_no_execution_data(self):
        s = _mp(total=30.0)
        result = calculate_race_pace_confidence([s])
        assert any("execution data" in w.lower() for w in result.warnings)

    def test_no_execution_warning_when_data_present(self):
        s = _mp(total=30.0, std_dev=5.0)
        result = calculate_race_pace_confidence([s])
        assert not any("execution data" in w.lower() for w in result.warnings)

    def test_diagnostics_populated(self):
        s = _mp(
            total=60.0,
            longest=35.0,
            fatigue=20.0,
            long_run=True,
            std_dev=7.0,
        )
        result = calculate_race_pace_confidence([s])
        assert result.cumulative_mp_weighted_min == pytest.approx(60.0, abs=0.5)
        assert result.longest_segment_min == 35.0
        assert result.fatigue_mp_total_min == 20.0
        assert result.mean_pace_std_dev_s == pytest.approx(7.0, abs=0.1)
