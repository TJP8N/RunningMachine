"""Frozen athlete state — immutable snapshot of all inputs for a single engine call."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from typing import TYPE_CHECKING

from science_engine.models.enums import ReadinessLevel, TrainingPhase

if TYPE_CHECKING:
    from science_engine.models.race_calendar import RaceCalendar
    from science_engine.models.training_debt import TrainingDebtLedger


@dataclass(frozen=True)
class AthleteState:
    """Immutable snapshot of an athlete's current state.

    This is the sole input to ScienceEngine.prescribe(). All fields are
    populated from Garmin data or mock data. Freezing prevents mutation
    bugs inside rules.
    """

    # Identity & demographics
    name: str
    age: int
    weight_kg: float
    sex: str  # "M" or "F"

    # Physiology
    max_hr: int
    lthr_bpm: int
    lthr_pace_s_per_km: int  # Lactate threshold pace in seconds per km
    vo2max: float
    vo2max_history: tuple[tuple[str, float], ...] = field(default_factory=tuple)
    resting_hr: int = 50

    # Plan context
    current_phase: TrainingPhase = TrainingPhase.BASE
    current_week: int = 1  # 1-indexed
    total_plan_weeks: int = 16
    day_of_week: int = 1  # 1=Monday, 7=Sunday
    goal_race_date: date | None = None

    # Training history
    weekly_volume_history: tuple[float, ...] = field(default_factory=tuple)
    daily_loads: tuple[float, ...] = field(default_factory=tuple)

    # Computed load metrics (can be pre-computed or computed by engine)
    acwr: float | None = None

    # Readiness / recovery (mocked for now)
    hrv_rmssd: float | None = None
    hrv_baseline: float | None = None
    sleep_score: float | None = None
    readiness: ReadinessLevel = ReadinessLevel.NORMAL
    body_battery: int | None = None

    # Critical Speed model data
    distance_time_pairs: tuple[tuple[float, float], ...] = field(default_factory=tuple)
    critical_speed_m_per_s: float | None = None
    d_prime_meters: float | None = None

    # DRIVE: training debt and marathon pace tracking
    training_debt: TrainingDebtLedger | None = None
    cumulative_mp_time_min: float = 0.0

    # Race calendar (multi-race support)
    race_calendar: RaceCalendar | None = None
    current_date: date | None = None

    # Environmental
    temperature_celsius: float | None = None
    humidity_pct: float | None = None  # Relative humidity 0-100
