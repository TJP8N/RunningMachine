"""Race calendar — multi-race scheduling model for periodization.

Supports A/B/C race priorities for training plans with multiple target
races (e.g. A-race marathon Oct, B-race half Jun, C-race 8K Mar).

Reference:
    Mujika (2010). Intense training: the key to optimal performance
    before and during the taper. Scand J Med Sci Sports 20(s2):24-31.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from science_engine.models.enums import RacePriority


@dataclass(frozen=True)
class RaceEntry:
    """A single race on the calendar."""

    race_date: date
    distance_km: float
    race_name: str
    priority: RacePriority


@dataclass(frozen=True)
class RaceCalendar:
    """Frozen calendar of planned races with query helpers.

    Entries are stored sorted chronologically. Use ``from_entries()``
    factory to build from unsorted inputs.
    """

    entries: tuple[RaceEntry, ...] = field(default_factory=tuple)

    # -- Factory ----------------------------------------------------------

    @classmethod
    def from_entries(cls, *entries: RaceEntry) -> RaceCalendar:
        """Create a RaceCalendar with entries sorted chronologically."""
        sorted_entries = tuple(sorted(entries, key=lambda e: e.race_date))
        return cls(entries=sorted_entries)

    # -- Query helpers ----------------------------------------------------

    def a_race(self) -> RaceEntry | None:
        """Return the first A-priority race, or None."""
        for entry in self.entries:
            if entry.priority == RacePriority.A:
                return entry
        return None

    def next_race(self, as_of: date) -> RaceEntry | None:
        """Return the next race on or after *as_of*, any priority."""
        for entry in self.entries:
            if entry.race_date >= as_of:
                return entry
        return None

    def next_race_by_priority(
        self, as_of: date, priority: RacePriority
    ) -> RaceEntry | None:
        """Return the next race of a specific priority on or after *as_of*."""
        for entry in self.entries:
            if entry.race_date >= as_of and entry.priority == priority:
                return entry
        return None

    def races_in_range(
        self, start: date, end: date
    ) -> tuple[RaceEntry, ...]:
        """Return all races whose date falls in [start, end] inclusive."""
        return tuple(
            e for e in self.entries if start <= e.race_date <= end
        )

    def days_until_next_race(self, as_of: date) -> int | None:
        """Days from *as_of* to the next race, or None if no future races."""
        nxt = self.next_race(as_of)
        if nxt is None:
            return None
        return (nxt.race_date - as_of).days

    def is_race_day(self, on_date: date) -> bool:
        """True if any race falls on *on_date*."""
        return any(e.race_date == on_date for e in self.entries)

    def race_on_date(self, on_date: date) -> RaceEntry | None:
        """Return the race entry for *on_date*, or None."""
        for entry in self.entries:
            if entry.race_date == on_date:
                return entry
        return None
