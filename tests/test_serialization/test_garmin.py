"""Tests for Garmin Connect JSON serialization."""

from __future__ import annotations

import json

import pytest

from science_engine.models.enums import (
    DurationType,
    IntensityLevel,
    SessionType,
    StepType,
    TrainingPhase,
)
from science_engine.models.structured_workout import StructuredWorkout, WorkoutStep
from science_engine.models.workout import WorkoutPrescription
from science_engine.serialization.garmin import (
    _build_target,
    _convert_repeat_step,
    _convert_step,
    _pace_s_per_km_to_m_per_s,
    to_garmin_json,
    to_garmin_json_string,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prescription(**overrides) -> WorkoutPrescription:
    defaults = {
        "session_type": SessionType.EASY,
        "intensity_level": IntensityLevel.A_FULL,
        "target_duration_min": 45.0,
        "phase": TrainingPhase.BASE,
        "week_number": 3,
    }
    defaults.update(overrides)
    return WorkoutPrescription(**defaults)


def _make_workout(steps, **overrides) -> StructuredWorkout:
    defaults = {
        "prescription": _make_prescription(),
        "steps": tuple(steps),
        "workout_title": "Easy Run",
        "workout_description": "Zone 2 easy run",
        "total_duration_min": 45.0,
    }
    defaults.update(overrides)
    return StructuredWorkout(**defaults)


# ---------------------------------------------------------------------------
# Pace conversion
# ---------------------------------------------------------------------------

class TestPaceConversion:
    def test_5_min_per_km(self):
        """5:00/km = 300 s/km → 3.333 m/s."""
        result = _pace_s_per_km_to_m_per_s(300.0)
        assert abs(result - 3.333) < 0.01

    def test_4_min_per_km(self):
        """4:00/km = 240 s/km → 4.167 m/s."""
        result = _pace_s_per_km_to_m_per_s(240.0)
        assert abs(result - 4.167) < 0.01

    def test_6_min_per_km(self):
        """6:00/km = 360 s/km → 2.778 m/s."""
        result = _pace_s_per_km_to_m_per_s(360.0)
        assert abs(result - 2.778) < 0.01

    def test_round_trip_within_tolerance(self):
        """Convert s/km → m/s → s/km and check within 0.1 s/km."""
        original = 330.0  # 5:30/km
        m_per_s = _pace_s_per_km_to_m_per_s(original)
        round_tripped = 1000.0 / m_per_s
        assert abs(round_tripped - original) < 0.1


# ---------------------------------------------------------------------------
# Duration conversion
# ---------------------------------------------------------------------------

class TestDurationConversion:
    def test_time_duration_to_seconds(self):
        """10 minutes → 600 seconds."""
        step = WorkoutStep(
            step_type=StepType.WARMUP,
            duration_type=DurationType.TIME,
            duration_value=10.0,
        )
        result = _convert_step(step, 1)
        assert result["endConditionValue"] == 600.0
        assert result["endCondition"]["conditionTypeKey"] == "time"

    def test_distance_duration_to_meters(self):
        """1.5 km → 1500 meters."""
        step = WorkoutStep(
            step_type=StepType.ACTIVE,
            duration_type=DurationType.DISTANCE,
            duration_value=1.5,
        )
        result = _convert_step(step, 1)
        assert result["endConditionValue"] == 1500.0
        assert result["endCondition"]["conditionTypeKey"] == "distance"

    def test_lap_button_duration(self):
        """LAP_BUTTON duration → conditionTypeKey 'lap.button'."""
        step = WorkoutStep(
            step_type=StepType.ACTIVE,
            duration_type=DurationType.LAP_BUTTON,
            duration_value=0.0,
        )
        result = _convert_step(step, 1)
        assert result["endCondition"]["conditionTypeKey"] == "lap.button"
        assert result["endConditionValue"] is None

    def test_zero_time_duration_becomes_lap_button(self):
        """Zero time duration falls back to lap button."""
        step = WorkoutStep(
            step_type=StepType.ACTIVE,
            duration_type=DurationType.TIME,
            duration_value=0.0,
        )
        result = _convert_step(step, 1)
        assert result["endCondition"]["conditionTypeKey"] == "lap.button"


# ---------------------------------------------------------------------------
# Step type mapping
# ---------------------------------------------------------------------------

class TestStepTypeMapping:
    @pytest.mark.parametrize(
        "step_type, expected_id, expected_key",
        [
            (StepType.WARMUP, 1, "warmup"),
            (StepType.COOLDOWN, 2, "cooldown"),
            (StepType.ACTIVE, 3, "interval"),
            (StepType.RECOVERY, 4, "recovery"),
            (StepType.REST, 5, "rest"),
        ],
    )
    def test_step_type_maps_to_garmin_id(self, step_type, expected_id, expected_key):
        step = WorkoutStep(step_type=step_type, duration_type=DurationType.TIME, duration_value=5.0)
        result = _convert_step(step, 1)
        assert result["stepType"]["stepTypeId"] == expected_id
        assert result["stepType"]["stepTypeKey"] == expected_key

    def test_repeat_step_type_id(self):
        step = WorkoutStep(
            step_type=StepType.REPEAT,
            repeat_count=4,
            child_steps=(
                WorkoutStep(step_type=StepType.ACTIVE, duration_type=DurationType.TIME, duration_value=3.0),
                WorkoutStep(step_type=StepType.RECOVERY, duration_type=DurationType.TIME, duration_value=2.0),
            ),
        )
        result = _convert_repeat_step(step, 1)
        assert result["stepType"]["stepTypeId"] == 6
        assert result["stepType"]["stepTypeKey"] == "repeat"


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

class TestTargets:
    def test_pace_target_faster_is_value_one(self):
        """Faster pace (lower s/km) → higher m/s → targetValueOne."""
        step = WorkoutStep(
            step_type=StepType.ACTIVE,
            pace_target_low=280.0,   # faster, 4:40/km
            pace_target_high=300.0,  # slower, 5:00/km
        )
        target = _build_target(step)
        assert target["targetType"]["workoutTargetTypeId"] == 6
        # targetValueOne should be the HIGHER m/s (from faster pace)
        assert target["targetValueOne"] > target["targetValueTwo"]
        assert abs(target["targetValueOne"] - 1000.0 / 280.0) < 0.01
        assert abs(target["targetValueTwo"] - 1000.0 / 300.0) < 0.01

    def test_hr_target(self):
        """HR targets passed as-is in BPM."""
        step = WorkoutStep(
            step_type=StepType.ACTIVE,
            hr_target_low=140,
            hr_target_high=155,
        )
        target = _build_target(step)
        assert target["targetType"]["workoutTargetTypeId"] == 4
        assert target["targetValueOne"] == 140
        assert target["targetValueTwo"] == 155

    def test_pace_takes_priority_over_hr(self):
        """When both pace and HR are set, pace wins."""
        step = WorkoutStep(
            step_type=StepType.ACTIVE,
            pace_target_low=280.0,
            pace_target_high=300.0,
            hr_target_low=140,
            hr_target_high=155,
        )
        target = _build_target(step)
        assert target["targetType"]["workoutTargetTypeId"] == 6  # pace, not HR

    def test_no_target(self):
        """No pace or HR → no target."""
        step = WorkoutStep(step_type=StepType.ACTIVE)
        target = _build_target(step)
        assert target["targetType"]["workoutTargetTypeId"] == 1
        assert target["targetValueOne"] is None
        assert target["targetValueTwo"] is None


# ---------------------------------------------------------------------------
# Repeat blocks
# ---------------------------------------------------------------------------

class TestRepeatBlocks:
    def test_repeat_group_structure(self):
        """REPEAT step becomes RepeatGroupDTO with nested children."""
        step = WorkoutStep(
            step_type=StepType.REPEAT,
            repeat_count=5,
            child_steps=(
                WorkoutStep(
                    step_type=StepType.ACTIVE,
                    duration_type=DurationType.DISTANCE,
                    duration_value=1.0,
                    pace_target_low=240.0,
                    pace_target_high=250.0,
                ),
                WorkoutStep(
                    step_type=StepType.RECOVERY,
                    duration_type=DurationType.TIME,
                    duration_value=2.0,
                ),
            ),
        )
        result = _convert_repeat_step(step, 1)
        assert result["type"] == "RepeatGroupDTO"
        assert result["endCondition"]["conditionTypeId"] == 7
        assert result["endConditionValue"] == 5
        assert len(result["workoutSteps"]) == 2
        assert result["workoutSteps"][0]["type"] == "ExecutableStepDTO"
        assert result["workoutSteps"][1]["type"] == "ExecutableStepDTO"

    def test_repeat_child_step_order(self):
        """Children within a repeat are numbered 1, 2, etc."""
        step = WorkoutStep(
            step_type=StepType.REPEAT,
            repeat_count=3,
            child_steps=(
                WorkoutStep(step_type=StepType.ACTIVE, duration_type=DurationType.TIME, duration_value=4.0),
                WorkoutStep(step_type=StepType.RECOVERY, duration_type=DurationType.TIME, duration_value=1.0),
            ),
        )
        result = _convert_repeat_step(step, 5)
        assert result["stepOrder"] == 5
        assert result["workoutSteps"][0]["stepOrder"] == 1
        assert result["workoutSteps"][1]["stepOrder"] == 2


# ---------------------------------------------------------------------------
# End-to-end: easy run
# ---------------------------------------------------------------------------

class TestEndToEndEasyRun:
    def test_easy_run_structure(self):
        """Easy run: warmup + active + cooldown → 3 steps, valid JSON."""
        steps = [
            WorkoutStep(step_type=StepType.WARMUP, duration_type=DurationType.TIME, duration_value=10.0,
                        hr_target_low=120, hr_target_high=140),
            WorkoutStep(step_type=StepType.ACTIVE, duration_type=DurationType.TIME, duration_value=30.0,
                        pace_target_low=330.0, pace_target_high=360.0),
            WorkoutStep(step_type=StepType.COOLDOWN, duration_type=DurationType.TIME, duration_value=5.0),
        ]
        workout = _make_workout(steps)
        result = to_garmin_json(workout)

        assert result["workoutName"] == "Easy Run"
        assert result["sportType"]["sportTypeKey"] == "running"
        ws = result["workoutSegments"][0]["workoutSteps"]
        assert len(ws) == 3
        assert ws[0]["stepType"]["stepTypeKey"] == "warmup"
        assert ws[1]["stepType"]["stepTypeKey"] == "interval"
        assert ws[2]["stepType"]["stepTypeKey"] == "cooldown"

    def test_easy_run_is_valid_json(self):
        """Serialized easy run can be parsed back from JSON."""
        steps = [
            WorkoutStep(step_type=StepType.WARMUP, duration_type=DurationType.TIME, duration_value=10.0),
            WorkoutStep(step_type=StepType.ACTIVE, duration_type=DurationType.TIME, duration_value=30.0),
            WorkoutStep(step_type=StepType.COOLDOWN, duration_type=DurationType.TIME, duration_value=5.0),
        ]
        workout = _make_workout(steps)
        json_str = to_garmin_json_string(workout)
        parsed = json.loads(json_str)
        assert parsed["workoutName"] == "Easy Run"


# ---------------------------------------------------------------------------
# End-to-end: interval workout
# ---------------------------------------------------------------------------

class TestEndToEndIntervals:
    def test_interval_workout(self):
        """Interval workout with repeat block produces RepeatGroupDTO."""
        steps = [
            WorkoutStep(step_type=StepType.WARMUP, duration_type=DurationType.TIME, duration_value=15.0),
            WorkoutStep(
                step_type=StepType.REPEAT,
                repeat_count=5,
                child_steps=(
                    WorkoutStep(
                        step_type=StepType.ACTIVE,
                        duration_type=DurationType.DISTANCE,
                        duration_value=1.0,
                        pace_target_low=240.0,
                        pace_target_high=250.0,
                    ),
                    WorkoutStep(
                        step_type=StepType.RECOVERY,
                        duration_type=DurationType.TIME,
                        duration_value=2.0,
                    ),
                ),
            ),
            WorkoutStep(step_type=StepType.COOLDOWN, duration_type=DurationType.TIME, duration_value=10.0),
        ]
        workout = _make_workout(
            steps,
            prescription=_make_prescription(session_type=SessionType.VO2MAX_INTERVALS),
            workout_title="VO2max Intervals",
        )
        result = to_garmin_json(workout)

        ws = result["workoutSegments"][0]["workoutSteps"]
        assert len(ws) == 3
        # Warmup
        assert ws[0]["type"] == "ExecutableStepDTO"
        # Repeat block
        assert ws[1]["type"] == "RepeatGroupDTO"
        assert ws[1]["endConditionValue"] == 5
        assert len(ws[1]["workoutSteps"]) == 2
        # Active interval within repeat
        active = ws[1]["workoutSteps"][0]
        assert active["endConditionValue"] == 1000.0  # 1km → 1000m
        assert active["targetType"]["workoutTargetTypeId"] == 6  # pace
        # Cooldown
        assert ws[2]["type"] == "ExecutableStepDTO"


# ---------------------------------------------------------------------------
# End-to-end: rest day
# ---------------------------------------------------------------------------

class TestEndToEndRestDay:
    def test_rest_day(self):
        """Rest day → minimal workout with no steps or single rest step."""
        steps = [
            WorkoutStep(step_type=StepType.REST, duration_type=DurationType.TIME, duration_value=0.0),
        ]
        workout = _make_workout(
            steps,
            prescription=_make_prescription(session_type=SessionType.REST, target_duration_min=0.0),
            workout_title="Rest Day",
            workout_description="Complete rest",
            total_duration_min=0.0,
        )
        result = to_garmin_json(workout)
        assert result["workoutName"] == "Rest Day"
        ws = result["workoutSegments"][0]["workoutSteps"]
        assert len(ws) == 1
        assert ws[0]["stepType"]["stepTypeKey"] == "rest"


# ---------------------------------------------------------------------------
# Text truncation
# ---------------------------------------------------------------------------

class TestTruncation:
    def test_name_truncation(self):
        """Workout name longer than 32 chars is truncated."""
        workout = _make_workout(
            [WorkoutStep(step_type=StepType.ACTIVE, duration_type=DurationType.TIME, duration_value=30.0)],
            workout_title="A" * 50,
        )
        result = to_garmin_json(workout)
        assert len(result["workoutName"]) == 32

    def test_description_truncation(self):
        """Description longer than 1024 chars is truncated."""
        workout = _make_workout(
            [WorkoutStep(step_type=StepType.ACTIVE, duration_type=DurationType.TIME, duration_value=30.0)],
            workout_description="B" * 2000,
        )
        result = to_garmin_json(workout)
        assert len(result["description"]) == 1024

    def test_step_notes_truncation(self):
        """Step notes longer than 200 chars are truncated."""
        step = WorkoutStep(
            step_type=StepType.ACTIVE,
            duration_type=DurationType.TIME,
            duration_value=10.0,
            step_notes="C" * 300,
        )
        result = _convert_step(step, 1)
        assert len(result["stepNotes"]) == 200


# ---------------------------------------------------------------------------
# to_garmin_json_string round-trip
# ---------------------------------------------------------------------------

class TestJsonStringRoundTrip:
    def test_json_string_round_trip(self):
        """to_garmin_json_string output can be parsed by json.loads."""
        steps = [
            WorkoutStep(step_type=StepType.WARMUP, duration_type=DurationType.TIME, duration_value=10.0),
            WorkoutStep(step_type=StepType.ACTIVE, duration_type=DurationType.TIME, duration_value=30.0,
                        pace_target_low=300.0, pace_target_high=330.0),
            WorkoutStep(step_type=StepType.COOLDOWN, duration_type=DurationType.TIME, duration_value=5.0),
        ]
        workout = _make_workout(steps)
        json_str = to_garmin_json_string(workout)
        parsed = json.loads(json_str)
        assert parsed == to_garmin_json(workout)

    def test_json_string_no_indent(self):
        """to_garmin_json_string with indent=None produces compact JSON."""
        steps = [
            WorkoutStep(step_type=StepType.ACTIVE, duration_type=DurationType.TIME, duration_value=10.0),
        ]
        workout = _make_workout(steps)
        json_str = to_garmin_json_string(workout, indent=None)
        assert "\n" not in json_str
        json.loads(json_str)  # still valid


# ---------------------------------------------------------------------------
# Step notes
# ---------------------------------------------------------------------------

class TestStepNotes:
    def test_notes_included(self):
        """Step notes are serialized into stepNotes field."""
        step = WorkoutStep(
            step_type=StepType.ACTIVE,
            duration_type=DurationType.TIME,
            duration_value=10.0,
            step_notes="Keep cadence above 170",
        )
        result = _convert_step(step, 1)
        assert result["stepNotes"] == "Keep cadence above 170"

    def test_empty_notes_omitted(self):
        """Empty step notes are not included in output."""
        step = WorkoutStep(
            step_type=StepType.ACTIVE,
            duration_type=DurationType.TIME,
            duration_value=10.0,
        )
        result = _convert_step(step, 1)
        assert "stepNotes" not in result


# ---------------------------------------------------------------------------
# Step order
# ---------------------------------------------------------------------------

class TestStepOrder:
    def test_top_level_step_ordering(self):
        """Top-level steps are numbered 1, 2, 3."""
        steps = [
            WorkoutStep(step_type=StepType.WARMUP, duration_type=DurationType.TIME, duration_value=10.0),
            WorkoutStep(step_type=StepType.ACTIVE, duration_type=DurationType.TIME, duration_value=20.0),
            WorkoutStep(step_type=StepType.COOLDOWN, duration_type=DurationType.TIME, duration_value=5.0),
        ]
        workout = _make_workout(steps)
        result = to_garmin_json(workout)
        ws = result["workoutSegments"][0]["workoutSteps"]
        assert [s["stepOrder"] for s in ws] == [1, 2, 3]
