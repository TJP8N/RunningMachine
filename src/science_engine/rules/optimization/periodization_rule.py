"""OPTIMIZATION rule: Periodization-based session type recommendation.

Reads the current week and total plan weeks, determines the training phase,
and recommends session types appropriate for that phase.

Reference:
    Pfitzinger & Douglas (2009), Advanced Marathoning, 2nd ed.
"""

from __future__ import annotations

from science_engine.math.periodization import (
    allocate_phases,
    get_phase_for_week,
    get_session_distribution,
)
from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import Priority, SessionType
from science_engine.models.recommendation import RuleRecommendation
from science_engine.rules.base import ScienceRule


# Key sessions by phase — the high-value workout for each phase
_PHASE_KEY_SESSIONS: dict[int, SessionType] = {
    1: SessionType.LONG_RUN,      # BASE: aerobic development
    2: SessionType.VO2MAX_INTERVALS,  # BUILD: VO2max development
    3: SessionType.MARATHON_PACE,  # SPECIFIC: race-pace specificity
    4: SessionType.EASY,           # TAPER: recovery
    5: SessionType.REST,           # RACE: rest before race
}


class PeriodizationRule(ScienceRule):
    """Recommends session types based on the current training phase."""

    rule_id = "periodization"
    version = "1.0.0"
    priority = Priority.OPTIMIZATION
    required_data = ["current_week", "total_plan_weeks"]

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        phases = allocate_phases(state.total_plan_weeks)
        phase = get_phase_for_week(state.current_week, phases)
        distribution = get_session_distribution(phase)

        # Pick the key session for this phase
        key_session = _PHASE_KEY_SESSIONS.get(int(phase), SessionType.EASY)

        # If the key session is in the distribution, recommend it
        if key_session not in distribution:
            # Fall back to the most frequent non-rest, non-easy session
            candidates = [
                (st, count)
                for st, count in distribution.items()
                if st not in (SessionType.REST, SessionType.EASY)
            ]
            if candidates:
                key_session = max(candidates, key=lambda x: x[1])[0]
            else:
                key_session = SessionType.EASY

        return RuleRecommendation(
            rule_id=self.rule_id,
            rule_version=self.version,
            priority=self.priority,
            recommended_session_type=key_session,
            explanation=(
                f"Phase {phase.name} (week {state.current_week}/{state.total_plan_weeks}): "
                f"key session is {key_session.name}. "
                f"Ref: Pfitzinger & Douglas (2009)."
            ),
            confidence=0.8,
        )
