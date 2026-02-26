"""Tests for training load calculations: TRIMP, ACWR, monotony."""

from __future__ import annotations

import pytest

from science_engine.math.training_load import (
    calculate_acwr,
    calculate_ewma,
    calculate_monotony,
    calculate_trimp,
    classify_acwr,
    project_acwr_with_session,
)


class TestTRIMP:
    def test_positive_for_normal_session(self) -> None:
        trimp = calculate_trimp(
            duration_min=60, avg_hr=150, max_hr=185, resting_hr=50, sex="M"
        )
        assert trimp > 0

    def test_longer_session_higher_trimp(self) -> None:
        short = calculate_trimp(
            duration_min=30, avg_hr=150, max_hr=185, resting_hr=50, sex="M"
        )
        long = calculate_trimp(
            duration_min=60, avg_hr=150, max_hr=185, resting_hr=50, sex="M"
        )
        assert long > short

    def test_higher_hr_higher_trimp(self) -> None:
        low = calculate_trimp(
            duration_min=60, avg_hr=130, max_hr=185, resting_hr=50, sex="M"
        )
        high = calculate_trimp(
            duration_min=60, avg_hr=170, max_hr=185, resting_hr=50, sex="M"
        )
        assert high > low

    def test_zero_when_max_equals_resting(self) -> None:
        trimp = calculate_trimp(
            duration_min=60, avg_hr=100, max_hr=100, resting_hr=100, sex="M"
        )
        assert trimp == 0.0

    def test_male_vs_female_different(self) -> None:
        male = calculate_trimp(
            duration_min=60, avg_hr=150, max_hr=185, resting_hr=50, sex="M"
        )
        female = calculate_trimp(
            duration_min=60, avg_hr=150, max_hr=185, resting_hr=50, sex="F"
        )
        assert male != female


class TestEWMA:
    def test_stable_series_returns_mean(self) -> None:
        values = [50.0] * 28
        ewma = calculate_ewma(values, span=7)
        assert abs(ewma - 50.0) < 1.0

    def test_empty_returns_zero(self) -> None:
        assert calculate_ewma([], span=7) == 0.0

    def test_recent_values_weighted_more(self) -> None:
        # Series that jumps from 50 to 100 at the end
        values = [50.0] * 20 + [100.0] * 5
        ewma = calculate_ewma(values, span=7)
        # EWMA should be pulled toward 100 but not quite there
        assert 70.0 < ewma < 100.0


class TestACWR:
    def test_stable_loads_near_one(self, safe_daily_loads: tuple[float, ...]) -> None:
        acwr = calculate_acwr(list(safe_daily_loads))
        assert 0.9 <= acwr <= 1.1

    def test_spiked_loads_above_threshold(self, spiked_daily_loads: tuple[float, ...]) -> None:
        acwr = calculate_acwr(list(spiked_daily_loads))
        assert acwr > 1.3

    def test_insufficient_data_returns_zero(self) -> None:
        acwr = calculate_acwr([50.0] * 3)
        assert acwr == 0.0

    def test_no_chronic_load_returns_zero(self) -> None:
        acwr = calculate_acwr([0.0] * 28)
        assert acwr == 0.0


class TestClassifyACWR:
    def test_danger(self) -> None:
        assert classify_acwr(1.6) == "danger"

    def test_caution(self) -> None:
        assert classify_acwr(1.4) == "caution"

    def test_optimal(self) -> None:
        assert classify_acwr(1.0) == "optimal"

    def test_undertrained(self) -> None:
        assert classify_acwr(0.5) == "undertrained"

    def test_boundary_at_1_5(self) -> None:
        assert classify_acwr(1.5) == "danger"

    def test_boundary_at_1_3(self) -> None:
        assert classify_acwr(1.3) == "caution"

    def test_boundary_at_0_8(self) -> None:
        assert classify_acwr(0.8) == "optimal"


class TestMonotony:
    def test_constant_loads_zero_monotony(self) -> None:
        # Constant loads → std = 0 → monotony = 0 (guarded)
        monotony = calculate_monotony([50.0] * 7)
        assert monotony == 0.0

    def test_varied_loads_nonzero(self) -> None:
        loads = [30.0, 60.0, 0.0, 70.0, 30.0, 50.0, 90.0]
        monotony = calculate_monotony(loads)
        assert monotony > 0

    def test_insufficient_data(self) -> None:
        assert calculate_monotony([50.0] * 3) == 0.0


class TestProjectACWR:
    def test_adding_high_load_increases_acwr(self, safe_daily_loads: tuple[float, ...]) -> None:
        current = calculate_acwr(list(safe_daily_loads))
        projected = project_acwr_with_session(list(safe_daily_loads), 200.0)
        assert projected > current
