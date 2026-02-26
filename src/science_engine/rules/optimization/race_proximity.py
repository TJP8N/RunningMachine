"""OPTIMIZATION rule: Race proximity adjustments.

Adjusts training around B and C races on the athlete's race calendar.
A-race taper/race-week handling is deferred to the periodization rule;
this rule handles supporting races.

Reference:
    Mujika (2010). Intense training: the key to optimal performance
    before and during the taper. Scand J Med Sci Sports 20(s2):24-31.
"""

from __future__ import annotations

from datetime import timedelta

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    B_RACE_RECOVERY_DAYS,
    B_RACE_TAPER_INTENSITY_MOD,
    B_RACE_TAPER_VOLUME_MOD,
    Priority,
    RacePriority,
    SessionType,
    TrainingPhase,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.rules.base import ScienceRule


class RaceProximityRule(ScienceRule):
    """Adjusts training around B/C races on the calendar."""

    rule_id = "race_proximity"
    version = "1.0.0"
    priority = Priority.OPTIMIZATION
    required_data = ["race_calendar", "current_date"]

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        # Defer during TAPER/RACE phases — A-race taper is handled by periodization
        if state.current_phase in (TrainingPhase.TAPER, TrainingPhase.RACE):
            return None

        calendar = state.race_calendar  # guaranteed not None by required_data
        today = state.current_date  # guaranteed not None by required_data

        # --- Race day ---
        race_today = calendar.race_on_date(today)  # type: ignore[union-attr]
        if race_today is not None:
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=SessionType.RACE_SIMULATION,
                intensity_modifier=1.0,
                volume_modifier=1.0,
                explanation=(
                    f"Race day: {race_today.race_name} "
                    f"({race_today.priority.name}-race, {race_today.distance_km}km). "
                    f"Ref: Mujika (2010)."
                ),
                confidence=1.0,
            )

        # --- Day before any race → EASY ---
        tomorrow = today + timedelta(days=1)  # type: ignore[operator]
        race_tomorrow = calendar.race_on_date(tomorrow)  # type: ignore[union-attr]
        if race_tomorrow is not None:
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=SessionType.EASY,
                intensity_modifier=0.7,
                volume_modifier=0.6,
                explanation=(
                    f"Day before {race_tomorrow.race_name} "
                    f"({race_tomorrow.priority.name}-race). Easy day for freshness. "
                    f"Ref: Mujika (2010)."
                ),
                confidence=0.9,
            )

        # --- B-race mini-taper (within 7 days, but not day-before) ---
        next_b = calendar.next_race_by_priority(today, RacePriority.B)  # type: ignore[union-attr]
        if next_b is not None:
            days_to_b = (next_b.race_date - today).days  # type: ignore[operator]
            if 2 <= days_to_b <= 7:
                return RuleRecommendation(
                    rule_id=self.rule_id,
                    rule_version=self.version,
                    priority=self.priority,
                    recommended_session_type=None,  # Don't override session type
                    intensity_modifier=B_RACE_TAPER_INTENSITY_MOD,
                    volume_modifier=B_RACE_TAPER_VOLUME_MOD,
                    explanation=(
                        f"{days_to_b} days until B-race {next_b.race_name}. "
                        f"Mini-taper: volume at {B_RACE_TAPER_VOLUME_MOD:.0%}, "
                        f"intensity at {B_RACE_TAPER_INTENSITY_MOD:.0%}. "
                        f"Ref: Mujika (2010)."
                    ),
                    confidence=0.8,
                )

        # --- Post-B-race recovery (within 3 days after) ---
        # Check recent past for B-races
        for days_ago in range(1, B_RACE_RECOVERY_DAYS + 1):
            past_date = today - timedelta(days=days_ago)  # type: ignore[operator]
            past_race = calendar.race_on_date(past_date)  # type: ignore[union-attr]
            if past_race is not None and past_race.priority == RacePriority.B:
                return RuleRecommendation(
                    rule_id=self.rule_id,
                    rule_version=self.version,
                    priority=self.priority,
                    recommended_session_type=SessionType.EASY,
                    intensity_modifier=0.7,
                    volume_modifier=0.6,
                    explanation=(
                        f"{days_ago} day(s) after B-race {past_race.race_name}. "
                        f"Recovery period. Ref: Mujika (2010)."
                    ),
                    confidence=0.8,
                )

        # No race proximity adjustments needed
        return None
