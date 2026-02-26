"""Tests for SleepQualityRule — RECOVERY tier sleep gating."""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import Priority, SessionType
from science_engine.rules.recovery.sleep_quality import SleepQualityRule


class TestSleepQualityRule:
    def setup_method(self) -> None:
        self.rule = SleepQualityRule()

    def _make_state(self, sleep_score: float | None = None) -> AthleteState:
        return AthleteState(
            name="Test",
            age=30,
            weight_kg=70.0,
            sex="M",
            max_hr=190,
            lthr_bpm=170,
            lthr_pace_s_per_km=300,
            vo2max=50.0,
            sleep_score=sleep_score,
        )

    def test_is_recovery_priority(self) -> None:
        assert self.rule.priority == Priority.RECOVERY

    def test_veto_on_very_poor_sleep(self) -> None:
        # Score 30 → below 40 veto threshold
        state = self._make_state(sleep_score=30.0)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.veto is True
        assert rec.recommended_session_type == SessionType.RECOVERY
        assert rec.confidence == 0.8

    def test_suppress_on_moderate_sleep(self) -> None:
        # Score 50 → below 60 suppress threshold
        state = self._make_state(sleep_score=50.0)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.veto is False
        assert rec.recommended_session_type == SessionType.EASY

    def test_no_action_on_good_sleep(self) -> None:
        # Score 75 → above suppress threshold
        state = self._make_state(sleep_score=75.0)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_boundary_at_veto_threshold(self) -> None:
        # Exactly 40 → should NOT veto (< 40 is veto)
        state = self._make_state(sleep_score=40.0)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.veto is False  # suppress, not veto

    def test_boundary_at_suppress_threshold(self) -> None:
        # Exactly 60 → no action (< 60 is suppress)
        state = self._make_state(sleep_score=60.0)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_graceful_when_no_data(self) -> None:
        state = self._make_state(sleep_score=None)
        assert not self.rule.has_required_data(state)

    def test_explanation_cites_references(self) -> None:
        state = self._make_state(sleep_score=30.0)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert "Fullagar" in rec.explanation
        assert "Vitale" in rec.explanation
