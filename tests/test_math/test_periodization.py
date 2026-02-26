"""Tests for periodization math: phase allocation, volume, recovery weeks."""

import pytest

from science_engine.math.periodization import (
    allocate_phases,
    get_phase_for_week,
    get_session_distribution,
    get_weekly_volume_target,
    is_recovery_week,
)
from science_engine.models.enums import SessionType, TrainingPhase


class TestAllocatePhases:
    def test_16_week_plan_has_all_phases(self) -> None:
        phases = allocate_phases(16)
        phase_types = {p.phase for p in phases}
        assert TrainingPhase.BASE in phase_types
        assert TrainingPhase.BUILD in phase_types
        assert TrainingPhase.SPECIFIC in phase_types
        assert TrainingPhase.TAPER in phase_types

    def test_phases_cover_all_weeks(self) -> None:
        for total in [12, 16, 20, 24]:
            phases = allocate_phases(total)
            assert phases[0].start_week == 1
            assert phases[-1].end_week == total

    def test_no_gaps_between_phases(self) -> None:
        phases = allocate_phases(16)
        for i in range(len(phases) - 1):
            assert phases[i].end_week + 1 == phases[i + 1].start_week

    def test_phases_in_chronological_order(self) -> None:
        phases = allocate_phases(16)
        for i in range(len(phases) - 1):
            assert phases[i].phase < phases[i + 1].phase

    def test_nonstandard_length_works(self) -> None:
        phases = allocate_phases(18)
        assert phases[-1].end_week == 18


class TestGetPhaseForWeek:
    def test_first_week_is_base(self) -> None:
        phases = allocate_phases(16)
        assert get_phase_for_week(1, phases) == TrainingPhase.BASE

    def test_last_week_is_race(self) -> None:
        phases = allocate_phases(16)
        assert get_phase_for_week(16, phases) == TrainingPhase.RACE

    def test_out_of_range_raises(self) -> None:
        phases = allocate_phases(16)
        with pytest.raises(ValueError):
            get_phase_for_week(17, phases)

    def test_mid_plan_is_build_or_specific(self) -> None:
        phases = allocate_phases(16)
        mid_phase = get_phase_for_week(8, phases)
        assert mid_phase in (TrainingPhase.BUILD, TrainingPhase.SPECIFIC)


class TestWeeklyVolumeTarget:
    def test_taper_volume_lower_than_specific(self) -> None:
        phases = allocate_phases(16)
        peak_vol = 70.0
        # Find a specific-phase week and a taper-phase week
        specific_week = None
        taper_week = None
        for p in phases:
            if p.phase == TrainingPhase.SPECIFIC:
                specific_week = p.start_week
            if p.phase == TrainingPhase.TAPER:
                taper_week = p.start_week
        assert specific_week is not None and taper_week is not None
        specific_vol = get_weekly_volume_target(specific_week, phases, peak_vol)
        taper_vol = get_weekly_volume_target(taper_week, phases, peak_vol)
        assert taper_vol < specific_vol

    def test_volume_positive(self) -> None:
        phases = allocate_phases(16)
        for week in range(1, 17):
            vol = get_weekly_volume_target(week, phases, 70.0)
            assert vol > 0


class TestRecoveryWeeks:
    def test_recovery_weeks_present_in_base(self) -> None:
        phases = allocate_phases(16)
        recovery_weeks = [w for w in range(1, 17) if is_recovery_week(w, phases)]
        assert len(recovery_weeks) > 0

    def test_no_recovery_in_taper(self) -> None:
        phases = allocate_phases(16)
        for p in phases:
            if p.phase == TrainingPhase.TAPER:
                for w in range(p.start_week, p.end_week + 1):
                    assert not is_recovery_week(w, phases)

    def test_recovery_week_volume_reduced(self) -> None:
        phases = allocate_phases(16)
        peak_vol = 70.0
        for w in range(1, 17):
            if is_recovery_week(w, phases):
                vol = get_weekly_volume_target(w, phases, peak_vol)
                # Recovery week volume should be notably less than peak
                assert vol < peak_vol * 0.8


class TestSessionDistribution:
    def test_base_includes_long_run(self) -> None:
        dist = get_session_distribution(TrainingPhase.BASE)
        assert SessionType.LONG_RUN in dist

    def test_build_includes_intervals(self) -> None:
        dist = get_session_distribution(TrainingPhase.BUILD)
        assert SessionType.VO2MAX_INTERVALS in dist or SessionType.THRESHOLD in dist

    def test_all_phases_have_rest(self) -> None:
        for phase in TrainingPhase:
            dist = get_session_distribution(phase)
            assert SessionType.REST in dist
