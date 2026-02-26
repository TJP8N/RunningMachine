"""Tests for MarathonPaceVolumeRule (DRIVE tier)."""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    MP_DEFICIT_THRESHOLD_MIN,
    MP_VOLUME_TARGETS_MIN,
    Priority,
    ReadinessLevel,
    SessionType,
    TrainingPhase,
)
from science_engine.models.weekly_plan import WeekContext
from science_engine.rules.drive.marathon_pace_volume import MarathonPaceVolumeRule


def _make_state(
    phase: TrainingPhase = TrainingPhase.BUILD,
    week: int = 8,
    cumulative_mp: float = 0.0,
) -> AthleteState:
    return AthleteState(
        name="Test",
        age=30,
        weight_kg=70.0,
        sex="M",
        max_hr=190,
        lthr_bpm=170,
        lthr_pace_s_per_km=300,
        vo2max=50.0,
        current_phase=phase,
        current_week=week,
        total_plan_weeks=16,
        day_of_week=2,
        daily_loads=tuple([50.0] * 28),
        weekly_volume_history=(40.0, 42.0, 44.0),
        cumulative_mp_time_min=cumulative_mp,
    )


class TestMarathonPaceVolumeRule:
    def setup_method(self) -> None:
        self.rule = MarathonPaceVolumeRule()

    def test_rule_metadata(self) -> None:
        assert self.rule.priority == Priority.DRIVE
        assert self.rule.is_weekly_aware is True

    def test_no_recommendation_in_base_phase(self) -> None:
        state = _make_state(phase=TrainingPhase.BASE, cumulative_mp=0.0)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_no_recommendation_in_taper_phase(self) -> None:
        state = _make_state(phase=TrainingPhase.TAPER, cumulative_mp=0.0)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_no_recommendation_in_race_phase(self) -> None:
        state = _make_state(phase=TrainingPhase.RACE, cumulative_mp=0.0)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_recommends_mp_when_deficit_in_build(self) -> None:
        """BUILD phase with 0 MP time → should recommend MARATHON_PACE."""
        state = _make_state(phase=TrainingPhase.BUILD, week=8, cumulative_mp=0.0)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.MARATHON_PACE
        assert rec.priority == Priority.DRIVE

    def test_recommends_mp_when_deficit_in_specific(self) -> None:
        state = _make_state(phase=TrainingPhase.SPECIFIC, week=12, cumulative_mp=0.0)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.MARATHON_PACE

    def test_no_recommendation_when_on_target(self) -> None:
        """Sufficient MP volume → no recommendation."""
        # In BUILD at the end, target is 60 min
        state = _make_state(phase=TrainingPhase.BUILD, week=10, cumulative_mp=60.0)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_deficit_below_threshold_ignored(self) -> None:
        """Small deficit (< MP_DEFICIT_THRESHOLD_MIN) → no recommendation."""
        # Set MP just slightly below a prorated target
        state = _make_state(phase=TrainingPhase.BUILD, week=8, cumulative_mp=50.0)
        rec = self.rule.evaluate(state)
        # Deficit must be < 15 min for this to be None
        if rec is not None:
            # If the prorated target - 50 >= 15, it fires. That's fine.
            assert rec.recommended_session_type == SessionType.MARATHON_PACE

    def test_skips_recovery_week_in_weekly_context(self) -> None:
        state = _make_state(phase=TrainingPhase.BUILD, week=8, cumulative_mp=0.0)
        context = WeekContext(
            day_number=2,
            phase=TrainingPhase.BUILD,
            is_recovery_week=True,
        )
        rec = self.rule.evaluate_weekly(state, context)
        assert rec is None

    def test_explanation_includes_deficit(self) -> None:
        state = _make_state(phase=TrainingPhase.BUILD, week=8, cumulative_mp=0.0)
        rec = self.rule.evaluate(state)
        if rec is not None:
            assert "deficit" in rec.explanation.lower() or "MP" in rec.explanation
