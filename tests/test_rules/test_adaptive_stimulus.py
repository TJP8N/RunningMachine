"""Tests for AdaptiveStimulusRule (DRIVE tier — Adaptive Stimulus Calibration)."""

from __future__ import annotations

from datetime import date

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    ASC_CONFIDENCE,
    ASC_VOLUME_BOOST_STRONG,
    ASC_VOLUME_BOOST_WEAK,
    Priority,
    ReadinessLevel,
    SessionType,
    TrainingPhase,
)
from science_engine.models.weekly_plan import WeekContext
from science_engine.rules.drive.adaptive_stimulus import AdaptiveStimulusRule

# ---------------------------------------------------------------------------
# Pre-defined VO2max histories (weekly measurements over 6 weeks)
# Linear regression slope is (change per week).
# ---------------------------------------------------------------------------

# Improving: ~0.20 ml/kg/min/wk  (well above 0.10 threshold)
_HISTORY_IMPROVING: tuple[tuple[str, float], ...] = (
    ("2026-01-05", 48.0),
    ("2026-01-12", 48.2),
    ("2026-01-19", 48.4),
    ("2026-01-26", 48.6),
    ("2026-02-02", 48.8),
    ("2026-02-09", 49.0),
)

# Stagnating: ~0.05 ml/kg/min/wk  (between -0.05 and 0.10)
_HISTORY_STAGNATING: tuple[tuple[str, float], ...] = (
    ("2026-01-05", 48.0),
    ("2026-01-12", 48.05),
    ("2026-01-19", 48.10),
    ("2026-01-26", 48.15),
    ("2026-02-02", 48.20),
    ("2026-02-09", 48.25),
)

# Declining: ~-0.15 ml/kg/min/wk  (below -0.05)
_HISTORY_DECLINING: tuple[tuple[str, float], ...] = (
    ("2026-01-05", 49.0),
    ("2026-01-12", 48.85),
    ("2026-01-19", 48.70),
    ("2026-01-26", 48.55),
    ("2026-02-02", 48.40),
    ("2026-02-09", 48.25),
)


def _make_state(
    phase: TrainingPhase = TrainingPhase.BUILD,
    readiness: ReadinessLevel = ReadinessLevel.NORMAL,
    vo2max: float = 50.0,
    vo2max_history: tuple[tuple[str, float], ...] = _HISTORY_STAGNATING,
    cs: float | None = 4.0,
    daily_loads: tuple[float, ...] | None = None,
    goal_race_date: date | None = None,
    current_date: date | None = None,
) -> AthleteState:
    if daily_loads is None:
        daily_loads = tuple([50.0] * 28)  # Stable → ACWR ~1.0
    if goal_race_date is None:
        goal_race_date = date(2026, 5, 1)
    if current_date is None:
        current_date = date(2026, 2, 15)
    return AthleteState(
        name="Test",
        age=30,
        weight_kg=70.0,
        sex="M",
        max_hr=190,
        lthr_bpm=170,
        lthr_pace_s_per_km=300,
        vo2max=vo2max,
        vo2max_history=vo2max_history,
        current_phase=phase,
        current_week=8,
        total_plan_weeks=16,
        day_of_week=2,
        daily_loads=daily_loads,
        readiness=readiness,
        critical_speed_m_per_s=cs,
        goal_race_date=goal_race_date,
        current_date=current_date,
    )


class TestAdaptiveStimulusRule:
    def setup_method(self) -> None:
        self.rule = AdaptiveStimulusRule()

    # --- Metadata ---

    def test_rule_metadata(self) -> None:
        assert self.rule.priority == Priority.DRIVE
        assert self.rule.is_weekly_aware is True

    def test_confidence_below_adaptation_demand(self) -> None:
        assert ASC_CONFIDENCE == 0.65
        assert ASC_CONFIDENCE < 0.70  # adaptation_demand confidence

    # --- Gate checks (should return None) ---

    def test_no_fire_taper_phase(self) -> None:
        state = _make_state(phase=TrainingPhase.TAPER)
        assert self.rule.evaluate(state) is None

    def test_no_fire_race_phase(self) -> None:
        state = _make_state(phase=TrainingPhase.RACE)
        assert self.rule.evaluate(state) is None

    def test_no_fire_recovery_week(self) -> None:
        state = _make_state()
        context = WeekContext(
            day_number=1,
            phase=TrainingPhase.BUILD,
            is_recovery_week=True,
        )
        assert self.rule.evaluate_weekly(state, context) is None

    def test_no_fire_suppressed_readiness(self) -> None:
        state = _make_state(readiness=ReadinessLevel.SUPPRESSED)
        assert self.rule.evaluate(state) is None

    def test_no_fire_very_suppressed_readiness(self) -> None:
        state = _make_state(readiness=ReadinessLevel.VERY_SUPPRESSED)
        assert self.rule.evaluate(state) is None

    def test_no_fire_high_acwr(self) -> None:
        """Spiked loads → ACWR > 1.3 → no stimulus boost."""
        state = _make_state(
            daily_loads=tuple([30.0] * 21 + [90.0] * 7),
        )
        assert self.rule.evaluate(state) is None

    def test_no_fire_insufficient_quality(self) -> None:
        """No CS + no VO2max history → INSUFFICIENT ceiling → None."""
        state = _make_state(
            cs=None,
            vo2max_history=(),
        )
        assert self.rule.evaluate(state) is None

    def test_no_fire_low_quality(self) -> None:
        """CS-only (no trajectory) → LOW ceiling → None."""
        state = _make_state(
            vo2max_history=(("2026-01-05", 50.0),),  # < 3 points
        )
        # With CS but no trajectory, quality is LOW at best
        assert self.rule.evaluate(state) is None

    def test_no_fire_no_trend(self) -> None:
        """< 3 history points → no trend → None."""
        state = _make_state(
            vo2max_history=(("2026-01-05", 50.0), ("2026-01-12", 50.1)),
        )
        assert self.rule.evaluate(state) is None

    def test_no_fire_on_track(self) -> None:
        """Improving trend >= 0.10 → on track → None."""
        state = _make_state(vo2max_history=_HISTORY_IMPROVING)
        assert self.rule.evaluate(state) is None

    # --- Core logic (should fire) ---

    def test_stagnation_weak_boost(self) -> None:
        """Stagnating trend (~0.05) → weak volume boost."""
        state = _make_state(vo2max_history=_HISTORY_STAGNATING)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.volume_modifier == ASC_VOLUME_BOOST_WEAK
        assert "stagnating" in rec.explanation

    def test_decline_strong_boost(self) -> None:
        """Declining trend (~-0.15) → strong volume boost."""
        state = _make_state(vo2max_history=_HISTORY_DECLINING)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.volume_modifier == ASC_VOLUME_BOOST_STRONG
        assert "declining" in rec.explanation

    # --- Limiter identification ---

    def test_limiter_aerobic_capacity(self) -> None:
        """CS much faster than VO2max → aerobic capacity limiter → VO2MAX_INTERVALS."""
        # Use a fast CS (high m/s) so CS estimate is much faster (lower seconds)
        # than VO2max estimate. VO2max=50 gives ~3:16:xx marathon.
        # CS=4.5 m/s with ~87% pct_cs gives ~10700s (~2:58) which is faster.
        state = _make_state(
            phase=TrainingPhase.BUILD,
            cs=4.5,
            vo2max=48.0,
            vo2max_history=_HISTORY_STAGNATING,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.VO2MAX_INTERVALS

    def test_limiter_threshold_economy(self) -> None:
        """VO2max much faster than CS → threshold/economy limiter → TEMPO."""
        # Use a slow CS so CS estimate is much slower than VO2max estimate.
        # VO2max=55 gives ~2:52:xx marathon; slow CS=3.2 gives much slower.
        state = _make_state(
            phase=TrainingPhase.BUILD,
            cs=3.2,
            vo2max=55.0,
            vo2max_history=(
                ("2026-01-05", 55.0),
                ("2026-01-12", 55.05),
                ("2026-01-19", 55.10),
                ("2026-01-26", 55.15),
                ("2026-02-02", 55.20),
                ("2026-02-09", 55.25),
            ),
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.recommended_session_type == SessionType.TEMPO

    def test_limiter_converged(self) -> None:
        """Signals close → converged → phase-appropriate default session."""
        # Projected VO2max from stagnating history ≈ 48.83 → vo2max_estimate ≈ 11670s.
        # CS=4.265 with pct_cs=0.848 → cs_estimate ≈ 11665s. Gap < 120s → converged.
        state = _make_state(
            phase=TrainingPhase.BUILD,
            cs=4.265,
            vo2max=50.0,
            vo2max_history=_HISTORY_STAGNATING,
        )
        rec = self.rule.evaluate(state)
        assert rec is not None
        # BUILD phase default is THRESHOLD
        assert rec.recommended_session_type == SessionType.THRESHOLD

    # --- Weekly delegation ---

    def test_evaluate_delegates_correctly(self) -> None:
        """evaluate() should match evaluate_weekly() with non-recovery context."""
        state = _make_state(vo2max_history=_HISTORY_STAGNATING)
        context = WeekContext(
            day_number=2,
            phase=TrainingPhase.BUILD,
            is_recovery_week=False,
        )
        rec_eval = self.rule.evaluate(state)
        rec_weekly = self.rule.evaluate_weekly(state, context)
        assert rec_eval is not None
        assert rec_weekly is not None
        assert rec_eval.volume_modifier == rec_weekly.volume_modifier
        assert rec_eval.recommended_session_type == rec_weekly.recommended_session_type
