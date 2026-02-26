"""Conflict resolver — combines multiple rule recommendations into one."""

from __future__ import annotations

from science_engine.conflict_resolution.strategies import (
    HighestPriorityWins,
    ResolutionStrategy,
)
from science_engine.models.recommendation import RuleRecommendation


class ConflictResolver:
    """Resolves conflicts between multiple rule recommendations.

    Uses a pluggable strategy pattern. Default is HighestPriorityWins
    with the 5-tier priority hierarchy.
    """

    def __init__(self, strategy: ResolutionStrategy | None = None) -> None:
        self.strategy = strategy or HighestPriorityWins()

    def resolve(
        self, recommendations: list[RuleRecommendation]
    ) -> tuple[RuleRecommendation, str]:
        """Resolve a list of recommendations into one final recommendation.

        Returns the winning recommendation and resolution notes for the
        decision trace.
        """
        return self.strategy.resolve(recommendations)
