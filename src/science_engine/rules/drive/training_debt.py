"""DRIVE rule: Training debt repayment.

When an athlete has accumulated training debt (missed sessions), this rule
recommends extending session duration or choosing a debt-appropriate session
type to gradually repay the deficit.

The debt is decayed over time so old missed sessions don't haunt the athlete
forever. Debt repayment is never applied during recovery weeks.

Reference:
    Internal model. Debt decay uses exponential half-life per
    enums.DEBT_HALF_LIFE_WEEKS.
"""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    MAX_DEBT_DURATION_EXTENSION_MIN,
    Priority,
    ReadinessLevel,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.models.training_debt import debt_by_session_type, total_effective_debt
from science_engine.models.weekly_plan import WeekContext
from science_engine.rules.base import ScienceRule


class TrainingDebtRule(ScienceRule):
    """Recommends debt repayment when the athlete has accumulated training debt."""

    rule_id = "training_debt"
    version = "1.0.0"
    priority = Priority.DRIVE
    required_data = ["training_debt"]
    is_weekly_aware = True

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        # Without weekly context, just check for debt and recommend extension
        return self._assess_debt(state, is_recovery_week=False)

    def evaluate_weekly(
        self, state: AthleteState, context: WeekContext
    ) -> RuleRecommendation | None:
        return self._assess_debt(state, is_recovery_week=context.is_recovery_week)

    def _assess_debt(
        self, state: AthleteState, is_recovery_week: bool
    ) -> RuleRecommendation | None:
        # Never repay debt during recovery weeks
        if is_recovery_week:
            return None

        # Only repay when readiness is NORMAL or ELEVATED
        if state.readiness not in (ReadinessLevel.NORMAL, ReadinessLevel.ELEVATED):
            return None

        if state.training_debt is None or state.training_debt.is_empty:
            return None

        total_debt = total_effective_debt(state.training_debt)
        if total_debt < 5.0:  # Ignore trivial debt
            return None

        # Find the session type with highest debt
        by_type = debt_by_session_type(state.training_debt)
        if not by_type:
            return None

        highest_debt_type = max(by_type, key=by_type.get)  # type: ignore[arg-type]
        highest_debt_min = by_type[highest_debt_type]

        # Recommend extending duration — capped at MAX_DEBT_DURATION_EXTENSION_MIN
        extension = min(highest_debt_min * 0.25, MAX_DEBT_DURATION_EXTENSION_MIN)
        volume_modifier = 1.0 + (extension / 45.0)  # Normalize against base ~45 min

        return RuleRecommendation(
            rule_id=self.rule_id,
            rule_version=self.version,
            priority=self.priority,
            recommended_session_type=highest_debt_type,
            volume_modifier=min(volume_modifier, 1.35),  # Cap at +35%
            explanation=(
                f"DRIVE: {total_debt:.0f} min total training debt "
                f"({highest_debt_min:.0f} min in {highest_debt_type.name}). "
                f"Extending session by ~{extension:.0f} min to repay deficit."
            ),
            confidence=0.7,
        )
