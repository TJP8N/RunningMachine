"""Tests for fueling step insertion logic."""

from __future__ import annotations

from science_engine.models.enums import DurationType, SessionType, StepType
from science_engine.models.structured_workout import WorkoutStep
from science_engine.workout_builder.fueling import insert_fueling_steps


def _make_step(step_type: StepType, duration: float) -> WorkoutStep:
    return WorkoutStep(
        step_type=step_type,
        duration_type=DurationType.TIME,
        duration_value=duration,
    )


class TestFuelingInsertion:
    def test_no_fueling_for_short_session(self) -> None:
        """Sessions <= 60 min should not get fueling steps."""
        steps = [
            _make_step(StepType.WARMUP, 10.0),
            _make_step(StepType.ACTIVE, 35.0),
            _make_step(StepType.COOLDOWN, 5.0),
        ]
        result = insert_fueling_steps(steps, 50.0)
        fuel_steps = [s for s in result if "Gel" in s.step_notes or "electrolyte" in s.step_notes.lower()]
        assert len(fuel_steps) == 0

    def test_fueling_inserted_at_threshold(self) -> None:
        """Sessions > 60 min should get fueling steps."""
        steps = [
            _make_step(StepType.WARMUP, 10.0),
            _make_step(StepType.ACTIVE, 60.0),
            _make_step(StepType.COOLDOWN, 5.0),
        ]
        result = insert_fueling_steps(steps, 75.0)
        fuel_steps = [s for s in result if "Gel" in s.step_notes]
        assert len(fuel_steps) >= 1

    def test_no_fueling_in_warmup_cooldown(self) -> None:
        """Fueling should never be inserted into warmup or cooldown steps."""
        steps = [
            _make_step(StepType.WARMUP, 50.0),
            _make_step(StepType.ACTIVE, 40.0),
            _make_step(StepType.COOLDOWN, 30.0),
        ]
        result = insert_fueling_steps(steps, 120.0)
        for i, s in enumerate(result):
            if "Gel" in s.step_notes or "electrolyte" in s.step_notes.lower():
                # Fueling steps should be RECOVERY type, not WARMUP/COOLDOWN
                assert s.step_type == StepType.RECOVERY

    def test_max_three_fueling_steps(self) -> None:
        """No more than 3 fueling steps per workout."""
        steps = [
            _make_step(StepType.WARMUP, 10.0),
            _make_step(StepType.ACTIVE, 200.0),
            _make_step(StepType.COOLDOWN, 10.0),
        ]
        result = insert_fueling_steps(steps, 220.0)
        fuel_steps = [
            s for s in result
            if s.step_notes and ("Gel" in s.step_notes or "electrolyte" in s.step_notes.lower())
        ]
        assert len(fuel_steps) <= 3

    def test_fueling_step_is_brief(self) -> None:
        """Fueling steps should be very short (0.25 min)."""
        steps = [
            _make_step(StepType.WARMUP, 10.0),
            _make_step(StepType.ACTIVE, 60.0),
            _make_step(StepType.COOLDOWN, 5.0),
        ]
        result = insert_fueling_steps(steps, 75.0)
        for s in result:
            if "Gel" in s.step_notes:
                assert s.duration_value == 0.25

    def test_electrolyte_for_long_run(self) -> None:
        """LONG_RUN sessions should get electrolyte reminders."""
        steps = [
            _make_step(StepType.WARMUP, 10.0),
            _make_step(StepType.ACTIVE, 100.0),
            _make_step(StepType.COOLDOWN, 5.0),
        ]
        result = insert_fueling_steps(steps, 115.0, SessionType.LONG_RUN)
        electrolyte_steps = [
            s for s in result
            if "electrolyte" in s.step_notes.lower()
        ]
        assert len(electrolyte_steps) >= 1

    def test_electrolyte_for_marathon_pace(self) -> None:
        """MARATHON_PACE sessions should also get electrolyte reminders."""
        steps = [
            _make_step(StepType.WARMUP, 15.0),
            _make_step(StepType.ACTIVE, 90.0),
            _make_step(StepType.COOLDOWN, 10.0),
        ]
        result = insert_fueling_steps(steps, 115.0, SessionType.MARATHON_PACE)
        electrolyte_steps = [
            s for s in result
            if "electrolyte" in s.step_notes.lower()
        ]
        assert len(electrolyte_steps) >= 1
