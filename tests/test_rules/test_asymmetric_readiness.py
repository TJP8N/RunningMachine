"""Tests for AsymmetricReadinessRule — RECOVERY meta-rule (ARR)."""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    ARR_CONFIDENCE,
    ARR_CONVERGED_INTENSITY_MOD,
    ARR_CONVERGED_VOLUME_MOD,
    ARR_ELEVATED_VOLUME_BOOST,
    ARR_EXPECTED_INTENSITY_MOD,
    ARR_EXPECTED_VOLUME_MOD,
    ARR_MODERATE_INTENSITY_MOD,
    ARR_MODERATE_VOLUME_MOD,
    ARR_VETO_INTENSITY_MOD,
    ARR_VETO_VOLUME_MOD,
    Priority,
    SessionType,
)
from science_engine.rules.recovery.asymmetric_readiness import (
    AsymmetricReadinessRule,
)

# Baseline HRV for all tests
_BASELINE = 50.0

# Daily loads: 28 days of typical training, mean ≈ 80
_NORMAL_LOADS = tuple([80.0] * 28)

# ACWR-optimal loads (steady state → ACWR ~1.0)
_OPTIMAL_ACWR_LOADS = _NORMAL_LOADS

# ACWR-high loads: recent spike → pushes ACWR > 1.3
_HIGH_ACWR_LOADS = tuple([60.0] * 21 + [150.0] * 7)


def _make_state(
    *,
    hrv_rmssd: float | None = _BASELINE * 0.95,  # normal by default
    hrv_baseline: float | None = _BASELINE,
    sleep_score: float | None = 80.0,
    body_battery: int | None = 80,
    previous_day_session_type: SessionType | None = None,
    daily_loads: tuple[float, ...] = _NORMAL_LOADS,
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


class TestAsymmetricReadinessRule:
    def setup_method(self) -> None:
        self.rule = AsymmetricReadinessRule()

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def test_rule_metadata(self) -> None:
        assert self.rule.priority == Priority.RECOVERY
        assert self.rule.is_weekly_aware is False
        assert self.rule.rule_id == "asymmetric_readiness"

    def test_confidence_beats_individual_rules(self) -> None:
        """ARR confidence (0.95) must exceed all individual recovery rules."""
        individual_max = max(0.9, 0.8, 0.7)  # HRV, Sleep, BB
        assert ARR_CONFIDENCE > individual_max

    # ------------------------------------------------------------------
    # Elevated HRV boost
    # ------------------------------------------------------------------

    def test_elevated_hrv_boost(self) -> None:
        """HRV >110% + all normal + ACWR optimal → volume boost."""
        state = _make_state(
            hrv_rmssd=_BASELINE * 1.15,
            daily_loads=_OPTIMAL_ACWR_LOADS,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.volume_modifier == ARR_ELEVATED_VOLUME_BOOST
        assert rec.intensity_modifier == 1.0
        assert rec.recommended_session_type is None
        assert rec.confidence == ARR_CONFIDENCE

    def test_elevated_blocked_by_high_acwr(self) -> None:
        """HRV elevated + ACWR >1.3 → no boost (parasympathetic saturation guard)."""
        state = _make_state(
            hrv_rmssd=_BASELINE * 1.15,
            daily_loads=_HIGH_ACWR_LOADS,
        )
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_elevated_blocked_by_low_sleep(self) -> None:
        """HRV elevated + sleep suppressed → no boost (signal not clean)."""
        state = _make_state(
            hrv_rmssd=_BASELINE * 1.15,
            sleep_score=50.0,  # below suppress threshold (60)
        )
        rec = self.rule.evaluate(state)
        # suppressed=1 (sleep), so elevated branch won't fire; but HRV is
        # good so hrv_ratio > suppress threshold → no HRV suppression.
        # Only sleep is suppressed (single signal, unexpected) → moderate
        assert rec is not None
        assert rec.intensity_modifier == ARR_MODERATE_INTENSITY_MOD

    # ------------------------------------------------------------------
    # All normal → no action
    # ------------------------------------------------------------------

    def test_no_fire_all_normal(self) -> None:
        """All signals within normal range → None."""
        state = _make_state()  # defaults are all normal
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_no_fire_no_hrv_data(self) -> None:
        """Missing HRV → rule doesn't fire (individual rules handle)."""
        state = _make_state(hrv_rmssd=None, hrv_baseline=None)
        assert not self.rule.has_required_data(state)

    # ------------------------------------------------------------------
    # Expected suppression — single signal → mild
    # ------------------------------------------------------------------

    def test_expected_single_signal_mild(self) -> None:
        """VO2max yesterday + HRV low → expected, single signal, mild modifiers."""
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.80,  # below 0.85 suppress
            previous_day_session_type=SessionType.VO2MAX_INTERVALS,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.intensity_modifier == ARR_EXPECTED_INTENSITY_MOD
        assert rec.volume_modifier == ARR_EXPECTED_VOLUME_MOD
        assert rec.recommended_session_type is None
        assert rec.veto is False

    def test_expected_tier1_48h_window(self) -> None:
        """VO2max 2 days ago (high load[-2]) + HRV low → expected."""
        # Build loads with a big spike 2 days ago
        loads = list(_NORMAL_LOADS)
        loads[-2] = 250.0  # > 2× mean (~80)
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.80,
            previous_day_session_type=None,  # no session type
            daily_loads=tuple(loads),
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        # Expected single signal → mild
        assert rec.intensity_modifier == ARR_EXPECTED_INTENSITY_MOD

    def test_expected_tier2_24h_only(self) -> None:
        """Tempo yesterday + HRV low → expected."""
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.80,
            previous_day_session_type=SessionType.TEMPO,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.intensity_modifier == ARR_EXPECTED_INTENSITY_MOD

    # ------------------------------------------------------------------
    # Expected + converged → moderate
    # ------------------------------------------------------------------

    def test_expected_converged_moderate(self) -> None:
        """Hard session + HRV and sleep both low → expected, converged, moderate."""
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.80,   # suppressed
            sleep_score=50.0,              # suppressed
            previous_day_session_type=SessionType.THRESHOLD,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.intensity_modifier == ARR_MODERATE_INTENSITY_MOD
        assert rec.volume_modifier == ARR_MODERATE_VOLUME_MOD
        assert rec.recommended_session_type == SessionType.EASY
        assert rec.veto is False

    # ------------------------------------------------------------------
    # Unexpected — single signal → moderate
    # ------------------------------------------------------------------

    def test_unexpected_single_moderate(self) -> None:
        """REST yesterday + HRV low → unexpected single signal, moderate."""
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.80,
            previous_day_session_type=SessionType.REST,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.intensity_modifier == ARR_MODERATE_INTENSITY_MOD
        assert rec.volume_modifier == ARR_MODERATE_VOLUME_MOD
        assert rec.recommended_session_type == SessionType.EASY

    def test_unexpected_single_veto_still_moderate(self) -> None:
        """REST yesterday + HRV at veto level → still moderate (single signal)."""
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.65,  # below veto threshold (0.70)
            previous_day_session_type=SessionType.REST,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        # Single signal even at veto level → moderate, not veto
        assert rec.intensity_modifier == ARR_MODERATE_INTENSITY_MOD
        assert rec.veto is False

    # ------------------------------------------------------------------
    # Unexpected + converged → strong
    # ------------------------------------------------------------------

    def test_unexpected_converged_strong(self) -> None:
        """No hard session + HRV and sleep both low → unexpected converged, strong."""
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.80,   # suppressed
            sleep_score=50.0,              # suppressed
            previous_day_session_type=SessionType.REST,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.intensity_modifier == ARR_CONVERGED_INTENSITY_MOD
        assert rec.volume_modifier == ARR_CONVERGED_VOLUME_MOD
        assert rec.recommended_session_type == SessionType.EASY
        assert rec.veto is False

    # ------------------------------------------------------------------
    # Unexpected + converged + veto → REST
    # ------------------------------------------------------------------

    def test_unexpected_converged_veto_rest(self) -> None:
        """No hard session + HRV+sleep suppressed + 1 veto → REST."""
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.65,   # veto level
            sleep_score=35.0,              # also veto level
            previous_day_session_type=SessionType.EASY,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.REST
        assert rec.intensity_modifier == ARR_VETO_INTENSITY_MOD
        assert rec.volume_modifier == ARR_VETO_VOLUME_MOD
        assert rec.veto is True
        assert "illness" in rec.explanation.lower()

    # ------------------------------------------------------------------
    # Expected classification edge cases
    # ------------------------------------------------------------------

    def test_expected_classification_easy(self) -> None:
        """EASY session yesterday → unexpected (not in any tier)."""
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.80,
            previous_day_session_type=SessionType.EASY,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        # Unexpected single signal → moderate
        assert rec.intensity_modifier == ARR_MODERATE_INTENSITY_MOD

    def test_expected_classification_rest(self) -> None:
        """REST yesterday → unexpected."""
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.80,
            previous_day_session_type=SessionType.REST,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.intensity_modifier == ARR_MODERATE_INTENSITY_MOD

    # ------------------------------------------------------------------
    # Fallback load-based expected detection
    # ------------------------------------------------------------------

    def test_expected_fallback_high_load(self) -> None:
        """No session type + high daily load yesterday → expected."""
        loads = list(_NORMAL_LOADS)
        loads[-1] = 150.0  # > 1.5× mean (~80)
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.80,
            previous_day_session_type=None,
            daily_loads=tuple(loads),
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.intensity_modifier == ARR_EXPECTED_INTENSITY_MOD

    def test_expected_fallback_low_load(self) -> None:
        """No session type + low daily load yesterday → unexpected."""
        loads = list(_NORMAL_LOADS)
        loads[-1] = 40.0  # < 1.5× mean (~80)
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.80,
            previous_day_session_type=None,
            daily_loads=tuple(loads),
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.intensity_modifier == ARR_MODERATE_INTENSITY_MOD

    # ------------------------------------------------------------------
    # Body Battery independence
    # ------------------------------------------------------------------

    def test_body_battery_not_independent(self) -> None:
        """HRV suppressed + BB suppressed (no sleep) → single signal (not converged).

        Body Battery is derived from HRV + sleep and is NOT independent when
        HRV data is present.
        """
        state = _make_state(
            hrv_rmssd=_BASELINE * 0.80,   # suppressed
            sleep_score=None,              # no sleep data
            body_battery=30,               # suppressed, but not counted
            previous_day_session_type=SessionType.REST,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        # Only 1 signal (HRV) → single signal moderate, not converged
        assert rec.intensity_modifier == ARR_MODERATE_INTENSITY_MOD
        assert rec.volume_modifier == ARR_MODERATE_VOLUME_MOD
