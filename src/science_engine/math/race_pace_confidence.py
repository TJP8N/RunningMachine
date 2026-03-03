"""Race-Pace Confidence Scoring — composite readiness metric for marathon pace.

Assesses four dimensions of marathon-pace preparation quality:
1. Cumulative MP time (recency-weighted)
2. Longest continuous MP segment
3. MP running under fatigue (long-run second halves)
4. Pace accuracy / execution quality

References:
    Pfitzinger & Douglas (2009). Advanced Marathoning, 2nd ed.
    Daniels (2014). Daniels' Running Formula, 3rd ed.
"""

from __future__ import annotations

import math
from typing import Sequence

from science_engine.models.enums import (
    RPCS_ACCURACY_DEFAULT_SCORE,
    RPCS_ACCURACY_EXCELLENT_S,
    RPCS_ACCURACY_POOR_S,
    RPCS_CUMULATIVE_TARGET_MIN,
    RPCS_FATIGUE_MINIMUM_MIN,
    RPCS_FATIGUE_TARGET_MIN,
    RPCS_LONGEST_SEGMENT_FLOOR_MIN,
    RPCS_LONGEST_SEGMENT_TARGET_MIN,
    RPCS_RECENCY_HALF_LIFE_WEEKS,
    RPCS_WEIGHT_ACCURACY,
    RPCS_WEIGHT_CUMULATIVE,
    RPCS_WEIGHT_FATIGUE,
    RPCS_WEIGHT_LONGEST_SEGMENT,
)
from science_engine.models.mp_session_record import MPSessionRecord
from science_engine.models.race_pace_confidence import RacePaceConfidence


def _recency_weight(weeks_ago: float) -> float:
    """Exponential decay weight with configurable half-life.

    Returns a value in (0, 1] where 1.0 is the current week.
    """
    return math.exp(-math.log(2) * weeks_ago / RPCS_RECENCY_HALF_LIFE_WEEKS)


def _score_cumulative_mp(sessions: Sequence[MPSessionRecord]) -> tuple[float, float]:
    """Score cumulative recency-weighted MP time.

    Returns:
        (score 0-100, weighted_total_min).
    """
    weighted_total = sum(
        s.total_mp_time_min * _recency_weight(s.weeks_ago) for s in sessions
    )
    if weighted_total >= RPCS_CUMULATIVE_TARGET_MIN:
        return 100.0, weighted_total
    score = (weighted_total / RPCS_CUMULATIVE_TARGET_MIN) * 100.0
    return max(0.0, score), weighted_total


def _score_longest_segment(sessions: Sequence[MPSessionRecord]) -> tuple[float, float]:
    """Score the longest continuous MP segment across all sessions.

    Linear interpolation between floor (0%) and target (100%).

    Returns:
        (score 0-100, longest_segment_min).
    """
    if not sessions:
        return 0.0, 0.0
    longest = max(s.longest_continuous_mp_min for s in sessions)
    if longest >= RPCS_LONGEST_SEGMENT_TARGET_MIN:
        return 100.0, longest
    if longest <= RPCS_LONGEST_SEGMENT_FLOOR_MIN:
        return 0.0, longest
    span = RPCS_LONGEST_SEGMENT_TARGET_MIN - RPCS_LONGEST_SEGMENT_FLOOR_MIN
    score = ((longest - RPCS_LONGEST_SEGMENT_FLOOR_MIN) / span) * 100.0
    return score, longest


def _score_mp_under_fatigue(sessions: Sequence[MPSessionRecord]) -> tuple[float, float]:
    """Score MP time accumulated in second halves of long runs.

    Only counts sessions where was_long_run=True.
    Linear interpolation between minimum (0%) and target (100%).

    Returns:
        (score 0-100, fatigue_total_min).
    """
    fatigue_total = sum(
        s.mp_in_second_half_min for s in sessions if s.was_long_run
    )
    if fatigue_total >= RPCS_FATIGUE_TARGET_MIN:
        return 100.0, fatigue_total
    if fatigue_total <= RPCS_FATIGUE_MINIMUM_MIN:
        return 0.0, fatigue_total
    span = RPCS_FATIGUE_TARGET_MIN - RPCS_FATIGUE_MINIMUM_MIN
    score = ((fatigue_total - RPCS_FATIGUE_MINIMUM_MIN) / span) * 100.0
    return score, fatigue_total


def _score_pace_accuracy(
    sessions: Sequence[MPSessionRecord],
) -> tuple[float, float | None, bool]:
    """Score pace consistency from standard deviation of actual pace.

    When no execution data is available, returns the default score (50).
    Inverted scale: lower std dev = higher score.

    Returns:
        (score 0-100, mean_std_dev_s or None, has_execution_data).
    """
    std_devs = [
        s.pace_std_dev_s_per_km
        for s in sessions
        if s.pace_std_dev_s_per_km is not None
    ]
    if not std_devs:
        return RPCS_ACCURACY_DEFAULT_SCORE, None, False

    mean_std = sum(std_devs) / len(std_devs)
    if mean_std <= RPCS_ACCURACY_EXCELLENT_S:
        return 100.0, mean_std, True
    if mean_std >= RPCS_ACCURACY_POOR_S:
        return 0.0, mean_std, True
    span = RPCS_ACCURACY_POOR_S - RPCS_ACCURACY_EXCELLENT_S
    score = ((RPCS_ACCURACY_POOR_S - mean_std) / span) * 100.0
    return score, mean_std, True


def calculate_race_pace_confidence(
    mp_sessions: Sequence[MPSessionRecord],
    phase: object | None = None,
    current_week: int = 1,
    total_plan_weeks: int = 16,
) -> RacePaceConfidence:
    """Calculate composite race-pace confidence score from MP session history.

    Args:
        mp_sessions: Sequence of completed MP session records.
        phase: Current training phase (reserved for future phase-aware scoring).
        current_week: Current week in the plan (1-indexed).
        total_plan_weeks: Total weeks in the training plan.

    Returns:
        RacePaceConfidence with composite score and component breakdowns.
    """
    warnings: list[str] = []

    if not mp_sessions:
        warnings.append("No marathon-pace sessions recorded")
        return RacePaceConfidence(
            composite_score=0.0,
            cumulative_mp_score=0.0,
            longest_segment_score=0.0,
            mp_under_fatigue_score=0.0,
            pace_accuracy_score=RPCS_ACCURACY_DEFAULT_SCORE,
            sessions_counted=0,
            has_execution_data=False,
            warnings=tuple(warnings),
        )

    # Score each component
    cum_score, cum_weighted = _score_cumulative_mp(mp_sessions)
    seg_score, seg_longest = _score_longest_segment(mp_sessions)
    fat_score, fat_total = _score_mp_under_fatigue(mp_sessions)
    acc_score, acc_std, has_exec = _score_pace_accuracy(mp_sessions)

    # Weighted composite
    composite = (
        RPCS_WEIGHT_CUMULATIVE * cum_score
        + RPCS_WEIGHT_LONGEST_SEGMENT * seg_score
        + RPCS_WEIGHT_FATIGUE * fat_score
        + RPCS_WEIGHT_ACCURACY * acc_score
    )

    # Generate warnings
    if cum_score < 30:
        warnings.append("Very low cumulative MP volume — prioritize MP sessions")
    long_run_sessions = [s for s in mp_sessions if s.was_long_run]
    if not long_run_sessions:
        warnings.append("No MP running in long runs — add MP segments to long runs")
    if not has_exec:
        warnings.append("No pace execution data — accuracy score is estimated")

    return RacePaceConfidence(
        composite_score=round(composite, 1),
        cumulative_mp_score=round(cum_score, 1),
        longest_segment_score=round(seg_score, 1),
        mp_under_fatigue_score=round(fat_score, 1),
        pace_accuracy_score=round(acc_score, 1),
        cumulative_mp_weighted_min=round(cum_weighted, 1),
        longest_segment_min=round(seg_longest, 1),
        fatigue_mp_total_min=round(fat_total, 1),
        mean_pace_std_dev_s=round(acc_std, 2) if acc_std is not None else None,
        sessions_counted=len(mp_sessions),
        has_execution_data=has_exec,
        warnings=tuple(warnings),
    )
