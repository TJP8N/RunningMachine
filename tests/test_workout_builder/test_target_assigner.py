"""Tests for target assigner — pace and HR target calculations."""

from __future__ import annotations

from datetime import date

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    IntensityLevel,
    ReadinessLevel,
    SessionType,
    TrainingPhase,
    ZoneType,
)
from science_engine.workout_builder.target_assigner import (
    PaceHRTargets,
    assign_targets,
)


def _make_athlete(**overrides) -> AthleteState:
    """Helper to create an athlete with sensible defaults."""
    defaults = dict(
        name="Test",
        age=35,
        weight_kg=70.0,
        sex="M",
        max_hr=190,
        lthr_bpm=170,
        lthr_pace_s_per_km=300,  # 5:00/km
        vo2max=50.0,
        resting_hr=48,
        current_phase=TrainingPhase.BUILD,
        current_week=8,
        total_plan_weeks=16,
        day_of_week=2,
    )
    defaults.update(overrides)
    return AthleteState(**defaults)


class TestTargetAssignerLTHR:
    """Tests for LTHR-derived pace/HR targets (no CS data)."""

    def test_returns_pace_hr_targets(self) -> None:
        state = _make_athlete()
        targets = assign_targets(state, ZoneType.ZONE_2)
        assert isinstance(targets, PaceHRTargets)
        assert targets.pace_target_low is not None
        assert targets.pace_target_high is not None
        assert targets.hr_target_low is not None
        assert targets.hr_target_high is not None

    def test_z2_pace_slower_than_z4(self) -> None:
        state = _make_athlete()
        z2 = assign_targets(state, ZoneType.ZONE_2)
        z4 = assign_targets(state, ZoneType.ZONE_4)
        # Higher zone → faster pace → lower s/km
        assert z2.pace_target_low > z4.pace_target_low

    def test_z2_hr_lower_than_z4(self) -> None:
        state = _make_athlete()
        z2 = assign_targets(state, ZoneType.ZONE_2)
        z4 = assign_targets(state, ZoneType.ZONE_4)
        assert z2.hr_target_low < z4.hr_target_low

    def test_hr_targets_are_integers(self) -> None:
        state = _make_athlete()
        targets = assign_targets(state, ZoneType.ZONE_3)
        assert isinstance(targets.hr_target_low, int)
        assert isinstance(targets.hr_target_high, int)


class TestTargetAssignerCS:
    """Tests for CS-derived pace targets."""

    def test_cs_derived_pace_targets(self) -> None:
        state = _make_athlete(critical_speed_m_per_s=4.2)
        targets = assign_targets(state, ZoneType.ZONE_3)
        assert targets.pace_target_low is not None
        # CS of 4.2 m/s → ~238 s/km at Z3 speeds, should be faster than LTHR estimate
        assert targets.pace_target_low > 0

    def test_cs_preferred_over_lthr(self) -> None:
        """When CS is available, pace targets should differ from LTHR-only."""
        state_no_cs = _make_athlete()
        state_with_cs = _make_athlete(critical_speed_m_per_s=4.2)
        t_no_cs = assign_targets(state_no_cs, ZoneType.ZONE_3)
        t_with_cs = assign_targets(state_with_cs, ZoneType.ZONE_3)
        # They should produce different pace targets
        assert t_no_cs.pace_target_low != t_with_cs.pace_target_low

    def test_cs_still_provides_hr_targets(self) -> None:
        """HR targets always come from LTHR, even when CS is available."""
        state = _make_athlete(critical_speed_m_per_s=4.2)
        targets = assign_targets(state, ZoneType.ZONE_2)
        assert targets.hr_target_low is not None
        assert targets.hr_target_high is not None


class TestIntensityModifiers:
    def test_b_moderate_makes_pace_slower(self) -> None:
        state = _make_athlete()
        full = assign_targets(state, ZoneType.ZONE_3, IntensityLevel.A_FULL)
        moderate = assign_targets(state, ZoneType.ZONE_3, IntensityLevel.B_MODERATE)
        # Slower pace = higher s/km
        assert moderate.pace_target_low > full.pace_target_low

    def test_c_easy_makes_pace_even_slower(self) -> None:
        state = _make_athlete()
        moderate = assign_targets(state, ZoneType.ZONE_3, IntensityLevel.B_MODERATE)
        easy = assign_targets(state, ZoneType.ZONE_3, IntensityLevel.C_EASY)
        assert easy.pace_target_low > moderate.pace_target_low

    def test_b_moderate_lowers_hr(self) -> None:
        state = _make_athlete()
        full = assign_targets(state, ZoneType.ZONE_3, IntensityLevel.A_FULL)
        moderate = assign_targets(state, ZoneType.ZONE_3, IntensityLevel.B_MODERATE)
        assert moderate.hr_target_high <= full.hr_target_high


class TestMarathonPace:
    def test_marathon_pace_from_cs(self) -> None:
        state = _make_athlete(critical_speed_m_per_s=4.2)
        targets = assign_targets(
            state, ZoneType.ZONE_3,
            session_type=SessionType.MARATHON_PACE,
        )
        # CS 4.2 m/s → MP ~84.8% → ~3.56 m/s → ~281 s/km
        assert targets.pace_target_low is not None
        assert 260 < targets.pace_target_low < 300

    def test_marathon_pace_from_lthr_fallback(self) -> None:
        state = _make_athlete()  # No CS data
        targets = assign_targets(
            state, ZoneType.ZONE_3,
            session_type=SessionType.MARATHON_PACE,
        )
        # LTHR pace 300 / 0.88 ≈ 341 s/km ± 3%
        assert targets.pace_target_low is not None
        assert 320 < targets.pace_target_low < 360


class TestHeatAdjustedTargets:
    """Tests for heat-adjusted pace targets."""

    def test_hot_weather_slows_pace(self) -> None:
        """30°C athlete gets slower pace targets than 15°C athlete."""
        cool = _make_athlete(temperature_celsius=15.0)
        hot = _make_athlete(temperature_celsius=30.0)
        t_cool = assign_targets(cool, ZoneType.ZONE_2)
        t_hot = assign_targets(hot, ZoneType.ZONE_2)
        # Slower = higher s/km
        assert t_hot.pace_target_low > t_cool.pace_target_low
        assert t_hot.pace_target_high > t_cool.pace_target_high

    def test_no_adjustment_when_temp_none(self) -> None:
        """Targets unchanged when temperature is None."""
        no_temp = _make_athlete(temperature_celsius=None)
        cool = _make_athlete(temperature_celsius=10.0)
        t_none = assign_targets(no_temp, ZoneType.ZONE_2)
        t_cool = assign_targets(cool, ZoneType.ZONE_2)
        assert t_none.pace_target_low == t_cool.pace_target_low

    def test_heat_stacks_with_intensity_modifier(self) -> None:
        """B_MODERATE + 30°C → both effects applied (slower than either alone)."""
        state_hot = _make_athlete(temperature_celsius=30.0)
        state_cool = _make_athlete(temperature_celsius=None)
        # Hot + full intensity
        t_hot_full = assign_targets(state_hot, ZoneType.ZONE_3, IntensityLevel.A_FULL)
        # Cool + moderate intensity
        t_cool_mod = assign_targets(state_cool, ZoneType.ZONE_3, IntensityLevel.B_MODERATE)
        # Hot + moderate intensity (both effects stacked)
        t_hot_mod = assign_targets(state_hot, ZoneType.ZONE_3, IntensityLevel.B_MODERATE)
        # Stacked should be slower than either effect alone
        assert t_hot_mod.pace_target_low > t_hot_full.pace_target_low
        assert t_hot_mod.pace_target_low > t_cool_mod.pace_target_low

    def test_hr_targets_unchanged_in_heat(self) -> None:
        """HR targets are identical regardless of temperature."""
        cool = _make_athlete(temperature_celsius=None)
        hot = _make_athlete(temperature_celsius=35.0)
        t_cool = assign_targets(cool, ZoneType.ZONE_3)
        t_hot = assign_targets(hot, ZoneType.ZONE_3)
        assert t_cool.hr_target_low == t_hot.hr_target_low
        assert t_cool.hr_target_high == t_hot.hr_target_high

    def test_humidity_increases_pace_adjustment(self) -> None:
        """High humidity makes pace targets even slower."""
        hot = _make_athlete(temperature_celsius=30.0)
        hot_humid = _make_athlete(temperature_celsius=30.0, humidity_pct=80.0)
        t_hot = assign_targets(hot, ZoneType.ZONE_2)
        t_humid = assign_targets(hot_humid, ZoneType.ZONE_2)
        assert t_humid.pace_target_low > t_hot.pace_target_low

    def test_marathon_pace_adjusted_in_heat(self) -> None:
        """Marathon pace session also gets heat adjustment."""
        cool = _make_athlete(temperature_celsius=None)
        hot = _make_athlete(temperature_celsius=30.0)
        t_cool = assign_targets(cool, ZoneType.ZONE_3, session_type=SessionType.MARATHON_PACE)
        t_hot = assign_targets(hot, ZoneType.ZONE_3, session_type=SessionType.MARATHON_PACE)
        assert t_hot.pace_target_low > t_cool.pace_target_low
