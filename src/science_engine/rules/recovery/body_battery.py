"""RECOVERY rule: Garmin Body Battery readiness gating.

Uses the athlete's Body Battery score (0-100, Garmin/Firstbeat) with
a 4-tier model: veto (<25), suppress (25-49), mild (50-74), normal (75+).

Reference:
    Firstbeat Analytics (Garmin). Body Battery uses HRV, stress, sleep,
    and activity data to estimate physiological readiness.
"""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    BODY_BATTERY_MILD_INTENSITY_MOD,
    BODY_BATTERY_MILD_THRESHOLD,
    BODY_BATTERY_MILD_VOLUME_MOD,
    BODY_BATTERY_SUPPRESS_INTENSITY_MOD,
    BODY_BATTERY_SUPPRESS_THRESHOLD,
    BODY_BATTERY_SUPPRESS_VOLUME_MOD,
    BODY_BATTERY_VETO_INTENSITY_MOD,
    BODY_BATTERY_VETO_THRESHOLD,
    BODY_BATTERY_VETO_VOLUME_MOD,
    Priority,
    SessionType,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.rules.base import ScienceRule


class BodyBatteryRule(ScienceRule):
    """Adjusts training based on Garmin Body Battery readiness score."""

    rule_id = "body_battery"
    version = "1.0.0"
    priority = Priority.RECOVERY
    required_data = ["body_battery"]

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        bb = state.body_battery  # guaranteed not None by required_data

        if bb < BODY_BATTERY_VETO_THRESHOLD:  # type: ignore[operator]
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=SessionType.REST,
                intensity_modifier=BODY_BATTERY_VETO_INTENSITY_MOD,
                volume_modifier=BODY_BATTERY_VETO_VOLUME_MOD,
                veto=True,
                explanation=(
                    f"Body Battery {bb} below veto threshold "
                    f"({BODY_BATTERY_VETO_THRESHOLD}). Recommending REST. "
                    f"Ref: Firstbeat/Garmin Body Battery model."
                ),
                confidence=0.7,
            )

        if bb < BODY_BATTERY_SUPPRESS_THRESHOLD:  # type: ignore[operator]
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=SessionType.EASY,
                intensity_modifier=BODY_BATTERY_SUPPRESS_INTENSITY_MOD,
                volume_modifier=BODY_BATTERY_SUPPRESS_VOLUME_MOD,
                veto=False,
                explanation=(
                    f"Body Battery {bb} below suppress threshold "
                    f"({BODY_BATTERY_SUPPRESS_THRESHOLD}). Reducing intensity. "
                    f"Ref: Firstbeat/Garmin Body Battery model."
                ),
                confidence=0.7,
            )

        if bb < BODY_BATTERY_MILD_THRESHOLD:  # type: ignore[operator]
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=None,  # No session override
                intensity_modifier=BODY_BATTERY_MILD_INTENSITY_MOD,
                volume_modifier=BODY_BATTERY_MILD_VOLUME_MOD,
                veto=False,
                explanation=(
                    f"Body Battery {bb} in mild zone "
                    f"({BODY_BATTERY_SUPPRESS_THRESHOLD}-{BODY_BATTERY_MILD_THRESHOLD}). "
                    f"Slight volume/intensity reduction. "
                    f"Ref: Firstbeat/Garmin Body Battery model."
                ),
                confidence=0.7,
            )

        # Body Battery is good — no action
        return None
