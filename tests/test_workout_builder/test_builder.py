"""Tests for WorkoutBuilder — end-to-end structured workout generation."""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.decision_trace import DecisionTrace, RuleResult, RuleStatus
from science_engine.models.enums import (
    IntensityLevel,
    ReadinessLevel,
    SessionType,
    StepType,
    TrainingPhase,
)
from science_engine.models.structured_workout import StructuredWorkout
from science_engine.models.workout import WorkoutPrescription
from science_engine.workout_builder.builder import WorkoutBuilder


def _make_state(**overrides) -> AthleteState:
    defaults = dict(
        name="Test",
        age=35,
        weight_kg=70.0,
        sex="M",
        max_hr=190,
        lthr_bpm=170,
        lthr_pace_s_per_km=300,
        vo2max=50.0,
        resting_hr=48,
        current_phase=TrainingPhase.BUILD,
        current_week=8,
        total_plan_weeks=16,
        day_of_week=2,
        weekly_volume_history=(42.0, 44.0, 46.0, 48.0, 50.0),
        daily_loads=tuple([55.0] * 28),
        readiness=ReadinessLevel.NORMAL,
    )
    defaults.update(overrides)
    return AthleteState(**defaults)


def _make_prescription(**overrides) -> WorkoutPrescription:
    defaults = dict(
        session_type=SessionType.EASY,
        intensity_level=IntensityLevel.A_FULL,
        target_duration_min=45.0,
        phase=TrainingPhase.BUILD,
        week_number=8,
    )
    defaults.update(overrides)
    return WorkoutPrescription(**defaults)


def _make_trace(*fired_rule_ids: str) -> DecisionTrace:
    results = []
    for rule_id in fired_rule_ids:
        results.append(RuleResult(
            rule_id=rule_id,
            status=RuleStatus.FIRED,
            explanation=f"{rule_id} fired.",
        ))
    return DecisionTrace(rule_results=tuple(results))


class TestBuilderEasySession:
    def test_easy_has_warmup_main_cooldown(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.EASY, target_duration_min=45.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        assert isinstance(sw, StructuredWorkout)
        step_types = [s.step_type for s in sw.steps]
        assert StepType.WARMUP in step_types
        assert StepType.ACTIVE in step_types
        assert StepType.COOLDOWN in step_types

    def test_easy_has_pace_targets(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.EASY, target_duration_min=45.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        active_steps = [s for s in sw.steps if s.step_type == StepType.ACTIVE]
        assert len(active_steps) >= 1
        assert active_steps[0].pace_target_low is not None

    def test_easy_has_coaching_cues(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.EASY, target_duration_min=45.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        for step in sw.steps:
            assert step.step_notes != "", f"Step {step.step_type.name} missing cue"


class TestBuilderRestSession:
    def test_rest_single_step(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.REST, target_duration_min=0.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        assert len(sw.steps) == 1
        assert sw.steps[0].step_type == StepType.REST
        assert sw.total_duration_min == 0.0

    def test_rest_no_warmup_cooldown(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.REST, target_duration_min=0.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        step_types = {s.step_type for s in sw.steps}
        assert StepType.WARMUP not in step_types
        assert StepType.COOLDOWN not in step_types


class TestBuilderIntervalSessions:
    def test_threshold_has_repeat_block(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.THRESHOLD, target_duration_min=50.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        repeat_steps = [s for s in sw.steps if s.step_type == StepType.REPEAT]
        assert len(repeat_steps) == 1
        repeat = repeat_steps[0]
        assert repeat.repeat_count >= 1
        assert len(repeat.child_steps) == 2  # work + recovery

    def test_threshold_rep_count(self) -> None:
        """50 min - 15 warmup - 10 cooldown = 25 min main. 25 // (8+2) = 2 reps."""
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.THRESHOLD, target_duration_min=50.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        repeat = [s for s in sw.steps if s.step_type == StepType.REPEAT][0]
        assert repeat.repeat_count == 2

    def test_vo2max_has_repeat_block(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.VO2MAX_INTERVALS, target_duration_min=45.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        repeat_steps = [s for s in sw.steps if s.step_type == StepType.REPEAT]
        assert len(repeat_steps) == 1

    def test_vo2max_rep_count(self) -> None:
        """45 min - 15 warmup - 10 cooldown = 20 min main. 20 // (3+3) = 3 reps."""
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.VO2MAX_INTERVALS, target_duration_min=45.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        repeat = [s for s in sw.steps if s.step_type == StepType.REPEAT][0]
        assert repeat.repeat_count == 3


class TestBuilderLongRun:
    def test_long_run_has_two_main_segments(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.LONG_RUN, target_duration_min=90.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        active_steps = [s for s in sw.steps if s.step_type == StepType.ACTIVE]
        assert len(active_steps) == 2

    def test_long_run_late_segment_has_different_cue(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.LONG_RUN, target_duration_min=90.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        active_steps = [s for s in sw.steps if s.step_type == StepType.ACTIVE]
        assert active_steps[0].step_notes != active_steps[1].step_notes


class TestBuilderIntensityModifiers:
    def test_b_moderate_slower_pace(self) -> None:
        builder = WorkoutBuilder()
        state = _make_state()

        rx_full = _make_prescription(
            session_type=SessionType.TEMPO,
            target_duration_min=50.0,
            intensity_level=IntensityLevel.A_FULL,
        )
        rx_moderate = _make_prescription(
            session_type=SessionType.TEMPO,
            target_duration_min=50.0,
            intensity_level=IntensityLevel.B_MODERATE,
        )

        sw_full = builder.build(rx_full, state, _make_trace())
        sw_moderate = builder.build(rx_moderate, state, _make_trace())

        # Compare active step pace targets
        active_full = [s for s in sw_full.steps if s.step_type == StepType.ACTIVE][0]
        active_mod = [s for s in sw_moderate.steps if s.step_type == StepType.ACTIVE][0]
        # B_MODERATE should be slower (higher s/km)
        assert active_mod.pace_target_low > active_full.pace_target_low


class TestBuilderFueling:
    def test_long_run_over_90_min_gets_fueling(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.LONG_RUN, target_duration_min=120.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        fuel_steps = [s for s in sw.steps if "Gel" in s.step_notes]
        assert len(fuel_steps) >= 1

    def test_short_session_no_fueling(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.EASY, target_duration_min=45.0)
        sw = builder.build(rx, _make_state(), _make_trace())
        fuel_steps = [s for s in sw.steps if "Gel" in s.step_notes]
        assert len(fuel_steps) == 0


class TestBuilderDescription:
    def test_workout_has_title(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.TEMPO, target_duration_min=50.0)
        sw = builder.build(rx, _make_state(), _make_trace("periodization"))
        assert "BUILD" in sw.workout_title
        assert "Tempo" in sw.workout_title

    def test_workout_has_description(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription(session_type=SessionType.TEMPO, target_duration_min=50.0)
        sw = builder.build(rx, _make_state(), _make_trace("periodization"))
        assert len(sw.workout_description) > 0

    def test_decision_summary_populated(self) -> None:
        builder = WorkoutBuilder()
        rx = _make_prescription()
        sw = builder.build(rx, _make_state(), _make_trace("periodization", "progressive_overload"))
        assert "periodization" in sw.decision_summary


class TestBuilderAllSessionTypes:
    """Smoke test: every session type produces a valid StructuredWorkout."""

    def test_all_session_types_produce_valid_workout(self) -> None:
        builder = WorkoutBuilder()
        state = _make_state()
        trace = _make_trace()
        durations = {
            SessionType.REST: 0.0,
            SessionType.RECOVERY: 30.0,
            SessionType.EASY: 45.0,
            SessionType.LONG_RUN: 90.0,
            SessionType.TEMPO: 50.0,
            SessionType.THRESHOLD: 50.0,
            SessionType.VO2MAX_INTERVALS: 45.0,
            SessionType.MARATHON_PACE: 60.0,
            SessionType.RACE_SIMULATION: 120.0,
        }
        for st, dur in durations.items():
            rx = _make_prescription(session_type=st, target_duration_min=dur)
            sw = builder.build(rx, state, trace)
            assert isinstance(sw, StructuredWorkout), f"Failed for {st.name}"
            assert len(sw.steps) >= 1, f"No steps for {st.name}"
            assert sw.workout_title != "", f"No title for {st.name}"
