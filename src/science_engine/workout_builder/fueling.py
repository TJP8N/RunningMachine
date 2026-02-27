"""Fueling step insertion for long sessions.

Inserts gel/hydration reminders into the main set of workouts exceeding
60 minutes. Based on Jeukendrup (2011) carbohydrate intake guidelines.

Reference:
    Jeukendrup (2011). Nutrition for endurance sports: marathon, triathlon,
    and road cycling. J Sports Sci 29(sup1):S91-S99.
"""

from __future__ import annotations

import dataclasses

from science_engine.models.enums import (
    DurationType,
    FUELING_INTERVAL_MIN,
    FUELING_THRESHOLD_DURATION_MIN,
    SessionType,
    StepType,
)
from science_engine.models.structured_workout import WorkoutStep

# Maximum fueling steps per workout to avoid excessive interruptions
_MAX_FUELING_STEPS = 3

# Sessions that get electrolyte reminders at 90 min
_ELECTROLYTE_SESSIONS = frozenset({SessionType.LONG_RUN, SessionType.MARATHON_PACE})


def insert_fueling_steps(
    steps: list[WorkoutStep],
    total_duration_min: float,
    session_type: SessionType = SessionType.EASY,
) -> list[WorkoutStep]:
    """Insert fueling reminder steps into a workout's step list.

    Rules:
    - Only for sessions > FUELING_THRESHOLD_DURATION_MIN (60 min).
    - Insert a brief (0.25 min) RECOVERY step with fueling note every
      ~FUELING_INTERVAL_MIN (45 min) into the main set.
    - For LONG_RUN and MARATHON_PACE: add "Take electrolytes" at 90 min.
    - Never insert fueling into warmup/cooldown.
    - Capped at _MAX_FUELING_STEPS (3) per workout.

    Args:
        steps: The current list of WorkoutStep objects.
        total_duration_min: Total workout duration in minutes.
        session_type: The session type (for electrolyte logic).

    Returns:
        New list of WorkoutStep with fueling steps inserted.
    """
    if total_duration_min <= FUELING_THRESHOLD_DURATION_MIN:
        return list(steps)

    result: list[WorkoutStep] = []
    elapsed_min = 0.0
    next_fuel_at = float(FUELING_INTERVAL_MIN)
    fueling_count = 0
    electrolyte_inserted = False

    for step in steps:
        # Never insert fueling into warmup or cooldown
        if step.step_type in (StepType.WARMUP, StepType.COOLDOWN):
            result.append(step)
            elapsed_min += step.duration_value
            continue

        step_end = elapsed_min + step.duration_value

        # Check if we need to insert fueling during this step
        if fueling_count < _MAX_FUELING_STEPS and step_end > next_fuel_at:
            # Insert fueling step before the current step
            note = "Gel + 4oz water now."
            if (
                session_type in _ELECTROLYTE_SESSIONS
                and not electrolyte_inserted
                and elapsed_min >= 75  # Close to 90 min mark
            ):
                note = "Gel + 4oz water. Take electrolytes."
                electrolyte_inserted = True

            fuel_step = WorkoutStep(
                step_type=StepType.RECOVERY,
                duration_type=DurationType.TIME,
                duration_value=0.25,
                step_notes=note,
            )
            result.append(fuel_step)
            fueling_count += 1
            next_fuel_at += FUELING_INTERVAL_MIN

        result.append(step)
        elapsed_min = step_end

        # Check for electrolyte at 90 min if not yet inserted
        if (
            session_type in _ELECTROLYTE_SESSIONS
            and not electrolyte_inserted
            and elapsed_min >= 90
            and fueling_count < _MAX_FUELING_STEPS
        ):
            electrolyte_step = WorkoutStep(
                step_type=StepType.RECOVERY,
                duration_type=DurationType.TIME,
                duration_value=0.25,
                step_notes="Take electrolytes with water.",
            )
            result.append(electrolyte_step)
            electrolyte_inserted = True
            fueling_count += 1

    return result
