"""Tests for science audit findings — TRIMP values, edge cases, cohesion."""

from __future__ import annotations

import math

from science_engine.conflict_resolution.resolver import ConflictResolver
from science_engine.conflict_resolution.strategies import HighestPriorityWins
from science_engine.math.training_load import calculate_trimp
from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    TRIMP_COEFFICIENT_MALE,
    TRIMP_COEFFICIENT_FEMALE,
    TRIMP_EXPONENT_MALE,
    TRIMP_EXPONENT_FEMALE,
    Priority,
    SessionType,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.rules.recovery.asymmetric_readiness import (
    AsymmetricReadinessRule,
)
from science_engine.rules.recovery.hrv_readiness import HRVReadinessRule


def _make_state(
    *,
    hrv_rmssd: float | None = None,
    hrv_baseline: float | None = None,
    sleep_score: float | None = None,
    body_battery: int | None = None,
    previous_day_session_type: SessionType | None = None,
    daily_loads: tuple[float, ...] = tuple([80.0] * 28),
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
        sleep_score=sleep_score,
        body_battery=body_battery,
        previous_day_session_type=previous_day_session_type,
        daily_loads=daily_loads,
    )


def _rec(
    rule_id: str,
    priority: Priority,
    session: SessionType = SessionType.EASY,
    veto: bool = False,
    confidence: float = 0.8,
    intensity: float = 1.0,
    volume: float = 1.0,
) -> RuleRecommendation:
    return RuleRecommendation(
        rule_id=rule_id,
        rule_version="1.0",
        priority=priority,
        recommended_session_type=session,
        intensity_modifier=intensity,
        volume_modifier=volume,
        veto=veto,
        explanation=f"Test recommendation from {rule_id}",
        confidence=confidence,
    )


# ------------------------------------------------------------------
# 1. TRIMP coefficient verification — Banister (1991)
# ------------------------------------------------------------------


class TestTRIMPAbsoluteValues:
    """Verify TRIMP values match the Banister (1991) formula.

    Formula: TRIMP = duration × ΔHR × 0.64 × exp(exponent × ΔHR)
    where exponent = 1.92 (M) / 1.67 (F) and ΔHR = (avg - rest) / (max - rest).
    """

    def test_banister_coefficients_correct(self) -> None:
        """Coefficient should be 0.64 for both sexes."""
        assert TRIMP_COEFFICIENT_MALE == 0.64
        assert TRIMP_COEFFICIENT_FEMALE == 0.64

    def test_banister_exponents_correct(self) -> None:
        """Exponent should be 1.92 (M) and 1.67 (F)."""
        assert TRIMP_EXPONENT_MALE == 1.92
        assert TRIMP_EXPONENT_FEMALE == 1.67

    def test_male_trimp_absolute_value(self) -> None:
        """Verify male TRIMP matches hand-calculated Banister value.

        Inputs: 60 min, avg_hr=150, max_hr=185, resting_hr=50
        ΔHR = (150-50)/(185-50) = 0.7407
        TRIMP = 60 × 0.7407 × 0.64 × exp(1.92 × 0.7407)
              = 60 × 0.7407 × 0.64 × exp(1.4222)
              = 60 × 0.7407 × 0.64 × 4.1461
              ≈ 118.0
        """
        trimp = calculate_trimp(
            duration_min=60, avg_hr=150, max_hr=185, resting_hr=50, sex="M"
        )
        delta_hr = (150 - 50) / (185 - 50)  # 0.7407
        expected = 60 * delta_hr * 0.64 * math.exp(1.92 * delta_hr)
        assert abs(trimp - expected) < 0.01

    def test_female_trimp_absolute_value(self) -> None:
        """Verify female TRIMP matches hand-calculated Banister value.

        Same inputs, exponent = 1.67 instead of 1.92.
        """
        trimp = calculate_trimp(
            duration_min=60, avg_hr=150, max_hr=185, resting_hr=50, sex="F"
        )
        delta_hr = (150 - 50) / (185 - 50)
        expected = 60 * delta_hr * 0.64 * math.exp(1.67 * delta_hr)
        assert abs(trimp - expected) < 0.01

    def test_male_trimp_greater_than_female(self) -> None:
        """Male exponent (1.92) > female (1.67) → male TRIMP should be higher."""
        male = calculate_trimp(
            duration_min=60, avg_hr=150, max_hr=185, resting_hr=50, sex="M"
        )
        female = calculate_trimp(
            duration_min=60, avg_hr=150, max_hr=185, resting_hr=50, sex="F"
        )
        assert male > female


# ------------------------------------------------------------------
# 2. HRV baseline=0 edge case
# ------------------------------------------------------------------


class TestHRVBaselineZero:
    def test_hrv_readiness_rule_baseline_zero(self) -> None:
        """HRV rule should return None for baseline=0, not crash."""
        rule = HRVReadinessRule()
        state = _make_state(hrv_rmssd=40.0, hrv_baseline=0.0)
        rec = rule.evaluate(state)
        assert rec is None

    def test_arr_rule_baseline_zero(self) -> None:
        """ARR rule should return None for baseline=0, not crash."""
        rule = AsymmetricReadinessRule()
        state = _make_state(hrv_rmssd=40.0, hrv_baseline=0.0)
        rec = rule.evaluate(state)
        assert rec is None


# ------------------------------------------------------------------
# 3. RECOVERY veto cascades modifiers against DRIVE winner
# ------------------------------------------------------------------


class TestRecoveryVetoCascade:
    def setup_method(self) -> None:
        self.resolver = ConflictResolver(HighestPriorityWins())

    def test_recovery_veto_cascades_modifiers_to_drive(self) -> None:
        """A RECOVERY veto's intensity/volume modifiers should apply to DRIVE winner."""
        recs = [
            _rec(
                "drive_rule",
                Priority.DRIVE,
                SessionType.THRESHOLD,
                confidence=0.8,
            ),
            _rec(
                "recovery_veto",
                Priority.RECOVERY,
                SessionType.REST,
                veto=True,
                confidence=0.95,
                intensity=0.50,
                volume=0.60,
            ),
        ]
        winner, _ = self.resolver.resolve(recs)
        # DRIVE wins on priority but RECOVERY veto modifiers cascade
        assert winner.rule_id == "drive_rule"
        assert winner.intensity_modifier <= 0.50
        assert winner.volume_modifier <= 0.60

    def test_non_veto_recovery_does_not_cascade(self) -> None:
        """A non-veto RECOVERY rule should NOT cascade to a DRIVE winner."""
        recs = [
            _rec(
                "drive_rule",
                Priority.DRIVE,
                SessionType.THRESHOLD,
                confidence=0.8,
            ),
            _rec(
                "recovery_mild",
                Priority.RECOVERY,
                SessionType.EASY,
                veto=False,
                confidence=0.9,
                intensity=0.80,
                volume=0.85,
            ),
        ]
        winner, _ = self.resolver.resolve(recs)
        assert winner.rule_id == "drive_rule"
        # Non-veto RECOVERY should NOT affect DRIVE
        assert winner.intensity_modifier == 1.0
        assert winner.volume_modifier == 1.0
