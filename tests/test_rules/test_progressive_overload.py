"""Tests for ProgressiveOverloadRule — safe volume progression."""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import TrainingPhase
from science_engine.rules.optimization.progressive_overload import ProgressiveOverloadRule


class TestProgressiveOverloadRule:
    def setup_method(self) -> None:
        self.rule = ProgressiveOverloadRule()

    def _make_state(
        self, weekly_volumes: tuple[float, ...], week: int, total_weeks: int = 16
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
            current_week=week,
            total_plan_weeks=total_weeks,
            weekly_volume_history=weekly_volumes,
        )

    def test_volume_increases_from_last_week(self) -> None:
        # Week 3 is a normal (non-recovery) week in a 16-week plan
        state = self._make_state((40.0, 42.0, 44.0), week=3)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.target_distance_km is not None
        assert rec.target_distance_km > 44.0

    def test_volume_never_spikes_above_10_percent(self) -> None:
        state = self._make_state((50.0,), week=3)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.target_distance_km is not None
        max_allowed = 50.0 * 1.10
        assert rec.target_distance_km <= max_allowed + 0.1  # Rounding tolerance

    def test_early_base_uses_higher_increase(self) -> None:
        # Week 2 of 16 = 12.5% through plan → early base
        state = self._make_state((40.0,), week=2, total_weeks=16)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.target_distance_km is not None
        # 8% increase from 40 = 43.2
        assert rec.target_distance_km >= 43.0

    def test_near_peak_uses_conservative_increase(self) -> None:
        # Week 13 of 16 = 81% → near-peak
        state = self._make_state((65.0,), week=13, total_weeks=16)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.target_distance_km is not None
        # 5% increase from 65 = 68.25
        assert rec.target_distance_km <= 69.0

    def test_recovery_week_reduces_volume(self) -> None:
        # Need to find a week that is actually a recovery week
        from science_engine.math.periodization import allocate_phases, is_recovery_week

        phases = allocate_phases(16)
        recovery_wk = None
        for w in range(1, 17):
            if is_recovery_week(w, phases):
                recovery_wk = w
                break

        if recovery_wk is not None:
            state = self._make_state((50.0,), week=recovery_wk)
            rec = self.rule.evaluate(state)
            assert rec is not None
            assert rec.target_distance_km is not None
            assert rec.target_distance_km < 50.0

    def test_returns_recommendation_always(self) -> None:
        state = self._make_state((30.0,), week=5)
        rec = self.rule.evaluate(state)
        assert rec is not None
