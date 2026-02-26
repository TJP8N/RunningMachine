"""OPTIMIZATION rule: Progressive overload — weekly volume progression.

Recommends next week's training volume based on history, ensuring safe
progression rates and deloading at recovery weeks.

References:
    Damsted et al. (2019). Is There Evidence for an Association Between
    Changes in Training Load and Running-Related Injuries? J Orthop
    Sports Phys Ther 49(8):561-567.

    Pfitzinger & Douglas (2009), Advanced Marathoning, 2nd ed.
"""

from __future__ import annotations

from science_engine.math.periodization import allocate_phases, is_recovery_week
from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    CONSERVATIVE_VOLUME_INCREASE_PCT,
    EARLY_BASE_VOLUME_INCREASE_PCT,
    MAX_WEEKLY_VOLUME_INCREASE_PCT,
    RECOVERY_WEEK_VOLUME_FRACTION,
    Priority,
    TrainingPhase,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.rules.base import ScienceRule


class ProgressiveOverloadRule(ScienceRule):
    """Recommends weekly volume with safe progression and recovery deloads."""

    rule_id = "progressive_overload"
    version = "1.0.0"
    priority = Priority.OPTIMIZATION
    required_data = ["weekly_volume_history", "current_week", "total_plan_weeks"]

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        phases = allocate_phases(state.total_plan_weeks)
        last_volume = state.weekly_volume_history[-1] if state.weekly_volume_history else 30.0

        # Check if this is a recovery week
        if is_recovery_week(state.current_week, phases):
            target_volume = last_volume * RECOVERY_WEEK_VOLUME_FRACTION
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                volume_modifier=RECOVERY_WEEK_VOLUME_FRACTION,
                target_distance_km=round(target_volume, 1),
                explanation=(
                    f"Recovery week {state.current_week}: volume reduced to "
                    f"{RECOVERY_WEEK_VOLUME_FRACTION:.0%} of last week "
                    f"({last_volume:.1f} km → {target_volume:.1f} km). "
                    f"Ref: Pfitzinger & Douglas (2009)."
                ),
                confidence=0.9,
            )

        # Determine progression rate based on phase
        progress_fraction = state.current_week / state.total_plan_weeks
        if progress_fraction < 0.3:
            # Early base: can increase faster
            increase_pct = EARLY_BASE_VOLUME_INCREASE_PCT
            phase_label = "early base"
        elif progress_fraction < 0.7:
            # Mid plan: standard progression
            increase_pct = MAX_WEEKLY_VOLUME_INCREASE_PCT
            phase_label = "build"
        else:
            # Approaching peak: conservative
            increase_pct = CONSERVATIVE_VOLUME_INCREASE_PCT
            phase_label = "near-peak"

        target_volume = last_volume * (1.0 + increase_pct)

        return RuleRecommendation(
            rule_id=self.rule_id,
            rule_version=self.version,
            priority=self.priority,
            volume_modifier=1.0 + increase_pct,
            target_distance_km=round(target_volume, 1),
            explanation=(
                f"Progressive overload ({phase_label}): "
                f"{increase_pct:.0%} increase from {last_volume:.1f} km → "
                f"{target_volume:.1f} km. Ref: Damsted et al. (2019)."
            ),
            confidence=0.85,
        )
