"""Tests for arbitrary-length periodization, date utilities, and recovery guards.

Verifies the hybrid fixed/proportional phase allocation model works correctly
for any plan length from 4 to 52+ weeks.
"""

from __future__ import annotations

from datetime import date

import pytest

from science_engine.math.periodization import (
    PhaseSpec,
    allocate_phases,
    compute_plan_weeks,
    derive_current_phase,
    get_phase_for_week,
    get_weekly_volume_target,
    is_recovery_week,
)
from science_engine.models.enums import (
    MAX_SPECIFIC_WEEKS,
    MAX_TAPER_WEEKS,
    MIN_PLAN_WEEKS,
    MIN_TAPER_WEEKS,
    RACE_WEEK_THRESHOLD,
    RECOVERY_WEEK_INTERVAL,
    TrainingPhase,
)


class TestAllocatePhasesArbitrary:
    """Tests for the hybrid allocation algorithm across all plan lengths."""

    @pytest.mark.parametrize("total_weeks", range(4, 53))
    def test_all_weeks_covered(self, total_weeks: int) -> None:
        """Every integer 4-52 produces phases covering all weeks with no gaps."""
        phases = allocate_phases(total_weeks)
        assert phases[0].start_week == 1
        assert phases[-1].end_week == total_weeks
        # No gaps
        for i in range(len(phases) - 1):
            assert phases[i].end_week + 1 == phases[i + 1].start_week

    @pytest.mark.parametrize("total_weeks", range(4, 53))
    def test_durations_sum_to_total(self, total_weeks: int) -> None:
        """Phase durations sum to total_weeks."""
        phases = allocate_phases(total_weeks)
        assert sum(p.duration_weeks for p in phases) == total_weeks

    @pytest.mark.parametrize("total_weeks", range(4, 53))
    def test_chronological_order(self, total_weeks: int) -> None:
        """Phases appear in strictly increasing order."""
        phases = allocate_phases(total_weeks)
        for i in range(len(phases) - 1):
            assert phases[i].phase < phases[i + 1].phase

    @pytest.mark.parametrize("total_weeks", range(4, 53))
    def test_every_phase_positive_duration(self, total_weeks: int) -> None:
        """No phase has zero or negative duration."""
        phases = allocate_phases(total_weeks)
        for p in phases:
            assert p.duration_weeks >= 1

    def test_below_minimum_raises(self) -> None:
        """Plans shorter than MIN_PLAN_WEEKS raise ValueError."""
        with pytest.raises(ValueError, match="at least"):
            allocate_phases(3)
        with pytest.raises(ValueError, match="at least"):
            allocate_phases(0)
        with pytest.raises(ValueError, match="at least"):
            allocate_phases(-1)

    def test_minimum_plan_works(self) -> None:
        """4-week plan produces a valid allocation."""
        phases = allocate_phases(4)
        assert phases[0].start_week == 1
        assert phases[-1].end_week == 4
        # Should have at least BASE and TAPER
        phase_types = {p.phase for p in phases}
        assert TrainingPhase.BASE in phase_types
        assert TrainingPhase.TAPER in phase_types


class TestTaperDuration:
    """TAPER must always be 2-3 weeks regardless of plan length."""

    @pytest.mark.parametrize("total_weeks", range(4, 53))
    def test_taper_bounded(self, total_weeks: int) -> None:
        phases = allocate_phases(total_weeks)
        taper_spec = [p for p in phases if p.phase == TrainingPhase.TAPER]
        assert len(taper_spec) == 1
        taper = taper_spec[0]
        assert MIN_TAPER_WEEKS <= taper.duration_weeks <= MAX_TAPER_WEEKS

    def test_short_plan_gets_min_taper(self) -> None:
        phases = allocate_phases(10)
        taper = [p for p in phases if p.phase == TrainingPhase.TAPER][0]
        assert taper.duration_weeks == MIN_TAPER_WEEKS

    def test_long_plan_gets_max_taper(self) -> None:
        phases = allocate_phases(24)
        taper = [p for p in phases if p.phase == TrainingPhase.TAPER][0]
        assert taper.duration_weeks == MAX_TAPER_WEEKS


class TestRaceWeek:
    """RACE week present for plans >= RACE_WEEK_THRESHOLD, absent otherwise."""

    @pytest.mark.parametrize("total_weeks", range(RACE_WEEK_THRESHOLD, 53))
    def test_race_present_for_long_plans(self, total_weeks: int) -> None:
        phases = allocate_phases(total_weeks)
        race_specs = [p for p in phases if p.phase == TrainingPhase.RACE]
        assert len(race_specs) == 1
        assert race_specs[0].duration_weeks == 1

    @pytest.mark.parametrize("total_weeks", range(4, RACE_WEEK_THRESHOLD))
    def test_no_race_for_short_plans(self, total_weeks: int) -> None:
        phases = allocate_phases(total_weeks)
        race_specs = [p for p in phases if p.phase == TrainingPhase.RACE]
        assert len(race_specs) == 0


class TestSpecificPhaseCap:
    """SPECIFIC phase is capped at MAX_SPECIFIC_WEEKS."""

    def test_long_plan_specific_capped(self) -> None:
        phases = allocate_phases(52)
        specific = [p for p in phases if p.phase == TrainingPhase.SPECIFIC][0]
        assert specific.duration_weeks <= MAX_SPECIFIC_WEEKS

    def test_34_week_plan(self) -> None:
        """User's scenario: ~34 weeks. SPECIFIC should not exceed 8."""
        phases = allocate_phases(34)
        specific = [p for p in phases if p.phase == TrainingPhase.SPECIFIC][0]
        assert specific.duration_weeks <= MAX_SPECIFIC_WEEKS


class TestBaseAbsorbsExtra:
    """For long plans, BASE gets the bulk of extra weeks."""

    def test_base_largest_in_long_plan(self) -> None:
        phases = allocate_phases(34)
        base = [p for p in phases if p.phase == TrainingPhase.BASE][0]
        build = [p for p in phases if p.phase == TrainingPhase.BUILD][0]
        assert base.duration_weeks > build.duration_weeks

    def test_base_much_larger_in_52_week_plan(self) -> None:
        phases = allocate_phases(52)
        base = [p for p in phases if p.phase == TrainingPhase.BASE][0]
        build = [p for p in phases if p.phase == TrainingPhase.BUILD][0]
        # BASE should be notably larger
        assert base.duration_weeks > build.duration_weeks
        # BASE should be at least 15 weeks in a 52-week plan
        assert base.duration_weeks >= 15


class TestShortPlans:
    """Plans < 10 weeks may skip BUILD."""

    def test_8_week_plan(self) -> None:
        phases = allocate_phases(8)
        assert phases[-1].end_week == 8
        phase_types = {p.phase for p in phases}
        assert TrainingPhase.BASE in phase_types
        assert TrainingPhase.SPECIFIC in phase_types
        assert TrainingPhase.TAPER in phase_types
        assert TrainingPhase.RACE not in phase_types

    def test_5_week_plan(self) -> None:
        phases = allocate_phases(5)
        assert phases[-1].end_week == 5
        phase_types = {p.phase for p in phases}
        assert TrainingPhase.BASE in phase_types
        assert TrainingPhase.TAPER in phase_types


class TestBackwardCompat:
    """Standard plan lengths produce reasonable splits."""

    @pytest.mark.parametrize("total_weeks", [12, 16, 20, 24])
    def test_standard_plans_have_all_training_phases(self, total_weeks: int) -> None:
        phases = allocate_phases(total_weeks)
        phase_types = {p.phase for p in phases}
        assert TrainingPhase.BASE in phase_types
        assert TrainingPhase.BUILD in phase_types
        assert TrainingPhase.SPECIFIC in phase_types
        assert TrainingPhase.TAPER in phase_types
        assert TrainingPhase.RACE in phase_types


class TestComputePlanWeeks:
    """Date math utility tests."""

    def test_basic_date_calculation(self) -> None:
        weeks = compute_plan_weeks(date(2026, 2, 25), date(2026, 10, 18))
        assert weeks == 33  # 233 days // 7 = 33

    def test_exact_weeks(self) -> None:
        weeks = compute_plan_weeks(date(2026, 1, 1), date(2026, 4, 2))
        assert weeks == 13  # 91 days // 7 = 13

    def test_partial_week_rounded_down(self) -> None:
        weeks = compute_plan_weeks(date(2026, 1, 1), date(2026, 1, 30))
        assert weeks == 4  # 29 days // 7 = 4

    def test_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="at least"):
            compute_plan_weeks(date(2026, 1, 1), date(2026, 1, 20))

    def test_same_day_raises(self) -> None:
        with pytest.raises(ValueError, match="at least"):
            compute_plan_weeks(date(2026, 6, 1), date(2026, 6, 1))


class TestDeriveCurrentPhase:
    """Convenience function tests."""

    def test_week_1_is_base(self) -> None:
        assert derive_current_phase(1, 16) == TrainingPhase.BASE

    def test_last_week_is_race(self) -> None:
        assert derive_current_phase(16, 16) == TrainingPhase.RACE

    def test_consistency_with_allocate(self) -> None:
        phases = allocate_phases(20)
        for week in range(1, 21):
            assert derive_current_phase(week, 20) == get_phase_for_week(week, phases)


class TestRecoveryWeekBoundary:
    """No more than RECOVERY_WEEK_INTERVAL consecutive hard weeks across boundaries."""

    @pytest.mark.parametrize("total_weeks", range(4, 53))
    def test_no_long_hard_streak(self, total_weeks: int) -> None:
        """No stretch of consecutive hard weeks exceeds RECOVERY_WEEK_INTERVAL."""
        phases = allocate_phases(total_weeks)
        consecutive_hard = 0
        for week in range(1, total_weeks + 1):
            phase = get_phase_for_week(week, phases)
            if phase in (TrainingPhase.TAPER, TrainingPhase.RACE):
                consecutive_hard = 0
                continue
            if is_recovery_week(week, phases):
                consecutive_hard = 0
            else:
                consecutive_hard += 1
                assert consecutive_hard <= RECOVERY_WEEK_INTERVAL, (
                    f"Plan {total_weeks}w: {consecutive_hard} consecutive hard "
                    f"weeks at week {week}"
                )

    def test_16_week_plan_recovery_schedule(self) -> None:
        """Spot-check recovery weeks for a 16-week plan."""
        phases = allocate_phases(16)
        recovery_weeks = [
            w for w in range(1, 17) if is_recovery_week(w, phases)
        ]
        # Should have some recovery weeks in BASE and BUILD
        assert len(recovery_weeks) >= 2
        # None in TAPER or RACE
        for w in recovery_weeks:
            phase = get_phase_for_week(w, phases)
            assert phase not in (TrainingPhase.TAPER, TrainingPhase.RACE)


class TestTaperVolumeExponential:
    """Exponential taper volume targets."""

    def test_taper_start_approximately_85_pct(self) -> None:
        """First taper week volume should be ~85% of peak."""
        phases = allocate_phases(16)
        taper_spec = [p for p in phases if p.phase == TrainingPhase.TAPER][0]
        peak = 70.0
        first_taper_vol = get_weekly_volume_target(
            taper_spec.start_week, phases, peak
        )
        # Should be close to 85% of peak (59.5 km)
        assert 55.0 <= first_taper_vol <= 65.0

    def test_taper_end_approximately_55_pct(self) -> None:
        """Last taper week volume should be ~55% of peak."""
        phases = allocate_phases(16)
        taper_spec = [p for p in phases if p.phase == TrainingPhase.TAPER][0]
        peak = 70.0
        last_taper_vol = get_weekly_volume_target(
            taper_spec.end_week, phases, peak
        )
        # Should be close to 55% of peak (38.5 km)
        assert 35.0 <= last_taper_vol <= 42.0

    def test_taper_monotonically_decreasing(self) -> None:
        """Volume decreases across taper weeks."""
        phases = allocate_phases(24)
        taper_spec = [p for p in phases if p.phase == TrainingPhase.TAPER][0]
        peak = 70.0
        volumes = [
            get_weekly_volume_target(w, phases, peak)
            for w in range(taper_spec.start_week, taper_spec.end_week + 1)
        ]
        for i in range(len(volumes) - 1):
            assert volumes[i] > volumes[i + 1], (
                f"Taper volume not decreasing: week {i}: {volumes[i]}, "
                f"week {i+1}: {volumes[i+1]}"
            )

    def test_race_week_volume_low(self) -> None:
        """RACE week volume should be ~30% of peak."""
        phases = allocate_phases(16)
        race_spec = [p for p in phases if p.phase == TrainingPhase.RACE][0]
        peak = 70.0
        race_vol = get_weekly_volume_target(race_spec.start_week, phases, peak)
        assert race_vol == pytest.approx(21.0, abs=1.0)
