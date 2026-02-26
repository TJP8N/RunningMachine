"""Weekly planning models: WeekContext and WeeklyPlan."""

from __future__ import annotations

from dataclasses import dataclass, field

from science_engine.models.decision_trace import DecisionTrace
from science_engine.models.enums import SessionType, TrainingPhase
from science_engine.models.workout import WorkoutPrescription


@dataclass(frozen=True)
class WeekContext:
    """Context passed to weekly-aware rules during week planning.

    Tracks what has already been planned for earlier days so that
    weekly-aware rules can reason about the shape of the whole week.
    """

    day_number: int  # 1-7, the day currently being planned
    planned_sessions: tuple[WorkoutPrescription, ...] = field(default_factory=tuple)
    phase: TrainingPhase = TrainingPhase.BASE
    is_recovery_week: bool = False
    weekly_volume_target_km: float | None = None

    @property
    def key_sessions_planned(self) -> int:
        """Count key (quality) sessions already planned this week."""
        key_types = {
            SessionType.THRESHOLD,
            SessionType.VO2MAX_INTERVALS,
            SessionType.MARATHON_PACE,
            SessionType.TEMPO,
            SessionType.RACE_SIMULATION,
            SessionType.LONG_RUN,
        }
        return sum(1 for s in self.planned_sessions if s.session_type in key_types)

    @property
    def remaining_days(self) -> int:
        """Days left in the week including the current day."""
        return 8 - self.day_number

    @property
    def planned_volume_min(self) -> float:
        """Total planned duration in minutes so far."""
        return sum(s.target_duration_min for s in self.planned_sessions)


@dataclass(frozen=True)
class WeeklyPlan:
    """Output of ScienceEngine.prescribe_week(): 7 daily prescriptions + traces."""

    prescriptions: tuple[WorkoutPrescription, ...] = field(default_factory=tuple)
    traces: tuple[DecisionTrace, ...] = field(default_factory=tuple)
    phase: TrainingPhase = TrainingPhase.BASE
    week_number: int = 1
    is_recovery_week: bool = False

    @property
    def total_duration_min(self) -> float:
        return sum(p.target_duration_min for p in self.prescriptions)

    @property
    def key_session_count(self) -> int:
        key_types = {
            SessionType.THRESHOLD,
            SessionType.VO2MAX_INTERVALS,
            SessionType.MARATHON_PACE,
            SessionType.TEMPO,
            SessionType.RACE_SIMULATION,
            SessionType.LONG_RUN,
        }
        return sum(1 for p in self.prescriptions if p.session_type in key_types)
