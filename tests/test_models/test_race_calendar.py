"""Tests for RaceCalendar and RaceEntry models."""

from __future__ import annotations

from datetime import date

import pytest

from science_engine.models.enums import RacePriority
from science_engine.models.race_calendar import RaceCalendar, RaceEntry


@pytest.fixture
def race_a() -> RaceEntry:
    return RaceEntry(
        race_date=date(2026, 10, 18),
        distance_km=42.195,
        race_name="Chicago Marathon",
        priority=RacePriority.A,
    )


@pytest.fixture
def race_b() -> RaceEntry:
    return RaceEntry(
        race_date=date(2026, 6, 14),
        distance_km=21.1,
        race_name="City Half Marathon",
        priority=RacePriority.B,
    )


@pytest.fixture
def race_c() -> RaceEntry:
    return RaceEntry(
        race_date=date(2026, 3, 15),
        distance_km=8.0,
        race_name="Spring 8K",
        priority=RacePriority.C,
    )


@pytest.fixture
def full_calendar(
    race_a: RaceEntry, race_b: RaceEntry, race_c: RaceEntry
) -> RaceCalendar:
    return RaceCalendar.from_entries(race_a, race_b, race_c)


class TestRaceEntry:
    def test_frozen(self, race_a: RaceEntry) -> None:
        with pytest.raises(AttributeError):
            race_a.race_name = "Nope"  # type: ignore[misc]

    def test_fields(self, race_a: RaceEntry) -> None:
        assert race_a.distance_km == 42.195
        assert race_a.priority == RacePriority.A


class TestRaceCalendar:
    def test_from_entries_sorts_chronologically(
        self, race_a: RaceEntry, race_b: RaceEntry, race_c: RaceEntry
    ) -> None:
        # Pass in reverse order
        cal = RaceCalendar.from_entries(race_a, race_b, race_c)
        assert cal.entries[0].race_date <= cal.entries[1].race_date
        assert cal.entries[1].race_date <= cal.entries[2].race_date

    def test_frozen(self, full_calendar: RaceCalendar) -> None:
        with pytest.raises(AttributeError):
            full_calendar.entries = ()  # type: ignore[misc]

    def test_a_race(self, full_calendar: RaceCalendar) -> None:
        a = full_calendar.a_race()
        assert a is not None
        assert a.priority == RacePriority.A
        assert a.race_name == "Chicago Marathon"

    def test_a_race_none_when_missing(self, race_b: RaceEntry) -> None:
        cal = RaceCalendar.from_entries(race_b)
        assert cal.a_race() is None

    def test_next_race(self, full_calendar: RaceCalendar) -> None:
        # Before all races
        nxt = full_calendar.next_race(date(2026, 1, 1))
        assert nxt is not None
        assert nxt.race_name == "Spring 8K"

    def test_next_race_on_race_day(self, full_calendar: RaceCalendar) -> None:
        nxt = full_calendar.next_race(date(2026, 3, 15))
        assert nxt is not None
        assert nxt.race_name == "Spring 8K"

    def test_next_race_after_all(self, full_calendar: RaceCalendar) -> None:
        assert full_calendar.next_race(date(2027, 1, 1)) is None

    def test_next_race_by_priority(self, full_calendar: RaceCalendar) -> None:
        b = full_calendar.next_race_by_priority(date(2026, 1, 1), RacePriority.B)
        assert b is not None
        assert b.race_name == "City Half Marathon"

    def test_races_in_range(self, full_calendar: RaceCalendar) -> None:
        races = full_calendar.races_in_range(date(2026, 3, 1), date(2026, 7, 1))
        assert len(races) == 2
        names = {r.race_name for r in races}
        assert "Spring 8K" in names
        assert "City Half Marathon" in names

    def test_races_in_range_empty(self, full_calendar: RaceCalendar) -> None:
        races = full_calendar.races_in_range(date(2025, 1, 1), date(2025, 12, 31))
        assert len(races) == 0

    def test_days_until_next_race(self, full_calendar: RaceCalendar) -> None:
        days = full_calendar.days_until_next_race(date(2026, 3, 10))
        assert days == 5  # 5 days to Spring 8K on Mar 15

    def test_days_until_next_race_none(self, full_calendar: RaceCalendar) -> None:
        assert full_calendar.days_until_next_race(date(2027, 1, 1)) is None

    def test_is_race_day_true(self, full_calendar: RaceCalendar) -> None:
        assert full_calendar.is_race_day(date(2026, 10, 18)) is True

    def test_is_race_day_false(self, full_calendar: RaceCalendar) -> None:
        assert full_calendar.is_race_day(date(2026, 5, 1)) is False

    def test_race_on_date(self, full_calendar: RaceCalendar) -> None:
        race = full_calendar.race_on_date(date(2026, 6, 14))
        assert race is not None
        assert race.race_name == "City Half Marathon"

    def test_race_on_date_none(self, full_calendar: RaceCalendar) -> None:
        assert full_calendar.race_on_date(date(2026, 5, 1)) is None

    def test_empty_calendar(self) -> None:
        cal = RaceCalendar()
        assert cal.a_race() is None
        assert cal.next_race(date(2026, 1, 1)) is None
        assert cal.days_until_next_race(date(2026, 1, 1)) is None
        assert cal.is_race_day(date(2026, 1, 1)) is False
