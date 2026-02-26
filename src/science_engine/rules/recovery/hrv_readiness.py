"""RECOVERY rule: HRV-based readiness gating.

Uses the ratio of current HRV (RMSSD) to the athlete's baseline to
decide whether to suppress or veto high-intensity training.

Reference:
    Plews et al. (2013). Training Adaptation and Heart Rate Variability
    in Elite Endurance Athletes. Int J Sports Physiol Perform 8(6):688-694.

    Buchheit (2014). Monitoring training status with HR measures. Int J
    Sports Physiol Perform 9(5):883-893.
"""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    HRV_SUPPRESS_INTENSITY_MOD,
    HRV_SUPPRESS_THRESHOLD,
    HRV_SUPPRESS_VOLUME_MOD,
    HRV_VETO_INTENSITY_MOD,
    HRV_VETO_THRESHOLD,
    HRV_VETO_VOLUME_MOD,
    Priority,
    SessionType,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.rules.base import ScienceRule


class HRVReadinessRule(ScienceRule):
    """Suppresses or vetoes intensity when HRV is below baseline thresholds."""

    rule_id = "hrv_readiness"
    version = "1.0.0"
    priority = Priority.RECOVERY
    required_data = ["hrv_rmssd", "hrv_baseline"]

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        # required_data check guarantees these are not None
        hrv_ratio = state.hrv_rmssd / state.hrv_baseline  # type: ignore[operator]

        if hrv_ratio < HRV_VETO_THRESHOLD:
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=SessionType.RECOVERY,
                intensity_modifier=HRV_VETO_INTENSITY_MOD,
                volume_modifier=HRV_VETO_VOLUME_MOD,
                veto=True,
                explanation=(
                    f"HRV ratio {hrv_ratio:.2f} below veto threshold "
                    f"({HRV_VETO_THRESHOLD}). Recommending RECOVERY session. "
                    f"Ref: Plews et al. (2013), Buchheit (2014)."
                ),
                confidence=0.9,
            )

        if hrv_ratio < HRV_SUPPRESS_THRESHOLD:
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=SessionType.EASY,
                intensity_modifier=HRV_SUPPRESS_INTENSITY_MOD,
                volume_modifier=HRV_SUPPRESS_VOLUME_MOD,
                veto=False,
                explanation=(
                    f"HRV ratio {hrv_ratio:.2f} below suppress threshold "
                    f"({HRV_SUPPRESS_THRESHOLD}). Reducing intensity. "
                    f"Ref: Plews et al. (2013), Buchheit (2014)."
                ),
                confidence=0.9,
            )

        # HRV is normal — no action
        return None
