"""Rule recommendation output — what a single rule suggests."""

from __future__ import annotations

from dataclasses import dataclass

from science_engine.models.enums import Priority, SessionType


@dataclass(frozen=True)
class RuleRecommendation:
    """A single rule's recommendation for the current training decision.

    Rules produce these; the ConflictResolver combines them into a final
    WorkoutPrescription.
    """

    rule_id: str
    rule_version: str
    priority: Priority

    # What the rule recommends
    recommended_session_type: SessionType | None = None
    intensity_modifier: float = 1.0  # 0.0-1.0, scales down intensity
    volume_modifier: float = 1.0  # 0.0-1.0, scales down volume
    target_duration_min: float | None = None
    target_distance_km: float | None = None

    # Control signals
    veto: bool = False  # If True, blocks high-intensity sessions
    explanation: str = ""
    confidence: float = 1.0  # 0.0-1.0, used for same-tier blending
