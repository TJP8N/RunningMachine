"""Pure functions mapping Garmin API response dicts to AthleteState fields.

No I/O — takes raw dicts from GarminClient.pull_daily_metrics() and returns
a flat dict whose keys match AthleteState field names.
"""

from __future__ import annotations

from typing import Any, Optional

from science_engine.models.enums import ReadinessLevel


def map_daily_metrics(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a full pull_daily_metrics() result to AthleteState-compatible fields.

    Returns a dict with keys:
        hrv_rmssd, hrv_baseline, sleep_score, body_battery,
        resting_hr, vo2max, readiness

    Values are None when the data is unavailable.
    """
    rmssd, baseline = _extract_hrv(raw.get("hrv"))
    return {
        "hrv_rmssd": rmssd,
        "hrv_baseline": baseline,
        "sleep_score": _extract_sleep_score(raw.get("sleep")),
        "body_battery": _extract_body_battery(raw.get("body_battery")),
        "resting_hr": _extract_resting_hr(raw.get("stats")),
        "vo2max": _extract_vo2max(raw.get("max_metrics")),
        "readiness": _extract_readiness(raw.get("training_readiness")),
    }


# ---------------------------------------------------------------------------
# Internal extractors — each handles None input gracefully
# ---------------------------------------------------------------------------


def _extract_hrv(data: Any) -> tuple[Optional[float], Optional[float]]:
    """Extract HRV RMSSD and weekly baseline from Garmin HRV data.

    Returns (rmssd_last_night, weekly_average).
    """
    if not data:
        return (None, None)

    rmssd: Optional[float] = None
    baseline: Optional[float] = None

    # hrvSummary contains lastNightAvg and weeklyAvg
    summary = data.get("hrvSummary") if isinstance(data, dict) else None
    if summary:
        rmssd = summary.get("lastNightAvg")
        baseline = summary.get("weeklyAvg")

    return (rmssd, baseline)


def _extract_sleep_score(data: Any) -> Optional[float]:
    """Extract overall sleep score from Garmin sleep data.

    Path: dailySleepDTO.sleepScores.overall.value
    """
    if not data:
        return None

    try:
        dto = data.get("dailySleepDTO") if isinstance(data, dict) else None
        if dto is None:
            return None
        scores = dto.get("sleepScores")
        if scores is None:
            return None
        overall = scores.get("overall")
        if overall is None:
            return None
        value = overall.get("value")
        return float(value) if value is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def _extract_body_battery(data: Any) -> Optional[int]:
    """Extract morning body battery peak from the charged body battery list.

    The Garmin API returns a list of body battery readings. We take the
    highest "charged" value from the morning window (first reading or max).
    """
    if not data:
        return None

    # data may be a list of dicts with 'charged' values,
    # or a dict with a body battery list
    bb_list = data
    if isinstance(data, dict):
        bb_list = data.get("bodyBatteryValuesArray") or data.get("bodyBattery") or []

    if not isinstance(bb_list, list) or len(bb_list) == 0:
        return None

    # Each entry may be [timestamp, level, charged, drained, status]
    # or a dict with 'charged' key
    max_val: Optional[int] = None
    for entry in bb_list:
        charged = None
        if isinstance(entry, dict):
            charged = entry.get("charged")
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            # [timestamp, level] — take level as the battery value
            charged = entry[1]

        if charged is not None:
            try:
                val = int(charged)
                if max_val is None or val > max_val:
                    max_val = val
            except (ValueError, TypeError):
                continue

    return max_val


def _extract_vo2max(data: Any) -> Optional[float]:
    """Extract VO2max from Garmin max metrics.

    Looks for generic.vo2MaxPreciseValue in the response.
    """
    if not data:
        return None

    # data may be a list with one entry or a dict
    metrics = data
    if isinstance(data, list) and len(data) > 0:
        metrics = data[0]

    if not isinstance(metrics, dict):
        return None

    generic = metrics.get("generic")
    if not isinstance(generic, dict):
        return None

    value = generic.get("vo2MaxPreciseValue")
    if value is not None:
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


def _extract_resting_hr(data: Any) -> Optional[int]:
    """Extract resting heart rate from daily stats."""
    if not data or not isinstance(data, dict):
        return None

    rhr = data.get("restingHeartRate")
    if rhr is not None:
        try:
            return int(rhr)
        except (ValueError, TypeError):
            return None
    return None


def _extract_readiness(data: Any) -> Optional[ReadinessLevel]:
    """Map Garmin Training Readiness score (0-100) to a ReadinessLevel.

    Thresholds:
        0-24  → VERY_SUPPRESSED
        25-49 → SUPPRESSED
        50-74 → NORMAL
        75+   → ELEVATED
    """
    if not data:
        return None

    # data may be a list or dict
    entry = data
    if isinstance(data, list) and len(data) > 0:
        entry = data[0]

    if not isinstance(entry, dict):
        return None

    score = entry.get("score") or entry.get("readinessScore")
    if score is None:
        return None

    try:
        score = float(score)
    except (ValueError, TypeError):
        return None

    if score >= 75:
        return ReadinessLevel.ELEVATED
    if score >= 50:
        return ReadinessLevel.NORMAL
    if score >= 25:
        return ReadinessLevel.SUPPRESSED
    return ReadinessLevel.VERY_SUPPRESSED
