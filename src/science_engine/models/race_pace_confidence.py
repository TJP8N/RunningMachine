"""Race-Pace Confidence scoring result — composite readiness at marathon pace."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RacePaceConfidence:
    """Immutable result of race-pace confidence scoring (0-100).

    The composite score is a weighted sum of four component scores,
    each measuring a distinct aspect of marathon-pace preparedness.

    Attributes:
        composite_score: Overall confidence score (0-100).
        cumulative_mp_score: Score for total recency-weighted MP time (0-100).
        longest_segment_score: Score for longest continuous MP segment (0-100).
        mp_under_fatigue_score: Score for MP running in long-run second halves (0-100).
        pace_accuracy_score: Score for pace consistency / execution quality (0-100).
        cumulative_mp_weighted_min: Recency-weighted cumulative MP time (diagnostic).
        longest_segment_min: Longest continuous MP segment in minutes (diagnostic).
        fatigue_mp_total_min: Total MP time under fatigue conditions (diagnostic).
        mean_pace_std_dev_s: Mean pace standard deviation across sessions (diagnostic).
        sessions_counted: Number of MP sessions included in scoring.
        has_execution_data: Whether any session had pace execution data.
        warnings: Diagnostic messages about data quality or gaps.
    """

    composite_score: float
    cumulative_mp_score: float
    longest_segment_score: float
    mp_under_fatigue_score: float
    pace_accuracy_score: float
    cumulative_mp_weighted_min: float = 0.0
    longest_segment_min: float = 0.0
    fatigue_mp_total_min: float = 0.0
    mean_pace_std_dev_s: float | None = None
    sessions_counted: int = 0
    has_execution_data: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)
