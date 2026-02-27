"""WorkoutBuilder — orchestrates structured workout generation.

Decomposes a WorkoutPrescription into a fully structured, step-by-step
StructuredWorkout using session templates, pace/HR targets, coaching
cues, and fueling logic.
"""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.decision_trace import DecisionTrace
from science_engine.models.enums import (
    DurationType,
    SessionType,
    StepType,
    ZoneType,
)
from science_engine.models.structured_workout import StructuredWorkout, WorkoutStep
from science_engine.models.workout import WorkoutPrescription
from science_engine.workout_builder.coaching_cues import get_coaching_cue
from science_engine.workout_builder.description_builder import (
    build_decision_summary,
    build_workout_description,
)
from science_engine.workout_builder.fueling import insert_fueling_steps
from science_engine.workout_builder.session_templates import get_template
from science_engine.workout_builder.target_assigner import assign_targets


class WorkoutBuilder:
    """Builds structured workouts from prescriptions.

    Usage::

        builder = WorkoutBuilder()
        structured = builder.build(prescription, state, trace)
    """

    def build(
        self,
        prescription: WorkoutPrescription,
        state: AthleteState,
        trace: DecisionTrace,
    ) -> StructuredWorkout:
        """Build a fully structured workout from a prescription.

        Algorithm:
        1. Look up session template for prescription.session_type
        2. Calculate warmup + cooldown durations from template
        3. Calculate main-set time = target_duration_min - warmup - cooldown
        4. For interval sessions: rep count = main_set_time // (work + recovery)
        5. Assign pace/HR targets per step via assign_targets()
        6. Apply intensity modifier from prescription.intensity_level
        7. Attach coaching cues per step
        8. Insert fueling steps if duration > 60 min
        9. Build workout title + description
        10. Return frozen StructuredWorkout

        Args:
            prescription: The source workout prescription.
            state: Frozen athlete state with physiology data.
            trace: Decision trace from the engine.

        Returns:
            A fully populated StructuredWorkout.
        """
        template = get_template(prescription.session_type)
        total_duration = prescription.target_duration_min

        # --- Handle REST / zero-duration ---
        if prescription.session_type == SessionType.REST or total_duration <= 0:
            return self._build_rest(prescription, state, trace)

        # --- Calculate segment durations ---
        warmup_min = min(template.warmup_duration_min, total_duration * 0.4)
        cooldown_min = min(template.cooldown_duration_min, total_duration * 0.2)
        main_set_min = max(total_duration - warmup_min - cooldown_min, 0.0)

        steps: list[WorkoutStep] = []

        # --- Warmup ---
        if warmup_min > 0:
            targets = assign_targets(
                state, template.warmup_zone, prescription.intensity_level,
            )
            cue = get_coaching_cue(
                prescription.session_type, StepType.WARMUP,
            )
            steps.append(WorkoutStep(
                step_type=StepType.WARMUP,
                duration_type=DurationType.TIME,
                duration_value=round(warmup_min, 1),
                pace_target_low=targets.pace_target_low,
                pace_target_high=targets.pace_target_high,
                hr_target_low=targets.hr_target_low,
                hr_target_high=targets.hr_target_high,
                step_notes=cue,
            ))

        # --- Main set ---
        main_steps = self._build_main_set(
            prescription, state, template, main_set_min,
        )
        steps.extend(main_steps)

        # --- Cooldown ---
        if cooldown_min > 0:
            targets = assign_targets(
                state, template.cooldown_zone, prescription.intensity_level,
            )
            cue = get_coaching_cue(
                prescription.session_type, StepType.COOLDOWN,
            )
            steps.append(WorkoutStep(
                step_type=StepType.COOLDOWN,
                duration_type=DurationType.TIME,
                duration_value=round(cooldown_min, 1),
                pace_target_low=targets.pace_target_low,
                pace_target_high=targets.pace_target_high,
                hr_target_low=targets.hr_target_low,
                hr_target_high=targets.hr_target_high,
                step_notes=cue,
            ))

        # --- Fueling ---
        steps = insert_fueling_steps(
            steps, total_duration, prescription.session_type,
        )

        # --- Description ---
        title, description = build_workout_description(
            prescription, state, trace,
        )
        decision_summary = build_decision_summary(trace)

        return StructuredWorkout(
            prescription=prescription,
            steps=tuple(steps),
            workout_title=title,
            workout_description=description,
            total_duration_min=total_duration,
            total_distance_km=prescription.target_distance_km,
            decision_summary=decision_summary,
        )

    def _build_rest(
        self,
        prescription: WorkoutPrescription,
        state: AthleteState,
        trace: DecisionTrace,
    ) -> StructuredWorkout:
        """Build a rest-day structured workout."""
        cue = get_coaching_cue(SessionType.REST, StepType.REST)
        step = WorkoutStep(
            step_type=StepType.REST,
            duration_type=DurationType.TIME,
            duration_value=0.0,
            step_notes=cue,
        )
        title, description = build_workout_description(
            prescription, state, trace,
        )
        return StructuredWorkout(
            prescription=prescription,
            steps=(step,),
            workout_title=title,
            workout_description=description,
            total_duration_min=0.0,
            decision_summary=build_decision_summary(trace),
        )

    def _build_main_set(
        self,
        prescription: WorkoutPrescription,
        state: AthleteState,
        template,
        main_set_min: float,
    ) -> list[WorkoutStep]:
        """Build main-set steps from template segments."""
        steps: list[WorkoutStep] = []
        session_type = prescription.session_type
        intensity = prescription.intensity_level

        for i, segment in enumerate(template.main_segments):
            if segment.is_repeat:
                # Interval repeat block
                rep_step = self._build_repeat_block(
                    state, segment, main_set_min, session_type, intensity,
                )
                steps.append(rep_step)
            elif segment.fraction_of_main > 0:
                # Split main set (e.g. LONG_RUN: 80% Z2, 20% Z3)
                segment_min = round(main_set_min * segment.fraction_of_main, 1)
                if segment_min <= 0:
                    continue
                is_late = i > 0  # Second+ segment is the "late" segment
                targets = assign_targets(
                    state, segment.zone, intensity, session_type,
                )
                cue = get_coaching_cue(
                    session_type, StepType.ACTIVE, is_late_segment=is_late,
                )
                steps.append(WorkoutStep(
                    step_type=StepType.ACTIVE,
                    duration_type=DurationType.TIME,
                    duration_value=segment_min,
                    pace_target_low=targets.pace_target_low,
                    pace_target_high=targets.pace_target_high,
                    hr_target_low=targets.hr_target_low,
                    hr_target_high=targets.hr_target_high,
                    step_notes=cue,
                ))
            else:
                # Single steady-state main set (uses all remaining time)
                targets = assign_targets(
                    state, segment.zone, intensity, session_type,
                )
                cue = get_coaching_cue(
                    session_type, StepType.ACTIVE,
                )
                steps.append(WorkoutStep(
                    step_type=StepType.ACTIVE,
                    duration_type=DurationType.TIME,
                    duration_value=round(main_set_min, 1),
                    pace_target_low=targets.pace_target_low,
                    pace_target_high=targets.pace_target_high,
                    hr_target_low=targets.hr_target_low,
                    hr_target_high=targets.hr_target_high,
                    step_notes=cue,
                ))

        return steps

    def _build_repeat_block(
        self,
        state: AthleteState,
        segment,
        main_set_min: float,
        session_type: SessionType,
        intensity,
    ) -> WorkoutStep:
        """Build a REPEAT block with work + recovery child steps."""
        rep_cycle = segment.rep_work_min + segment.rep_recovery_min
        rep_count = max(1, int(main_set_min // rep_cycle))

        # Work step
        work_targets = assign_targets(
            state, segment.zone, intensity, session_type,
        )
        work_cue = get_coaching_cue(session_type, StepType.ACTIVE)
        work_step = WorkoutStep(
            step_type=StepType.ACTIVE,
            duration_type=DurationType.TIME,
            duration_value=segment.rep_work_min,
            pace_target_low=work_targets.pace_target_low,
            pace_target_high=work_targets.pace_target_high,
            hr_target_low=work_targets.hr_target_low,
            hr_target_high=work_targets.hr_target_high,
            step_notes=work_cue,
        )

        # Recovery step
        recovery_targets = assign_targets(
            state, ZoneType.ZONE_1, intensity,
        )
        recovery_cue = get_coaching_cue(session_type, StepType.RECOVERY)
        recovery_step = WorkoutStep(
            step_type=StepType.RECOVERY,
            duration_type=DurationType.TIME,
            duration_value=segment.rep_recovery_min,
            pace_target_low=recovery_targets.pace_target_low,
            pace_target_high=recovery_targets.pace_target_high,
            hr_target_low=recovery_targets.hr_target_low,
            hr_target_high=recovery_targets.hr_target_high,
            step_notes=recovery_cue,
        )

        return WorkoutStep(
            step_type=StepType.REPEAT,
            repeat_count=rep_count,
            child_steps=(work_step, recovery_step),
            step_notes=f"{rep_count}x ({segment.rep_work_min:.0f}min work + {segment.rep_recovery_min:.0f}min recovery)",
        )
