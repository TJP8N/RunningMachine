"""Structured workout models — step-by-step workout decomposition."""

from __future__ import annotations

from dataclasses import dataclass, field

from science_engine.models.enums import DurationType, StepType
from science_engine.models.workout import WorkoutPrescription


@dataclass(frozen=True)
class WorkoutStep:
    """A single step within a structured workout.

    Steps may be nested inside REPEAT blocks via ``child_steps``.
    Pace targets are in seconds per km (lower = faster).
    HR targets are in bpm.
    """

    step_type: StepType
    duration_type: DurationType = DurationType.TIME
    duration_value: float = 0.0        # min if TIME, km if DISTANCE
    pace_target_low: float | None = None   # faster bound (s/km)
    pace_target_high: float | None = None  # slower bound (s/km)
    hr_target_low: int | None = None       # bpm
    hr_target_high: int | None = None      # bpm
    step_notes: str = ""                   # max ~200 chars
    repeat_count: int = 1
    child_steps: tuple[WorkoutStep, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StructuredWorkout:
    """Complete structured workout with step-by-step coaching targets.

    Built from a WorkoutPrescription by the WorkoutBuilder. Contains
    all the information an athlete needs to execute the session.
    """

    prescription: WorkoutPrescription      # source prescription
    steps: tuple[WorkoutStep, ...]
    workout_title: str
    workout_description: str               # rich context (ACWR, readiness, etc.)
    total_duration_min: float
    total_distance_km: float | None = None
    decision_summary: str = ""             # top 2-3 firing rules
