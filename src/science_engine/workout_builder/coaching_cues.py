"""Coaching cues — per-step coaching notes keyed by (SessionType, StepType).

Each cue includes RPE guidance to help the athlete gauge effort without
relying solely on pace or HR.
"""

from __future__ import annotations

from science_engine.models.enums import SessionType, StepType

# ---------------------------------------------------------------------------
# Cue lookup: (SessionType, StepType) -> coaching note
# A None SessionType key means "default for any session type".
# ---------------------------------------------------------------------------

_CUES: dict[tuple[SessionType | None, StepType, bool], str] = {
    # --- Generic cues (any session type) ---
    (None, StepType.WARMUP, False): (
        "Easy jog, gradually increase pace. Activate muscles."
    ),
    (None, StepType.COOLDOWN, False): (
        "Gentle jog, let HR come down gradually."
    ),
    (None, StepType.RECOVERY, False): (
        "Easy jog, focus on recovery. Shake out legs."
    ),
    (None, StepType.REST, False): (
        "Full rest. Hydrate and refuel."
    ),

    # --- EASY ---
    (SessionType.EASY, StepType.ACTIVE, False): (
        "Conversational pace, nasal breathing. RPE 3-4/10."
    ),

    # --- RECOVERY ---
    (SessionType.RECOVERY, StepType.ACTIVE, False): (
        "Very easy shuffle. Keep effort minimal. RPE 2-3/10."
    ),

    # --- LONG_RUN ---
    (SessionType.LONG_RUN, StepType.ACTIVE, False): (
        "Steady aerobic effort, comfortable pace. RPE 4-5/10."
    ),
    (SessionType.LONG_RUN, StepType.ACTIVE, True): (
        "Building fatigue resistance for miles 18-22. Stay relaxed. RPE 5-6/10."
    ),

    # --- TEMPO ---
    (SessionType.TEMPO, StepType.ACTIVE, False): (
        "Comfortably hard — controlled breathing. RPE 6-7/10."
    ),

    # --- THRESHOLD ---
    (SessionType.THRESHOLD, StepType.ACTIVE, False): (
        "Strong, controlled effort. RPE 7-8/10. Quick turnover."
    ),

    # --- VO2MAX_INTERVALS ---
    (SessionType.VO2MAX_INTERVALS, StepType.ACTIVE, False): (
        "Hard effort, controlled form. RPE 8-9/10."
    ),

    # --- MARATHON_PACE ---
    (SessionType.MARATHON_PACE, StepType.ACTIVE, False): (
        "Goal race pace. Practice fueling. RPE 6-7/10."
    ),

    # --- RACE_SIMULATION ---
    (SessionType.RACE_SIMULATION, StepType.ACTIVE, False): (
        "Race effort. Simulate race day conditions. RPE 7-8/10."
    ),
}


def get_coaching_cue(
    session_type: SessionType,
    step_type: StepType,
    is_late_segment: bool = False,
) -> str:
    """Look up the coaching cue for a given session type and step type.

    Args:
        session_type: The current session type.
        step_type: The current step type.
        is_late_segment: True for the progression segment of split main sets
            (e.g. last 20% of LONG_RUN). Triggers a different cue.

    Returns:
        A coaching note string. Falls back to generic cues if no
        session-specific cue is defined.
    """
    # Try session-specific cue first
    key = (session_type, step_type, is_late_segment)
    if key in _CUES:
        return _CUES[key]

    # Fall back to non-late-segment version
    key_no_late = (session_type, step_type, False)
    if key_no_late in _CUES:
        return _CUES[key_no_late]

    # Fall back to generic cue
    generic_key = (None, step_type, False)
    if generic_key in _CUES:
        return _CUES[generic_key]

    return ""
