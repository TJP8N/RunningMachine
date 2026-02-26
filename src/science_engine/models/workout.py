"""Workout prescription — the final output of the science engine."""

from __future__ import annotations

from dataclasses import dataclass

from science_engine.models.enums import IntensityLevel, SessionType, TrainingPhase


@dataclass(frozen=True)
class WorkoutPrescription:
    """Final prescribed workout after all rules and conflict resolution.

    This is one half of the ScienceEngine.prescribe() return value.
    """

    session_type: SessionType
    intensity_level: IntensityLevel
    target_duration_min: float
    target_distance_km: float | None = None
    description: str = ""
    phase: TrainingPhase = TrainingPhase.BASE
    week_number: int = 1
