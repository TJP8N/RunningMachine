"""SAFETY rule: Injury risk based on Acute:Chronic Workload Ratio (ACWR).

Reference:
    Gabbett (2016). The training-injury prevention paradox: should athletes
    be training smarter and harder? Br J Sports Med 50(5):273-280.

Thresholds:
    ACWR > 1.5  → VETO: block high-intensity sessions
    ACWR 1.3-1.5 → CAUTION: reduce intensity by 20-30%
    ACWR 0.8-1.3 → OPTIMAL: no modification
    ACWR < 0.8  → UNDERTRAINED: recommend increased stimulus
"""

from __future__ import annotations

from science_engine.math.training_load import calculate_acwr, classify_acwr
from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    ACWR_CAUTION_HIGH,
    ACWR_DANGER_THRESHOLD,
    ACWR_UNDERTRAINED,
    Priority,
    SessionType,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.rules.base import ScienceRule


class InjuryRiskACWRRule(ScienceRule):
    """Monitors ACWR and vetoes or modifies training when injury risk is elevated."""

    rule_id = "injury_risk_acwr"
    version = "1.0.0"
    priority = Priority.SAFETY
    required_data = ["daily_loads"]

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        acwr = calculate_acwr(list(state.daily_loads))

        if acwr == 0.0:
            return None  # Insufficient data to assess

        classification = classify_acwr(acwr)

        if classification == "danger":
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=SessionType.EASY,
                intensity_modifier=0.5,
                volume_modifier=0.7,
                veto=True,
                explanation=(
                    f"ACWR={acwr:.2f} exceeds danger threshold ({ACWR_DANGER_THRESHOLD}). "
                    f"High-intensity sessions blocked to prevent injury. "
                    f"Ref: Gabbett (2016)."
                ),
                confidence=1.0,
            )

        if classification == "caution":
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=None,  # Don't override session type
                intensity_modifier=0.75,
                volume_modifier=0.85,
                veto=False,
                explanation=(
                    f"ACWR={acwr:.2f} in caution zone ({ACWR_CAUTION_HIGH}-{ACWR_DANGER_THRESHOLD}). "
                    f"Intensity reduced by 25%. Ref: Gabbett (2016)."
                ),
                confidence=0.9,
            )

        if classification == "undertrained":
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=None,
                intensity_modifier=1.0,
                volume_modifier=1.1,  # Encourage slightly more volume
                veto=False,
                explanation=(
                    f"ACWR={acwr:.2f} below optimal ({ACWR_UNDERTRAINED}). "
                    f"Athlete may benefit from increased training stimulus. "
                    f"Ref: Gabbett (2016)."
                ),
                confidence=0.7,
            )

        # Optimal range — no modification needed
        return None
