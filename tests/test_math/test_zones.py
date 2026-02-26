"""Tests for heart rate and pace zone calculations."""

from science_engine.math.zones import calculate_hr_zones, calculate_pace_zones
from science_engine.models.enums import ZoneType


class TestHRZones:
    def test_zone_boundaries_dont_overlap(self) -> None:
        zones = calculate_hr_zones(lthr_bpm=168, max_hr=185)
        for i in range(len(zones) - 1):
            assert zones[i].upper <= zones[i + 1].lower or zones[i].upper == zones[i + 1].lower

    def test_zone_4_straddles_lthr(self) -> None:
        lthr = 168
        zones = calculate_hr_zones(lthr_bpm=lthr, max_hr=185)
        z4 = next(z for z in zones if z.zone == ZoneType.ZONE_4)
        assert z4.lower <= lthr <= z4.upper

    def test_zone_1_starts_at_zero(self) -> None:
        zones = calculate_hr_zones(lthr_bpm=168, max_hr=185)
        z1 = zones[0]
        assert z1.zone == ZoneType.ZONE_1
        assert z1.lower == 0

    def test_zone_5_ends_at_max_hr(self) -> None:
        zones = calculate_hr_zones(lthr_bpm=168, max_hr=185)
        z5 = next(z for z in zones if z.zone == ZoneType.ZONE_5)
        assert z5.upper == 185

    def test_different_athletes_get_different_zones(self) -> None:
        zones_beginner = calculate_hr_zones(lthr_bpm=155, max_hr=170)
        zones_advanced = calculate_hr_zones(lthr_bpm=175, max_hr=195)
        z3_beginner = next(z for z in zones_beginner if z.zone == ZoneType.ZONE_3)
        z3_advanced = next(z for z in zones_advanced if z.zone == ZoneType.ZONE_3)
        assert z3_beginner.lower != z3_advanced.lower

    def test_five_zones_returned(self) -> None:
        zones = calculate_hr_zones(lthr_bpm=168, max_hr=185)
        assert len(zones) == 5
        zone_types = [z.zone for z in zones]
        for zt in ZoneType:
            assert zt in zone_types


class TestPaceZones:
    def test_five_zones_returned(self) -> None:
        zones = calculate_pace_zones(lthr_pace_s_per_km=305)
        assert len(zones) == 5

    def test_zone_1_is_slowest(self) -> None:
        zones = calculate_pace_zones(lthr_pace_s_per_km=305)
        z1 = next(z for z in zones if z.zone == ZoneType.ZONE_1)
        z5 = next(z for z in zones if z.zone == ZoneType.ZONE_5)
        # Z1 upper (slowest pace) should be greater than Z5 upper
        assert z1.upper > z5.upper

    def test_different_lthr_paces_give_different_zones(self) -> None:
        zones_slow = calculate_pace_zones(lthr_pace_s_per_km=360)
        zones_fast = calculate_pace_zones(lthr_pace_s_per_km=250)
        z3_slow = next(z for z in zones_slow if z.zone == ZoneType.ZONE_3)
        z3_fast = next(z for z in zones_fast if z.zone == ZoneType.ZONE_3)
        assert z3_slow.lower > z3_fast.lower  # Slower athlete has higher s/km
