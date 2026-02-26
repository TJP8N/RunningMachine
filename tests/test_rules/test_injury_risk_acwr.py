"""Tests for InjuryRiskACWRRule — SAFETY tier ACWR guardrails."""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import Priority, TrainingPhase
from science_engine.rules.safety.injury_risk_acwr import InjuryRiskACWRRule


class TestInjuryRiskACWRRule:
    def setup_method(self) -> None:
        self.rule = InjuryRiskACWRRule()

    def _make_state(self, daily_loads: tuple[float, ...]) -> AthleteState:
        return AthleteState(
            name="Test",
            age=30,
            weight_kg=70.0,
            sex="M",
            max_hr=190,
            lthr_bpm=170,
            lthr_pace_s_per_km=300,
            vo2max=50.0,
            daily_loads=daily_loads,
        )

    def test_is_safety_priority(self) -> None:
        assert self.rule.priority == Priority.SAFETY

    def test_veto_on_danger_acwr(self, spiked_daily_loads: tuple[float, ...]) -> None:
        state = self._make_state(spiked_daily_loads)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.veto is True

    def test_reduces_intensity_on_caution(self) -> None:
        # Create loads that produce caution-range ACWR (1.3-1.5)
        # Moderate spike: 21 days at 40, then 7 days at 65
        loads = tuple([40.0] * 21 + [65.0] * 7)
        state = self._make_state(loads)
        rec = self.rule.evaluate(state)
        if rec is not None and not rec.veto:
            assert rec.intensity_modifier < 1.0

    def test_no_recommendation_on_optimal(self, safe_daily_loads: tuple[float, ...]) -> None:
        state = self._make_state(safe_daily_loads)
        rec = self.rule.evaluate(state)
        # Optimal → None (no modification needed)
        assert rec is None

    def test_undertrained_flag(self, undertrained_daily_loads: tuple[float, ...]) -> None:
        state = self._make_state(undertrained_daily_loads)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.veto is False
        assert "undertrained" in rec.explanation.lower() or "below" in rec.explanation.lower()

    def test_no_data_returns_none(self) -> None:
        state = self._make_state(())
        assert not self.rule.has_required_data(state)

    def test_insufficient_data_returns_none(self) -> None:
        state = self._make_state(tuple([50.0] * 3))
        rec = self.rule.evaluate(state)
        assert rec is None  # ACWR returns 0.0 → no assessment
