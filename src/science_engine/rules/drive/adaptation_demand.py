"""DRIVE rule: Adaptation demand — detect and break volume stagnation.

When weekly volume has stagnated (2+ weeks within 2% of each other) and
the athlete's ACWR is in the optimal range with normal readiness, this rule
nudges volume upward by 5-8% to ensure continued adaptation.

Never fires during TAPER or RACE phases.

Reference:
    Damsted et al. (2019). Is there evidence for an association between
    changes in training load and running-related injuries? A systematic review.
    J Orthop Sports Phys Ther 49(8):576-587.
"""

from __future__ import annotations

from science_engine.math.training_load import calculate_acwr, classify_acwr
from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    ADAPTATION_DEMAND_MAX_MODIFIER,
    ADAPTATION_DEMAND_MIN_MODIFIER,
    STAGNATION_TOLERANCE_PCT,
    Priority,
    ReadinessLevel,
    TrainingPhase,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.rules.base import ScienceRule


class AdaptationDemandRule(ScienceRule):
    """Detects volume stagnation and recommends a modest volume bump."""

    rule_id = "adaptation_demand"
    version = "1.0.0"
    priority = Priority.DRIVE
    required_data = ["weekly_volume_history", "daily_loads"]
    is_weekly_aware = False

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        # Not applicable during taper/race
        if state.current_phase in (TrainingPhase.TAPER, TrainingPhase.RACE):
            return None

        # Need at least 3 weeks of history to detect stagnation
        history = state.weekly_volume_history
        if len(history) < 3:
            return None

        # Only bump when readiness is NORMAL or ELEVATED
        if state.readiness not in (ReadinessLevel.NORMAL, ReadinessLevel.ELEVATED):
            return None

        # Only bump when ACWR is in optimal range
        acwr = calculate_acwr(list(state.daily_loads))
        if acwr > 0 and classify_acwr(acwr) != "optimal":
            return None

        # Detect stagnation: last 2+ weeks within STAGNATION_TOLERANCE_PCT
        if not self._is_stagnating(history):
            return None

        # Graduated modifier: more stagnation → bigger bump
        stagnation_weeks = self._count_stagnation_weeks(history)
        if stagnation_weeks >= 3:
            modifier = ADAPTATION_DEMAND_MAX_MODIFIER
        else:
            modifier = ADAPTATION_DEMAND_MIN_MODIFIER

        return RuleRecommendation(
            rule_id=self.rule_id,
            rule_version=self.version,
            priority=self.priority,
            volume_modifier=modifier,
            explanation=(
                f"DRIVE: Volume stagnating for {stagnation_weeks} weeks "
                f"(within {STAGNATION_TOLERANCE_PCT*100:.0f}%). "
                f"ACWR optimal, readiness {state.readiness.name}. "
                f"Bumping volume by {(modifier-1)*100:.0f}%. "
                f"Ref: Damsted et al. (2019)."
            ),
            confidence=0.7,
        )

    @staticmethod
    def _is_stagnating(history: tuple[float, ...]) -> bool:
        """Check if the last 2+ weeks are within tolerance of each other."""
        if len(history) < 2:
            return False
        recent = history[-2:]
        avg = sum(recent) / len(recent)
        if avg == 0:
            return False
        return all(
            abs(v - avg) / avg <= STAGNATION_TOLERANCE_PCT for v in recent
        )

    @staticmethod
    def _count_stagnation_weeks(history: tuple[float, ...]) -> int:
        """Count consecutive stagnating weeks from the end of history."""
        if len(history) < 2:
            return 0
        count = 1
        for i in range(len(history) - 1, 0, -1):
            avg = (history[i] + history[i - 1]) / 2
            if avg == 0:
                break
            if abs(history[i] - history[i - 1]) / avg <= STAGNATION_TOLERANCE_PCT:
                count += 1
            else:
                break
        return count
