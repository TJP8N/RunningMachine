"""Marathon-pace session record — one completed MP workout."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MPSessionRecord:
    """Immutable record of a single completed marathon-pace session.

    Attributes:
        date: ISO date string of the session (YYYY-MM-DD).
        total_mp_time_min: Total time spent at marathon pace (minutes).
        longest_continuous_mp_min: Longest unbroken MP segment (minutes).
        mp_in_second_half_min: MP time in the second half of the session (minutes).
        was_long_run: Whether this was a long run (>= 90 min total).
        weeks_ago: How many weeks ago this session occurred (0 = this week).
        prescribed_pace_s_per_km: Target pace in seconds per km (None if unknown).
        actual_pace_s_per_km: Average actual pace in seconds per km (None if unknown).
        pace_std_dev_s_per_km: Standard deviation of pace (None if unknown).
    """

    date: str
    total_mp_time_min: float
    longest_continuous_mp_min: float
    mp_in_second_half_min: float = 0.0
    was_long_run: bool = False
    weeks_ago: float = 0.0
    prescribed_pace_s_per_km: float | None = None
    actual_pace_s_per_km: float | None = None
    pace_std_dev_s_per_km: float | None = None
