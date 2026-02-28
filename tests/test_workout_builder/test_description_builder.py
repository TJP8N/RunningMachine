"""Tests for description builder — workout titles and rich descriptions."""

from __future__ import annotations

from science_engine.models.athlete_state import AthleteState
from science_engine.models.decision_trace import DecisionTrace, RuleResult, RuleStatus
from science_engine.models.enums import (
    IntensityLevel,
    ReadinessLevel,
    SessionType,
    TrainingPhase,
)
from science_engine.models.workout import WorkoutPrescription
from science_engine.workout_builder.description_builder import (
    build_decision_summary,
    build_workout_description,
)


def _make_prescription(**overrides) -> WorkoutPrescription:
    defaults = dict(
        session_type=SessionType.TEMPO,
        intensity_level=IntensityLevel.A_FULL,
        target_duration_min=50.0,
        phase=TrainingPhase.BUILD,
        week_number=8,
    )
    defaults.update(overrides)
    return WorkoutPrescription(**defaults)


def _make_state(**overrides) -> AthleteState:
    defaults = dict(
        name="Test",
        age=35,
        weight_kg=70.0,
        sex="M",
        max_hr=190,
        lthr_bpm=170,
        lthr_pace_s_per_km=300,
        vo2max=50.0,
        current_phase=TrainingPhase.BUILD,
        current_week=8,
        total_plan_weeks=16,
        day_of_week=2,
    )
    defaults.update(overrides)
    return AthleteState(**defaults)


def _make_trace(*fired_rule_ids: str) -> DecisionTrace:
    results = []
    for rule_id in fired_rule_ids:
        results.append(RuleResult(
            rule_id=rule_id,
            status=RuleStatus.FIRED,
            explanation=f"{rule_id} fired: recommends adjustment.",
        ))
    return DecisionTrace(rule_results=tuple(results))


class TestBuildWorkoutDescription:
    def test_title_format(self) -> None:
        rx = _make_prescription()
        state = _make_state()
        trace = _make_trace()
        title, _ = build_workout_description(rx, state, trace)
        assert "BUILD" in title
        assert "W8" in title
        assert "Tempo" in title
        assert "50 min" in title

    def test_description_includes_phase(self) -> None:
        rx = _make_prescription()
        state = _make_state()
        trace = _make_trace()
        _, desc = build_workout_description(rx, state, trace)
        assert "BUILD" in desc
        assert "Week 8" in desc

    def test_description_includes_acwr(self) -> None:
        rx = _make_prescription()
        state = _make_state(acwr=1.05)
        trace = _make_trace()
        _, desc = build_workout_description(rx, state, trace)
        assert "ACWR" in desc
        assert "1.05" in desc
        assert "OPTIMAL" in desc

    def test_description_includes_readiness(self) -> None:
        rx = _make_prescription()
        state = _make_state(
            hrv_rmssd=40.0, hrv_baseline=50.0,
            sleep_score=75.0, body_battery=60,
        )
        trace = _make_trace()
        _, desc = build_workout_description(rx, state, trace)
        assert "HRV ratio" in desc
        assert "Sleep" in desc
        assert "Body battery" in desc

    def test_description_includes_firing_rules(self) -> None:
        rx = _make_prescription()
        state = _make_state()
        trace = _make_trace("workout_type_selector", "progressive_overload")
        _, desc = build_workout_description(rx, state, trace)
        assert "workout_type_selector" in desc
        assert "progressive_overload" in desc


class TestBuildDecisionSummary:
    def test_summary_with_fired_rules(self) -> None:
        trace = _make_trace("workout_type_selector", "progressive_overload", "injury_risk_acwr")
        summary = build_decision_summary(trace)
        assert "workout_type_selector" in summary
        assert "progressive_overload" in summary
        # Only top 2 rules, separated by |
        assert summary.count("|") == 1
        # Third rule should not appear
        assert "injury_risk_acwr" not in summary

    def test_summary_no_rules(self) -> None:
        trace = DecisionTrace()
        summary = build_decision_summary(trace)
        assert "No rules fired" in summary
