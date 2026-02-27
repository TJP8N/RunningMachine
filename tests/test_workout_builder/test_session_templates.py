"""Tests for session templates — structural patterns for each SessionType."""

from __future__ import annotations

from science_engine.models.enums import SessionType, StepType, ZoneType
from science_engine.workout_builder.session_templates import (
    SESSION_TEMPLATES,
    SessionTemplate,
    get_template,
)


class TestSessionTemplates:
    def test_all_session_types_have_templates(self) -> None:
        """Every SessionType must have a corresponding template."""
        for st in SessionType:
            assert st in SESSION_TEMPLATES, f"Missing template for {st.name}"

    def test_get_template_returns_correct_type(self) -> None:
        template = get_template(SessionType.EASY)
        assert isinstance(template, SessionTemplate)

    def test_get_template_raises_for_unknown(self) -> None:
        """Accessing a non-existent key should raise KeyError."""
        try:
            get_template(999)  # type: ignore[arg-type]
            assert False, "Should have raised KeyError"
        except KeyError:
            pass

    def test_rest_template_has_no_warmup_cooldown(self) -> None:
        t = get_template(SessionType.REST)
        assert t.warmup_duration_min == 0
        assert t.cooldown_duration_min == 0
        assert len(t.main_segments) == 1
        assert t.main_segments[0].step_type == StepType.REST

    def test_recovery_template_is_z1_full_duration(self) -> None:
        t = get_template(SessionType.RECOVERY)
        assert t.warmup_duration_min == 0
        assert t.cooldown_duration_min == 0
        assert len(t.main_segments) == 1
        assert t.main_segments[0].zone == ZoneType.ZONE_1
        assert t.main_segments[0].step_type == StepType.ACTIVE

    def test_easy_template_structure(self) -> None:
        t = get_template(SessionType.EASY)
        assert t.warmup_duration_min == 10
        assert t.cooldown_duration_min == 5
        assert t.warmup_zone == ZoneType.ZONE_1
        assert t.cooldown_zone == ZoneType.ZONE_1
        assert len(t.main_segments) == 1
        assert t.main_segments[0].zone == ZoneType.ZONE_2

    def test_long_run_has_two_main_segments(self) -> None:
        t = get_template(SessionType.LONG_RUN)
        assert len(t.main_segments) == 2
        assert t.main_segments[0].fraction_of_main == 0.80
        assert t.main_segments[0].zone == ZoneType.ZONE_2
        assert t.main_segments[1].fraction_of_main == 0.20
        assert t.main_segments[1].zone == ZoneType.ZONE_3

    def test_threshold_is_interval(self) -> None:
        t = get_template(SessionType.THRESHOLD)
        assert t.warmup_duration_min == 15
        assert t.cooldown_duration_min == 10
        seg = t.main_segments[0]
        assert seg.is_repeat is True
        assert seg.rep_work_min == 8.0
        assert seg.rep_recovery_min == 2.0
        assert seg.zone == ZoneType.ZONE_4

    def test_vo2max_is_interval(self) -> None:
        t = get_template(SessionType.VO2MAX_INTERVALS)
        seg = t.main_segments[0]
        assert seg.is_repeat is True
        assert seg.rep_work_min == 3.0
        assert seg.rep_recovery_min == 3.0
        assert seg.zone == ZoneType.ZONE_5

    def test_quality_sessions_have_longer_warmup_cooldown(self) -> None:
        """TEMPO, THRESHOLD, VO2MAX, MP, RACE_SIM all use 15 min warmup, 10 min cooldown."""
        quality_types = [
            SessionType.TEMPO,
            SessionType.THRESHOLD,
            SessionType.VO2MAX_INTERVALS,
            SessionType.MARATHON_PACE,
            SessionType.RACE_SIMULATION,
        ]
        for st in quality_types:
            t = get_template(st)
            assert t.warmup_duration_min == 15, f"{st.name} warmup should be 15"
            assert t.cooldown_duration_min == 10, f"{st.name} cooldown should be 10"

    def test_marathon_pace_template(self) -> None:
        t = get_template(SessionType.MARATHON_PACE)
        assert len(t.main_segments) == 1
        assert t.main_segments[0].zone == ZoneType.ZONE_3
        assert t.main_segments[0].is_repeat is False

    def test_race_simulation_template(self) -> None:
        t = get_template(SessionType.RACE_SIMULATION)
        assert len(t.main_segments) == 1
        assert t.main_segments[0].zone == ZoneType.ZONE_3
