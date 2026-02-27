"""Session templates — structural patterns for each SessionType.

Each template defines the warmup/main-set/cooldown decomposition and the
target zone for each segment. The WorkoutBuilder uses these to split a
prescription's total duration into individual WorkoutSteps.
"""

from __future__ import annotations

from dataclasses import dataclass

from science_engine.models.enums import (
    COOLDOWN_DURATION_MIN,
    QUALITY_COOLDOWN_DURATION_MIN,
    QUALITY_WARMUP_DURATION_MIN,
    WARMUP_DURATION_MIN,
    SessionType,
    StepType,
    ZoneType,
)


@dataclass(frozen=True)
class SegmentTemplate:
    """Template for a single segment within a session.

    Attributes:
        step_type: The type of workout step.
        zone: Target heart rate / pace zone.
        is_repeat: Whether this segment is a repeat block (intervals).
        rep_work_min: Per-rep work duration in minutes (for intervals).
        rep_recovery_min: Per-rep recovery duration in minutes (for intervals).
        fraction_of_main: Fraction of main-set time (e.g. 0.2 = last 20%).
            Only used for split main-set segments like LONG_RUN progression.
    """

    step_type: StepType
    zone: ZoneType
    is_repeat: bool = False
    rep_work_min: float = 0.0
    rep_recovery_min: float = 0.0
    fraction_of_main: float = 0.0


@dataclass(frozen=True)
class SessionTemplate:
    """Complete template for a session type.

    Attributes:
        warmup_duration_min: Duration of warmup in minutes (0 = no warmup).
        warmup_zone: Target zone for warmup.
        main_segments: Tuple of main-set segment templates.
        cooldown_duration_min: Duration of cooldown in minutes (0 = no cooldown).
        cooldown_zone: Target zone for cooldown.
    """

    warmup_duration_min: float
    warmup_zone: ZoneType
    main_segments: tuple[SegmentTemplate, ...]
    cooldown_duration_min: float
    cooldown_zone: ZoneType


# ---------------------------------------------------------------------------
# Template definitions for all 9 session types
# ---------------------------------------------------------------------------

SESSION_TEMPLATES: dict[SessionType, SessionTemplate] = {
    # REST: single rest step, no warmup/cooldown
    SessionType.REST: SessionTemplate(
        warmup_duration_min=0,
        warmup_zone=ZoneType.ZONE_1,
        main_segments=(
            SegmentTemplate(step_type=StepType.REST, zone=ZoneType.ZONE_1),
        ),
        cooldown_duration_min=0,
        cooldown_zone=ZoneType.ZONE_1,
    ),

    # RECOVERY: Z1 steady, full duration, no warmup/cooldown
    SessionType.RECOVERY: SessionTemplate(
        warmup_duration_min=0,
        warmup_zone=ZoneType.ZONE_1,
        main_segments=(
            SegmentTemplate(step_type=StepType.ACTIVE, zone=ZoneType.ZONE_1),
        ),
        cooldown_duration_min=0,
        cooldown_zone=ZoneType.ZONE_1,
    ),

    # EASY: 10 min Z1 warmup | remaining Z2 | 5 min Z1 cooldown
    SessionType.EASY: SessionTemplate(
        warmup_duration_min=WARMUP_DURATION_MIN,
        warmup_zone=ZoneType.ZONE_1,
        main_segments=(
            SegmentTemplate(step_type=StepType.ACTIVE, zone=ZoneType.ZONE_2),
        ),
        cooldown_duration_min=COOLDOWN_DURATION_MIN,
        cooldown_zone=ZoneType.ZONE_1,
    ),

    # LONG_RUN: 10 min Z1 warmup | 80% at Z2, last 20% at Z3 | 5 min Z1 cooldown
    SessionType.LONG_RUN: SessionTemplate(
        warmup_duration_min=WARMUP_DURATION_MIN,
        warmup_zone=ZoneType.ZONE_1,
        main_segments=(
            SegmentTemplate(
                step_type=StepType.ACTIVE, zone=ZoneType.ZONE_2,
                fraction_of_main=0.80,
            ),
            SegmentTemplate(
                step_type=StepType.ACTIVE, zone=ZoneType.ZONE_3,
                fraction_of_main=0.20,
            ),
        ),
        cooldown_duration_min=COOLDOWN_DURATION_MIN,
        cooldown_zone=ZoneType.ZONE_1,
    ),

    # TEMPO: 15 min Z2 warmup | remaining Z3 | 10 min Z1 cooldown
    SessionType.TEMPO: SessionTemplate(
        warmup_duration_min=QUALITY_WARMUP_DURATION_MIN,
        warmup_zone=ZoneType.ZONE_2,
        main_segments=(
            SegmentTemplate(step_type=StepType.ACTIVE, zone=ZoneType.ZONE_3),
        ),
        cooldown_duration_min=QUALITY_COOLDOWN_DURATION_MIN,
        cooldown_zone=ZoneType.ZONE_1,
    ),

    # THRESHOLD: 15 min Z2 warmup | Repeat(8 min Z4 + 2 min Z1) | 10 min Z1 cooldown
    SessionType.THRESHOLD: SessionTemplate(
        warmup_duration_min=QUALITY_WARMUP_DURATION_MIN,
        warmup_zone=ZoneType.ZONE_2,
        main_segments=(
            SegmentTemplate(
                step_type=StepType.REPEAT, zone=ZoneType.ZONE_4,
                is_repeat=True,
                rep_work_min=8.0,
                rep_recovery_min=2.0,
            ),
        ),
        cooldown_duration_min=QUALITY_COOLDOWN_DURATION_MIN,
        cooldown_zone=ZoneType.ZONE_1,
    ),

    # VO2MAX_INTERVALS: 15 min Z2 warmup | Repeat(3 min Z5 + 3 min Z1) | 10 min Z1 cooldown
    SessionType.VO2MAX_INTERVALS: SessionTemplate(
        warmup_duration_min=QUALITY_WARMUP_DURATION_MIN,
        warmup_zone=ZoneType.ZONE_2,
        main_segments=(
            SegmentTemplate(
                step_type=StepType.REPEAT, zone=ZoneType.ZONE_5,
                is_repeat=True,
                rep_work_min=3.0,
                rep_recovery_min=3.0,
            ),
        ),
        cooldown_duration_min=QUALITY_COOLDOWN_DURATION_MIN,
        cooldown_zone=ZoneType.ZONE_1,
    ),

    # MARATHON_PACE: 15 min Z2 warmup | remaining Z3 at MP | 10 min Z1 cooldown
    SessionType.MARATHON_PACE: SessionTemplate(
        warmup_duration_min=QUALITY_WARMUP_DURATION_MIN,
        warmup_zone=ZoneType.ZONE_2,
        main_segments=(
            SegmentTemplate(step_type=StepType.ACTIVE, zone=ZoneType.ZONE_3),
        ),
        cooldown_duration_min=QUALITY_COOLDOWN_DURATION_MIN,
        cooldown_zone=ZoneType.ZONE_1,
    ),

    # RACE_SIMULATION: 15 min Z2 warmup | remaining at race pace (Z3) | 10 min Z1 cooldown
    SessionType.RACE_SIMULATION: SessionTemplate(
        warmup_duration_min=QUALITY_WARMUP_DURATION_MIN,
        warmup_zone=ZoneType.ZONE_2,
        main_segments=(
            SegmentTemplate(step_type=StepType.ACTIVE, zone=ZoneType.ZONE_3),
        ),
        cooldown_duration_min=QUALITY_COOLDOWN_DURATION_MIN,
        cooldown_zone=ZoneType.ZONE_1,
    ),
}


def get_template(session_type: SessionType) -> SessionTemplate:
    """Look up the session template for a given session type.

    Args:
        session_type: The type of session.

    Returns:
        The corresponding SessionTemplate.

    Raises:
        KeyError: If no template is defined for the session type.
    """
    return SESSION_TEMPLATES[session_type]
