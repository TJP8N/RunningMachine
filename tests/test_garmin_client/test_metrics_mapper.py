"""Tests for garmin_client.metrics_mapper — pure functions, no mocking needed."""

from __future__ import annotations

import pytest

from garmin_client.metrics_mapper import (
    _extract_body_battery,
    _extract_hrv,
    _extract_readiness,
    _extract_resting_hr,
    _extract_sleep_score,
    _extract_vo2max,
    map_daily_metrics,
)
from science_engine.models.enums import ReadinessLevel


# ---------------------------------------------------------------------------
# _extract_hrv
# ---------------------------------------------------------------------------


class TestExtractHrv:
    def test_correct_values(self, garmin_hrv_data):
        rmssd, baseline = _extract_hrv(garmin_hrv_data)
        assert rmssd == 48.0
        assert baseline == 52.0

    def test_missing_summary(self):
        rmssd, baseline = _extract_hrv({"someOtherKey": 1})
        assert rmssd is None
        assert baseline is None

    def test_none_input(self):
        rmssd, baseline = _extract_hrv(None)
        assert rmssd is None
        assert baseline is None

    def test_empty_dict(self):
        rmssd, baseline = _extract_hrv({})
        assert rmssd is None
        assert baseline is None

    def test_partial_summary(self):
        data = {"hrvSummary": {"lastNightAvg": 55.0}}
        rmssd, baseline = _extract_hrv(data)
        assert rmssd == 55.0
        assert baseline is None


# ---------------------------------------------------------------------------
# _extract_sleep_score
# ---------------------------------------------------------------------------


class TestExtractSleepScore:
    def test_correct_value(self, garmin_sleep_data):
        score = _extract_sleep_score(garmin_sleep_data)
        assert score == 82.0

    def test_missing_daily_sleep_dto(self):
        assert _extract_sleep_score({"other": 1}) is None

    def test_missing_sleep_scores(self):
        assert _extract_sleep_score({"dailySleepDTO": {}}) is None

    def test_missing_overall(self):
        data = {"dailySleepDTO": {"sleepScores": {}}}
        assert _extract_sleep_score(data) is None

    def test_missing_value(self):
        data = {"dailySleepDTO": {"sleepScores": {"overall": {}}}}
        assert _extract_sleep_score(data) is None

    def test_none_input(self):
        assert _extract_sleep_score(None) is None


# ---------------------------------------------------------------------------
# _extract_body_battery
# ---------------------------------------------------------------------------


class TestExtractBodyBattery:
    def test_morning_peak(self, garmin_body_battery_data):
        bb = _extract_body_battery(garmin_body_battery_data)
        # Max charged value from array: 90
        assert bb == 90

    def test_empty_list(self):
        assert _extract_body_battery({"bodyBatteryValuesArray": []}) is None

    def test_none_input(self):
        assert _extract_body_battery(None) is None

    def test_dict_entries(self):
        data = [
            {"charged": 70},
            {"charged": 85},
            {"charged": 60},
        ]
        assert _extract_body_battery(data) == 85

    def test_list_entries(self):
        data = {"bodyBatteryValuesArray": [[0, 50], [1, 75], [2, 60]]}
        assert _extract_body_battery(data) == 75


# ---------------------------------------------------------------------------
# _extract_vo2max
# ---------------------------------------------------------------------------


class TestExtractVo2max:
    def test_precise_value(self, garmin_max_metrics_data):
        assert _extract_vo2max(garmin_max_metrics_data) == 48.5

    def test_missing_generic(self):
        assert _extract_vo2max([{"calendarDate": "2025-01-15"}]) is None

    def test_none_input(self):
        assert _extract_vo2max(None) is None

    def test_empty_list(self):
        assert _extract_vo2max([]) is None

    def test_dict_input(self):
        data = {"generic": {"vo2MaxPreciseValue": 55.2}}
        assert _extract_vo2max(data) == 55.2


# ---------------------------------------------------------------------------
# _extract_resting_hr
# ---------------------------------------------------------------------------


class TestExtractRestingHr:
    def test_from_stats(self, garmin_stats_data):
        assert _extract_resting_hr(garmin_stats_data) == 52

    def test_none_input(self):
        assert _extract_resting_hr(None) is None

    def test_missing_key(self):
        assert _extract_resting_hr({"totalSteps": 10000}) is None


# ---------------------------------------------------------------------------
# _extract_readiness
# ---------------------------------------------------------------------------


class TestExtractReadiness:
    def test_elevated(self):
        assert _extract_readiness([{"score": 80}]) == ReadinessLevel.ELEVATED

    def test_normal(self):
        assert _extract_readiness([{"score": 60}]) == ReadinessLevel.NORMAL

    def test_suppressed(self):
        assert _extract_readiness([{"score": 30}]) == ReadinessLevel.SUPPRESSED

    def test_very_suppressed(self):
        assert _extract_readiness([{"score": 10}]) == ReadinessLevel.VERY_SUPPRESSED

    # Boundary tests
    def test_boundary_75(self):
        assert _extract_readiness([{"score": 75}]) == ReadinessLevel.ELEVATED

    def test_boundary_50(self):
        assert _extract_readiness([{"score": 50}]) == ReadinessLevel.NORMAL

    def test_boundary_25(self):
        assert _extract_readiness([{"score": 25}]) == ReadinessLevel.SUPPRESSED

    def test_boundary_24(self):
        assert _extract_readiness([{"score": 24}]) == ReadinessLevel.VERY_SUPPRESSED

    def test_none_input(self):
        assert _extract_readiness(None) is None

    def test_empty_list(self):
        assert _extract_readiness([]) is None

    def test_missing_score(self):
        assert _extract_readiness([{"level": "HIGH"}]) is None

    def test_readiness_score_key(self):
        assert _extract_readiness([{"readinessScore": 55}]) == ReadinessLevel.NORMAL


# ---------------------------------------------------------------------------
# map_daily_metrics (integration of all extractors)
# ---------------------------------------------------------------------------


class TestMapDailyMetrics:
    def test_full_mapping(self, garmin_full_metrics):
        result = map_daily_metrics(garmin_full_metrics)
        assert result["hrv_rmssd"] == 48.0
        assert result["hrv_baseline"] == 52.0
        assert result["sleep_score"] == 82.0
        assert result["body_battery"] == 90
        assert result["resting_hr"] == 52
        assert result["vo2max"] == 48.5
        assert result["readiness"] == ReadinessLevel.NORMAL  # score=72

    def test_partial_data(self):
        raw = {
            "hrv": None,
            "sleep": None,
            "body_battery": None,
            "stats": {"restingHeartRate": 55},
            "max_metrics": None,
            "training_readiness": None,
        }
        result = map_daily_metrics(raw)
        assert result["hrv_rmssd"] is None
        assert result["sleep_score"] is None
        assert result["body_battery"] is None
        assert result["resting_hr"] == 55
        assert result["vo2max"] is None
        assert result["readiness"] is None

    def test_empty_dict(self):
        result = map_daily_metrics({})
        assert all(v is None for v in result.values())

    def test_all_keys_present(self, garmin_full_metrics):
        result = map_daily_metrics(garmin_full_metrics)
        expected_keys = {
            "hrv_rmssd", "hrv_baseline", "sleep_score",
            "body_battery", "resting_hr", "vo2max", "readiness",
        }
        assert set(result.keys()) == expected_keys
