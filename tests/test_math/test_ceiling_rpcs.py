"""Integration tests: Race-Pace Confidence Scoring inside CeilingEstimate."""

from __future__ import annotations

import pytest

from science_engine.math.ceiling import estimate_ceiling
from science_engine.models.mp_session_record import MPSessionRecord
from science_engine.models.race_pace_confidence import RacePaceConfidence


def _make_sessions() -> list[MPSessionRecord]:
    return [
        MPSessionRecord(
            date="2026-02-28",
            total_mp_time_min=40.0,
            longest_continuous_mp_min=40.0,
            mp_in_second_half_min=20.0,
            was_long_run=True,
            weeks_ago=0.5,
            pace_std_dev_s_per_km=5.0,
        ),
        MPSessionRecord(
            date="2026-02-14",
            total_mp_time_min=30.0,
            longest_continuous_mp_min=30.0,
            mp_in_second_half_min=15.0,
            was_long_run=True,
            weeks_ago=2.5,
        ),
    ]


class TestCeilingRPCSIntegration:
    def test_no_mp_sessions_gives_none_rpcs(self):
        """Backward compat: no mp_sessions → race_pace_confidence is None."""
        est = estimate_ceiling(vo2max=50.0)
        assert est.race_pace_confidence is None

    def test_empty_mp_sessions_gives_none_rpcs(self):
        """Empty list → race_pace_confidence is None."""
        est = estimate_ceiling(vo2max=50.0, mp_sessions=[])
        assert est.race_pace_confidence is None

    def test_mp_sessions_produces_rpcs(self):
        """Non-empty mp_sessions → race_pace_confidence is populated."""
        sessions = _make_sessions()
        est = estimate_ceiling(vo2max=50.0, mp_sessions=sessions)
        rpcs = est.race_pace_confidence
        assert rpcs is not None
        assert isinstance(rpcs, RacePaceConfidence)
        assert 0 <= rpcs.composite_score <= 100
        assert rpcs.sessions_counted == 2

    def test_rpcs_does_not_affect_marathon_time(self):
        """RPCS is additive info — doesn't change the time estimate itself."""
        est_without = estimate_ceiling(vo2max=50.0)
        est_with = estimate_ceiling(vo2max=50.0, mp_sessions=_make_sessions())
        assert est_without.marathon_time_s == pytest.approx(
            est_with.marathon_time_s, abs=0.01
        )

    def test_rpcs_with_cs_and_vo2max(self):
        """RPCS works alongside both convergence signals."""
        sessions = _make_sessions()
        est = estimate_ceiling(cs=4.2, vo2max=50.0, mp_sessions=sessions)
        assert est.race_pace_confidence is not None
        assert est.data_quality in ("MODERATE", "HIGH")
