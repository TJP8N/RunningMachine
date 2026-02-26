"""RECOVERY rule: Sleep quality gating.

Uses the athlete's sleep score (0-100) to decide whether to suppress
or veto high-intensity training.

Reference:
    Fullagar et al. (2015). Sleep and Athletic Performance. Sports Med
    45(Suppl 1):S161-S186.

    Vitale et al. (2019). Sleep Hygiene for Optimizing Recovery in
    Athletes. Int J Sports Physiol Perform 14(5):587-596.
"""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    SLEEP_SUPPRESS_INTENSITY_MOD,
    SLEEP_SUPPRESS_THRESHOLD,
    SLEEP_SUPPRESS_VOLUME_MOD,
    SLEEP_VETO_INTENSITY_MOD,
    SLEEP_VETO_THRESHOLD,
    SLEEP_VETO_VOLUME_MOD,
    Priority,
    SessionType,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.rules.base import ScienceRule


class SleepQualityRule(ScienceRule):
    """Suppresses or vetoes intensity when sleep quality is poor."""

    rule_id = "sleep_quality"
    version = "1.0.0"
    priority = Priority.RECOVERY
    required_data = ["sleep_score"]

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        sleep_score = state.sleep_score  # guaranteed not None by required_data

        if sleep_score < SLEEP_VETO_THRESHOLD:  # type: ignore[operator]
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=SessionType.RECOVERY,
                intensity_modifier=SLEEP_VETO_INTENSITY_MOD,
                volume_modifier=SLEEP_VETO_VOLUME_MOD,
                veto=True,
                explanation=(
                    f"Sleep score {sleep_score} below veto threshold "
                    f"({SLEEP_VETO_THRESHOLD}). Recommending RECOVERY session. "
                    f"Ref: Fullagar et al. (2015), Vitale et al. (2019)."
                ),
                confidence=0.8,
            )

        if sleep_score < SLEEP_SUPPRESS_THRESHOLD:  # type: ignore[operator]
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=SessionType.EASY,
                intensity_modifier=SLEEP_SUPPRESS_INTENSITY_MOD,
                volume_modifier=SLEEP_SUPPRESS_VOLUME_MOD,
                veto=False,
                explanation=(
                    f"Sleep score {sleep_score} below suppress threshold "
                    f"({SLEEP_SUPPRESS_THRESHOLD}). Reducing intensity. "
                    f"Ref: Fullagar et al. (2015), Vitale et al. (2019)."
                ),
                confidence=0.8,
            )

        # Sleep is adequate — no action
        return None
