"""Critical Speed (CS) model — linear D = CS*t + D' regression.

The Critical Speed model is the primary independent physiological model for
pacing. It uses race or time-trial data at multiple distances to determine
CS (the speed sustainable for extended durations) and D' (the finite work
capacity above CS).

References:
    Poole et al. (2016). Critical power: an important fatigue threshold in
    exercise physiology. Med Sci Sports Exerc 48(11):2320-2334.

    Jones et al. (2019). The maximal metabolic steady state: redefining the
    'gold standard'. Physiol Rep 7(10):e14098.

    Smyth & Muniz-Pumares (2020). Calculation of critical speed from raw
    training data. Med Sci Sports Exerc 52(7):1606-1615.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from science_engine.math.zones import ZoneBoundary
from science_engine.models.enums import (
    CS_MARATHON_PCT_DEFAULT,
    CS_MIN_DATA_POINTS,
    ZoneType,
)


@dataclass(frozen=True)
class CriticalSpeedResult:
    """Result of fitting the Critical Speed model.

    Attributes:
        critical_speed_m_per_s: CS in metres per second.
        d_prime_meters: D' (anaerobic distance reserve) in metres.
        r_squared: Coefficient of determination for the linear fit.
        se_cs: Standard error of CS estimate.
        se_d_prime: Standard error of D' estimate.
        residuals: Per-point residuals in metres.
    """

    critical_speed_m_per_s: float
    d_prime_meters: float
    r_squared: float
    se_cs: float = 0.0
    se_d_prime: float = 0.0
    residuals: tuple[float, ...] = field(default_factory=tuple)


def fit_critical_speed(
    distance_time_pairs: tuple[tuple[float, float], ...] | list[tuple[float, float]],
) -> CriticalSpeedResult:
    """Fit the linear Critical Speed model: D = CS * t + D'.

    Uses numpy.polyfit on the distance-time relationship. The slope is CS
    (m/s) and the intercept is D' (metres).

    Args:
        distance_time_pairs: Iterable of (distance_m, time_s) pairs.
            Must have at least CS_MIN_DATA_POINTS entries.

    Returns:
        CriticalSpeedResult with CS, D', R², standard errors, and residuals.

    Raises:
        ValueError: If fewer than CS_MIN_DATA_POINTS pairs are provided,
            or if any distance/time value is non-positive.
    """
    pairs = list(distance_time_pairs)
    if len(pairs) < CS_MIN_DATA_POINTS:
        raise ValueError(
            f"Need at least {CS_MIN_DATA_POINTS} distance-time pairs, "
            f"got {len(pairs)}"
        )

    for d, t in pairs:
        if d <= 0 or t <= 0:
            raise ValueError(
                f"Distance and time must be positive, got d={d}, t={t}"
            )

    times = np.array([t for _, t in pairs], dtype=np.float64)
    distances = np.array([d for d, _ in pairs], dtype=np.float64)

    # Linear fit: D = CS * t + D'
    # numpy.polyfit(x, y, 1) returns [slope, intercept]
    coeffs, residual_sum, _, _, _ = np.polyfit(times, distances, 1, full=True)
    cs = float(coeffs[0])
    d_prime = float(coeffs[1])

    # R² calculation
    d_predicted = cs * times + d_prime
    ss_res = float(np.sum((distances - d_predicted) ** 2))
    ss_tot = float(np.sum((distances - np.mean(distances)) ** 2))
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    # Standard errors via residual variance
    n = len(pairs)
    residuals_arr = distances - d_predicted
    if n > 2:
        mse = ss_res / (n - 2)
        t_mean = float(np.mean(times))
        ss_t = float(np.sum((times - t_mean) ** 2))
        se_cs = float(np.sqrt(mse / ss_t)) if ss_t > 0 else 0.0
        se_d_prime = float(
            np.sqrt(mse * (1.0 / n + t_mean**2 / ss_t)) if ss_t > 0 else 0.0
        )
    else:
        se_cs = 0.0
        se_d_prime = 0.0

    return CriticalSpeedResult(
        critical_speed_m_per_s=cs,
        d_prime_meters=d_prime,
        r_squared=r_squared,
        se_cs=se_cs,
        se_d_prime=se_d_prime,
        residuals=tuple(float(r) for r in residuals_arr),
    )


def cs_to_pace_s_per_km(cs_m_per_s: float) -> float:
    """Convert critical speed (m/s) to pace (seconds per km).

    Args:
        cs_m_per_s: Critical speed in metres per second.

    Returns:
        Pace in seconds per km.

    Raises:
        ValueError: If cs_m_per_s is non-positive.
    """
    if cs_m_per_s <= 0:
        raise ValueError(f"CS must be positive, got {cs_m_per_s}")
    return 1000.0 / cs_m_per_s


def marathon_pace_from_cs(
    cs_m_per_s: float,
    pct_cs: float = CS_MARATHON_PCT_DEFAULT,
) -> float:
    """Estimate marathon pace from Critical Speed.

    Marathon is run at approximately 84.8% of CS according to
    Smyth & Muniz-Pumares (2020).

    Args:
        cs_m_per_s: Critical speed in m/s.
        pct_cs: Fraction of CS for marathon pace (default 0.848).

    Returns:
        Marathon pace in seconds per km.

    Raises:
        ValueError: If cs_m_per_s is non-positive or pct_cs is out of range.
    """
    if cs_m_per_s <= 0:
        raise ValueError(f"CS must be positive, got {cs_m_per_s}")
    if not 0.0 < pct_cs <= 1.0:
        raise ValueError(f"pct_cs must be in (0, 1], got {pct_cs}")
    marathon_speed = cs_m_per_s * pct_cs
    return 1000.0 / marathon_speed


def calculate_cs_zones(cs_m_per_s: float) -> list[ZoneBoundary]:
    """Calculate pace zones derived from Critical Speed.

    Zone boundaries as fractions of CS:
        Z1 (Recovery):  < 70% CS
        Z2 (Aerobic):   70-85% CS
        Z3 (Threshold):  85-95% CS
        Z4 (VO2max):    95-110% CS
        Z5 (Anaerobic): > 110% CS

    These are expressed in s/km (lower bound = faster pace, higher number).

    Args:
        cs_m_per_s: Critical speed in metres per second.

    Returns:
        List of ZoneBoundary with pace in seconds per km.

    Raises:
        ValueError: If cs_m_per_s is non-positive.
    """
    if cs_m_per_s <= 0:
        raise ValueError(f"CS must be positive, got {cs_m_per_s}")

    # Zone boundaries as fractions of CS speed (lower_pct, upper_pct)
    zone_fractions = {
        ZoneType.ZONE_1: (0.0, 0.70),
        ZoneType.ZONE_2: (0.70, 0.85),
        ZoneType.ZONE_3: (0.85, 0.95),
        ZoneType.ZONE_4: (0.95, 1.10),
        ZoneType.ZONE_5: (1.10, 1.30),
    }

    zones: list[ZoneBoundary] = []
    for zone_type, (lower_frac, upper_frac) in zone_fractions.items():
        # Higher speed fraction → faster → lower s/km
        if lower_frac == 0.0:
            pace_upper = 1000.0  # Cap at ~16:40/km for Z1 floor
        else:
            pace_upper = 1000.0 / (cs_m_per_s * lower_frac)

        pace_lower = 1000.0 / (cs_m_per_s * upper_frac)

        zones.append(ZoneBoundary(zone=zone_type, lower=pace_lower, upper=pace_upper))
    return zones


def validate_cs_result(result: CriticalSpeedResult) -> list[str]:
    """Validate a CriticalSpeedResult for physiological plausibility.

    Checks:
    - R² ≥ 0.95 (good fit)
    - CS between 2.5 and 7.0 m/s (recreational jogger to elite)
    - D' between 50 and 500 m (physiological range)
    - CS positive and D' positive

    Args:
        result: The fitted CS model result.

    Returns:
        List of warning strings. Empty list means all checks pass.
    """
    warnings: list[str] = []

    if result.r_squared < 0.95:
        warnings.append(
            f"Low R²={result.r_squared:.3f} (expected ≥0.95). "
            f"Data may be inconsistent or contain errors."
        )

    if result.critical_speed_m_per_s <= 0:
        warnings.append(
            f"CS={result.critical_speed_m_per_s:.3f} m/s is non-positive. "
            f"Model fit failed."
        )
    elif result.critical_speed_m_per_s < 2.5:
        warnings.append(
            f"CS={result.critical_speed_m_per_s:.3f} m/s is unusually slow "
            f"(expected ≥2.5 for recreational runners)."
        )
    elif result.critical_speed_m_per_s > 7.0:
        warnings.append(
            f"CS={result.critical_speed_m_per_s:.3f} m/s is unusually fast "
            f"(expected ≤7.0 even for elites)."
        )

    if result.d_prime_meters < 0:
        warnings.append(
            f"D'={result.d_prime_meters:.1f} m is negative. "
            f"Model fit may be unreliable."
        )
    elif result.d_prime_meters < 50:
        warnings.append(
            f"D'={result.d_prime_meters:.1f} m is unusually low "
            f"(expected ≥50 m)."
        )
    elif result.d_prime_meters > 500:
        warnings.append(
            f"D'={result.d_prime_meters:.1f} m is unusually high "
            f"(expected ≤500 m)."
        )

    return warnings
