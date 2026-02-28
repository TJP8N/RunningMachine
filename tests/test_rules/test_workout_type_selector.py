"""Tests for WorkoutTypeSelectorRule — session type by phase + day."""

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import SessionType, TrainingPhase
from science_engine.rules.optimization.workout_type_selector import WorkoutTypeSelectorRule


class TestWorkoutTypeSelectorRule:
    def setup_method(self) -> None:
        self.rule = WorkoutTypeSelectorRule()

    def _make_state(
        self, week: int, day: int, total_weeks: int = 16
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
            current_week=week,
            total_plan_weeks=total_weeks,
            day_of_week=day,
        )

    def test_produces_valid_session_type(self) -> None:
        for day in range(1, 8):
            state = self._make_state(week=5, day=day)
            rec = self.rule.evaluate(state)
            assert rec is not None
            assert rec.recommended_session_type is not None
            assert isinstance(rec.recommended_session_type, SessionType)

    def test_rest_day_on_monday(self) -> None:
        state = self._make_state(week=5, day=1)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.REST

    def test_sunday_is_long_run_in_base(self) -> None:
        # Week 2 of 16 should be BASE phase
        state = self._make_state(week=2, day=7)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.LONG_RUN

    def test_tuesday_quality_session_in_build(self) -> None:
        # Find a BUILD-phase week
        from science_engine.math.periodization import allocate_phases, get_phase_for_week

        phases = allocate_phases(16)
        build_week = None
        for w in range(1, 17):
            if get_phase_for_week(w, phases) == TrainingPhase.BUILD:
                build_week = w
                break
        assert build_week is not None

        state = self._make_state(week=build_week, day=2)
        rec = self.rule.evaluate(state)
        assert rec is not None
        # BUILD quality_1 = THRESHOLD
        assert rec.recommended_session_type == SessionType.THRESHOLD

    def test_recovery_week_monday_is_easy_not_rest(self) -> None:
        # Week 4 is a recovery week in a 16-week plan
        state = self._make_state(week=4, day=1)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.EASY

    def test_week_has_variety(self) -> None:
        """Different days should produce different session types."""
        session_types = set()
        for day in range(1, 8):
            state = self._make_state(week=5, day=day)
            rec = self.rule.evaluate(state)
            session_types.add(rec.recommended_session_type)
        # At least 3 different session types across the week
        assert len(session_types) >= 3

    def test_all_phases_all_days_produce_recommendation(self) -> None:
        for week in [1, 5, 9, 13, 16]:
            for day in range(1, 8):
                state = self._make_state(week=week, day=day)
                rec = self.rule.evaluate(state)
                assert rec is not None
