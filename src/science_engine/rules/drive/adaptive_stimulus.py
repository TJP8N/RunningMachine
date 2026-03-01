"""DRIVE rule: Adaptive Stimulus Calibration (ASC).

When the athlete's VO2max trajectory is stagnating or declining, this rule
increases training stimulus and identifies the limiting physiological factor
(aerobic capacity vs. lactate threshold/economy) by comparing the CS and
VO2max marathon-time estimates from the Performance Ceiling Model.

Never fires during TAPER/RACE phases, recovery weeks, suppressed readiness,
or elevated ACWR.

References:
    Midgley et al. (2007). Training to enhance the physiological determinants
        of long-distance running performance. Sports Med 37(10):857-880.
    Daniels & Gilbert (1979). Oxygen Power. Privately published.
    Smyth & Muniz-Pumares (2020). Calculation of critical speed from raw
        training data. Med Sci Sports Exerc 52(7):1606-1615.
"""

from __future__ import annotations

from science_engine.math.ceiling import CeilingEstimate, estimate_ceiling
from science_engine.math.training_load import calculate_acwr
from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    ASC_ACWR_CEILING,
    ASC_CONFIDENCE,
    ASC_SIGNAL_GAP_S,
    ASC_TREND_DECLINE_THRESHOLD,
    ASC_TREND_STAGNATION_THRESHOLD,
    ASC_VOLUME_BOOST_STRONG,
    ASC_VOLUME_BOOST_WEAK,
    Priority,
    ReadinessLevel,
    SessionType,
    TrainingPhase,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.models.weekly_plan import WeekContext
from science_engine.rules.base import ScienceRule


class AdaptiveStimulusRule(ScienceRule):
    """Ceiling-informed DRIVE rule that calibrates stimulus based on VO2max trend."""

    rule_id = "adaptive_stimulus"
    version = "1.0.0"
    priority = Priority.DRIVE
    required_data = ["vo2max", "vo2max_history", "goal_race_date", "current_date"]
    is_weekly_aware = True

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        """Delegate to _assess with is_recovery_week=False."""
        return self._assess(state, is_recovery_week=False)

    def evaluate_weekly(
        self, state: AthleteState, context: WeekContext
    ) -> RuleRecommendation | None:
        """Weekly-aware entry point — gates on recovery weeks."""
        return self._assess(state, is_recovery_week=context.is_recovery_week)

    def _assess(
        self, state: AthleteState, *, is_recovery_week: bool
    ) -> RuleRecommendation | None:
        # --- Gate checks ---

        # 1. Phase gate
        if state.current_phase in (TrainingPhase.TAPER, TrainingPhase.RACE):
            return None

        # 2. Recovery week gate
        if is_recovery_week:
            return None

        # 3. Readiness gate
        if state.readiness in (ReadinessLevel.SUPPRESSED, ReadinessLevel.VERY_SUPPRESSED):
            return None

        # 4. ACWR gate
        if state.daily_loads:
            acwr = calculate_acwr(list(state.daily_loads))
            if acwr > ASC_ACWR_CEILING:
                return None

        # 5-6. Build ceiling estimate and check quality / trend
        ceiling = estimate_ceiling(
            cs=state.critical_speed_m_per_s,
            vo2max=state.vo2max,
            vo2max_history=state.vo2max_history,
            race_date=state.goal_race_date,
            current_date=state.current_date,
        )

        if ceiling.data_quality in ("INSUFFICIENT", "LOW"):
            return None

        if ceiling.vo2max_weekly_trend is None:
            return None

        # 7. On-track gate
        trend = ceiling.vo2max_weekly_trend
        if trend >= ASC_TREND_STAGNATION_THRESHOLD:
            return None

        # --- Core logic ---
        if trend < ASC_TREND_DECLINE_THRESHOLD:
            volume_modifier = ASC_VOLUME_BOOST_STRONG
            trend_label = "declining"
        else:
            volume_modifier = ASC_VOLUME_BOOST_WEAK
            trend_label = "stagnating"

        # Identify limiting factor and recommend session type
        session_type = self._identify_limiter(ceiling, state.current_phase)

        return RuleRecommendation(
            rule_id=self.rule_id,
            rule_version=self.version,
            priority=self.priority,
            recommended_session_type=session_type,
            volume_modifier=volume_modifier,
            explanation=(
                f"DRIVE: VO2max trend {trend_label} ({trend:+.3f} ml/kg/min/wk). "
                f"Ceiling data quality {ceiling.data_quality}. "
                f"Limiting factor → {session_type.name}. "
                f"Volume boost {(volume_modifier - 1) * 100:.0f}%. "
                f"Ref: Midgley et al. (2007)."
            ),
            confidence=ASC_CONFIDENCE,
        )

    @staticmethod
    def _identify_limiter(
        ceiling: CeilingEstimate, phase: TrainingPhase
    ) -> SessionType:
        """Compare CS vs VO2max marathon-time estimates to find the limiter.

        - Gap > 120s and CS faster → aerobic capacity is the limiter
        - Gap > 120s and VO2max faster → threshold/economy is the limiter
        - Signals within 120s → converged → phase-appropriate default
        """
        cs_s = ceiling.cs_estimate_s
        vo2_s = ceiling.vo2max_estimate_s

        if cs_s is not None and vo2_s is not None:
            gap = abs(cs_s - vo2_s)
            if gap > ASC_SIGNAL_GAP_S:
                if cs_s < vo2_s:
                    # CS faster → aerobic capacity is the limiter
                    if phase == TrainingPhase.BASE:
                        return SessionType.TEMPO
                    return SessionType.VO2MAX_INTERVALS
                else:
                    # VO2max faster → threshold/economy is the limiter
                    if phase == TrainingPhase.SPECIFIC:
                        return SessionType.MARATHON_PACE
                    return SessionType.TEMPO

        # Signals converged or one signal missing → phase default
        _PHASE_DEFAULT: dict[TrainingPhase, SessionType] = {
            TrainingPhase.BASE: SessionType.TEMPO,
            TrainingPhase.BUILD: SessionType.THRESHOLD,
            TrainingPhase.SPECIFIC: SessionType.MARATHON_PACE,
        }
        return _PHASE_DEFAULT.get(phase, SessionType.THRESHOLD)
