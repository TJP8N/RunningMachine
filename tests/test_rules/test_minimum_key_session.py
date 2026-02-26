"""Tests for MinimumKeySessionRule (DRIVE tier)."""

from __future__ import annotations

from datetime import date

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    MIN_KEY_SESSIONS_PER_WEEK,
    Priority,
    ReadinessLevel,
    SessionType,
    TrainingPhase,
)
from science_engine.models.weekly_plan import WeekContext
from science_engine.models.workout import WorkoutPrescription
from science_engine.rules.drive.minimum_key_session import MinimumKeySessionRule


def _make_state(
    phase: TrainingPhase = TrainingPhase.BUILD,
    week: int = 8,
    day: int = 2,
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
        day_of_week=day,
        daily_loads=tuple([50.0] * 28),
        weekly_volume_history=(40.0, 42.0, 44.0),
    )


def _make_prescription(session_type: SessionType) -> WorkoutPrescription:
    from science_engine.models.enums import IntensityLevel
    return WorkoutPrescription(
        session_type=session_type,
        intensity_level=IntensityLevel.A_FULL,
        target_duration_min=50.0,
    )


class TestMinimumKeySessionRule:
    def setup_method(self) -> None:
        self.rule = MinimumKeySessionRule()

    def test_rule_metadata(self) -> None:
        assert self.rule.priority == Priority.DRIVE
        assert self.rule.is_weekly_aware is True

    def test_evaluate_returns_none_without_context(self) -> None:
        state = _make_state()
        assert self.rule.evaluate(state) is None

    def test_no_recommendation_when_enough_key_sessions(self) -> None:
        state = _make_state(day=5)
        context = WeekContext(
            day_number=5,
            planned_sessions=(
                _make_prescription(SessionType.THRESHOLD),
                _make_prescription(SessionType.VO2MAX_INTERVALS),
                _make_prescription(SessionType.EASY),
                _make_prescription(SessionType.EASY),
            ),
            phase=TrainingPhase.BUILD,
        )
        rec = self.rule.evaluate_weekly(state, context)
        assert rec is None

    def test_forces_key_session_on_last_day(self) -> None:
        """Day 7 with only 1 key session → must force another."""
        state = _make_state(day=7)
        context = WeekContext(
            day_number=7,
            planned_sessions=(
                _make_prescription(SessionType.REST),
                _make_prescription(SessionType.THRESHOLD),
                _make_prescription(SessionType.EASY),
                _make_prescription(SessionType.EASY),
                _make_prescription(SessionType.EASY),
                _make_prescription(SessionType.EASY),
            ),
            phase=TrainingPhase.BUILD,
        )
        rec = self.rule.evaluate_weekly(state, context)
        assert rec is not None
        assert rec.recommended_session_type in (
            SessionType.THRESHOLD, SessionType.VO2MAX_INTERVALS,
            SessionType.MARATHON_PACE, SessionType.TEMPO,
        )

    def test_recommends_on_quality_day(self) -> None:
        """Day 2 (Tuesday) with 0 key sessions → recommend."""
        state = _make_state(day=2)
        context = WeekContext(
            day_number=2,
            planned_sessions=(
                _make_prescription(SessionType.REST),
            ),
            phase=TrainingPhase.BUILD,
        )
        rec = self.rule.evaluate_weekly(state, context)
        assert rec is not None
        assert rec.priority == Priority.DRIVE

    def test_no_recommendation_on_non_quality_day_with_room(self) -> None:
        """Day 3 (Wednesday) with 0 key sessions but plenty of room → skip."""
        state = _make_state(day=3)
        context = WeekContext(
            day_number=3,
            planned_sessions=(
                _make_prescription(SessionType.REST),
                _make_prescription(SessionType.EASY),
            ),
            phase=TrainingPhase.BUILD,
        )
        rec = self.rule.evaluate_weekly(state, context)
        assert rec is None

    def test_skips_recovery_week(self) -> None:
        state = _make_state()
        context = WeekContext(
            day_number=2,
            planned_sessions=(),
            phase=TrainingPhase.BUILD,
            is_recovery_week=True,
        )
        rec = self.rule.evaluate_weekly(state, context)
        assert rec is None

    def test_skips_taper_phase(self) -> None:
        state = _make_state(phase=TrainingPhase.TAPER)
        context = WeekContext(
            day_number=2,
            planned_sessions=(),
            phase=TrainingPhase.TAPER,
        )
        rec = self.rule.evaluate_weekly(state, context)
        assert rec is None

    def test_build_phase_recommends_threshold(self) -> None:
        state = _make_state(phase=TrainingPhase.BUILD, day=2)
        context = WeekContext(
            day_number=2,
            planned_sessions=(),
            phase=TrainingPhase.BUILD,
        )
        rec = self.rule.evaluate_weekly(state, context)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.THRESHOLD

    def test_specific_phase_recommends_marathon_pace(self) -> None:
        state = _make_state(phase=TrainingPhase.SPECIFIC, day=2)
        context = WeekContext(
            day_number=2,
            planned_sessions=(),
            phase=TrainingPhase.SPECIFIC,
        )
        rec = self.rule.evaluate_weekly(state, context)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.MARATHON_PACE

    def test_base_phase_recommends_tempo(self) -> None:
        state = _make_state(phase=TrainingPhase.BASE, day=2)
        context = WeekContext(
            day_number=2,
            planned_sessions=(),
            phase=TrainingPhase.BASE,
        )
        rec = self.rule.evaluate_weekly(state, context)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.TEMPO
