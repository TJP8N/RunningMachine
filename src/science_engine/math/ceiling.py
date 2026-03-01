"""Performance Ceiling Model — marathon time projection with confidence intervals.

Combines converging physiological estimates (Critical Speed extrapolation +
VO2max trajectory) to project a race-day marathon time.  Running economy and
durability signals are designed as extension points for later.

References:
    Daniels & Gilbert (1979). Oxygen Power. Privately published.
    Smyth & Muniz-Pumares (2020). Calculation of critical speed from raw
        training data. Med Sci Sports Exerc 52(7):1606-1615.
    Jones (2006). The physiology of the world record holder for the women's
        marathon. Int J Sports Sci Coach 1(2):101-116.
    Billat et al. (2003). The concept of maximal lactate steady state.
        Sports Med 33(6):407-426.
    Riegel (1981). Athletic records and human endurance. American Scientist
        69(3):285-290.
    Midgley et al. (2007). Training to enhance the physiological determinants
        of long-distance running performance. Sports Med 37(10):857-880.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from science_engine.models.enums import (
    CEILING_BASE_UNCERTAINTY_PCT,
    CEILING_CONFIDENCE_LEVEL,
    CEILING_CS_PCT_ELITE,
    CEILING_CS_PCT_MIDPACK,
    CEILING_CS_PCT_NOVICE,
    CEILING_NO_TRAJECTORY_WIDENING,
    CEILING_VO2MAX_ELITE,
    CEILING_VO2MAX_MIDPACK,
    CEILING_VO2MAX_NOVICE,
    CEILING_WEIGHT_CS,
    CEILING_WEIGHT_VO2MAX,
    CEILING_Z_SCORE_85,
    DANIELS_A,
    DANIELS_B,
    DANIELS_C,
    DANIELS_PCT_A,
    DANIELS_PCT_B,
    DANIELS_PCT_C,
    DANIELS_PCT_D,
    DANIELS_PCT_E,
    MARATHON_DISTANCE_M,
    VO2MAX_MAX_WEEKLY_IMPROVEMENT,
    VO2MAX_MIN_HISTORY_POINTS,
    VO2MAX_PROJECTION_MAX_WEEKS,
)


@dataclass(frozen=True)
class CeilingEstimate:
    """Result of performance ceiling estimation.

    Attributes:
        marathon_time_s: Central estimate of marathon time in seconds.
        marathon_time_low_s: Lower bound (faster) of confidence interval.
        marathon_time_high_s: Upper bound (slower) of confidence interval.
        marathon_pace_s_per_km: Central marathon pace in seconds per km.
        confidence_level: Confidence level of the interval (e.g. 0.85).
        cs_estimate_s: Marathon time from CS signal alone (None if unavailable).
        vo2max_estimate_s: Marathon time from VO2max signal alone (None if unavailable).
        vo2max_projected: Projected VO2max at race date (None if unavailable).
        vo2max_weekly_trend: Weekly VO2max change rate (None if unavailable).
        pct_cs_used: Athlete-specific %CS used for CS estimate.
        data_quality: "HIGH", "MODERATE", "LOW", or "INSUFFICIENT".
        warnings: Diagnostic messages.
        signal_count: Number of convergence signals used (0-4).
    """

    marathon_time_s: float
    marathon_time_low_s: float
    marathon_time_high_s: float
    marathon_pace_s_per_km: float
    confidence_level: float
    cs_estimate_s: float | None = None
    vo2max_estimate_s: float | None = None
    vo2max_projected: float | None = None
    vo2max_weekly_trend: float | None = None
    pct_cs_used: float = 0.0
    data_quality: str = "INSUFFICIENT"
    warnings: tuple[str, ...] = field(default_factory=tuple)
    signal_count: int = 0


# ---------------------------------------------------------------------------
# Athlete-specific %CS interpolation
# ---------------------------------------------------------------------------


def athlete_specific_pct_cs(vo2max: float) -> float:
    """Interpolate marathon %CS based on athlete fitness level (VO2max).

    Returns a value between CEILING_CS_PCT_NOVICE (0.82) and
    CEILING_CS_PCT_ELITE (0.93), interpolated linearly between fitness tiers.

    Higher-fitness athletes sustain a higher fraction of CS over a marathon.

    Args:
        vo2max: Athlete's VO2max in ml/kg/min.

    Returns:
        Fraction of CS sustainable for a marathon (0.82-0.93).
    """
    if vo2max >= CEILING_VO2MAX_ELITE:
        return CEILING_CS_PCT_ELITE
    if vo2max <= CEILING_VO2MAX_NOVICE:
        return CEILING_CS_PCT_NOVICE
    if vo2max >= CEILING_VO2MAX_MIDPACK:
        # Interpolate between midpack and elite
        frac = (vo2max - CEILING_VO2MAX_MIDPACK) / (CEILING_VO2MAX_ELITE - CEILING_VO2MAX_MIDPACK)
        return CEILING_CS_PCT_MIDPACK + frac * (CEILING_CS_PCT_ELITE - CEILING_CS_PCT_MIDPACK)
    # Interpolate between novice and midpack
    frac = (vo2max - CEILING_VO2MAX_NOVICE) / (CEILING_VO2MAX_MIDPACK - CEILING_VO2MAX_NOVICE)
    return CEILING_CS_PCT_NOVICE + frac * (CEILING_CS_PCT_MIDPACK - CEILING_CS_PCT_NOVICE)


# ---------------------------------------------------------------------------
# Marathon time from Critical Speed
# ---------------------------------------------------------------------------


def marathon_time_from_cs(cs_m_per_s: float, pct_cs: float) -> float:
    """Estimate marathon time from Critical Speed and %CS.

    Args:
        cs_m_per_s: Critical Speed in metres per second.
        pct_cs: Fraction of CS sustainable for a marathon (0 < pct_cs <= 1).

    Returns:
        Marathon time in seconds.

    Raises:
        ValueError: If cs_m_per_s or pct_cs is non-positive or pct_cs > 1.
    """
    if cs_m_per_s <= 0:
        raise ValueError(f"CS must be positive, got {cs_m_per_s}")
    if not 0.0 < pct_cs <= 1.0:
        raise ValueError(f"pct_cs must be in (0, 1], got {pct_cs}")
    marathon_speed = cs_m_per_s * pct_cs
    return MARATHON_DISTANCE_M / marathon_speed


# ---------------------------------------------------------------------------
# Daniels-Gilbert model: marathon time from VO2max
# ---------------------------------------------------------------------------


def _pct_vo2max_at_duration(duration_min: float) -> float:
    """Fraction of VO2max sustainable at a given duration.

    Uses the Daniels-Gilbert decay curve.

    Args:
        duration_min: Exercise duration in minutes.

    Returns:
        Fraction of VO2max (e.g. 0.82 for marathon duration).
    """
    return (
        DANIELS_PCT_A
        + DANIELS_PCT_B * math.exp(DANIELS_PCT_C * duration_min)
        + DANIELS_PCT_D * math.exp(DANIELS_PCT_E * duration_min)
    )


def _velocity_from_vo2(vo2: float) -> float:
    """Inverse Daniels oxygen cost equation: VO2 → velocity in m/min.

    Solves: VO2 = DANIELS_A + DANIELS_B * v + DANIELS_C * v^2
    for v using the quadratic formula.

    Args:
        vo2: Oxygen consumption in ml/kg/min.

    Returns:
        Running velocity in metres per minute.

    Raises:
        ValueError: If the discriminant is negative (invalid VO2).
    """
    # Rearrange to: DANIELS_C * v^2 + DANIELS_B * v + (DANIELS_A - vo2) = 0
    a = DANIELS_C
    b = DANIELS_B
    c = DANIELS_A - vo2
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        raise ValueError(f"Invalid VO2 {vo2}: negative discriminant")
    return (-b + math.sqrt(discriminant)) / (2 * a)


def marathon_time_from_vo2max(vo2max: float, max_iterations: int = 20) -> float:
    """Estimate marathon time from VO2max using iterative Daniels solver.

    The sustainable VO2 depends on duration, and duration depends on speed
    (which depends on VO2), so we iterate until convergence.

    Args:
        vo2max: VO2max in ml/kg/min.
        max_iterations: Maximum iterations for convergence.

    Returns:
        Marathon time in seconds.

    Raises:
        ValueError: If vo2max is non-positive or solver doesn't converge.
    """
    if vo2max <= 0:
        raise ValueError(f"VO2max must be positive, got {vo2max}")

    # Initial guess: 180 min marathon
    duration_min = 180.0

    for _ in range(max_iterations):
        pct = _pct_vo2max_at_duration(duration_min)
        usable_vo2 = vo2max * pct
        velocity_m_per_min = _velocity_from_vo2(usable_vo2)
        new_duration_min = MARATHON_DISTANCE_M / velocity_m_per_min
        if abs(new_duration_min - duration_min) < 0.01:
            return new_duration_min * 60.0  # Convert to seconds
        duration_min = new_duration_min

    # Return best estimate even if not fully converged
    return duration_min * 60.0


# ---------------------------------------------------------------------------
# VO2max trajectory projection
# ---------------------------------------------------------------------------


def project_vo2max(
    history: tuple[tuple[str, float], ...],
    race_date: date,
    current_date: date,
) -> tuple[float | None, float | None]:
    """Project VO2max at race date using linear regression on history.

    Args:
        history: Chronological (ISO date string, VO2max value) pairs.
        race_date: Target race date for projection.
        current_date: Today's date.

    Returns:
        (projected_vo2max, weekly_trend) tuple.
        Both are None if insufficient data.
    """
    if len(history) < VO2MAX_MIN_HISTORY_POINTS:
        return None, None

    # Convert dates to weeks-from-first-measurement
    first_date = date.fromisoformat(history[0][0])
    x_weeks: list[float] = []
    y_vo2: list[float] = []
    for date_str, vo2 in history:
        d = date.fromisoformat(date_str)
        weeks = (d - first_date).days / 7.0
        x_weeks.append(weeks)
        y_vo2.append(vo2)

    # Simple linear regression: y = slope * x + intercept
    n = len(x_weeks)
    sum_x = sum(x_weeks)
    sum_y = sum(y_vo2)
    sum_xy = sum(x * y for x, y in zip(x_weeks, y_vo2))
    sum_xx = sum(x * x for x in x_weeks)

    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-10:
        # All measurements at same time — can't compute trend
        return None, None

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    # Cap weekly improvement rate
    weekly_trend = slope
    if weekly_trend > VO2MAX_MAX_WEEKLY_IMPROVEMENT:
        weekly_trend = VO2MAX_MAX_WEEKLY_IMPROVEMENT
        # Recompute intercept with capped slope using last data point
        last_x = x_weeks[-1]
        last_y = y_vo2[-1]
        intercept = last_y - weekly_trend * last_x

    # Project to race date
    race_weeks = (race_date - first_date).days / 7.0
    current_weeks = (current_date - first_date).days / 7.0

    # Don't project more than VO2MAX_PROJECTION_MAX_WEEKS beyond current data
    weeks_ahead = race_weeks - current_weeks
    if weeks_ahead > VO2MAX_PROJECTION_MAX_WEEKS:
        race_weeks = current_weeks + VO2MAX_PROJECTION_MAX_WEEKS

    projected = intercept + weekly_trend * race_weeks

    # Clamp to physiological range (20-90 ml/kg/min)
    projected = max(20.0, min(90.0, projected))

    return projected, weekly_trend


# ---------------------------------------------------------------------------
# Main entry: estimate ceiling
# ---------------------------------------------------------------------------


def estimate_ceiling(
    cs: float | None = None,
    se_cs: float = 0.0,
    vo2max: float | None = None,
    vo2max_history: tuple[tuple[str, float], ...] = (),
    race_date: date | None = None,
    current_date: date | None = None,
    confidence_level: float = CEILING_CONFIDENCE_LEVEL,
) -> CeilingEstimate:
    """Estimate performance ceiling by combining CS and VO2max signals.

    Convergence logic:
    - Neither signal → quality=INSUFFICIENT
    - CS-only → use CS estimate, quality=LOW
    - VO2max-only → use Daniels estimate, quality=LOW
    - Both → weighted average (60% CS / 40% VO2max), quality=MODERATE
    - Both + VO2max trajectory → quality=HIGH

    Args:
        cs: Critical Speed in m/s (None if unavailable).
        se_cs: Standard error of CS estimate.
        vo2max: Current VO2max in ml/kg/min (None if unavailable).
        vo2max_history: (ISO date, VO2max) pairs for trajectory projection.
        race_date: Target race date (None if unknown).
        current_date: Today's date (None → date.today()).
        confidence_level: Desired confidence level (default 0.85).

    Returns:
        CeilingEstimate with marathon time, CI, quality, and diagnostics.
    """
    if current_date is None:
        current_date = date.today()

    warnings: list[str] = []
    cs_estimate_s: float | None = None
    vo2max_estimate_s: float | None = None
    vo2max_projected: float | None = None
    vo2max_weekly_trend: float | None = None
    pct_cs_used = 0.0
    has_cs = cs is not None and cs > 0
    has_vo2max = vo2max is not None and vo2max > 0

    # --- CS signal ---
    if has_cs:
        pct_cs_used = athlete_specific_pct_cs(vo2max if has_vo2max else 45.0)
        cs_estimate_s = marathon_time_from_cs(cs, pct_cs_used)

    # --- VO2max signal ---
    effective_vo2max = vo2max
    has_trajectory = False
    if has_vo2max:
        # Try to project VO2max to race date
        if race_date is not None and len(vo2max_history) >= VO2MAX_MIN_HISTORY_POINTS:
            projected, trend = project_vo2max(vo2max_history, race_date, current_date)
            if projected is not None and trend is not None:
                vo2max_projected = projected
                vo2max_weekly_trend = trend
                effective_vo2max = projected
                has_trajectory = True

        vo2max_estimate_s = marathon_time_from_vo2max(effective_vo2max)

    # --- Convergence ---
    signal_count = 0
    if has_cs:
        signal_count += 1
    if has_vo2max:
        signal_count += 1
    if has_trajectory:
        signal_count += 1

    if not has_cs and not has_vo2max:
        # INSUFFICIENT
        return CeilingEstimate(
            marathon_time_s=0.0,
            marathon_time_low_s=0.0,
            marathon_time_high_s=0.0,
            marathon_pace_s_per_km=0.0,
            confidence_level=confidence_level,
            data_quality="INSUFFICIENT",
            warnings=("No CS or VO2max data available",),
            signal_count=0,
        )

    if has_cs and has_vo2max:
        # Weighted average
        central = (
            CEILING_WEIGHT_CS * cs_estimate_s
            + CEILING_WEIGHT_VO2MAX * vo2max_estimate_s
        )
        data_quality = "HIGH" if has_trajectory else "MODERATE"
    elif has_cs:
        central = cs_estimate_s
        data_quality = "LOW"
        warnings.append("VO2max data unavailable — using CS-only estimate")
    else:
        central = vo2max_estimate_s
        data_quality = "LOW"
        warnings.append("CS data unavailable — using VO2max-only estimate")

    # --- Confidence interval ---
    base_uncertainty = central * CEILING_BASE_UNCERTAINTY_PCT

    # Reduce uncertainty when signals agree, widen when they disagree
    if has_cs and has_vo2max:
        disagreement = abs(cs_estimate_s - vo2max_estimate_s) / central
        # Blended uncertainty: base scaled by signal agreement
        uncertainty = base_uncertainty * (0.7 + disagreement)
    else:
        uncertainty = base_uncertainty

    # CS standard error contribution
    if has_cs and se_cs > 0:
        # Convert speed SE to time SE: dt ≈ (D / v^2) * dv
        cs_time_se = (MARATHON_DISTANCE_M / (cs * pct_cs_used) ** 2) * se_cs * pct_cs_used
        uncertainty = math.sqrt(uncertainty ** 2 + cs_time_se ** 2)

    # Widen without trajectory data
    if not has_trajectory:
        uncertainty *= CEILING_NO_TRAJECTORY_WIDENING

    # Apply z-score for CI (lookup table avoids scipy dependency)
    _Z_SCORES = {
        0.80: 1.282,
        0.85: 1.440,
        0.90: 1.645,
        0.95: 1.960,
        0.99: 2.576,
    }
    z = _Z_SCORES.get(confidence_level, CEILING_Z_SCORE_85)
    half_width = z * uncertainty

    marathon_time_low_s = central - half_width
    marathon_time_high_s = central + half_width

    # Pace
    marathon_pace = central / (MARATHON_DISTANCE_M / 1000.0)

    return CeilingEstimate(
        marathon_time_s=central,
        marathon_time_low_s=marathon_time_low_s,
        marathon_time_high_s=marathon_time_high_s,
        marathon_pace_s_per_km=marathon_pace,
        confidence_level=confidence_level,
        cs_estimate_s=cs_estimate_s,
        vo2max_estimate_s=vo2max_estimate_s,
        vo2max_projected=vo2max_projected,
        vo2max_weekly_trend=vo2max_weekly_trend,
        pct_cs_used=pct_cs_used,
        data_quality=data_quality,
        warnings=tuple(warnings),
        signal_count=signal_count,
    )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_marathon_time(seconds: float) -> str:
    """Format seconds as 'H:MM:SS'.

    Args:
        seconds: Marathon time in seconds.

    Returns:
        Formatted time string, e.g. '2:52:30'.
    """
    if seconds <= 0:
        return "0:00:00"
    total_secs = int(round(seconds))
    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    secs = total_secs % 60
    return f"{hours}:{minutes:02d}:{secs:02d}"


def format_ceiling_range(estimate: CeilingEstimate) -> str:
    """Format a ceiling estimate as a human-readable range.

    Args:
        estimate: A CeilingEstimate from estimate_ceiling().

    Returns:
        String like 'Current ceiling: 2:52:00-2:58:00 at 85% confidence'.
    """
    if estimate.data_quality == "INSUFFICIENT":
        return "Insufficient data to estimate ceiling"
    low = format_marathon_time(estimate.marathon_time_low_s)
    high = format_marathon_time(estimate.marathon_time_high_s)
    pct = int(estimate.confidence_level * 100)
    return f"Current ceiling: {low}-{high} at {pct}% confidence"
