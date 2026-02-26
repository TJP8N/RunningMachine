"""Tests for RaceProximityRule — OPTIMIZATION tier race calendar adjustments."""

from __future__ import annotations

from datetime import date

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import Priority, RacePriority, SessionType, TrainingPhase
from science_engine.models.race_calendar import RaceCalendar, RaceEntry
from science_engine.rules.optimization.race_proximity import RaceProximityRule


def _make_calendar(*entries: RaceEntry) -> RaceCalendar:
    return RaceCalendar.from_entries(*entries)


def _make_state(
    current_date: date,
    race_calendar: RaceCalendar,
    phase: TrainingPhase = TrainingPhase.BUILD,
) -> AthleteState:
    return AthleteState(
        name="Test",
        age=30,
        weight_kg=70.0,
        sex="M",
        max_hr=190,
        lthr_bpm=170,
        lthr_pace_s_per_km=300,
        vo2max=50.0,
        current_phase=phase,
        current_date=current_date,
        race_calendar=race_calendar,
        daily_loads=tuple([50.0] * 28),
    )


class TestRaceProximityRule:
    def setup_method(self) -> None:
        self.rule = RaceProximityRule()
        self.b_race = RaceEntry(
            race_date=date(2026, 6, 14),
            distance_km=21.1,
            race_name="City Half",
            priority=RacePriority.B,
        )
        self.c_race = RaceEntry(
            race_date=date(2026, 3, 15),
            distance_km=8.0,
            race_name="Spring 8K",
            priority=RacePriority.C,
        )
        self.a_race = RaceEntry(
            race_date=date(2026, 10, 18),
            distance_km=42.195,
            race_name="Chicago Marathon",
            priority=RacePriority.A,
        )

    def test_is_optimization_priority(self) -> None:
        assert self.rule.priority == Priority.OPTIMIZATION

    def test_race_day_returns_race_simulation(self) -> None:
        cal = _make_calendar(self.b_race)
        state = _make_state(date(2026, 6, 14), cal)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.RACE_SIMULATION
        assert rec.confidence == 1.0

    def test_day_before_race_returns_easy(self) -> None:
        cal = _make_calendar(self.b_race)
        state = _make_state(date(2026, 6, 13), cal)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.EASY
        assert rec.intensity_modifier == 0.7
        assert rec.volume_modifier == 0.6

    def test_day_before_c_race_returns_easy(self) -> None:
        cal = _make_calendar(self.c_race)
        state = _make_state(date(2026, 3, 14), cal)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.EASY

    def test_b_race_mini_taper_within_7_days(self) -> None:
        cal = _make_calendar(self.b_race)
        # 5 days before B-race
        state = _make_state(date(2026, 6, 9), cal)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type is None  # modifiers only
        assert rec.volume_modifier < 1.0
        assert rec.intensity_modifier < 1.0

    def test_b_race_mini_taper_at_2_days(self) -> None:
        cal = _make_calendar(self.b_race)
        state = _make_state(date(2026, 6, 12), cal)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.volume_modifier < 1.0

    def test_post_b_race_recovery(self) -> None:
        cal = _make_calendar(self.b_race)
        # 2 days after B-race
        state = _make_state(date(2026, 6, 16), cal)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.EASY
        assert "Recovery" in rec.explanation or "recovery" in rec.explanation

    def test_post_b_race_recovery_day_3(self) -> None:
        cal = _make_calendar(self.b_race)
        # 3 days after B-race (still within recovery window)
        state = _make_state(date(2026, 6, 17), cal)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.EASY

    def test_post_b_race_day_4_no_recovery(self) -> None:
        cal = _make_calendar(self.b_race)
        # 4 days after → outside recovery window
        state = _make_state(date(2026, 6, 18), cal)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_defers_during_taper_phase(self) -> None:
        cal = _make_calendar(self.b_race)
        state = _make_state(date(2026, 6, 13), cal, phase=TrainingPhase.TAPER)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_defers_during_race_phase(self) -> None:
        cal = _make_calendar(self.b_race)
        state = _make_state(date(2026, 6, 13), cal, phase=TrainingPhase.RACE)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_no_data_graceful(self) -> None:
        state = AthleteState(
            name="Test",
            age=30,
            weight_kg=70.0,
            sex="M",
            max_hr=190,
            lthr_bpm=170,
            lthr_pace_s_per_km=300,
            vo2max=50.0,
        )
        assert not self.rule.has_required_data(state)

    def test_no_nearby_races_returns_none(self) -> None:
        cal = _make_calendar(self.a_race)  # A-race is in October
        state = _make_state(date(2026, 4, 1), cal)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_explanation_cites_mujika(self) -> None:
        cal = _make_calendar(self.b_race)
        state = _make_state(date(2026, 6, 14), cal)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert "Mujika" in rec.explanation
