"""Pure functions mapping Garmin API response dicts to AthleteState fields.

No I/O — takes raw dicts from GarminClient methods and returns
flat dicts whose keys match sidebar profile field names or AthleteState
field names.
"""

from __future__ import annotations

import math
from datetime import date, datetime
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


# ---------------------------------------------------------------------------
# Profile mapping — GarminClient.pull_profile() → sidebar fields
# ---------------------------------------------------------------------------


def _deep_get(data: Any, *keys: Any) -> Any:
    """Traverse nested dicts/lists by key path, returning None on failure."""
    current = data
    for key in keys:
        if current is None:
            return None
        if isinstance(key, int) and isinstance(current, (list, tuple)):
            if 0 <= key < len(current):
                current = current[key]
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def map_profile(raw: dict[str, Any]) -> dict[str, Any]:
    """Map a full pull_profile() result to sidebar-compatible field dict.

    Returns a dict with keys matching the sidebar profile fields.
    Only includes keys where a value was successfully extracted.
    Values are the appropriate types for the sidebar widgets.
    """
    result: dict[str, Any] = {}

    # --- User profile: name, age, sex ---
    profile = raw.get("user_profile")
    if isinstance(profile, dict):
        # Prefer real name over displayName (which is often a username)
        first = profile.get("firstName") or ""
        last = profile.get("lastName") or ""
        full_name = f"{first} {last}".strip()
        if not full_name:
            full_name = profile.get("displayName") or profile.get("userName") or ""
        if full_name:
            result["name"] = str(full_name)

        # Age from birth date
        birth = profile.get("birthDate")
        if birth:
            age = _birth_date_to_age(birth)
            if age:
                result["age"] = age

        # Sex / gender
        gender = profile.get("gender")
        if gender:
            result["sex"] = "F" if str(gender).upper() in ("FEMALE", "F") else "M"

    # Also check user_settings for demographics
    settings = raw.get("user_settings")
    if isinstance(settings, dict):
        user_data = settings.get("userData") or settings

        # Age from settings if not found in profile
        if "age" not in result:
            birth = user_data.get("birthDate")
            if birth:
                age = _birth_date_to_age(birth)
                if age:
                    result["age"] = age

        # Weight — Garmin stores in grams; detect by magnitude
        weight_raw = user_data.get("weight")
        if weight_raw is not None:
            try:
                w = float(weight_raw)
                # > 500 means grams, otherwise already kg
                result["weight_kg"] = round(w / 1000.0, 1) if w > 500 else round(w, 1)
            except (ValueError, TypeError):
                pass

    # --- Body composition: weight fallback ---
    body_comp = raw.get("body_composition")
    if isinstance(body_comp, dict) and "weight_kg" not in result:
        # Try several common paths
        weight_raw = (
            body_comp.get("weight")
            or _deep_get(body_comp, "totalAverage", "weight")
        )
        if weight_raw is not None:
            try:
                w = float(weight_raw)
                result["weight_kg"] = round(w / 1000.0, 1) if w > 500 else round(w, 1)
            except (ValueError, TypeError):
                pass

    # --- Max metrics: VO2max ---
    vo2 = _extract_vo2max(raw.get("max_metrics"))
    if vo2 is not None:
        result["vo2max"] = vo2

    # --- Resting HR ---
    rhr_data = raw.get("resting_hr")
    if isinstance(rhr_data, dict):
        # Try multiple common field paths
        for path in [
            ("restingHeartRate",),
            ("rhr",),
            ("allMetrics", "metricsMap", "WELLNESS_RESTING_HEART_RATE", 0, "value"),
        ]:
            val = _deep_get(rhr_data, *path)
            if val is not None:
                try:
                    result["resting_hr"] = int(val)
                    break
                except (ValueError, TypeError):
                    pass
    # Fallback from stats
    if "resting_hr" not in result:
        rhr_from_stats = _extract_resting_hr(raw.get("stats"))
        if rhr_from_stats is not None:
            result["resting_hr"] = rhr_from_stats

    # Note: stats.maxHeartRate is the highest HR recorded TODAY (not
    # physiological max HR), so we don't use it for the max_hr profile field.

    # --- Lactate threshold: LTHR bpm + pace ---
    lt = raw.get("lactate_threshold")
    if isinstance(lt, dict):
        # Try direct fields and nested allMetrics paths
        lt_hr = (
            lt.get("heartRateThreshold")
            or _deep_get(lt, "allMetrics", "metricsMap", "HEART_RATE", 0, "value")
        )
        if lt_hr is not None:
            try:
                result["lthr_bpm"] = int(lt_hr)
            except (ValueError, TypeError):
                pass

        # Speed: could be m/s directly, or in a nested metrics map
        lt_speed = (
            lt.get("runningLactateThresholdSpeed")
            or _deep_get(lt, "allMetrics", "metricsMap", "SPEED", 0, "value")
        )
        if lt_speed is not None:
            try:
                speed = float(lt_speed)
                # Garmin returns speed in m/s; if value is very large (>100)
                # it might be in mm/s or cm/s
                if speed > 100:
                    speed = speed / 1000.0  # mm/s → m/s
                elif speed > 20:
                    speed = speed / 100.0  # cm/s → m/s
                # Now speed is in m/s
                if speed > 0:
                    pace_s_per_km = 1000.0 / speed
                    result["lthr_pace_min"] = int(pace_s_per_km // 60)
                    result["lthr_pace_sec"] = int(pace_s_per_km % 60)
            except (ValueError, TypeError, ZeroDivisionError):
                pass

    # --- Recent activities: avg weekly km ---
    activities = raw.get("recent_activities")
    if isinstance(activities, list) and len(activities) > 0:
        total_km = 0.0
        num_weeks = 6.0  # 6-week window
        for act in activities:
            if not isinstance(act, dict):
                continue
            dist = act.get("distance")
            if dist is not None:
                try:
                    d = float(dist)
                    # Garmin returns meters; if suspiciously small, might be km
                    total_km += d / 1000.0 if d > 500 else d
                except (ValueError, TypeError):
                    pass
        if total_km > 0:
            result["avg_weekly_km"] = round(total_km / num_weeks, 1)

    # --- Readiness metrics (daily) ---
    rmssd, baseline = _extract_hrv(raw.get("hrv"))
    if rmssd is not None:
        result["hrv_rmssd"] = rmssd
    if baseline is not None:
        result["hrv_baseline"] = baseline

    sleep = _extract_sleep_score(raw.get("sleep"))
    if sleep is not None:
        result["sleep_score"] = sleep

    bb = _extract_body_battery(raw.get("body_battery"))
    if bb is not None:
        result["body_battery"] = bb

    # Sanitize: drop values outside sidebar widget bounds to prevent crashes
    _BOUNDS: dict[str, tuple[float, float]] = {
        "age": (16, 99),
        "weight_kg": (30.0, 200.0),
        "max_hr": (120, 230),
        "resting_hr": (30, 100),
        "lthr_bpm": (100, 220),
        "lthr_pace_min": (2, 12),
        "lthr_pace_sec": (0, 59),
        "vo2max": (20.0, 90.0),
        "avg_weekly_km": (5.0, 250.0),
        "hrv_rmssd": (0.0, 200.0),
        "hrv_baseline": (0.0, 200.0),
        "sleep_score": (0.0, 100.0),
        "body_battery": (0, 100),
    }
    for key, (lo, hi) in _BOUNDS.items():
        if key in result:
            try:
                val = float(result[key])
                if val < lo or val > hi:
                    del result[key]
            except (ValueError, TypeError):
                del result[key]

    return result


def _birth_date_to_age(birth_date: Any) -> Optional[int]:
    """Convert a birth date string or epoch to age in years."""
    try:
        if isinstance(birth_date, str):
            bd = datetime.strptime(birth_date, "%Y-%m-%d").date()
        elif isinstance(birth_date, (int, float)):
            bd = datetime.fromtimestamp(birth_date / 1000.0).date()
        else:
            return None
        today = date.today()
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        return age if 10 <= age <= 120 else None
    except (ValueError, TypeError, OSError):
        return None
