"""Description builder — generates workout titles and rich descriptions.

Produces human-readable context for each workout including training phase,
ACWR status, readiness summary, and top firing rules.
"""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.decision_trace import DecisionTrace, RuleStatus
from science_engine.models.enums import (
    ACWR_CAUTION_HIGH,
    ACWR_DANGER_THRESHOLD,
    ACWR_OPTIMAL_HIGH,
    ACWR_OPTIMAL_LOW,
    SessionType,
    TrainingPhase,
)
from science_engine.models.workout import WorkoutPrescription

_PHASE_LABELS: dict[TrainingPhase, str] = {
    TrainingPhase.BASE: "BASE",
    TrainingPhase.BUILD: "BUILD",
    TrainingPhase.SPECIFIC: "SPECIFIC",
    TrainingPhase.TAPER: "TAPER",
    TrainingPhase.RACE: "RACE",
}

_SESSION_LABELS: dict[SessionType, str] = {
    SessionType.REST: "Rest Day",
    SessionType.RECOVERY: "Recovery Run",
    SessionType.EASY: "Easy Run",
    SessionType.LONG_RUN: "Long Run",
    SessionType.TEMPO: "Tempo Run",
    SessionType.THRESHOLD: "Threshold Intervals",
    SessionType.VO2MAX_INTERVALS: "VO2max Intervals",
    SessionType.MARATHON_PACE: "Marathon Pace Run",
    SessionType.RACE_SIMULATION: "Race Simulation",
}


def _classify_acwr(acwr: float) -> str:
    """Classify ACWR into a human-readable status."""
    if acwr >= ACWR_DANGER_THRESHOLD:
        return "DANGER (injury risk high)"
    elif acwr >= ACWR_CAUTION_HIGH:
        return "CAUTION (elevated load)"
    elif acwr >= ACWR_OPTIMAL_LOW:
        return "OPTIMAL (sweet spot)"
    else:
        return "UNDERTRAINED (insufficient stimulus)"


def build_workout_description(
    prescription: WorkoutPrescription,
    state: AthleteState,
    trace: DecisionTrace,
) -> tuple[str, str]:
    """Build a workout title and rich description.

    Args:
        prescription: The source workout prescription.
        state: Frozen athlete state.
        trace: Decision trace from the engine.

    Returns:
        A (title, description) tuple.
    """
    # --- Title ---
    phase_label = _PHASE_LABELS.get(prescription.phase, "UNKNOWN")
    session_label = _SESSION_LABELS.get(prescription.session_type, "Workout")
    duration_str = f"{prescription.target_duration_min:.0f} min"
    title = f"{phase_label} W{prescription.week_number} — {session_label} ({duration_str})"

    # --- Description ---
    lines: list[str] = []

    # Phase + week context
    lines.append(f"Phase: {phase_label} | Week {prescription.week_number}")

    # ACWR status
    if state.acwr is not None:
        acwr_status = _classify_acwr(state.acwr)
        lines.append(f"ACWR: {state.acwr:.2f} — {acwr_status}")

    # Readiness summary
    readiness_parts: list[str] = []
    if state.hrv_rmssd is not None and state.hrv_baseline is not None:
        ratio = state.hrv_rmssd / state.hrv_baseline
        readiness_parts.append(f"HRV ratio: {ratio:.2f}")
    if state.sleep_score is not None:
        readiness_parts.append(f"Sleep: {state.sleep_score:.0f}/100")
    if state.body_battery is not None:
        readiness_parts.append(f"Body battery: {state.body_battery}/100")
    if readiness_parts:
        lines.append("Readiness: " + " | ".join(readiness_parts))

    # Top firing rules
    fired_rules = [
        rr for rr in trace.rule_results
        if rr.status == RuleStatus.FIRED and rr.explanation
    ]
    if fired_rules:
        # Take top 3 by priority (rules are already ordered by evaluation)
        top_rules = fired_rules[:3]
        lines.append("Key decisions:")
        for rr in top_rules:
            explanation = rr.explanation[:120]
            lines.append(f"  - [{rr.rule_id}] {explanation}")

    description = "\n".join(lines)
    return title, description


def build_decision_summary(trace: DecisionTrace) -> str:
    """Build a short summary of top 2-3 firing rules.

    Args:
        trace: Decision trace from the engine.

    Returns:
        A brief summary string.
    """
    fired_rules = [
        rr for rr in trace.rule_results
        if rr.status == RuleStatus.FIRED and rr.explanation
    ]
    if not fired_rules:
        return "No rules fired."

    parts: list[str] = []
    for rr in fired_rules[:2]:
        short_exp = rr.explanation[:80]
        parts.append(f"{rr.rule_id}: {short_exp}")
    return " | ".join(parts)
