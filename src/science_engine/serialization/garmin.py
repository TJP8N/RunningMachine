"""Garmin Connect JSON serialization for StructuredWorkout objects.

Converts internal StructuredWorkout → Garmin Connect-compatible JSON that can
be imported via Garmin Connect web/app and synced to a Garmin watch.

All functions are pure (no I/O, no network calls).
"""

from __future__ import annotations

import json

from science_engine.models.enums import DurationType, StepType
from science_engine.models.structured_workout import StructuredWorkout, WorkoutStep

# Garmin enforces limits on certain text fields.
_GARMIN_NAME_MAX = 32
_GARMIN_DESCRIPTION_MAX = 1024
_GARMIN_STEP_NOTES_MAX = 200

# StepType → Garmin stepTypeKey mapping.
_STEP_TYPE_KEYS = {
    StepType.WARMUP: "warmup",
    StepType.COOLDOWN: "cooldown",
    StepType.ACTIVE: "interval",
    StepType.RECOVERY: "recovery",
    StepType.REST: "rest",
    StepType.REPEAT: "repeat",
}

_SPORT_TYPE = {
    "sportTypeId": 1,
    "sportTypeKey": "running",
    "displayOrder": 1,
}


def to_garmin_json(workout: StructuredWorkout) -> dict:
    """Convert a StructuredWorkout to a Garmin Connect-compatible dict."""
    steps = []
    for order, step in enumerate(workout.steps, start=1):
        if step.step_type == StepType.REPEAT:
            steps.append(_convert_repeat_step(step, order))
        else:
            steps.append(_convert_step(step, order))

    return {
        "workoutName": workout.workout_title[:_GARMIN_NAME_MAX],
        "description": workout.workout_description[:_GARMIN_DESCRIPTION_MAX],
        "sportType": dict(_SPORT_TYPE),
        "workoutSegments": [
            {
                "segmentOrder": 1,
                "sportType": dict(_SPORT_TYPE),
                "workoutSteps": steps,
            }
        ],
    }


def to_garmin_json_string(workout: StructuredWorkout, indent: int = 2) -> str:
    """Convert a StructuredWorkout to a Garmin-compatible JSON string."""
    return json.dumps(to_garmin_json(workout), indent=indent)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _convert_step(step: WorkoutStep, step_order: int) -> dict:
    """Build an ExecutableStepDTO for a non-repeat step."""
    result = {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": {
            "stepTypeId": step.step_type.value,
            "stepTypeKey": _STEP_TYPE_KEYS[step.step_type],
        },
    }

    # Duration / end condition
    if step.duration_type == DurationType.TIME and step.duration_value > 0:
        result["endCondition"] = {
            "conditionTypeId": 2,
            "conditionTypeKey": "time",
        }
        result["endConditionValue"] = step.duration_value * 60  # min → sec
    elif step.duration_type == DurationType.DISTANCE and step.duration_value > 0:
        result["endCondition"] = {
            "conditionTypeId": 3,
            "conditionTypeKey": "distance",
        }
        result["endConditionValue"] = step.duration_value * 1000  # km → m
    else:
        # LAP_BUTTON or zero-duration → lap button press
        result["endCondition"] = {
            "conditionTypeId": 1,
            "conditionTypeKey": "lap.button",
        }
        result["endConditionValue"] = None

    # Target
    result.update(_build_target(step))

    # Notes
    if step.step_notes:
        result["stepNotes"] = step.step_notes[:_GARMIN_STEP_NOTES_MAX]

    return result


def _convert_repeat_step(step: WorkoutStep, step_order: int) -> dict:
    """Build a RepeatGroupDTO for a REPEAT step with nested children."""
    child_steps = []
    for child_order, child in enumerate(step.child_steps, start=1):
        if child.step_type == StepType.REPEAT:
            child_steps.append(_convert_repeat_step(child, child_order))
        else:
            child_steps.append(_convert_step(child, child_order))

    return {
        "type": "RepeatGroupDTO",
        "stepOrder": step_order,
        "stepType": {
            "stepTypeId": StepType.REPEAT.value,
            "stepTypeKey": "repeat",
        },
        "endCondition": {
            "conditionTypeId": 7,
            "conditionTypeKey": "iterations",
        },
        "endConditionValue": step.repeat_count,
        "workoutSteps": child_steps,
    }


def _build_target(step: WorkoutStep) -> dict:
    """Build the target fields for a step.

    Priority: pace target > HR target > no target.
    Pace: faster pace (lower s/km) → higher m/s → targetValueOne.
    """
    if step.pace_target_low is not None and step.pace_target_high is not None:
        # Pace target — faster bound (low s/km) becomes higher m/s (targetValueOne)
        return {
            "targetType": {
                "workoutTargetTypeId": 6,
                "workoutTargetTypeKey": "pace.zone",
            },
            "targetValueOne": _pace_s_per_km_to_m_per_s(step.pace_target_low),
            "targetValueTwo": _pace_s_per_km_to_m_per_s(step.pace_target_high),
        }

    if step.hr_target_low is not None and step.hr_target_high is not None:
        return {
            "targetType": {
                "workoutTargetTypeId": 4,
                "workoutTargetTypeKey": "heart.rate.zone",
            },
            "targetValueOne": step.hr_target_low,
            "targetValueTwo": step.hr_target_high,
        }

    return {
        "targetType": {
            "workoutTargetTypeId": 1,
            "workoutTargetTypeKey": "no.target",
        },
        "targetValueOne": None,
        "targetValueTwo": None,
    }


def _pace_s_per_km_to_m_per_s(s_per_km: float) -> float:
    """Convert pace in seconds/km to speed in meters/second.

    Example: 300 s/km (5:00/km) → 1000/300 ≈ 3.333 m/s
    """
    return 1000.0 / s_per_km
