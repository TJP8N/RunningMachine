"""Tests for StructuredWorkout and WorkoutStep data models."""

from __future__ import annotations

from science_engine.models.enums import (
    DurationType,
    IntensityLevel,
    SessionType,
    StepType,
    TrainingPhase,
)
from science_engine.models.structured_workout import StructuredWorkout, WorkoutStep
from science_engine.models.workout import WorkoutPrescription


class TestWorkoutStep:
    def test_create_simple_step(self) -> None:
        step = WorkoutStep(
            step_type=StepType.ACTIVE,
            duration_type=DurationType.TIME,
            duration_value=10.0,
        )
        assert step.step_type == StepType.ACTIVE
        assert step.duration_type == DurationType.TIME
        assert step.duration_value == 10.0
        assert step.pace_target_low is None
        assert step.hr_target_low is None
        assert step.repeat_count == 1
        assert step.child_steps == ()

    def test_step_is_frozen(self) -> None:
        step = WorkoutStep(step_type=StepType.WARMUP)
        try:
            step.step_type = StepType.COOLDOWN  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass

    def test_step_with_targets(self) -> None:
        step = WorkoutStep(
            step_type=StepType.ACTIVE,
            duration_value=8.0,
            pace_target_low=240.0,
            pace_target_high=260.0,
            hr_target_low=160,
            hr_target_high=172,
            step_notes="Threshold effort.",
        )
        assert step.pace_target_low == 240.0
        assert step.pace_target_high == 260.0
        assert step.hr_target_low == 160
        assert step.hr_target_high == 172
        assert step.step_notes == "Threshold effort."

    def test_repeat_block_with_children(self) -> None:
        work = WorkoutStep(step_type=StepType.ACTIVE, duration_value=3.0)
        recovery = WorkoutStep(step_type=StepType.RECOVERY, duration_value=3.0)
        repeat = WorkoutStep(
            step_type=StepType.REPEAT,
            repeat_count=5,
            child_steps=(work, recovery),
        )
        assert repeat.step_type == StepType.REPEAT
        assert repeat.repeat_count == 5
        assert len(repeat.child_steps) == 2
        assert repeat.child_steps[0].step_type == StepType.ACTIVE
        assert repeat.child_steps[1].step_type == StepType.RECOVERY

    def test_distance_duration_type(self) -> None:
        step = WorkoutStep(
            step_type=StepType.ACTIVE,
            duration_type=DurationType.DISTANCE,
            duration_value=5.0,
        )
        assert step.duration_type == DurationType.DISTANCE
        assert step.duration_value == 5.0


class TestStructuredWorkout:
    def _make_prescription(self) -> WorkoutPrescription:
        return WorkoutPrescription(
            session_type=SessionType.EASY,
            intensity_level=IntensityLevel.A_FULL,
            target_duration_min=45.0,
            phase=TrainingPhase.BUILD,
            week_number=8,
        )

    def test_create_structured_workout(self) -> None:
        rx = self._make_prescription()
        steps = (
            WorkoutStep(step_type=StepType.WARMUP, duration_value=10.0),
            WorkoutStep(step_type=StepType.ACTIVE, duration_value=30.0),
            WorkoutStep(step_type=StepType.COOLDOWN, duration_value=5.0),
        )
        sw = StructuredWorkout(
            prescription=rx,
            steps=steps,
            workout_title="BUILD W8 — Easy Run (45 min)",
            workout_description="Phase: BUILD | Week 8",
            total_duration_min=45.0,
        )
        assert sw.prescription == rx
        assert len(sw.steps) == 3
        assert sw.total_duration_min == 45.0
        assert sw.total_distance_km is None
        assert sw.decision_summary == ""

    def test_structured_workout_is_frozen(self) -> None:
        rx = self._make_prescription()
        sw = StructuredWorkout(
            prescription=rx,
            steps=(),
            workout_title="Test",
            workout_description="Test",
            total_duration_min=0.0,
        )
        try:
            sw.total_duration_min = 99.0  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass

    def test_structured_workout_with_distance(self) -> None:
        rx = self._make_prescription()
        sw = StructuredWorkout(
            prescription=rx,
            steps=(),
            workout_title="Test",
            workout_description="Test",
            total_duration_min=60.0,
            total_distance_km=10.0,
            decision_summary="test: summary",
        )
        assert sw.total_distance_km == 10.0
        assert sw.decision_summary == "test: summary"
