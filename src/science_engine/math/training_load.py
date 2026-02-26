"""Training load calculations: TRIMP, ACWR (EWMA-based), monotony, strain.

References:
    - Banister (1991): TRIMP formula
    - Williams et al. (2017): EWMA-based ACWR
    - Gabbett (2016): ACWR injury risk thresholds
    - Foster (1998): Monotony and strain
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from science_engine.models.enums import (
    ACWR_CAUTION_HIGH,
    ACWR_DANGER_THRESHOLD,
    ACWR_OPTIMAL_LOW,
    ACWR_UNDERTRAINED,
    EWMA_ACUTE_SPAN,
    EWMA_CHRONIC_SPAN,
    TRIMP_COEFFICIENT_FEMALE,
    TRIMP_COEFFICIENT_MALE,
    TRIMP_EXPONENT_FEMALE,
    TRIMP_EXPONENT_MALE,
)


def calculate_trimp(
    duration_min: float,
    avg_hr: float,
    max_hr: int,
    resting_hr: int,
    sex: str = "M",
) -> float:
    """Calculate Banister TRIMP (Training Impulse) for a single session.

    TRIMP = duration × delta_hr_ratio × coefficient × e^(exponent × delta_hr_ratio)

    Args:
        duration_min: Session duration in minutes.
        avg_hr: Average heart rate during the session.
        max_hr: Athlete's maximum heart rate.
        resting_hr: Athlete's resting heart rate.
        sex: "M" or "F" — affects the exponential weighting.

    Returns:
        TRIMP score (arbitrary units, higher = more load).

    Reference:
        Banister (1991). Modeling elite athletic performance. In:
        Physiological Testing of Elite Athletes.
    """
    if max_hr <= resting_hr:
        return 0.0
    delta_hr_ratio = (avg_hr - resting_hr) / (max_hr - resting_hr)
    delta_hr_ratio = max(0.0, min(1.0, delta_hr_ratio))

    if sex.upper() == "F":
        coefficient = TRIMP_COEFFICIENT_FEMALE
        exponent = TRIMP_EXPONENT_FEMALE
    else:
        coefficient = TRIMP_COEFFICIENT_MALE
        exponent = TRIMP_EXPONENT_MALE

    return duration_min * delta_hr_ratio * coefficient * math.exp(exponent * delta_hr_ratio)


def calculate_ewma(values: list[float] | tuple[float, ...], span: int) -> float:
    """Calculate the most recent value of an exponentially weighted moving average.

    Args:
        values: Time series of daily values (oldest first).
        span: EWMA span parameter (e.g., 7 for acute, 28 for chronic).

    Returns:
        The most recent EWMA value.

    Reference:
        Williams et al. (2017). J Sci Med Sport 20(5):493-497.
    """
    if not values:
        return 0.0
    series = pd.Series(values, dtype=np.float64)
    ewma = series.ewm(span=span, adjust=False).mean()
    return float(ewma.iloc[-1])


def calculate_acwr(daily_loads: list[float] | tuple[float, ...]) -> float:
    """Calculate Acute:Chronic Workload Ratio using EWMA method.

    ACWR = acute_ewma / chronic_ewma

    Args:
        daily_loads: Daily training load values (oldest first, minimum 7 days).

    Returns:
        ACWR ratio. Returns 0.0 if chronic load is negligible.

    Reference:
        Williams et al. (2017): EWMA preferable to rolling averages for
        injury risk detection. Gabbett (2016): ACWR thresholds.
    """
    if len(daily_loads) < EWMA_ACUTE_SPAN:
        return 0.0

    acute = calculate_ewma(daily_loads, span=EWMA_ACUTE_SPAN)
    chronic = calculate_ewma(daily_loads, span=EWMA_CHRONIC_SPAN)

    if chronic < 1e-6:
        return 0.0
    return acute / chronic


def classify_acwr(acwr: float) -> str:
    """Classify an ACWR value into a risk category.

    Args:
        acwr: Acute:Chronic Workload Ratio.

    Returns:
        One of: "undertrained", "optimal", "caution", "danger"

    Reference:
        Gabbett (2016), Br J Sports Med 50(5):273-280.
        Sweet spot: 0.8 - 1.3. Danger zone: >1.5.
    """
    if acwr >= ACWR_DANGER_THRESHOLD:
        return "danger"
    if acwr >= ACWR_CAUTION_HIGH:
        return "caution"
    if acwr >= ACWR_OPTIMAL_LOW:
        return "optimal"
    if acwr < ACWR_UNDERTRAINED:
        return "undertrained"
    return "optimal"


def calculate_monotony(daily_loads: list[float] | tuple[float, ...]) -> float:
    """Calculate training monotony over the most recent 7 days.

    Monotony = mean(daily_load) / std(daily_load)
    High monotony (>2.0) indicates insufficient variation.

    Args:
        daily_loads: Daily training loads (at least 7 values).

    Returns:
        Monotony value. Returns 0.0 if insufficient data.

    Reference:
        Foster (1998). Monitoring training in athletes with reference to
        overtraining syndrome. Med Sci Sports Exerc 30(7):1164-1168.
    """
    if len(daily_loads) < 7:
        return 0.0
    recent = np.array(daily_loads[-7:], dtype=np.float64)
    std = float(np.std(recent, ddof=0))
    if std < 1e-6:
        return 0.0
    return float(np.mean(recent)) / std


def project_acwr_with_session(
    daily_loads: list[float] | tuple[float, ...], planned_load: float
) -> float:
    """Project what the ACWR would be if a planned session is added.

    Appends the planned load to the daily_loads and recalculates ACWR.

    Args:
        daily_loads: Current daily loads (oldest first).
        planned_load: The load of the planned session.

    Returns:
        Projected ACWR after the planned session.
    """
    extended = list(daily_loads) + [planned_load]
    return calculate_acwr(extended)
