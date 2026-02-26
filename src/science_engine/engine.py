"""ScienceEngine — the main orchestrator that prescribes training sessions."""

from __future__ import annotations

import dataclasses

from science_engine.conflict_resolution.resolver import ConflictResolver
from science_engine.math.periodization import allocate_phases, get_phase_for_week, is_recovery_week
from science_engine.models.athlete_state import AthleteState
from science_engine.models.decision_trace import (
    DecisionTrace,
    RuleResult,
    RuleStatus,
)
from science_engine.models.enums import IntensityLevel, SessionType, TrainingPhase
from science_engine.models.recommendation import RuleRecommendation
from science_engine.models.weekly_plan import WeekContext, WeeklyPlan
from science_engine.models.workout import WorkoutPrescription
from science_engine.registry import RuleRegistry


# Default session durations in minutes by session type
_DEFAULT_DURATION: dict[SessionType, float] = {
    SessionType.REST: 0.0,
    SessionType.RECOVERY: 30.0,
    SessionType.EASY: 45.0,
    SessionType.LONG_RUN: 90.0,
    SessionType.TEMPO: 50.0,
    SessionType.THRESHOLD: 50.0,
    SessionType.VO2MAX_INTERVALS: 45.0,
    SessionType.MARATHON_PACE: 60.0,
    SessionType.RACE_SIMULATION: 120.0,
}

# Session types that count as "key" (quality) sessions
_KEY_SESSION_TYPES = frozenset({
    SessionType.THRESHOLD,
    SessionType.VO2MAX_INTERVALS,
    SessionType.MARATHON_PACE,
    SessionType.TEMPO,
    SessionType.RACE_SIMULATION,
    SessionType.LONG_RUN,
})


class ScienceEngine:
    """Orchestrates rule evaluation, conflict resolution, and workout prescription.

    Usage:
        engine = ScienceEngine()
        prescription, trace = engine.prescribe(athlete_state)
        weekly_plan = engine.prescribe_week(athlete_state)
    """

    def __init__(
        self,
        registry: RuleRegistry | None = None,
        resolver: ConflictResolver | None = None,
    ) -> None:
        self.registry = registry or RuleRegistry()
        self.resolver = resolver or ConflictResolver()

        # Auto-discover rules if using default registry
        if registry is None:
            self.registry.discover_rules()

    def prescribe(
        self, state: AthleteState
    ) -> tuple[WorkoutPrescription, DecisionTrace]:
        """Evaluate all rules and produce a workout prescription.

        Args:
            state: Frozen snapshot of the athlete's current state.

        Returns:
            A tuple of (WorkoutPrescription, DecisionTrace).
        """
        return self._prescribe_day(state, context=None)

    def prescribe_week(self, state: AthleteState) -> WeeklyPlan:
        """Plan a full 7-day training week.

        Iterates days 1–7, building a WeekContext that accumulates planned
        sessions. Weekly-aware rules receive the context so they can reason
        about the shape of the whole week.

        Args:
            state: Frozen athlete state snapshot. ``day_of_week`` is ignored;
                   the engine plans all 7 days.

        Returns:
            A WeeklyPlan containing 7 prescriptions and their traces.
        """
        phases = allocate_phases(state.total_plan_weeks)
        phase = get_phase_for_week(state.current_week, phases)
        recovery = is_recovery_week(state.current_week, phases)

        prescriptions: list[WorkoutPrescription] = []
        traces: list[DecisionTrace] = []

        for day in range(1, 8):
            context = WeekContext(
                day_number=day,
                planned_sessions=tuple(prescriptions),
                phase=phase,
                is_recovery_week=recovery,
            )

            # Create a day-specific state with the correct day_of_week
            day_state = dataclasses.replace(state, day_of_week=day)

            prescription, trace = self._prescribe_day(day_state, context)
            prescriptions.append(prescription)
            traces.append(trace)

        return WeeklyPlan(
            prescriptions=tuple(prescriptions),
            traces=tuple(traces),
            phase=phase,
            week_number=state.current_week,
            is_recovery_week=recovery,
        )

    def _prescribe_day(
        self,
        state: AthleteState,
        context: WeekContext | None,
    ) -> tuple[WorkoutPrescription, DecisionTrace]:
        """Core single-day prescription logic.

        Args:
            state: Frozen athlete state snapshot.
            context: Optional WeekContext for weekly planning. None for
                     standalone prescribe() calls.

        Returns:
            A tuple of (WorkoutPrescription, DecisionTrace).
        """
        rules = self.registry.get_all_rules()
        rule_results: list[RuleResult] = []
        recommendations: list[RuleRecommendation] = []

        for rule in rules:
            if not rule.has_required_data(state):
                rule_results.append(
                    RuleResult(
                        rule_id=rule.rule_id,
                        status=RuleStatus.NOT_APPLICABLE,
                        explanation=f"Missing required data: {rule.required_data}",
                    )
                )
                continue

            # Use weekly evaluation if context is available and rule is weekly-aware
            if context is not None and rule.is_weekly_aware:
                recommendation = rule.evaluate_weekly(state, context)
            else:
                recommendation = rule.evaluate(state)

            if recommendation is not None:
                recommendations.append(recommendation)
                rule_results.append(
                    RuleResult(
                        rule_id=rule.rule_id,
                        status=RuleStatus.FIRED,
                        recommendation=recommendation,
                        explanation=recommendation.explanation,
                    )
                )
            else:
                rule_results.append(
                    RuleResult(
                        rule_id=rule.rule_id,
                        status=RuleStatus.SKIPPED,
                        explanation="Rule returned no recommendation.",
                    )
                )

        # Resolve conflicts
        winner, resolution_notes = self.resolver.resolve(recommendations)

        # Build the final prescription from the winning recommendation
        prescription = self._build_prescription(winner, state)

        trace = DecisionTrace(
            rule_results=tuple(rule_results),
            final_prescription=prescription,
            conflict_resolution_notes=resolution_notes,
        )

        return prescription, trace

    def _build_prescription(
        self, rec: RuleRecommendation, state: AthleteState
    ) -> WorkoutPrescription:
        """Convert a winning recommendation into a concrete WorkoutPrescription."""
        session_type = rec.recommended_session_type or SessionType.EASY
        base_duration = rec.target_duration_min or _DEFAULT_DURATION.get(session_type, 45.0)
        adjusted_duration = base_duration * rec.volume_modifier

        # If there's a safety veto, override to easy/recovery
        if rec.veto:
            session_type = SessionType.EASY
            adjusted_duration = min(adjusted_duration, 45.0)

        # Map intensity modifier to IntensityLevel
        if rec.intensity_modifier >= 0.9:
            intensity = IntensityLevel.A_FULL
        elif rec.intensity_modifier >= 0.7:
            intensity = IntensityLevel.B_MODERATE
        else:
            intensity = IntensityLevel.C_EASY

        return WorkoutPrescription(
            session_type=session_type,
            intensity_level=intensity,
            target_duration_min=round(adjusted_duration, 1),
            target_distance_km=rec.target_distance_km,
            description=rec.explanation,
            phase=state.current_phase,
            week_number=state.current_week,
        )

    @staticmethod
    def is_key_session(session_type: SessionType) -> bool:
        """Check if a session type is a key (quality) session."""
        return session_type in _KEY_SESSION_TYPES
