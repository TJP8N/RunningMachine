"""Decision trace — full audit trail of how the engine reached its prescription."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import auto, IntEnum

from science_engine.models.recommendation import RuleRecommendation
from science_engine.models.workout import WorkoutPrescription


class RuleStatus(IntEnum):
    """Whether a rule fired, was skipped, or was not applicable."""

    FIRED = auto()
    SKIPPED = auto()
    NOT_APPLICABLE = auto()


@dataclass(frozen=True)
class RuleResult:
    """Record of a single rule's evaluation during an engine call."""

    rule_id: str
    status: RuleStatus
    recommendation: RuleRecommendation | None = None
    explanation: str = ""


@dataclass(frozen=True)
class DecisionTrace:
    """Complete audit trail for a single engine.prescribe() call.

    Records every rule's outcome so training decisions are fully
    explainable and debuggable.
    """

    rule_results: tuple[RuleResult, ...] = field(default_factory=tuple)
    final_prescription: WorkoutPrescription | None = None
    conflict_resolution_notes: str = ""
