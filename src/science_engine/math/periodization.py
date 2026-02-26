"""Periodization math: phase allocation, volume targets, session distribution.

Implements a hybrid fixed/proportional marathon periodization model:
- Fixed TAPER (2-3 weeks) and RACE (1 week) durations
- Proportional BASE/BUILD/SPECIFIC from remaining weeks
- Recovery weeks every 4th week with cross-boundary guard

References:
    Pfitzinger & Douglas (2009), Advanced Marathoning, 2nd ed.
    Bosquet et al. (2007), Effects of tapering on performance: a meta-analysis.
    Mujika & Padilla (2003), Scientific bases for precompetition tapering.
    Issurin (2010), New horizons for the methodology and physiology of training
        periodization.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from science_engine.models.enums import (
    CONSERVATIVE_VOLUME_INCREASE_PCT,
    EARLY_BASE_VOLUME_INCREASE_PCT,
    MAX_SPECIFIC_WEEKS,
    MAX_TAPER_WEEKS,
    MAX_WEEKLY_VOLUME_INCREASE_PCT,
    MIN_PLAN_WEEKS,
    MIN_SPECIFIC_WEEKS,
    MIN_TAPER_WEEKS,
    RACE_WEEK_THRESHOLD,
    RECOVERY_WEEK_INTERVAL,
    RECOVERY_WEEK_VOLUME_FRACTION,
    TAPER_LONG_PLAN_THRESHOLD,
    SessionType,
    TrainingPhase,
)


@dataclass(frozen=True)
class PhaseSpec:
    """Specification for a single training phase within the macrocycle."""

    phase: TrainingPhase
    start_week: int  # 1-indexed
    end_week: int  # inclusive
    duration_weeks: int


# Session distribution per week by phase (how many of each session type).
# Total sessions per week: 6 (1 rest day).
# 2 quality sessions per 6-slot week targets ~85% low-intensity by
# time-in-zone (Seiler 2010, polarized training).  LONG_RUN is a sub-VT1
# effort and counts as low-intensity for intensity accounting purposes.
_SESSION_DISTRIBUTION: dict[TrainingPhase, dict[SessionType, int]] = {
    TrainingPhase.BASE: {
        SessionType.REST: 1,
        SessionType.EASY: 3,
        SessionType.LONG_RUN: 1,
        SessionType.TEMPO: 1,
    },
    TrainingPhase.BUILD: {
        SessionType.REST: 1,
        SessionType.EASY: 2,
        SessionType.LONG_RUN: 1,
        SessionType.THRESHOLD: 1,
        SessionType.VO2MAX_INTERVALS: 1,
    },
    TrainingPhase.SPECIFIC: {
        SessionType.REST: 1,
        SessionType.EASY: 2,
        SessionType.LONG_RUN: 1,
        SessionType.MARATHON_PACE: 1,
        SessionType.THRESHOLD: 1,
    },
    TrainingPhase.TAPER: {
        SessionType.REST: 2,
        SessionType.EASY: 2,
        SessionType.MARATHON_PACE: 1,
        SessionType.THRESHOLD: 1,
    },
    TrainingPhase.RACE: {
        SessionType.REST: 3,
        SessionType.EASY: 2,
        SessionType.RACE_SIMULATION: 1,
    },
}


def allocate_phases(total_weeks: int) -> list[PhaseSpec]:
    """Allocate training phases across the macrocycle.

    Uses a hybrid fixed/proportional model:
    - TAPER: fixed 2-3 weeks (Bosquet et al. 2007, Mujika 2010)
    - RACE: fixed 1 week for plans >= 12 weeks
    - SPECIFIC: proportional with floor of 3 and cap of 8
    - BASE/BUILD: split remaining weeks 55/45 (Pfitzinger-inspired)

    For plans > 24 weeks, BASE absorbs extra proportionally since
    aerobic adaptations need 8-12+ weeks (Holloszy & Coyle 1984).

    Args:
        total_weeks: Total weeks in the training plan (minimum 4).

    Returns:
        List of PhaseSpec in chronological order.

    Raises:
        ValueError: If total_weeks < MIN_PLAN_WEEKS.
    """
    if total_weeks < MIN_PLAN_WEEKS:
        raise ValueError(
            f"Plan must be at least {MIN_PLAN_WEEKS} weeks, got {total_weeks}"
        )

    # 1. Carve fixed durations from the end
    race_weeks = 1 if total_weeks >= RACE_WEEK_THRESHOLD else 0
    taper_weeks = (
        MAX_TAPER_WEEKS
        if total_weeks > TAPER_LONG_PLAN_THRESHOLD
        else MIN_TAPER_WEEKS
    )

    remaining = total_weeks - taper_weeks - race_weeks

    # 2. Allocate SPECIFIC (proportional with floor and cap)
    specific_weeks = min(
        max(MIN_SPECIFIC_WEEKS, round(remaining * 0.22)), MAX_SPECIFIC_WEEKS
    )
    # Don't let SPECIFIC consume more than available minus 1 for BASE
    specific_weeks = min(specific_weeks, remaining - 1)
    specific_weeks = max(1, specific_weeks)

    remaining2 = remaining - specific_weeks

    # 3. Split remainder between BASE and BUILD
    if remaining2 >= 2:
        base_weeks = max(1, round(remaining2 * 0.55))
        build_weeks = remaining2 - base_weeks
        if build_weeks < 1:
            build_weeks = 1
            base_weeks = remaining2 - 1
    else:
        # Very short plan: skip BUILD
        base_weeks = max(1, remaining2)
        build_weeks = 0

    # 4. Build phase specs (skip phases with 0 duration)
    phase_durations = [
        (TrainingPhase.BASE, base_weeks),
        (TrainingPhase.BUILD, build_weeks),
        (TrainingPhase.SPECIFIC, specific_weeks),
        (TrainingPhase.TAPER, taper_weeks),
        (TrainingPhase.RACE, race_weeks),
    ]

    phases: list[PhaseSpec] = []
    current_week = 1
    for phase_type, duration in phase_durations:
        if duration > 0:
            phases.append(
                PhaseSpec(
                    phase=phase_type,
                    start_week=current_week,
                    end_week=current_week + duration - 1,
                    duration_weeks=duration,
                )
            )
            current_week += duration

    return phases


def get_phase_for_week(week: int, phases: list[PhaseSpec]) -> TrainingPhase:
    """Determine which training phase a given week falls in.

    Args:
        week: 1-indexed week number.
        phases: List of PhaseSpec from allocate_phases().

    Returns:
        The TrainingPhase for that week.

    Raises:
        ValueError: If week is outside the plan range.
    """
    for spec in phases:
        if spec.start_week <= week <= spec.end_week:
            return spec.phase
    raise ValueError(
        f"Week {week} is outside plan range "
        f"(1-{phases[-1].end_week if phases else 0})"
    )


def get_weekly_volume_target(
    week: int,
    phases: list[PhaseSpec],
    peak_volume_km: float,
) -> float:
    """Calculate the target weekly volume for a given week.

    Volume ramps up progressively during BASE and BUILD, peaks in SPECIFIC,
    and drops during TAPER using exponential decay (Bosquet et al. 2007).
    Recovery weeks (every 4th week) reduce volume to 60-70% of the normal
    target.

    Args:
        week: 1-indexed week number.
        phases: Phase allocation from allocate_phases().
        peak_volume_km: The peak weekly volume in km (reached in SPECIFIC).

    Returns:
        Target weekly volume in km.
    """
    phase = get_phase_for_week(week, phases)

    # Base volume fractions by phase (fraction of peak_volume_km)
    phase_volume_fraction: dict[TrainingPhase, float] = {
        TrainingPhase.BASE: 0.65,
        TrainingPhase.BUILD: 0.80,
        TrainingPhase.SPECIFIC: 1.0,
        TrainingPhase.TAPER: 0.60,  # Not used directly; see exponential below
        TrainingPhase.RACE: 0.30,
    }

    base_fraction = phase_volume_fraction[phase]

    # Progressive ramp within BASE and BUILD: linearly increase within the phase
    for spec in phases:
        if spec.phase == phase:
            phase_progress = (week - spec.start_week) / max(1, spec.duration_weeks - 1)
            break
    else:
        phase_progress = 0.0

    if phase in (TrainingPhase.BASE, TrainingPhase.BUILD):
        # Ramp from base_fraction * 0.85 to base_fraction
        ramp_start = base_fraction * 0.85
        volume = ramp_start + (base_fraction - ramp_start) * phase_progress
    elif phase == TrainingPhase.TAPER:
        # Exponential taper decay (Bosquet et al. 2007):
        # Exponential tapers produce significantly better performance outcomes
        # than linear.  Volume drops from ~85% to ~55% of SPECIFIC peak.
        # Optimal volume reduction is 41-60% of pre-taper (Mujika & Padilla 2003).
        taper_start_fraction = 0.85
        taper_end_fraction = 0.55
        decay_rate = -math.log(taper_end_fraction / taper_start_fraction)
        volume = taper_start_fraction * math.exp(-decay_rate * phase_progress)
    else:
        volume = base_fraction

    target = peak_volume_km * volume

    # Apply recovery week reduction
    if is_recovery_week(week, phases):
        target *= RECOVERY_WEEK_VOLUME_FRACTION

    return round(target, 1)


def get_session_distribution(phase: TrainingPhase) -> dict[SessionType, int]:
    """Get the recommended session distribution for a training phase.

    Args:
        phase: The current training phase.

    Returns:
        Dict mapping SessionType to number of sessions per week.
    """
    return dict(_SESSION_DISTRIBUTION.get(phase, _SESSION_DISTRIBUTION[TrainingPhase.BASE]))


def is_recovery_week(week: int, phases: list[PhaseSpec]) -> bool:
    """Determine if a given week is a recovery (deload) week.

    Recovery weeks occur every 4th week within a phase (3 hard + 1 recovery
    cycle).  A global guard ensures no more than RECOVERY_WEEK_INTERVAL
    consecutive hard weeks across phase boundaries.

    TAPER and RACE phases are never recovery weeks (they have their own
    volume reduction built in).

    Args:
        week: 1-indexed week number.
        phases: Phase allocation from allocate_phases().

    Returns:
        True if this is a recovery week.
    """
    phase = get_phase_for_week(week, phases)

    # Taper and race phases handle their own volume reduction
    if phase in (TrainingPhase.TAPER, TrainingPhase.RACE):
        return False

    # Simulate recovery schedule from week 1 to determine the current week's
    # status.  This accounts for both within-phase recovery and the global
    # cross-boundary guard.
    consecutive_hard = 0
    for w in range(1, week + 1):
        w_phase = get_phase_for_week(w, phases)

        if w_phase in (TrainingPhase.TAPER, TrainingPhase.RACE):
            consecutive_hard = 0
            continue

        # Phase-level recovery check
        is_phase_recovery = False
        for spec in phases:
            if spec.phase == w_phase:
                w_in_phase = w - spec.start_week  # 0-indexed within phase
                is_phase_recovery = (
                    (w_in_phase + 1) % (RECOVERY_WEEK_INTERVAL + 1) == 0
                )
                break

        # Global guard: force recovery if consecutive hard weeks exceed limit
        if is_phase_recovery or consecutive_hard >= RECOVERY_WEEK_INTERVAL:
            if w == week:
                return True
            consecutive_hard = 0
        else:
            consecutive_hard += 1

    return False


# ---------------------------------------------------------------------------
# Date-driven utilities
# ---------------------------------------------------------------------------


def compute_plan_weeks(start_date: date, race_date: date) -> int:
    """Calculate the number of full training weeks between two dates.

    Args:
        start_date: First day of training.
        race_date: Race day.

    Returns:
        Number of full weeks (rounded down).

    Raises:
        ValueError: If the resulting plan would be shorter than MIN_PLAN_WEEKS.
    """
    delta_days = (race_date - start_date).days
    weeks = delta_days // 7
    if weeks < MIN_PLAN_WEEKS:
        raise ValueError(
            f"Plan must be at least {MIN_PLAN_WEEKS} weeks, "
            f"got {weeks} weeks ({delta_days} days)"
        )
    return weeks


def derive_current_phase(
    current_week: int, total_plan_weeks: int
) -> TrainingPhase:
    """Convenience: get the training phase for a given week in a plan.

    Args:
        current_week: 1-indexed current week number.
        total_plan_weeks: Total weeks in the plan.

    Returns:
        The TrainingPhase for that week.
    """
    return get_phase_for_week(current_week, allocate_phases(total_plan_weeks))
