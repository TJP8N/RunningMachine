"""Tests for TrainingDebtRule (DRIVE tier) and training debt model functions."""

from __future__ import annotations

import math

import pytest

from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    DEBT_HALF_LIFE_WEEKS,
    DEBT_WRITE_OFF_WEEKS,
    MAX_DEBT_DURATION_EXTENSION_MIN,
    Priority,
    ReadinessLevel,
    SessionType,
    TrainingPhase,
)
from science_engine.models.training_debt import (
    DebtEntry,
    TrainingDebtLedger,
    apply_debt_decay,
    debt_by_session_type,
    total_effective_debt,
)
from science_engine.models.weekly_plan import WeekContext
from science_engine.rules.drive.training_debt import TrainingDebtRule


def _make_state(
    debt: TrainingDebtLedger | None = None,
    readiness: ReadinessLevel = ReadinessLevel.NORMAL,
) -> AthleteState:
    return AthleteState(
        name="Test",
        age=30,
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
        daily_loads=tuple([50.0] * 28),
        weekly_volume_history=(40.0, 42.0, 44.0),
        training_debt=debt,
        readiness=readiness,
    )


# ---------------------------------------------------------------------------
# Tests for debt math functions
# ---------------------------------------------------------------------------


class TestDebtDecay:
    def test_current_week_no_decay(self) -> None:
        entry = DebtEntry(session_type=SessionType.TEMPO, missed_duration_min=60.0, weeks_ago=0)
        assert apply_debt_decay(entry) == pytest.approx(60.0)

    def test_half_life_decay(self) -> None:
        entry = DebtEntry(
            session_type=SessionType.TEMPO,
            missed_duration_min=60.0,
            weeks_ago=DEBT_HALF_LIFE_WEEKS,
        )
        assert apply_debt_decay(entry) == pytest.approx(30.0)

    def test_write_off(self) -> None:
        entry = DebtEntry(
            session_type=SessionType.TEMPO,
            missed_duration_min=60.0,
            weeks_ago=DEBT_WRITE_OFF_WEEKS,
        )
        assert apply_debt_decay(entry) == 0.0

    def test_total_effective_debt(self) -> None:
        ledger = TrainingDebtLedger(entries=(
            DebtEntry(session_type=SessionType.TEMPO, missed_duration_min=60.0, weeks_ago=0),
            DebtEntry(session_type=SessionType.LONG_RUN, missed_duration_min=40.0, weeks_ago=DEBT_HALF_LIFE_WEEKS),
        ))
        total = total_effective_debt(ledger)
        assert total == pytest.approx(60.0 + 20.0)

    def test_debt_by_session_type(self) -> None:
        ledger = TrainingDebtLedger(entries=(
            DebtEntry(session_type=SessionType.TEMPO, missed_duration_min=60.0, weeks_ago=0),
            DebtEntry(session_type=SessionType.TEMPO, missed_duration_min=30.0, weeks_ago=0),
            DebtEntry(session_type=SessionType.LONG_RUN, missed_duration_min=40.0, weeks_ago=0),
        ))
        by_type = debt_by_session_type(ledger)
        assert by_type[SessionType.TEMPO] == pytest.approx(90.0)
        assert by_type[SessionType.LONG_RUN] == pytest.approx(40.0)

    def test_empty_ledger(self) -> None:
        ledger = TrainingDebtLedger()
        assert ledger.is_empty
        assert total_effective_debt(ledger) == 0.0


# ---------------------------------------------------------------------------
# Tests for TrainingDebtRule
# ---------------------------------------------------------------------------


class TestTrainingDebtRule:
    def setup_method(self) -> None:
        self.rule = TrainingDebtRule()

    def test_rule_metadata(self) -> None:
        assert self.rule.priority == Priority.DRIVE
        assert self.rule.is_weekly_aware is True

    def test_no_recommendation_without_debt(self) -> None:
        state = _make_state(debt=None)
        # has_required_data should fail since training_debt is None
        assert not self.rule.has_required_data(state)

    def test_no_recommendation_empty_ledger(self) -> None:
        state = _make_state(debt=TrainingDebtLedger())
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_recommends_when_debt_present(self) -> None:
        ledger = TrainingDebtLedger(entries=(
            DebtEntry(session_type=SessionType.TEMPO, missed_duration_min=60.0, weeks_ago=0),
        ))
        state = _make_state(debt=ledger)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.priority == Priority.DRIVE
        assert rec.recommended_session_type == SessionType.TEMPO

    def test_volume_modifier_capped(self) -> None:
        """Even with huge debt, volume modifier should be capped."""
        ledger = TrainingDebtLedger(entries=(
            DebtEntry(session_type=SessionType.TEMPO, missed_duration_min=300.0, weeks_ago=0),
        ))
        state = _make_state(debt=ledger)
        rec = self.rule.evaluate(state)
        assert rec is not None
        assert rec.volume_modifier <= 1.35

    def test_skips_recovery_week(self) -> None:
        ledger = TrainingDebtLedger(entries=(
            DebtEntry(session_type=SessionType.TEMPO, missed_duration_min=60.0, weeks_ago=0),
        ))
        state = _make_state(debt=ledger)
        context = WeekContext(day_number=2, phase=TrainingPhase.BUILD, is_recovery_week=True)
        rec = self.rule.evaluate_weekly(state, context)
        assert rec is None

    def test_skips_suppressed_readiness(self) -> None:
        ledger = TrainingDebtLedger(entries=(
            DebtEntry(session_type=SessionType.TEMPO, missed_duration_min=60.0, weeks_ago=0),
        ))
        state = _make_state(debt=ledger, readiness=ReadinessLevel.SUPPRESSED)
        rec = self.rule.evaluate(state)
        assert rec is None

    def test_trivial_debt_ignored(self) -> None:
        ledger = TrainingDebtLedger(entries=(
            DebtEntry(session_type=SessionType.EASY, missed_duration_min=3.0, weeks_ago=0),
        ))
        state = _make_state(debt=ledger)
        rec = self.rule.evaluate(state)
        assert rec is None
