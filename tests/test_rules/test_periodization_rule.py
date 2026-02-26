"""Tests for PeriodizationRule — session type by training phase."""

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import SessionType, TrainingPhase
from science_engine.rules.optimization.periodization_rule import PeriodizationRule


class TestPeriodizationRule:
    def setup_method(self) -> None:
        self.rule = PeriodizationRule()

    def _make_state(
        self, phase: TrainingPhase, week: int, total_weeks: int = 16
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
            total_plan_weeks=total_weeks,
        )

    def test_base_phase_recommends_long_run(self) -> None:
        state = self._make_state(TrainingPhase.BASE, week=2)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.LONG_RUN

    def test_build_phase_recommends_vo2max(self) -> None:
        state = self._make_state(TrainingPhase.BUILD, week=8)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.VO2MAX_INTERVALS

    def test_specific_phase_recommends_marathon_pace(self) -> None:
        state = self._make_state(TrainingPhase.SPECIFIC, week=12)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.MARATHON_PACE

    def test_always_returns_recommendation(self) -> None:
        for phase in TrainingPhase:
            state = self._make_state(phase, week=1, total_weeks=20)
            rec = self.rule.evaluate(state)
            assert rec is not None
            assert rec.recommended_session_type is not None

    def test_explanation_mentions_phase(self) -> None:
        state = self._make_state(TrainingPhase.BUILD, week=8)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert "BUILD" in rec.explanation
