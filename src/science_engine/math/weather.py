"""Weather-based pace adjustment — Ely et al. (2007) heat model.

Pure functions for calculating pace degradation due to heat and humidity.
Applied post-hoc to pace targets in the workout builder.

References:
    Ely et al. (2007). Impact of weather on marathon-running performance.
        Med Sci Sports Exerc 39(3):487-493.
    Running Writings humidity correction model.
"""

from __future__ import annotations

from science_engine.models.enums import (
    HEAT_REFERENCE_TEMP_C,
    HEAT_VO2MAX_ELITE,
    HEAT_VO2MAX_MIDPACK,
    HUMIDITY_CORRECTION_PER_PCT,
    HUMIDITY_CORRECTION_THRESHOLD,
    PACE_DEGRADATION_BACK_PER_DEGREE_C,
    PACE_DEGRADATION_ELITE_PER_DEGREE_C,
    PACE_DEGRADATION_PER_DEGREE_C,
)


def _degradation_rate(vo2max: float | None) -> float:
    """Return per-degree pace degradation rate based on VO2max ability tier.

    Interpolates linearly between elite (>=65), midpack (~50), and
    back-of-pack (<50) tiers.
    """
    if vo2max is None:
        return PACE_DEGRADATION_PER_DEGREE_C  # default midpack

    if vo2max >= HEAT_VO2MAX_ELITE:
        return PACE_DEGRADATION_ELITE_PER_DEGREE_C
    elif vo2max >= HEAT_VO2MAX_MIDPACK:
        # Interpolate between midpack and elite
        t = (vo2max - HEAT_VO2MAX_MIDPACK) / (HEAT_VO2MAX_ELITE - HEAT_VO2MAX_MIDPACK)
        return PACE_DEGRADATION_PER_DEGREE_C + t * (
            PACE_DEGRADATION_ELITE_PER_DEGREE_C - PACE_DEGRADATION_PER_DEGREE_C
        )
    else:
        # Interpolate between back-of-pack (VO2max ~35) and midpack
        # Use 35 as the lower anchor for back-of-pack
        lower_anchor = 35.0
        if vo2max <= lower_anchor:
            return PACE_DEGRADATION_BACK_PER_DEGREE_C
        t = (vo2max - lower_anchor) / (HEAT_VO2MAX_MIDPACK - lower_anchor)
        return PACE_DEGRADATION_BACK_PER_DEGREE_C + t * (
            PACE_DEGRADATION_PER_DEGREE_C - PACE_DEGRADATION_BACK_PER_DEGREE_C
        )


def pace_adjustment_factor(
    temperature_c: float | None,
    humidity_pct: float | None = None,
    vo2max: float | None = None,
) -> float:
    """Calculate pace adjustment multiplier for heat conditions.

    Returns a factor >= 1.0 where 1.0 means no adjustment and e.g. 1.05
    means pace targets should be 5% slower (higher s/km).

    Args:
        temperature_c: Ambient temperature in Celsius, or None.
        humidity_pct: Relative humidity 0-100, or None.
        vo2max: Athlete VO2max for ability-dependent degradation.

    Returns:
        Multiplicative pace adjustment factor (>= 1.0).
    """
    if temperature_c is None or temperature_c <= HEAT_REFERENCE_TEMP_C:
        return 1.0

    degrees_above = temperature_c - HEAT_REFERENCE_TEMP_C
    rate = _degradation_rate(vo2max)
    factor = 1.0 + degrees_above * rate

    # Humidity correction: +0.2% per 1% above threshold
    if humidity_pct is not None and humidity_pct > HUMIDITY_CORRECTION_THRESHOLD:
        humidity_above = humidity_pct - HUMIDITY_CORRECTION_THRESHOLD
        factor += humidity_above * HUMIDITY_CORRECTION_PER_PCT

    return factor


def heat_risk_category(
    temperature_c: float | None,
    humidity_pct: float | None = None,
) -> str:
    """Classify heat risk for coaching cues and descriptions.

    Returns one of "LOW", "MODERATE", "HIGH", "EXTREME".
    Humidity > 70% bumps the category up one tier.
    """
    if temperature_c is None:
        return "LOW"

    # Base category from temperature
    if temperature_c >= 35.0:
        base = 3  # EXTREME
    elif temperature_c >= 27.0:
        base = 2  # HIGH
    elif temperature_c >= 20.0:
        base = 1  # MODERATE
    else:
        base = 0  # LOW

    # Humidity bump
    if humidity_pct is not None and humidity_pct > 70.0:
        base = min(base + 1, 3)

    categories = ("LOW", "MODERATE", "HIGH", "EXTREME")
    return categories[base]
