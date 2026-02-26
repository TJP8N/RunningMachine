"""Tests for HRVReadinessRule — RECOVERY tier HRV gating."""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    HRV_SUPPRESS_THRESHOLD,
    HRV_VETO_THRESHOLD,
    Priority,
    SessionType,
)
from science_engine.rules.recovery.hrv_readiness import HRVReadinessRule


class TestHRVReadinessRule:
    def setup_method(self) -> None:
        self.rule = HRVReadinessRule()

    def _make_state(
        self,
        hrv_rmssd: float | None = None,
        hrv_baseline: float | None = None,
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
            hrv_rmssd=hrv_rmssd,
            hrv_baseline=hrv_baseline,
        )

    def test_is_recovery_priority(self) -> None:
        assert self.rule.priority == Priority.RECOVERY

    def test_veto_on_very_low_hrv(self) -> None:
        # 63% of baseline → below 70% veto threshold
        state = self._make_state(hrv_rmssd=31.5, hrv_baseline=50.0)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.veto is True
        assert rec.recommended_session_type == SessionType.RECOVERY
        assert rec.confidence == 0.9

    def test_suppress_on_moderate_hrv(self) -> None:
        # 80% of baseline → below 85% suppress threshold
        state = self._make_state(hrv_rmssd=40.0, hrv_baseline=50.0)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.veto is False
        assert rec.recommended_session_type == SessionType.EASY
        assert rec.intensity_modifier < 1.0

    def test_no_action_on_normal_hrv(self) -> None:
        # 91% of baseline → above suppress threshold
        state = self._make_state(hrv_rmssd=45.5, hrv_baseline=50.0)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_boundary_at_veto_threshold(self) -> None:
        # Exactly at 70% → should NOT veto (< 0.70 is veto)
        state = self._make_state(hrv_rmssd=35.0, hrv_baseline=50.0)
        rec = self.rule.evaluate(state)
        # ratio = 0.70, not < 0.70, so suppress
        assert rec is not None
        assert rec.veto is False

    def test_boundary_at_suppress_threshold(self) -> None:
        # Exactly at 85% → should be None (< 0.85 is suppress)
        state = self._make_state(hrv_rmssd=42.5, hrv_baseline=50.0)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_just_below_veto_threshold(self) -> None:
        # 69% → veto
        state = self._make_state(hrv_rmssd=34.5, hrv_baseline=50.0)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.veto is True

    def test_graceful_when_no_data(self) -> None:
        state = self._make_state(hrv_rmssd=None, hrv_baseline=None)
        assert not self.rule.has_required_data(state)

    def test_graceful_when_partial_data(self) -> None:
        state = self._make_state(hrv_rmssd=45.0, hrv_baseline=None)
        assert not self.rule.has_required_data(state)

    def test_explanation_cites_references(self) -> None:
        state = self._make_state(hrv_rmssd=30.0, hrv_baseline=50.0)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert "Plews" in rec.explanation
        assert "Buchheit" in rec.explanation
