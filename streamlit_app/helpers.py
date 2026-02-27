"""Utility helpers bridging the Streamlit UI and the science engine.

Pure functions for formatting, synthetic data generation, athlete state
construction, and profile persistence.
"""

from __future__ import annotations

import json
import math
import os
import random
from datetime import date
from pathlib import Path

from science_engine.math.periodization import allocate_phases, get_phase_for_week
from science_engine.math.training_load import calculate_trimp
from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    SessionType,
    StepType,
    TrainingPhase,
)

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_pace(s_per_km: float) -> str:
    """Convert seconds-per-km to 'M:SS/km' string. e.g. 305.0 -> '5:05/km'."""
    if s_per_km <= 0:
        return "--"
    mins = int(s_per_km) // 60
    secs = int(s_per_km) % 60
    return f"{mins}:{secs:02d}/km"


def format_pace_range(low: float | None, high: float | None) -> str:
    """Format a pace range. low = faster (lower s/km), high = slower."""
    if low is None and high is None:
        return "--"
    if low is not None and high is not None:
        return f"{format_pace(low)} - {format_pace(high)}"
    if low is not None:
        return format_pace(low)
    return format_pace(high)  # type: ignore[arg-type]


def format_hr_range(low: int | None, high: int | None) -> str:
    """Format a heart rate range. e.g. 145, 160 -> '145-160 bpm'."""
    if low is None and high is None:
        return "--"
    if low is not None and high is not None:
        return f"{low}-{high} bpm"
    if low is not None:
        return f"{low} bpm"
    return f"{high} bpm"


def format_duration(minutes: float) -> str:
    """Convert minutes to human string. e.g. 90.0 -> '1h 30m'."""
    if minutes <= 0:
        return "0m"
    h = int(minutes) // 60
    m = int(minutes) % 60
    if h > 0 and m > 0:
        return f"{h}h {m}m"
    if h > 0:
        return f"{h}h"
    return f"{m}m"


# ---------------------------------------------------------------------------
# Color maps
# ---------------------------------------------------------------------------

STEP_COLORS: dict[StepType, str] = {
    StepType.WARMUP: "#FF8C00",     # orange
    StepType.COOLDOWN: "#4A90D9",   # blue
    StepType.ACTIVE: "#2ECC71",     # green
    StepType.RECOVERY: "#AED6F1",   # pastel blue
    StepType.REST: "#D5DBDB",       # grey
    StepType.REPEAT: "#D7BDE2",     # lavender
}

SESSION_COLORS: dict[SessionType, str] = {
    SessionType.REST: "#D5DBDB",
    SessionType.RECOVERY: "#AED6F1",
    SessionType.EASY: "#82E0AA",
    SessionType.LONG_RUN: "#F9E79F",
    SessionType.TEMPO: "#F5B041",
    SessionType.THRESHOLD: "#E74C3C",
    SessionType.VO2MAX_INTERVALS: "#8E44AD",
    SessionType.MARATHON_PACE: "#3498DB",
    SessionType.RACE_SIMULATION: "#1ABC9C",
}

STEP_LABELS: dict[StepType, str] = {
    StepType.WARMUP: "Warmup",
    StepType.COOLDOWN: "Cooldown",
    StepType.ACTIVE: "Active",
    StepType.RECOVERY: "Recovery",
    StepType.REST: "Rest",
    StepType.REPEAT: "Repeat",
}

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

PHASE_LABELS: dict[TrainingPhase, str] = {
    TrainingPhase.BASE: "Base",
    TrainingPhase.BUILD: "Build",
    TrainingPhase.SPECIFIC: "Specific",
    TrainingPhase.TAPER: "Taper",
    TrainingPhase.RACE: "Race",
}


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------


def estimate_daily_loads(
    avg_weekly_km: float,
    max_hr: int = 185,
    resting_hr: int = 50,
    sex: str = "M",
    days: int = 28,
) -> tuple[float, ...]:
    """Generate synthetic 28-day TRIMP loads from average weekly km.

    Uses a realistic weekly pattern (rest day, easy days, 1-2 harder days,
    long run) and converts distance → duration → TRIMP.
    """
    # Rough pace: ~6:00/km for an intermediate runner
    pace_min_per_km = 6.0
    avg_daily_km = avg_weekly_km / 7.0

    # Weekly pattern multipliers (Mon-Sun): rest, easy, moderate, easy, tempo, easy, long
    pattern = [0.0, 0.8, 1.0, 0.7, 1.3, 0.6, 1.8]

    # Intensity as fraction of HR reserve for each day pattern
    hr_fraction = [0.0, 0.65, 0.72, 0.65, 0.82, 0.65, 0.75]

    loads: list[float] = []
    for i in range(days):
        day_idx = i % 7
        km = avg_daily_km * pattern[day_idx]
        duration = km * pace_min_per_km
        if duration < 1:
            loads.append(0.0)
            continue
        avg_hr = resting_hr + hr_fraction[day_idx] * (max_hr - resting_hr)
        trimp = calculate_trimp(duration, avg_hr, max_hr, resting_hr, sex)
        # Add slight randomness (+-10%) for realism
        jitter = 1.0 + random.uniform(-0.10, 0.10)
        loads.append(round(trimp * jitter, 1))

    return tuple(loads)


def estimate_weekly_volume_history(
    avg_km: float, weeks: int = 5
) -> tuple[float, ...]:
    """Generate plausible progressive weekly volume history.

    Builds backwards from avg_km with ~5% weekly progression.
    """
    volumes: list[float] = []
    current = avg_km
    for _ in range(weeks):
        volumes.append(round(current, 1))
        current *= 0.95  # each earlier week was ~5% less
    volumes.reverse()
    return tuple(volumes)


# ---------------------------------------------------------------------------
# Athlete state construction
# ---------------------------------------------------------------------------


def build_athlete_state(profile: dict) -> AthleteState:
    """Convert a UI form dict into a frozen AthleteState.

    Auto-derives current_phase from week/total_plan_weeks.
    Converts 0 → None for optional numeric fields.
    """
    total_weeks = profile.get("total_plan_weeks", 16)
    current_week = profile.get("current_week", 1)

    # Derive phase from periodization math
    phases = allocate_phases(total_weeks)
    current_phase = get_phase_for_week(current_week, phases)

    # Synthetic load data from avg_weekly_km
    avg_km = profile.get("avg_weekly_km", 35.0)
    max_hr = profile.get("max_hr", 185)
    resting_hr = profile.get("resting_hr", 50)
    sex = profile.get("sex", "M")

    daily_loads = estimate_daily_loads(avg_km, max_hr, resting_hr, sex)
    weekly_vol = estimate_weekly_volume_history(avg_km)

    # Convert lthr_pace from min:sec UI fields to seconds per km
    lt_pace_min = profile.get("lthr_pace_min", 5)
    lt_pace_sec = profile.get("lthr_pace_sec", 30)
    lthr_pace_s = lt_pace_min * 60 + lt_pace_sec

    # Optional fields: 0 means "not provided"
    def opt(key: str) -> float | None:
        v = profile.get(key, 0)
        return float(v) if v else None

    def opt_int(key: str) -> int | None:
        v = profile.get(key, 0)
        return int(v) if v else None

    # Goal race date
    goal_date = profile.get("goal_race_date")
    if isinstance(goal_date, str) and goal_date:
        goal_date = date.fromisoformat(goal_date)
    elif not isinstance(goal_date, date):
        goal_date = None

    # Critical speed
    cs = opt("critical_speed")
    dp = opt("d_prime")

    return AthleteState(
        name=profile.get("name", "Runner"),
        age=profile.get("age", 35),
        weight_kg=profile.get("weight_kg", 70.0),
        sex=sex,
        max_hr=max_hr,
        lthr_bpm=profile.get("lthr_bpm", 165),
        lthr_pace_s_per_km=lthr_pace_s,
        vo2max=profile.get("vo2max", 45.0),
        resting_hr=resting_hr,
        current_phase=current_phase,
        current_week=current_week,
        total_plan_weeks=total_weeks,
        day_of_week=profile.get("day_of_week", date.today().isoweekday()),
        goal_race_date=goal_date,
        weekly_volume_history=weekly_vol,
        daily_loads=daily_loads,
        hrv_rmssd=opt("hrv_rmssd"),
        hrv_baseline=opt("hrv_baseline"),
        sleep_score=opt("sleep_score"),
        body_battery=opt_int("body_battery"),
        critical_speed_m_per_s=cs,
        d_prime_meters=dp,
        temperature_celsius=opt("temperature"),
    )


# ---------------------------------------------------------------------------
# Profile persistence
# ---------------------------------------------------------------------------

_PROFILES_DIR = Path(__file__).parent / "profiles"


def _ensure_profiles_dir() -> Path:
    _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return _PROFILES_DIR


def save_profile(name: str, profile: dict) -> Path:
    """Save a profile dict as JSON. Returns the file path."""
    d = _ensure_profiles_dir()
    # Sanitise filename
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in name).strip()
    if not safe:
        safe = "profile"
    path = d / f"{safe}.json"
    # Convert date objects to ISO strings for JSON
    serializable = {}
    for k, v in profile.items():
        if isinstance(v, date):
            serializable[k] = v.isoformat()
        else:
            serializable[k] = v
    with open(path, "w") as f:
        json.dump(serializable, f, indent=2)
    return path


def load_profile(name: str) -> dict:
    """Load a profile dict from JSON."""
    path = _PROFILES_DIR / f"{name}.json"
    with open(path) as f:
        return json.load(f)


def list_profiles() -> list[str]:
    """List available profile names (without .json extension)."""
    d = _ensure_profiles_dir()
    return sorted(p.stem for p in d.glob("*.json"))
