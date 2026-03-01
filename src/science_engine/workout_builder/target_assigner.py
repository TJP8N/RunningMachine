"""Target assigner — calculates pace and HR targets per zone from athlete state.

Prefers CS-derived zones when Critical Speed data is available; falls back
to LTHR-derived zones. Applies intensity modifiers from the prescription.

References:
    Coggan & Allen (2010). Training and Racing with a Power Meter.
    Smyth & Muniz-Pumares (2020). Calculation of critical speed. Med Sci
        Sports Exerc 52(7):1606-1615.
"""

from __future__ import annotations

from dataclasses import dataclass

from science_engine.math.critical_speed import (
    calculate_cs_zones,
    marathon_pace_from_cs,
)
from science_engine.math.weather import pace_adjustment_factor
from science_engine.math.zones import calculate_hr_zones, calculate_pace_zones
from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    INTENSITY_B_MODERATE_FACTOR,
    INTENSITY_C_EASY_FACTOR,
    IntensityLevel,
    SessionType,
    ZoneType,
)


@dataclass(frozen=True)
class PaceHRTargets:
    """Pace and HR target bounds for a single workout step.

    Pace values are in seconds per km. Lower = faster.
    HR values are in bpm.
    """

    pace_target_low: float | None = None   # faster bound (s/km)
    pace_target_high: float | None = None  # slower bound (s/km)
    hr_target_low: int | None = None       # bpm
    hr_target_high: int | None = None      # bpm


def _intensity_factor(intensity: IntensityLevel) -> float:
    """Return the pace/HR scaling factor for a given intensity level.

    A_FULL = 1.0, B_MODERATE = 0.95, C_EASY = 0.85.
    For pace: multiply targets by 1/factor (makes pace slower).
    For HR: multiply targets by factor (makes HR lower).
    """
    if intensity == IntensityLevel.B_MODERATE:
        return INTENSITY_B_MODERATE_FACTOR
    elif intensity == IntensityLevel.C_EASY:
        return INTENSITY_C_EASY_FACTOR
    return 1.0


def assign_targets(
    state: AthleteState,
    zone: ZoneType,
    intensity: IntensityLevel = IntensityLevel.A_FULL,
    session_type: SessionType | None = None,
) -> PaceHRTargets:
    """Calculate pace and HR targets for a zone + intensity combination.

    Logic:
    1. Pace: Prefer CS-derived zones if ``critical_speed_m_per_s`` is
       available; fall back to LTHR-derived zones.
    2. HR: Always from ``calculate_hr_zones(lthr_bpm, max_hr)``.
    3. Marathon pace: Special case for MARATHON_PACE sessions — use
       ``marathon_pace_from_cs()`` if CS available, else estimate from
       ``lthr_pace_s_per_km / 0.88``.
    4. Intensity modifier: Apply B_MODERATE (5% easier) or C_EASY
       (15% easier) — makes pace targets slower and HR targets lower.

    Args:
        state: Frozen athlete state with physiology data.
        zone: Target zone for this step.
        intensity: Intensity level modifier.
        session_type: Optional session type for marathon pace special case.

    Returns:
        PaceHRTargets with all four bounds.
    """
    factor = _intensity_factor(intensity)

    # --- Pace targets ---
    is_mp = session_type in (SessionType.MARATHON_PACE, SessionType.RACE_SIMULATION)

    if is_mp:
        # Marathon pace special case
        mp_pace = _get_marathon_pace(state)
        # Apply intensity modifier (slower = higher s/km)
        adjusted_pace = mp_pace / factor
        # Use +-3% band around marathon pace
        pace_low = round(adjusted_pace * 0.97, 1)
        pace_high = round(adjusted_pace * 1.03, 1)
    elif state.critical_speed_m_per_s is not None:
        # CS-derived pace zones
        cs_zones = calculate_cs_zones(state.critical_speed_m_per_s)
        pace_zone = _find_zone(cs_zones, zone)
        if pace_zone is not None:
            # Apply intensity modifier (slower = divide by factor)
            pace_low = round(pace_zone[0] / factor, 1)
            pace_high = round(pace_zone[1] / factor, 1)
        else:
            pace_low = None
            pace_high = None
    else:
        # LTHR-derived pace zones
        lthr_zones = calculate_pace_zones(state.lthr_pace_s_per_km)
        pace_zone = _find_zone(lthr_zones, zone)
        if pace_zone is not None:
            pace_low = round(pace_zone[0] / factor, 1)
            pace_high = round(pace_zone[1] / factor, 1)
        else:
            pace_low = None
            pace_high = None

    # --- Heat adjustment (pace only) ---
    heat_factor = pace_adjustment_factor(
        state.temperature_celsius, state.humidity_pct, state.vo2max,
    )
    if pace_low is not None:
        pace_low = round(pace_low * heat_factor, 1)
    if pace_high is not None:
        pace_high = round(pace_high * heat_factor, 1)

    # --- HR targets ---
    hr_zones = calculate_hr_zones(state.lthr_bpm, state.max_hr)
    hr_zone = _find_zone(hr_zones, zone)
    if hr_zone is not None:
        hr_low = int(hr_zone[0] * factor)
        hr_high = int(hr_zone[1] * factor)
    else:
        hr_low = None
        hr_high = None

    return PaceHRTargets(
        pace_target_low=pace_low,
        pace_target_high=pace_high,
        hr_target_low=hr_low,
        hr_target_high=hr_high,
    )


def _get_marathon_pace(state: AthleteState) -> float:
    """Get marathon pace in s/km from CS or LTHR estimate."""
    if state.critical_speed_m_per_s is not None:
        return marathon_pace_from_cs(state.critical_speed_m_per_s)
    # Fallback: LTHR pace / 0.88 (MP is ~88% of LT intensity)
    return state.lthr_pace_s_per_km / 0.88


def _find_zone(
    zones: list,
    target_zone: ZoneType,
) -> tuple[float, float] | None:
    """Find a specific zone's bounds from a list of ZoneBoundary objects."""
    for zb in zones:
        if zb.zone == target_zone:
            return (zb.lower, zb.upper)
    return None
