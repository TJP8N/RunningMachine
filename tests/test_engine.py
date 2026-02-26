"""Tests for ScienceEngine — full orchestration tests."""

from datetime import date

from science_engine.engine import ScienceEngine
from science_engine.models.athlete_state import AthleteState
from science_engine.models.decision_trace import RuleStatus
from science_engine.models.enums import ReadinessLevel, SessionType, TrainingPhase
from science_engine.models.weekly_plan import WeeklyPlan
from science_engine.models.workout import WorkoutPrescription


class TestScienceEngine:
    def test_prescribe_returns_prescription_and_trace(
        self, intermediate_athlete: AthleteState
    ) -> None:
        engine = ScienceEngine()
        prescription, trace = engine.prescribe(intermediate_athlete)
        assert isinstance(prescription, WorkoutPrescription)
        assert trace.final_prescription is not None

    def test_all_rules_evaluated(self, intermediate_athlete: AthleteState) -> None:
        engine = ScienceEngine()
        _, trace = engine.prescribe(intermediate_athlete)
        # At least the 4 implemented rules should appear
        rule_ids = [r.rule_id for r in trace.rule_results]
        assert "injury_risk_acwr" in rule_ids
        assert "periodization" in rule_ids
        assert "progressive_overload" in rule_ids
        assert "workout_type_selector" in rule_ids

    def test_decision_trace_has_resolution_notes(
        self, intermediate_athlete: AthleteState
    ) -> None:
        engine = ScienceEngine()
        _, trace = engine.prescribe(intermediate_athlete)
        assert trace.conflict_resolution_notes != ""

    def test_safety_veto_overrides_workout(self) -> None:
        """When ACWR is dangerously high, the engine should prescribe easy/rest."""
        spiked_loads = tuple([30.0] * 21 + [90.0] * 7)
        state = AthleteState(
            name="Overloaded",
            age=30,
            weight_kg=70.0,
            sex="M",
            max_hr=190,
            lthr_bpm=170,
            lthr_pace_s_per_km=300,
            vo2max=50.0,
            current_week=8,
            total_plan_weeks=16,
            day_of_week=2,
            daily_loads=spiked_loads,
            weekly_volume_history=(40.0, 45.0, 50.0),
        )
        engine = ScienceEngine()
        prescription, trace = engine.prescribe(state)
        # Safety veto should force an easy workout
        assert prescription.session_type in (SessionType.EASY, SessionType.REST, SessionType.RECOVERY)

    def test_prescription_has_phase_and_week(
        self, intermediate_athlete: AthleteState
    ) -> None:
        engine = ScienceEngine()
        prescription, _ = engine.prescribe(intermediate_athlete)
        assert prescription.phase == intermediate_athlete.current_phase
        assert prescription.week_number == intermediate_athlete.current_week

    def test_prescription_has_positive_duration(
        self, intermediate_athlete: AthleteState
    ) -> None:
        engine = ScienceEngine()
        prescription, _ = engine.prescribe(intermediate_athlete)
        assert prescription.target_duration_min >= 0


class TestWeeklyPlanning:
    """Tests for prescribe_week()."""

    def test_returns_seven_prescriptions(
        self, intermediate_athlete: AthleteState
    ) -> None:
        engine = ScienceEngine()
        plan = engine.prescribe_week(intermediate_athlete)
        assert isinstance(plan, WeeklyPlan)
        assert len(plan.prescriptions) == 7
        assert len(plan.traces) == 7

    def test_all_prescriptions_have_valid_session_type(
        self, intermediate_athlete: AthleteState
    ) -> None:
        engine = ScienceEngine()
        plan = engine.prescribe_week(intermediate_athlete)
        for p in plan.prescriptions:
            assert isinstance(p.session_type, SessionType)

    def test_phase_preserved(self, intermediate_athlete: AthleteState) -> None:
        engine = ScienceEngine()
        plan = engine.prescribe_week(intermediate_athlete)
        assert plan.phase == TrainingPhase.BUILD

    def test_week_number_preserved(self, intermediate_athlete: AthleteState) -> None:
        engine = ScienceEngine()
        plan = engine.prescribe_week(intermediate_athlete)
        assert plan.week_number == intermediate_athlete.current_week

    def test_total_duration_positive(self, intermediate_athlete: AthleteState) -> None:
        engine = ScienceEngine()
        plan = engine.prescribe_week(intermediate_athlete)
        assert plan.total_duration_min > 0

    def test_backward_compat_prescribe_unchanged(
        self, intermediate_athlete: AthleteState
    ) -> None:
        """prescribe() should still work exactly as before."""
        engine = ScienceEngine()
        prescription, trace = engine.prescribe(intermediate_athlete)
        assert isinstance(prescription, WorkoutPrescription)
        assert trace.final_prescription is not None

    def test_safety_veto_in_weekly_plan(self) -> None:
        """Safety veto should still apply within weekly planning."""
        spiked_loads = tuple([30.0] * 21 + [90.0] * 7)
        state = AthleteState(
            name="Overloaded",
            age=30,
            weight_kg=70.0,
            sex="M",
            max_hr=190,
            lthr_bpm=170,
            lthr_pace_s_per_km=300,
            vo2max=50.0,
            current_week=8,
            total_plan_weeks=16,
            day_of_week=1,
            daily_loads=spiked_loads,
            weekly_volume_history=(40.0, 45.0, 50.0),
        )
        engine = ScienceEngine()
        plan = engine.prescribe_week(state)
        # Every day should be easy/rest/recovery due to ACWR danger
        for p in plan.prescriptions:
            assert p.session_type in (
                SessionType.EASY, SessionType.REST, SessionType.RECOVERY
            )

    def test_is_key_session_helper(self) -> None:
        assert ScienceEngine.is_key_session(SessionType.THRESHOLD) is True
        assert ScienceEngine.is_key_session(SessionType.EASY) is False
        assert ScienceEngine.is_key_session(SessionType.REST) is False
        assert ScienceEngine.is_key_session(SessionType.LONG_RUN) is True
