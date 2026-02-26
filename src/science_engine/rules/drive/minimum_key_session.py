"""DRIVE rule: Minimum key sessions per week.

Ensures the athlete gets at least MIN_KEY_SESSIONS_PER_WEEK quality sessions
per non-recovery week. If the weekly plan is falling short, this rule
recommends a phase-appropriate key session. On the last eligible day, it
forces one if needed.

Reference:
    Pfitzinger & Douglas (2009). Advanced Marathoning, 2nd ed.
    Minimum 2 quality sessions per week during BUILD/SPECIFIC.
"""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    MIN_KEY_SESSIONS_PER_WEEK,
    Priority,
    SessionType,
    TrainingPhase,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.models.weekly_plan import WeekContext
from science_engine.rules.base import ScienceRule


# Phase-appropriate key session to recommend when we need one
_PHASE_KEY_SESSION: dict[TrainingPhase, SessionType] = {
    TrainingPhase.BASE: SessionType.TEMPO,
    TrainingPhase.BUILD: SessionType.THRESHOLD,
    TrainingPhase.SPECIFIC: SessionType.MARATHON_PACE,
    TrainingPhase.TAPER: SessionType.THRESHOLD,
    TrainingPhase.RACE: SessionType.EASY,
}


class MinimumKeySessionRule(ScienceRule):
    """Ensures at least 2 key sessions per non-recovery week."""

    rule_id = "minimum_key_session"
    version = "1.0.0"
    priority = Priority.DRIVE
    required_data = ["current_week", "total_plan_weeks"]
    is_weekly_aware = True

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        # Without weekly context, this rule cannot make a decision
        return None

    def evaluate_weekly(
        self, state: AthleteState, context: WeekContext
    ) -> RuleRecommendation | None:
        # Don't force key sessions during recovery weeks
        if context.is_recovery_week:
            return None

        # TAPER/RACE phases have their own reduced schedule
        if context.phase in (TrainingPhase.TAPER, TrainingPhase.RACE):
            return None

        key_planned = context.key_sessions_planned
        remaining = context.remaining_days
        deficit = MIN_KEY_SESSIONS_PER_WEEK - key_planned

        if deficit <= 0:
            # Already have enough key sessions
            return None

        # Force a key session on the last eligible day
        # Or recommend one if there are still enough remaining days
        if remaining <= deficit:
            # Must plan a key session today
            session = _PHASE_KEY_SESSION.get(context.phase, SessionType.THRESHOLD)
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=session,
                explanation=(
                    f"DRIVE: Only {key_planned} key session(s) planned with "
                    f"{remaining} day(s) remaining. Forcing {session.name} "
                    f"to meet minimum of {MIN_KEY_SESSIONS_PER_WEEK}. "
                    f"Ref: Pfitzinger & Douglas (2009)."
                ),
                confidence=0.9,
            )

        # Still room — recommend but don't force
        # Only recommend on quality-day slots (Tue=2, Thu=4)
        if state.day_of_week in (2, 4):
            session = _PHASE_KEY_SESSION.get(context.phase, SessionType.THRESHOLD)
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=session,
                explanation=(
                    f"DRIVE: {key_planned} of {MIN_KEY_SESSIONS_PER_WEEK} key "
                    f"sessions planned. Recommending {session.name} for "
                    f"{context.phase.name} phase. "
                    f"Ref: Pfitzinger & Douglas (2009)."
                ),
                confidence=0.75,
            )

        return None
