"""DRIVE rule: Marathon pace volume tracking.

Compares the athlete's cumulative marathon-pace time against phase-specific
targets. If the athlete is falling behind on MP volume during BUILD or
SPECIFIC phases, this rule recommends a MARATHON_PACE session.

Never fires during BASE phase (MP volume is not a priority yet).

Reference:
    Pfitzinger & Douglas (2009). Advanced Marathoning, 2nd ed.
    Marathon-pace runs accumulate progressively through BUILD and SPECIFIC.
"""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    MP_DEFICIT_THRESHOLD_MIN,
    MP_VOLUME_TARGETS_MIN,
    Priority,
    SessionType,
    TrainingPhase,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.models.weekly_plan import WeekContext
from science_engine.rules.base import ScienceRule


class MarathonPaceVolumeRule(ScienceRule):
    """Ensures adequate cumulative marathon-pace running volume."""

    rule_id = "marathon_pace_volume"
    version = "1.0.0"
    priority = Priority.DRIVE
    required_data = ["current_week", "total_plan_weeks"]
    is_weekly_aware = True

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        return self._assess_mp_deficit(state)

    def evaluate_weekly(
        self, state: AthleteState, context: WeekContext
    ) -> RuleRecommendation | None:
        # Skip in recovery weeks
        if context.is_recovery_week:
            return None

        # Only recommend 1 MP session per week — check if one is already planned
        mp_already_planned = any(
            s.session_type == SessionType.MARATHON_PACE
            for s in context.planned_sessions
        )
        if mp_already_planned:
            return None

        return self._assess_mp_deficit(state)

    def _assess_mp_deficit(self, state: AthleteState) -> RuleRecommendation | None:
        # Only applies in BUILD and SPECIFIC phases
        if state.current_phase not in (TrainingPhase.BUILD, TrainingPhase.SPECIFIC):
            return None

        target = MP_VOLUME_TARGETS_MIN.get(state.current_phase)
        if target is None:
            return None

        # Pro-rate the target based on progress through the phase
        # (don't expect the full target at the start of BUILD)
        phase_progress = self._phase_progress(state)
        prorated_target = target * phase_progress

        deficit = prorated_target - state.cumulative_mp_time_min

        if deficit < MP_DEFICIT_THRESHOLD_MIN:
            return None

        return RuleRecommendation(
            rule_id=self.rule_id,
            rule_version=self.version,
            priority=self.priority,
            recommended_session_type=SessionType.MARATHON_PACE,
            explanation=(
                f"DRIVE: MP volume deficit of {deficit:.0f} min "
                f"(cumulative {state.cumulative_mp_time_min:.0f}/{prorated_target:.0f} min "
                f"target for {state.current_phase.name}). "
                f"Recommending MARATHON_PACE session. "
                f"Ref: Pfitzinger & Douglas (2009)."
            ),
            confidence=0.75,
        )

    @staticmethod
    def _phase_progress(state: AthleteState) -> float:
        """Estimate progress through the current phase (0.0 to 1.0)."""
        from science_engine.math.periodization import allocate_phases, get_phase_for_week

        phases = allocate_phases(state.total_plan_weeks)
        for spec in phases:
            if spec.phase == state.current_phase:
                if spec.duration_weeks <= 1:
                    return 1.0
                return (state.current_week - spec.start_week) / (spec.duration_weeks - 1)
        return 0.5  # Fallback
