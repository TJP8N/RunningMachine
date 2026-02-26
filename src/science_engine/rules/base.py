"""Abstract base class for all science engine rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import Priority
from science_engine.models.recommendation import RuleRecommendation

if TYPE_CHECKING:
    from science_engine.models.weekly_plan import WeekContext


class ScienceRule(ABC):
    """Base class for all training rules in the science engine.

    Each rule encapsulates one piece of sports-science logic. Rules are
    discovered automatically by the RuleRegistry and evaluated by the
    ScienceEngine.

    Subclasses must define:
        rule_id: unique identifier (e.g. "injury_risk_acwr")
        version: semantic version string
        priority: Priority tier (SAFETY, DRIVE, RECOVERY, OPTIMIZATION, PREFERENCE)
        required_data: list of AthleteState field names needed by this rule
        evaluate(): the rule's decision logic

    Weekly-aware rules should set ``is_weekly_aware = True`` and override
    ``evaluate_weekly()`` to receive the WeekContext during week planning.
    """

    rule_id: str
    version: str
    priority: Priority
    required_data: list[str]
    is_weekly_aware: bool = False

    def has_required_data(self, state: AthleteState) -> bool:
        """Check that all required AthleteState fields are not None."""
        for field_name in self.required_data:
            value = getattr(state, field_name, None)
            if value is None:
                return False
            # Also treat empty sequences as missing data
            if isinstance(value, (list, tuple)) and len(value) == 0:
                return False
        return True

    @abstractmethod
    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        """Evaluate this rule against the current athlete state.

        Returns a RuleRecommendation if the rule has something to say,
        or None if the rule is not applicable.
        """
        ...

    def evaluate_weekly(
        self, state: AthleteState, context: WeekContext
    ) -> RuleRecommendation | None:
        """Evaluate this rule with weekly planning context.

        Default implementation delegates to evaluate(). Weekly-aware rules
        (is_weekly_aware=True) should override this to consider the week
        context when making recommendations.

        Args:
            state: Frozen athlete state snapshot.
            context: WeekContext with sessions planned so far this week.

        Returns:
            A RuleRecommendation or None.
        """
        return self.evaluate(state)
