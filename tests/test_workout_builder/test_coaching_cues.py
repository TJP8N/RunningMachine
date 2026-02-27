"""Tests for coaching cues — per-step coaching notes with RPE guidance."""

from __future__ import annotations

from science_engine.models.enums import SessionType, StepType
from science_engine.workout_builder.coaching_cues import get_coaching_cue


class TestCoachingCues:
    def test_warmup_cue_for_any_session(self) -> None:
        cue = get_coaching_cue(SessionType.EASY, StepType.WARMUP)
        assert "warm" in cue.lower() or "jog" in cue.lower() or "activate" in cue.lower()

    def test_cooldown_cue_for_any_session(self) -> None:
        cue = get_coaching_cue(SessionType.TEMPO, StepType.COOLDOWN)
        assert "cool" in cue.lower() or "gentle" in cue.lower() or "hr" in cue.lower()

    def test_easy_active_includes_rpe(self) -> None:
        cue = get_coaching_cue(SessionType.EASY, StepType.ACTIVE)
        assert "RPE" in cue

    def test_tempo_active_includes_rpe(self) -> None:
        cue = get_coaching_cue(SessionType.TEMPO, StepType.ACTIVE)
        assert "RPE" in cue

    def test_threshold_active_includes_rpe(self) -> None:
        cue = get_coaching_cue(SessionType.THRESHOLD, StepType.ACTIVE)
        assert "RPE" in cue

    def test_vo2max_active_includes_rpe(self) -> None:
        cue = get_coaching_cue(SessionType.VO2MAX_INTERVALS, StepType.ACTIVE)
        assert "RPE" in cue

    def test_marathon_pace_mentions_fueling(self) -> None:
        cue = get_coaching_cue(SessionType.MARATHON_PACE, StepType.ACTIVE)
        assert "fueling" in cue.lower() or "race pace" in cue.lower()

    def test_long_run_late_segment_different(self) -> None:
        early = get_coaching_cue(SessionType.LONG_RUN, StepType.ACTIVE, is_late_segment=False)
        late = get_coaching_cue(SessionType.LONG_RUN, StepType.ACTIVE, is_late_segment=True)
        assert early != late
        assert "fatigue" in late.lower() or "18-22" in late

    def test_all_running_session_types_have_active_cue(self) -> None:
        """Every running session type should return a non-empty cue for ACTIVE steps."""
        running_types = [
            st for st in SessionType if st != SessionType.REST
        ]
        for st in running_types:
            cue = get_coaching_cue(st, StepType.ACTIVE)
            assert cue != "", f"Missing ACTIVE cue for {st.name}"

    def test_recovery_step_cue(self) -> None:
        cue = get_coaching_cue(SessionType.THRESHOLD, StepType.RECOVERY)
        assert "recovery" in cue.lower() or "easy" in cue.lower()
