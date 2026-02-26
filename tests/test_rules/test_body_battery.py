"""Tests for BodyBatteryRule — RECOVERY tier Garmin Body Battery gating."""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import Priority, SessionType
from science_engine.rules.recovery.body_battery import BodyBatteryRule


class TestBodyBatteryRule:
    def setup_method(self) -> None:
        self.rule = BodyBatteryRule()

    def _make_state(self, body_battery: int | None = None) -> AthleteState:
        return AthleteState(
            name="Test",
            age=30,
            weight_kg=70.0,
            sex="M",
            max_hr=190,
            lthr_bpm=170,
            lthr_pace_s_per_km=300,
            vo2max=50.0,
            body_battery=body_battery,
        )

    def test_is_recovery_priority(self) -> None:
        assert self.rule.priority == Priority.RECOVERY

    def test_veto_on_very_low_battery(self) -> None:
        # 15 → below 25 veto threshold
        state = self._make_state(body_battery=15)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.veto is True
        assert rec.recommended_session_type == SessionType.REST
        assert rec.confidence == 0.7

    def test_suppress_on_low_battery(self) -> None:
        # 35 → below 50 suppress threshold
        state = self._make_state(body_battery=35)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.veto is False
        assert rec.recommended_session_type == SessionType.EASY

    def test_mild_on_moderate_battery(self) -> None:
        # 60 → below 75 mild threshold
        state = self._make_state(body_battery=60)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.veto is False
        assert rec.recommended_session_type is None  # No session override
        assert rec.intensity_modifier < 1.0
        assert rec.volume_modifier < 1.0

    def test_no_action_on_good_battery(self) -> None:
        # 85 → above mild threshold
        state = self._make_state(body_battery=85)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_boundary_at_veto_threshold(self) -> None:
        # Exactly 25 → suppress, not veto (< 25 is veto)
        state = self._make_state(body_battery=25)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.veto is False

    def test_boundary_at_suppress_threshold(self) -> None:
        # Exactly 50 → mild, not suppress (< 50 is suppress)
        state = self._make_state(body_battery=50)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type is None  # mild zone

    def test_boundary_at_mild_threshold(self) -> None:
        # Exactly 75 → no action (< 75 is mild)
        state = self._make_state(body_battery=75)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_graceful_when_no_data(self) -> None:
        state = self._make_state(body_battery=None)
        assert not self.rule.has_required_data(state)

    def test_explanation_cites_reference(self) -> None:
        state = self._make_state(body_battery=10)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert "Firstbeat" in rec.explanation or "Garmin" in rec.explanation
