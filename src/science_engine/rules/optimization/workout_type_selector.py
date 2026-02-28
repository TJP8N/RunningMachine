"""OPTIMIZATION rule: Workout type selector — picks a session type for today.

Selects a specific SessionType based on the current phase and day of week,
following the phase's session distribution pattern.

Reference:
    Pfitzinger & Douglas (2009), Advanced Marathoning, 2nd ed.
"""

from __future__ import annotations

from science_engine.math.periodization import (
    allocate_phases,
    get_phase_for_week,
    get_session_distribution,
    is_recovery_week,
)
from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import Priority, SessionType, TrainingPhase
from science_engine.models.recommendation import RuleRecommendation
from science_engine.rules.base import ScienceRule


# Day-of-week session slots: which "role" each day plays
# 1=Monday through 7=Sunday
# Typical marathon schedule: hard days Tue/Thu, long run Sun, rest Mon or Fri
_DAY_ROLE: dict[int, str] = {
    1: "rest_or_easy",   # Monday: recovery from weekend long run
    2: "quality_1",      # Tuesday: first quality session
    3: "easy",           # Wednesday: easy day
    4: "quality_2",      # Thursday: second quality session
    5: "easy",           # Friday: easy / pre-long-run
    6: "moderate",       # Saturday: moderate effort
    7: "long_run",       # Sunday: long run
}

# Phase-specific quality session assignments
_QUALITY_SESSIONS: dict[TrainingPhase, tuple[SessionType, SessionType]] = {
    TrainingPhase.BASE: (SessionType.TEMPO, SessionType.EASY),
    TrainingPhase.BUILD: (SessionType.THRESHOLD, SessionType.VO2MAX_INTERVALS),
    TrainingPhase.SPECIFIC: (SessionType.THRESHOLD, SessionType.MARATHON_PACE),
    TrainingPhase.TAPER: (SessionType.THRESHOLD, SessionType.EASY),
    TrainingPhase.RACE: (SessionType.EASY, SessionType.REST),
}


class WorkoutTypeSelectorRule(ScienceRule):
    """Selects the specific session type for today based on phase and day of week."""

    rule_id = "workout_type_selector"
    version = "1.0.0"
    priority = Priority.OPTIMIZATION
    required_data = ["current_week", "total_plan_weeks", "day_of_week"]

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        phases = allocate_phases(state.total_plan_weeks)
        phase = get_phase_for_week(state.current_week, phases)
        day_role = _DAY_ROLE.get(state.day_of_week, "easy")

        # Recovery weeks: downgrade quality sessions to easy
        recovery = is_recovery_week(state.current_week, phases)

        session_type = self._select_session(phase, day_role, recovery)

        return RuleRecommendation(
            rule_id=self.rule_id,
            rule_version=self.version,
            priority=self.priority,
            recommended_session_type=session_type,
            explanation=(
                f"Day {state.day_of_week} ({day_role}) in {phase.name} phase: "
                f"{session_type.name}"
                f"{' (recovery week — downgraded)' if recovery else ''}. "
                f"Ref: Pfitzinger & Douglas (2009)."
            ),
            confidence=0.85,
        )

    def _select_session(
        self, phase: TrainingPhase, day_role: str, recovery: bool
    ) -> SessionType:
        """Map a day role + phase to a concrete SessionType."""
        quality_1, quality_2 = _QUALITY_SESSIONS[phase]

        if day_role == "rest_or_easy":
            return SessionType.EASY if recovery else SessionType.REST

        if day_role == "quality_1":
            return SessionType.EASY if recovery else quality_1

        if day_role == "quality_2":
            return SessionType.EASY if recovery else quality_2

        if day_role == "long_run":
            if recovery:
                return SessionType.EASY
            if phase == TrainingPhase.TAPER:
                return SessionType.EASY
            return SessionType.LONG_RUN

        if day_role == "moderate":
            if phase == TrainingPhase.SPECIFIC:
                return SessionType.MARATHON_PACE if not recovery else SessionType.EASY
            return SessionType.EASY

        return SessionType.EASY
