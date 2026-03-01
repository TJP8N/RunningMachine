"""Shared test fixtures: mock athletes, training load data, readiness states."""

from __future__ import annotations

from datetime import date
from typing import Callable

import pytest

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import RacePriority, ReadinessLevel, SessionType, TrainingPhase
from science_engine.models.race_calendar import RaceCalendar, RaceEntry
from science_engine.models.training_debt import DebtEntry, TrainingDebtLedger
from science_engine.models.weekly_plan import WeekContext
from science_engine.models.workout import WorkoutPrescription


@pytest.fixture
def beginner_athlete() -> AthleteState:
    """50-year-old beginner: VO2max 38, LTHR 155, LT pace 6:00/km, 30 km/week."""
    return AthleteState(
        name="Bob",
        age=50,
        weight_kg=82.0,
        sex="M",
        max_hr=170,
        lthr_bpm=155,
        lthr_pace_s_per_km=360,  # 6:00/km
        vo2max=38.0,
        resting_hr=55,
        current_phase=TrainingPhase.BASE,
        current_week=3,
        total_plan_weeks=16,
        day_of_week=2,  # Tuesday
        weekly_volume_history=(28.0, 30.0, 31.0),
        daily_loads=tuple([40.0] * 28),  # Stable loads
        readiness=ReadinessLevel.NORMAL,
    )


@pytest.fixture
def intermediate_athlete() -> AthleteState:
    """35-year-old intermediate (Sarah from blueprint): VO2max 48, LTHR 168, 50 km/week."""
    return AthleteState(
        name="Sarah",
        age=35,
        weight_kg=62.0,
        sex="F",
        max_hr=185,
        lthr_bpm=168,
        lthr_pace_s_per_km=305,  # 5:05/km
        vo2max=48.0,
        resting_hr=48,
        current_phase=TrainingPhase.BUILD,
        current_week=9,
        total_plan_weeks=16,
        day_of_week=2,  # Tuesday
        weekly_volume_history=(42.0, 44.0, 46.0, 48.0, 50.0),
        daily_loads=tuple([55.0] * 28),  # Stable loads
        readiness=ReadinessLevel.NORMAL,
        goal_race_date=date(2026, 6, 15),
    )


@pytest.fixture
def advanced_athlete() -> AthleteState:
    """28-year-old advanced: VO2max 58, LTHR 175, LT pace 4:10/km, 80 km/week."""
    return AthleteState(
        name="Alex",
        age=28,
        weight_kg=68.0,
        sex="M",
        max_hr=195,
        lthr_bpm=175,
        lthr_pace_s_per_km=250,  # 4:10/km
        vo2max=58.0,
        resting_hr=42,
        current_phase=TrainingPhase.SPECIFIC,
        current_week=12,
        total_plan_weeks=16,
        day_of_week=4,  # Thursday
        weekly_volume_history=(70.0, 75.0, 78.0, 80.0),
        daily_loads=tuple([75.0] * 28),  # Stable loads
        readiness=ReadinessLevel.NORMAL,
    )


@pytest.fixture
def safe_daily_loads() -> tuple[float, ...]:
    """28 days of stable training → ACWR ~1.0."""
    return tuple([50.0] * 28)


@pytest.fixture
def spiked_daily_loads() -> tuple[float, ...]:
    """21 days low + 7 days high → ACWR > 1.5."""
    low_days = [30.0] * 21
    high_days = [90.0] * 7
    return tuple(low_days + high_days)


@pytest.fixture
def undertrained_daily_loads() -> tuple[float, ...]:
    """21 days moderate + 7 days very low → ACWR < 0.8."""
    moderate_days = [60.0] * 21
    low_days = [15.0] * 7
    return tuple(moderate_days + low_days)


# ---------------------------------------------------------------------------
# Milestone 2 fixtures: Critical Speed, Training Debt, Weekly Planning
# ---------------------------------------------------------------------------


@pytest.fixture
def cs_distance_time_pairs() -> tuple[tuple[float, float], ...]:
    """Realistic distance-time pairs for CS fitting.

    Based on a ~4.2 m/s CS runner (~3:58/km threshold pace):
        1500m in 5:20 (320s), 3k in 11:00 (660s),
        5k in 19:00 (1140s), 10k in 39:30 (2370s).
    """
    return (
        (1500.0, 320.0),
        (3000.0, 660.0),
        (5000.0, 1140.0),
        (10000.0, 2370.0),
    )


@pytest.fixture
def athlete_with_cs_data(
    cs_distance_time_pairs: tuple[tuple[float, float], ...],
) -> AthleteState:
    """Intermediate athlete with Critical Speed data populated."""
    return AthleteState(
        name="Sarah",
        age=35,
        weight_kg=62.0,
        sex="F",
        max_hr=185,
        lthr_bpm=168,
        lthr_pace_s_per_km=305,
        vo2max=48.0,
        resting_hr=48,
        current_phase=TrainingPhase.BUILD,
        current_week=8,
        total_plan_weeks=16,
        day_of_week=2,
        weekly_volume_history=(42.0, 44.0, 46.0, 48.0, 50.0),
        daily_loads=tuple([55.0] * 28),
        readiness=ReadinessLevel.NORMAL,
        goal_race_date=date(2026, 6, 15),
        distance_time_pairs=cs_distance_time_pairs,
    )


@pytest.fixture
def sample_debt_ledger() -> TrainingDebtLedger:
    """Ledger with a mix of recent and older debt entries."""
    return TrainingDebtLedger(entries=(
        DebtEntry(session_type=SessionType.TEMPO, missed_duration_min=50.0, weeks_ago=0),
        DebtEntry(session_type=SessionType.LONG_RUN, missed_duration_min=30.0, weeks_ago=2),
        DebtEntry(session_type=SessionType.THRESHOLD, missed_duration_min=40.0, weeks_ago=5),
    ))


@pytest.fixture
def week_context_factory() -> Callable[..., WeekContext]:
    """Factory fixture for creating WeekContext instances.

    Usage:
        ctx = week_context_factory(day=3, key_sessions=1)
    """
    from science_engine.models.enums import IntensityLevel

    def _make_easy() -> WorkoutPrescription:
        return WorkoutPrescription(
            session_type=SessionType.EASY,
            intensity_level=IntensityLevel.A_FULL,
            target_duration_min=45.0,
        )

    def _make_key(st: SessionType = SessionType.THRESHOLD) -> WorkoutPrescription:
        return WorkoutPrescription(
            session_type=st,
            intensity_level=IntensityLevel.A_FULL,
            target_duration_min=50.0,
        )

    def factory(
        day: int = 1,
        key_sessions: int = 0,
        easy_sessions: int = 0,
        phase: TrainingPhase = TrainingPhase.BUILD,
        is_recovery_week: bool = False,
    ) -> WeekContext:
        sessions: list[WorkoutPrescription] = []
        for _ in range(key_sessions):
            sessions.append(_make_key())
        for _ in range(easy_sessions):
            sessions.append(_make_easy())
        return WeekContext(
            day_number=day,
            planned_sessions=tuple(sessions),
            phase=phase,
            is_recovery_week=is_recovery_week,
        )

    return factory


# ---------------------------------------------------------------------------
# Milestone 3 fixtures: Race Calendar, HRV / Recovery data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_race_calendar() -> RaceCalendar:
    """Calendar with A-race (marathon Oct), B-race (half Jun), C-race (8K Mar)."""
    return RaceCalendar.from_entries(
        RaceEntry(
            race_date=date(2026, 10, 18),
            distance_km=42.195,
            race_name="Chicago Marathon",
            priority=RacePriority.A,
        ),
        RaceEntry(
            race_date=date(2026, 6, 14),
            distance_km=21.1,
            race_name="City Half Marathon",
            priority=RacePriority.B,
        ),
        RaceEntry(
            race_date=date(2026, 3, 15),
            distance_km=8.0,
            race_name="Spring 8K",
            priority=RacePriority.C,
        ),
    )


@pytest.fixture
def athlete_with_race_calendar(sample_race_calendar: RaceCalendar) -> AthleteState:
    """Intermediate athlete with a multi-race calendar."""
    return AthleteState(
        name="Sarah",
        age=35,
        weight_kg=62.0,
        sex="F",
        max_hr=185,
        lthr_bpm=168,
        lthr_pace_s_per_km=305,
        vo2max=48.0,
        resting_hr=48,
        current_phase=TrainingPhase.BUILD,
        current_week=8,
        total_plan_weeks=16,
        day_of_week=2,
        weekly_volume_history=(42.0, 44.0, 46.0, 48.0, 50.0),
        daily_loads=tuple([55.0] * 28),
        readiness=ReadinessLevel.NORMAL,
        goal_race_date=date(2026, 10, 18),
        race_calendar=sample_race_calendar,
        current_date=date(2026, 4, 15),
    )


@pytest.fixture
def athlete_for_structured() -> AthleteState:
    """Athlete with CS data + HRV for rich structured workout descriptions."""
    return AthleteState(
        name="Structured Runner",
        age=32,
        weight_kg=65.0,
        sex="F",
        max_hr=188,
        lthr_bpm=168,
        lthr_pace_s_per_km=305,
        vo2max=48.0,
        resting_hr=48,
        current_phase=TrainingPhase.BUILD,
        current_week=8,
        total_plan_weeks=16,
        day_of_week=2,
        weekly_volume_history=(42.0, 44.0, 46.0, 48.0, 50.0),
        daily_loads=tuple([55.0] * 28),
        readiness=ReadinessLevel.NORMAL,
        goal_race_date=date(2026, 6, 15),
        critical_speed_m_per_s=4.2,
        d_prime_meters=200.0,
        hrv_rmssd=45.0,
        hrv_baseline=50.0,
        sleep_score=78.0,
        body_battery=72,
        acwr=1.05,
    )


@pytest.fixture
def athlete_for_ceiling() -> AthleteState:
    """Athlete with CS, VO2max, and VO2max history for ceiling estimation."""
    return AthleteState(
        name="Ceiling Runner",
        age=35,
        weight_kg=62.0,
        sex="F",
        max_hr=185,
        lthr_bpm=168,
        lthr_pace_s_per_km=305,
        vo2max=48.0,
        vo2max_history=(
            ("2025-10-01", 45.0),
            ("2025-11-01", 46.0),
            ("2025-12-01", 47.0),
            ("2026-01-01", 48.0),
            ("2026-02-01", 49.0),
        ),
        resting_hr=48,
        current_phase=TrainingPhase.BUILD,
        current_week=8,
        total_plan_weeks=16,
        day_of_week=2,
        weekly_volume_history=(42.0, 44.0, 46.0, 48.0, 50.0),
        daily_loads=tuple([55.0] * 28),
        readiness=ReadinessLevel.NORMAL,
        goal_race_date=date(2026, 6, 15),
        critical_speed_m_per_s=4.2,
        d_prime_meters=200.0,
    )


@pytest.fixture
def athlete_with_hrv_data() -> AthleteState:
    """Athlete with HRV, sleep, and body battery data populated."""
    return AthleteState(
        name="HRV Runner",
        age=32,
        weight_kg=68.0,
        sex="F",
        max_hr=188,
        lthr_bpm=165,
        lthr_pace_s_per_km=310,
        vo2max=46.0,
        resting_hr=50,
        current_phase=TrainingPhase.BUILD,
        current_week=6,
        total_plan_weeks=16,
        day_of_week=3,
        weekly_volume_history=(40.0, 42.0, 44.0),
        daily_loads=tuple([50.0] * 28),
        readiness=ReadinessLevel.NORMAL,
        hrv_rmssd=35.0,
        hrv_baseline=50.0,
        sleep_score=55.0,
        body_battery=45,
    )
