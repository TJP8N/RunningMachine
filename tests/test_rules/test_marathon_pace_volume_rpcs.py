"""Integration tests: RPCS confidence boost in MarathonPaceVolumeRule."""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    RPCS_LOW_CONFIDENCE_BOOST,
    RPCS_LOW_CONFIDENCE_THRESHOLD,
    SessionType,
    TrainingPhase,
)
from science_engine.models.mp_session_record import MPSessionRecord
from science_engine.rules.drive.marathon_pace_volume import MarathonPaceVolumeRule


def _make_state(
    cumulative_mp: float = 0.0,
    mp_sessions: tuple[MPSessionRecord, ...] = (),
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
        current_phase=TrainingPhase.BUILD,
        current_week=8,
        total_plan_weeks=16,
        day_of_week=2,
        daily_loads=tuple([50.0] * 28),
        weekly_volume_history=(40.0, 42.0, 44.0),
        cumulative_mp_time_min=cumulative_mp,
        mp_session_history=mp_sessions,
    )


class TestMarathonPaceVolumeRPCS:
    def setup_method(self) -> None:
        self.rule = MarathonPaceVolumeRule()

    def test_no_mp_history_keeps_default_confidence(self):
        """Without mp_session_history, confidence stays at 0.75."""
        state = _make_state(cumulative_mp=0.0)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.confidence == 0.75

    def test_low_rpcs_boosts_confidence(self):
        """Low RPCS composite score → confidence boosted to RPCS_LOW_CONFIDENCE_BOOST."""
        # Minimal sessions → low composite score
        sessions = (
            MPSessionRecord(
                date="2026-02-28",
                total_mp_time_min=10.0,
                longest_continuous_mp_min=10.0,
                weeks_ago=0.5,
            ),
        )
        state = _make_state(cumulative_mp=0.0, mp_sessions=sessions)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.confidence == RPCS_LOW_CONFIDENCE_BOOST
        assert "RPCS" in rec.explanation

    def test_high_rpcs_keeps_default_confidence(self):
        """High RPCS composite score → confidence stays at 0.75."""
        # Sessions that max out most components
        sessions = (
            MPSessionRecord(
                date="2026-02-28",
                total_mp_time_min=120.0,
                longest_continuous_mp_min=50.0,
                mp_in_second_half_min=40.0,
                was_long_run=True,
                weeks_ago=0.0,
                pace_std_dev_s_per_km=3.0,
            ),
        )
        state = _make_state(cumulative_mp=0.0, mp_sessions=sessions)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.confidence == 0.75
        assert "RPCS" not in rec.explanation

    def test_rpcs_boost_explanation_includes_score(self):
        """Boosted recommendation includes RPCS score in explanation."""
        sessions = (
            MPSessionRecord(
                date="2026-02-28",
                total_mp_time_min=5.0,
                longest_continuous_mp_min=5.0,
                weeks_ago=0.5,
            ),
        )
        state = _make_state(cumulative_mp=0.0, mp_sessions=sessions)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert "RPCS=" in rec.explanation
        assert "boosted" in rec.explanation.lower()
