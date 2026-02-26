"""Heart rate and pace zone calculations.

Zone model: Coggan 5-zone system anchored on LTHR.
Reference: Coggan & Allen (2010), Training and Racing with a Power Meter.
"""

from __future__ import annotations

from dataclasses import dataclass

from science_engine.models.enums import ZONE_BOUNDARIES_PCT_LTHR, ZoneType


@dataclass(frozen=True)
class ZoneBoundary:
    """A single HR or pace zone with lower and upper bounds."""

    zone: ZoneType
    lower: float
    upper: float


def calculate_hr_zones(lthr_bpm: int, max_hr: int) -> list[ZoneBoundary]:
    """Calculate heart rate zones from LTHR using Coggan %LTHR boundaries.

    Args:
        lthr_bpm: Lactate threshold heart rate in BPM.
        max_hr: Maximum heart rate in BPM.

    Returns:
        List of ZoneBoundary with HR values (not percentages).

    Reference:
        Coggan & Allen (2010). Zone boundaries as %LTHR:
        Z1: <81%, Z2: 81-90%, Z3: 90-96%, Z4: 96-102%, Z5: >102%
    """
    zones: list[ZoneBoundary] = []
    for zone_type, (lower_pct, upper_pct) in ZONE_BOUNDARIES_PCT_LTHR.items():
        lower_hr = round(lthr_bpm * lower_pct)
        upper_hr = min(round(lthr_bpm * upper_pct), max_hr)
        # Z1 floor is resting-ish, just use 0
        if zone_type == ZoneType.ZONE_1:
            lower_hr = 0
        # Z5 ceiling is max_hr
        if zone_type == ZoneType.ZONE_5:
            upper_hr = max_hr
        zones.append(ZoneBoundary(zone=zone_type, lower=lower_hr, upper=upper_hr))
    return zones


def calculate_pace_zones(lthr_pace_s_per_km: int) -> list[ZoneBoundary]:
    """Calculate pace zones from lactate threshold pace.

    Pace zones use the same Coggan percentages but inverted: a higher
    %LTHR corresponds to a *faster* (lower) pace value in s/km.

    Args:
        lthr_pace_s_per_km: Lactate threshold pace in seconds per km.

    Returns:
        List of ZoneBoundary with pace values in seconds per km.
        Lower bound = faster pace (lower s/km), upper = slower pace.
    """
    zones: list[ZoneBoundary] = []
    for zone_type, (lower_pct, upper_pct) in ZONE_BOUNDARIES_PCT_LTHR.items():
        # Invert: higher effort % → faster pace (lower s/km)
        # Zone 1 (low effort) → slowest pace; Zone 5 (high effort) → fastest
        if lower_pct == 0.0:
            pace_upper = round(lthr_pace_s_per_km * 1.5)  # Very easy cap
        else:
            pace_upper = round(lthr_pace_s_per_km / lower_pct)
        pace_lower = round(lthr_pace_s_per_km / upper_pct)

        zones.append(ZoneBoundary(zone=zone_type, lower=pace_lower, upper=pace_upper))
    return zones
