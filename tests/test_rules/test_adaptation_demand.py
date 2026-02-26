"""Tests for AdaptationDemandRule (DRIVE tier)."""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    ADAPTATION_DEMAND_MAX_MODIFIER,
    ADAPTATION_DEMAND_MIN_MODIFIER,
    Priority,
    ReadinessLevel,
    TrainingPhase,
)
from science_engine.rules.drive.adaptation_demand import AdaptationDemandRule


def _make_state(
    phase: TrainingPhase = TrainingPhase.BUILD,
    volume_history: tuple[float, ...] = (50.0, 50.0, 50.0),
    readiness: ReadinessLevel = ReadinessLevel.NORMAL,
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
        current_week=8,
        total_plan_weeks=16,
        day_of_week=2,
        daily_loads=tuple([50.0] * 28),  # Stable → ACWR ~1.0 (optimal)
        weekly_volume_history=volume_history,
        readiness=readiness,
    )


class TestAdaptationDemandRule:
    def setup_method(self) -> None:
        self.rule = AdaptationDemandRule()

    def test_rule_metadata(self) -> None:
        assert self.rule.priority == Priority.DRIVE
        assert self.rule.is_weekly_aware is False

    def test_detects_stagnation(self) -> None:
        """3 weeks at 50.0 km with optimal ACWR → should recommend bump."""
        state = _make_state(volume_history=(50.0, 50.0, 50.0))
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.volume_modifier >= ADAPTATION_DEMAND_MIN_MODIFIER

    def test_no_recommendation_when_volume_increasing(self) -> None:
        state = _make_state(volume_history=(40.0, 44.0, 48.0))
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_no_recommendation_during_taper(self) -> None:
        state = _make_state(
            phase=TrainingPhase.TAPER,
            volume_history=(50.0, 50.0, 50.0),
        )
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_no_recommendation_during_race(self) -> None:
        state = _make_state(
            phase=TrainingPhase.RACE,
            volume_history=(50.0, 50.0, 50.0),
        )
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_no_recommendation_suppressed_readiness(self) -> None:
        state = _make_state(
            volume_history=(50.0, 50.0, 50.0),
            readiness=ReadinessLevel.SUPPRESSED,
        )
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_no_recommendation_insufficient_history(self) -> None:
        state = _make_state(volume_history=(50.0, 50.0))
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_higher_modifier_for_longer_stagnation(self) -> None:
        """4+ weeks of stagnation → MAX modifier."""
        state = _make_state(volume_history=(50.0, 50.0, 50.0, 50.0))
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.volume_modifier == ADAPTATION_DEMAND_MAX_MODIFIER

    def test_base_phase_stagnation_detected(self) -> None:
        state = _make_state(
            phase=TrainingPhase.BASE,
            volume_history=(30.0, 30.0, 30.0),
        )
        rec = self.rule.evaluate(state)
        assert rec is not None

    def test_no_recommendation_acwr_not_optimal(self) -> None:
        """Spiked loads → ACWR in danger zone → no adaptation bump."""
        state = AthleteState(
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
            daily_loads=tuple([30.0] * 21 + [90.0] * 7),  # ACWR > 1.5
            weekly_volume_history=(50.0, 50.0, 50.0),
            readiness=ReadinessLevel.NORMAL,
        )
        rec = self.rule.evaluate(state)
        assert rec is None
