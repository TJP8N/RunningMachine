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
    """Extract highest body battery level from Garmin body battery data.

    The API returns either:
    - A list of day-summary dicts, each containing bodyBatteryValuesArray
      with [timestamp, level] pairs
    - A dict with bodyBatteryValuesArray directly
    - A list of [timestamp, level] pairs
    - A list of dicts with 'charged' keys

    We extract the highest battery LEVEL (not charged amount).
    """
    if not data:
        return None

    # Collect all [timestamp, level] arrays from the data
    level_arrays: list[list] = []

    if isinstance(data, dict):
        arr = data.get("bodyBatteryValuesArray") or data.get("bodyBattery") or []
        if isinstance(arr, list):
            level_arrays.append(arr)
    elif isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict) and "bodyBatteryValuesArray" in entry:
                arr = entry["bodyBatteryValuesArray"]
                if isinstance(arr, list):
                    level_arrays.append(arr)
            elif isinstance(entry, (list, tuple)):
                # Might be [timestamp, level] directly
                level_arrays.append(data)
                break
            elif isinstance(entry, dict) and "charged" in entry:
                # Fallback: older format with just 'charged' per entry
                level_arrays.append(data)
                break

    max_val: Optional[int] = None
    for arr in level_arrays:
        for item in arr:
            level = None
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                level = item[1]  # [timestamp, level]
            elif isinstance(item, dict):
                level = item.get("charged")

            if level is not None:
                try:
                    val = int(level)
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


def _extract_max_hr_from_activities(activities: list) -> Optional[int]:
    """Find the highest maxHR across a list of Garmin activity summaries.

    Each activity dict may contain 'maxHR' (the peak HR during that session).
    We return the overall maximum as a floor for physiological max HR.
    """
    max_hr: Optional[int] = None
    for act in activities:
        if not isinstance(act, dict):
            continue
        hr = act.get("maxHR")
        if hr is not None:
            try:
                val = int(hr)
                # Sanity: must be in physiological range
                if 120 <= val <= 230:
                    if max_hr is None or val > max_hr:
                        max_hr = val
            except (ValueError, TypeError):
                continue
    return max_hr


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

    # --- User settings: PRIMARY source for demographics + biometrics ---
    # get_userprofile_settings() returns {id, userData: {gender, weight,
    # birthDate, lactateThresholdHeartRate, lactateThresholdSpeed, ...}, ...}
    lt_hr_from_settings: Any = None
    lt_speed_from_settings: Any = None

    settings = raw.get("user_settings")
    if isinstance(settings, dict):
        user_data = settings.get("userData") or settings

        # Sex / gender
        gender = user_data.get("gender")
        if gender:
            result["sex"] = "F" if str(gender).upper() in ("FEMALE", "F") else "M"

        # Age from birth date
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

        # Stash LT values from settings as fallback
        lt_hr_from_settings = user_data.get("lactateThresholdHeartRate")
        lt_speed_from_settings = user_data.get("lactateThresholdSpeed")

    # --- User profile: name only if real first/last name available ---
    # get_user_profile() returns {displayName, preferredLocale, ...}
    # displayName is a USERNAME (e.g. "tjpaton8"), not a real name.
    profile = raw.get("user_profile")
    if isinstance(profile, dict):
        first = profile.get("firstName") or ""
        last = profile.get("lastName") or ""
        full_name = f"{first} {last}".strip()
        # Only set name if we found a real first/last name
        if full_name:
            result["name"] = str(full_name)

        # Fallback demographics from profile (unlikely, but just in case)
        if "age" not in result:
            birth = profile.get("birthDate")
            if birth:
                age = _birth_date_to_age(birth)
                if age:
                    result["age"] = age
        if "sex" not in result:
            gender = profile.get("gender")
            if gender:
                result["sex"] = "F" if str(gender).upper() in ("FEMALE", "F") else "M"

    # --- Body composition: weight fallback ---
    body_comp = raw.get("body_composition")
    if isinstance(body_comp, dict) and "weight_kg" not in result:
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

    # VO2max fallback: check user_settings.userData.vo2MaxRunning
    if "vo2max" not in result:
        if isinstance(settings, dict):
            user_data_for_vo2 = (settings.get("userData") or settings)
            vo2_setting = user_data_for_vo2.get("vo2MaxRunning")
            if vo2_setting is not None:
                try:
                    result["vo2max"] = float(vo2_setting)
                except (ValueError, TypeError):
                    pass

    # --- Max HR ---
    # Strategy 1: observed max from all recent activities
    all_acts = raw.get("all_activities")
    if isinstance(all_acts, list) and len(all_acts) > 0:
        observed_max = _extract_max_hr_from_activities(all_acts)
        if observed_max is not None:
            result["max_hr"] = observed_max

    # Strategy 2: estimate from LTHR (~88% of max HR)
    if "max_hr" not in result and "lthr_bpm" in result:
        result["max_hr"] = int(round(result["lthr_bpm"] / 0.88))

    # Strategy 3: Tanaka formula from age (least reliable)
    if "max_hr" not in result and "age" in result:
        result["max_hr"] = int(round(208 - 0.7 * result["age"]))

    # --- Resting HR ---
    # get_rhr_day() → {allMetrics: {metricsMap: {WELLNESS_RESTING_HEART_RATE: [{value}]}}}
    rhr_data = raw.get("resting_hr")
    if isinstance(rhr_data, dict):
        for path in [
            ("allMetrics", "metricsMap", "WELLNESS_RESTING_HEART_RATE", 0, "value"),
            ("restingHeartRate",),
        ]:
            val = _deep_get(rhr_data, *path)
            if val is not None:
                try:
                    result["resting_hr"] = int(val)
                    break
                except (ValueError, TypeError):
                    pass

    # Fallback: stats.restingHeartRate
    if "resting_hr" not in result:
        stats = raw.get("stats")
        if isinstance(stats, dict):
            # Prefer 7-day average (more stable) over today's value
            for key in ("lastSevenDaysAvgRestingHeartRate", "restingHeartRate"):
                rhr_val = stats.get(key)
                if rhr_val is not None:
                    try:
                        result["resting_hr"] = int(rhr_val)
                        break
                    except (ValueError, TypeError):
                        pass

    # --- Lactate threshold: LTHR bpm + pace ---
    # get_lactate_threshold() → {speed_and_heart_rate: {heartRate, speed}, power: {...}}
    lt = raw.get("lactate_threshold")
    if isinstance(lt, dict):
        shr = lt.get("speed_and_heart_rate")
        if isinstance(shr, dict):
            lt_hr = shr.get("heartRate")
            if lt_hr is not None:
                try:
                    result["lthr_bpm"] = int(lt_hr)
                except (ValueError, TypeError):
                    pass
            lt_speed = shr.get("speed")
            if lt_speed is not None:
                _set_lt_pace(result, lt_speed)

    # Fallback: LT from user_settings.userData
    if "lthr_bpm" not in result and lt_hr_from_settings is not None:
        try:
            result["lthr_bpm"] = int(lt_hr_from_settings)
        except (ValueError, TypeError):
            pass
    if "lthr_pace_min" not in result and lt_speed_from_settings is not None:
        _set_lt_pace(result, lt_speed_from_settings)

    # --- Recent activities: avg weekly km ---
    activities = raw.get("recent_activities")
    if isinstance(activities, list):
        if len(activities) > 0:
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
            result["avg_weekly_km"] = round(total_km / num_weeks, 1) if total_km > 0 else 0.0
        else:
            # Empty activity list — no recent running
            result["avg_weekly_km"] = 0.0

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

    # --- Critical speed: estimate from LT speed ---
    # CS is typically ~95% of lactate threshold speed for trained runners.
    if "lthr_pace_min" in result and "lthr_pace_sec" in result:
        lt_pace_s = result["lthr_pace_min"] * 60 + result["lthr_pace_sec"]
        if lt_pace_s > 0:
            lt_speed_ms = 1000.0 / lt_pace_s
            # CS ≈ 95% of LT speed
            cs = round(lt_speed_ms * 0.95, 2)
            if 1.5 <= cs <= 7.0:
                result["critical_speed"] = cs
                # D' rough estimate: 200-400m for most runners, scale with speed
                result["d_prime"] = round(cs * 60, 0)  # ~200-400m range

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
        "avg_weekly_km": (0.0, 250.0),
        "hrv_rmssd": (0.0, 200.0),
        "hrv_baseline": (0.0, 200.0),
        "sleep_score": (0.0, 100.0),
        "body_battery": (0, 100),
        "critical_speed": (0.0, 8.0),
        "d_prime": (0.0, 1000.0),
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


def _set_lt_pace(result: dict[str, Any], speed_raw: Any) -> None:
    """Convert LT speed to pace and store lthr_pace_min/sec in result."""
    try:
        speed = float(speed_raw)
        if speed <= 0:
            return
        # Normal running LT speed is 2.5-6.0 m/s.
        # Garmin sometimes stores values scaled down by 10x (e.g. 0.394
        # instead of 3.94 m/s). Correct if clearly too slow for running.
        if speed < 1.0:
            speed = speed * 10.0
        elif speed > 100:
            speed = speed / 1000.0  # mm/s → m/s
        elif speed > 20:
            speed = speed / 100.0  # cm/s → m/s
        if speed > 0:
            pace_s_per_km = 1000.0 / speed
            result["lthr_pace_min"] = int(pace_s_per_km // 60)
            result["lthr_pace_sec"] = int(pace_s_per_km % 60)
    except (ValueError, TypeError, ZeroDivisionError):
        pass


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
