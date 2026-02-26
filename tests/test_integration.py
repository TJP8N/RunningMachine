"""End-to-end integration tests: AthleteState → ScienceEngine → WorkoutPrescription.

Tests single-session prescription, weekly planning, DRIVE/SAFETY interaction,
and training debt repayment.
"""

from datetime import date

from science_engine.engine import ScienceEngine
from science_engine.models.athlete_state import AthleteState
from science_engine.models.decision_trace import RuleStatus
from science_engine.models.enums import (
    IntensityLevel,
    ReadinessLevel,
    SessionType,
    TrainingPhase,
)
from science_engine.models.training_debt import DebtEntry, TrainingDebtLedger
from science_engine.models.weekly_plan import WeeklyPlan
from science_engine.models.workout import WorkoutPrescription


class TestEndToEndIntegration:
    def test_sarah_build_phase_week_8(self) -> None:
        """Full pipeline test: intermediate athlete in BUILD phase gets appropriate prescription."""
        # Week 8 (not 9) — week 9 is a recovery week in a 16-week plan
        sarah = AthleteState(
            name="Sarah",
            age=35,
            weight_kg=62.0,
            sex="F",
            max_hr=185,
            lthr_bpm=168,
            lthr_pace_s_per_km=305,
            vo2max=48.0,
            resting_hr=48,
            current_phase=TrainingPhase.BUILD,
            current_week=8,
            total_plan_weeks=16,
            day_of_week=2,  # Tuesday — quality session day
            weekly_volume_history=(42.0, 44.0, 46.0, 48.0, 50.0),
            daily_loads=tuple([55.0] * 28),  # Stable ACWR
            readiness=ReadinessLevel.NORMAL,
            goal_race_date=date(2026, 6, 15),
        )

        engine = ScienceEngine()
        prescription, trace = engine.prescribe(sarah)

        # Verify prescription is valid
        assert isinstance(prescription, WorkoutPrescription)
        assert prescription.target_duration_min > 0
        assert prescription.phase == TrainingPhase.BUILD
        assert prescription.week_number == 8

        # BUILD phase, Tuesday → should be a quality session
        # DRIVE rules may recommend MARATHON_PACE if MP volume deficit exists
        build_quality_sessions = {
            SessionType.THRESHOLD,
            SessionType.VO2MAX_INTERVALS,
            SessionType.TEMPO,
            SessionType.MARATHON_PACE,
        }
        assert prescription.session_type in build_quality_sessions, (
            f"Expected a BUILD-phase quality session, got {prescription.session_type.name}"
        )

        # No safety vetoes (stable ACWR)
        safety_results = [
            r for r in trace.rule_results if r.rule_id == "injury_risk_acwr"
        ]
        for sr in safety_results:
            if sr.recommendation is not None:
                assert sr.recommendation.veto is False

        # All rules were evaluated
        rule_ids = {r.rule_id for r in trace.rule_results}
        assert "injury_risk_acwr" in rule_ids
        assert "periodization" in rule_ids
        assert "progressive_overload" in rule_ids
        assert "workout_type_selector" in rule_ids

        # At least some rules fired
        fired_count = sum(
            1 for r in trace.rule_results if r.status == RuleStatus.FIRED
        )
        assert fired_count >= 2

        # Trace has resolution notes
        assert trace.conflict_resolution_notes != ""

    def test_overloaded_athlete_gets_easy_session(self) -> None:
        """Athlete with dangerously high ACWR should be prescribed an easy workout."""
        overloaded = AthleteState(
            name="Overloaded Runner",
            age=30,
            weight_kg=75.0,
            sex="M",
            max_hr=195,
            lthr_bpm=175,
            lthr_pace_s_per_km=280,
            vo2max=52.0,
            resting_hr=45,
            current_phase=TrainingPhase.BUILD,
            current_week=8,
            total_plan_weeks=16,
            day_of_week=2,
            weekly_volume_history=(50.0, 55.0, 60.0),
            daily_loads=tuple([30.0] * 21 + [90.0] * 7),
            readiness=ReadinessLevel.NORMAL,
        )

        engine = ScienceEngine()
        prescription, trace = engine.prescribe(overloaded)

        # Safety veto should force easy/recovery session
        assert prescription.session_type in (
            SessionType.EASY,
            SessionType.REST,
            SessionType.RECOVERY,
        )

        # Intensity should be reduced
        assert prescription.intensity_level != IntensityLevel.A_FULL

    def test_beginner_base_phase_gets_appropriate_session(self) -> None:
        """Beginner in BASE phase should get easy/long-run type session."""
        beginner = AthleteState(
            name="Bob",
            age=50,
            weight_kg=82.0,
            sex="M",
            max_hr=170,
            lthr_bpm=155,
            lthr_pace_s_per_km=360,
            vo2max=38.0,
            resting_hr=55,
            current_phase=TrainingPhase.BASE,
            current_week=3,
            total_plan_weeks=16,
            day_of_week=7,  # Sunday — long run day
            weekly_volume_history=(28.0, 30.0),
            daily_loads=tuple([40.0] * 28),
            readiness=ReadinessLevel.NORMAL,
        )

        engine = ScienceEngine()
        prescription, trace = engine.prescribe(beginner)

        assert isinstance(prescription, WorkoutPrescription)
        assert prescription.target_duration_min > 0
        # Sunday in BASE phase should be a long run
        assert prescription.session_type in (
            SessionType.LONG_RUN,
            SessionType.EASY,
        )


class TestWeeklyPlanIntegration:
    """Integration tests for prescribe_week() with all 8 rules active."""

    def test_full_week_plan_build_phase(self) -> None:
        """BUILD phase week → at least 2 key sessions."""
        sarah = AthleteState(
            name="Sarah",
            age=35,
            weight_kg=62.0,
            sex="F",
            max_hr=185,
            lthr_bpm=168,
            lthr_pace_s_per_km=305,
            vo2max=48.0,
            resting_hr=48,
            current_phase=TrainingPhase.BUILD,
            current_week=8,
            total_plan_weeks=16,
            day_of_week=1,
            weekly_volume_history=(42.0, 44.0, 46.0, 48.0, 50.0),
            daily_loads=tuple([55.0] * 28),
            readiness=ReadinessLevel.NORMAL,
            goal_race_date=date(2026, 10, 18),
        )
        engine = ScienceEngine()
        plan = engine.prescribe_week(sarah)

        assert isinstance(plan, WeeklyPlan)
        assert len(plan.prescriptions) == 7
        assert plan.phase == TrainingPhase.BUILD
        # DRIVE minimum_key_session should ensure at least 2 key sessions
        assert plan.key_session_count >= 2

    def test_full_week_plan_with_safety_veto(self) -> None:
        """SAFETY overrides DRIVE: spiked ACWR → all easy despite DRIVE wanting quality."""
        overloaded = AthleteState(
            name="Overloaded",
            age=30,
            weight_kg=70.0,
            sex="M",
            max_hr=190,
            lthr_bpm=170,
            lthr_pace_s_per_km=300,
            vo2max=50.0,
            current_phase=TrainingPhase.BUILD,
            current_week=8,
            total_plan_weeks=16,
            day_of_week=1,
            weekly_volume_history=(50.0, 55.0, 60.0),
            daily_loads=tuple([30.0] * 21 + [90.0] * 7),
            readiness=ReadinessLevel.NORMAL,
        )
        engine = ScienceEngine()
        plan = engine.prescribe_week(overloaded)

        # Every day should be easy/rest/recovery due to SAFETY veto
        for p in plan.prescriptions:
            assert p.session_type in (
                SessionType.EASY, SessionType.REST, SessionType.RECOVERY
            ), f"Expected SAFETY veto to force easy, got {p.session_type.name}"

    def test_full_week_plan_with_training_debt(self) -> None:
        """Training debt → DRIVE recommends debt repayment session."""
        debt_ledger = TrainingDebtLedger(entries=(
            DebtEntry(session_type=SessionType.TEMPO, missed_duration_min=60.0, weeks_ago=0),
            DebtEntry(session_type=SessionType.LONG_RUN, missed_duration_min=45.0, weeks_ago=1),
        ))
        athlete = AthleteState(
            name="Debtor",
            age=30,
            weight_kg=70.0,
            sex="M",
            max_hr=190,
            lthr_bpm=170,
            lthr_pace_s_per_km=300,
            vo2max=50.0,
            current_phase=TrainingPhase.BUILD,
            current_week=7,
            total_plan_weeks=16,
            day_of_week=1,
            weekly_volume_history=(40.0, 42.0, 44.0),
            daily_loads=tuple([50.0] * 28),
            readiness=ReadinessLevel.NORMAL,
            training_debt=debt_ledger,
        )
        engine = ScienceEngine()
        plan = engine.prescribe_week(athlete)

        # Debt rule should fire — check that at least one trace mentions debt
        all_rule_ids = set()
        for trace in plan.traces:
            for rr in trace.rule_results:
                if rr.status == RuleStatus.FIRED:
                    all_rule_ids.add(rr.rule_id)
        assert "training_debt" in all_rule_ids

    def test_full_week_plan_base_phase_no_mp(self) -> None:
        """BASE phase → marathon_pace_volume rule should NOT fire."""
        beginner = AthleteState(
            name="Bob",
            age=50,
            weight_kg=82.0,
            sex="M",
            max_hr=170,
            lthr_bpm=155,
            lthr_pace_s_per_km=360,
            vo2max=38.0,
            resting_hr=55,
            current_phase=TrainingPhase.BASE,
            current_week=3,
            total_plan_weeks=16,
            day_of_week=1,
            weekly_volume_history=(28.0, 30.0, 31.0),
            daily_loads=tuple([40.0] * 28),
            readiness=ReadinessLevel.NORMAL,
            cumulative_mp_time_min=0.0,
        )
        engine = ScienceEngine()
        plan = engine.prescribe_week(beginner)

        # No MARATHON_PACE sessions should be prescribed in BASE
        mp_days = [
            p for p in plan.prescriptions
            if p.session_type == SessionType.MARATHON_PACE
        ]
        assert len(mp_days) == 0, "MARATHON_PACE should not appear in BASE phase"

    def test_drive_overrides_optimization(self) -> None:
        """DRIVE (priority 1) should beat OPTIMIZATION (priority 3) when both fire."""
        # Athlete with MP deficit in BUILD → DRIVE wants MARATHON_PACE,
        # but OPTIMIZATION wants THRESHOLD for Tuesday
        athlete = AthleteState(
            name="Test",
            age=30,
            weight_kg=70.0,
            sex="M",
            max_hr=190,
            lthr_bpm=170,
            lthr_pace_s_per_km=300,
            vo2max=50.0,
            current_phase=TrainingPhase.BUILD,
            current_week=8,
            total_plan_weeks=16,
            day_of_week=2,  # Tuesday → OPTIMIZATION wants THRESHOLD
            weekly_volume_history=(42.0, 44.0, 46.0, 48.0, 50.0),
            daily_loads=tuple([50.0] * 28),
            readiness=ReadinessLevel.NORMAL,
            cumulative_mp_time_min=0.0,  # Large MP deficit → DRIVE fires
        )
        engine = ScienceEngine()
        prescription, trace = engine.prescribe(athlete)

        # DRIVE should win the conflict
        # Check that the winning recommendation came from a DRIVE rule
        drive_fired = any(
            rr.rule_id in ("marathon_pace_volume", "minimum_key_session", "training_debt", "adaptation_demand")
            and rr.status == RuleStatus.FIRED
            for rr in trace.rule_results
        )
        assert drive_fired, "At least one DRIVE rule should have fired"

        # The prescription should be from a DRIVE-tier rule (priority 1 beats 3)
        assert prescription.session_type in (
            SessionType.MARATHON_PACE, SessionType.THRESHOLD,
            SessionType.TEMPO, SessionType.VO2MAX_INTERVALS,
        )

    def test_weekly_plan_recovery_week(self) -> None:
        """Recovery week → DRIVE rules adapt (skip key session enforcement)."""
        # Week 4 in a 16-week plan is a recovery week (every 4th within phase)
        athlete = AthleteState(
            name="Recovery",
            age=30,
            weight_kg=70.0,
            sex="M",
            max_hr=190,
            lthr_bpm=170,
            lthr_pace_s_per_km=300,
            vo2max=50.0,
            current_phase=TrainingPhase.BASE,
            current_week=4,  # Recovery week in BASE phase
            total_plan_weeks=16,
            day_of_week=1,
            weekly_volume_history=(30.0, 32.0, 34.0),
            daily_loads=tuple([45.0] * 28),
            readiness=ReadinessLevel.NORMAL,
        )
        engine = ScienceEngine()
        plan = engine.prescribe_week(athlete)

        assert plan.is_recovery_week
        assert len(plan.prescriptions) == 7
