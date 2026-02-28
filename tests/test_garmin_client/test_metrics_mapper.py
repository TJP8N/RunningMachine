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
    _set_lt_pace,
    map_daily_metrics,
    map_profile,
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


# ---------------------------------------------------------------------------
# _set_lt_pace
# ---------------------------------------------------------------------------


class TestSetLtPace:
    def test_normal_speed(self):
        result = {}
        _set_lt_pace(result, 4.0)  # 4:10/km
        assert result["lthr_pace_min"] == 4
        assert result["lthr_pace_sec"] == 10

    def test_speed_needs_10x_correction(self):
        # Garmin stores 0.394 instead of 3.94 m/s
        result = {}
        _set_lt_pace(result, 0.39444334)
        # 3.9444 m/s → 253.5 s/km → 4:13/km
        assert result["lthr_pace_min"] == 4
        assert result["lthr_pace_sec"] == 13

    def test_zero_speed(self):
        result = {}
        _set_lt_pace(result, 0.0)
        assert "lthr_pace_min" not in result

    def test_negative_speed(self):
        result = {}
        _set_lt_pace(result, -1.0)
        assert "lthr_pace_min" not in result

    def test_mms_speed(self):
        # 3944 mm/s = 3.944 m/s → 4:13/km
        result = {}
        _set_lt_pace(result, 3944.0)
        assert result["lthr_pace_min"] == 4
        assert result["lthr_pace_sec"] == 13


# ---------------------------------------------------------------------------
# map_profile — using actual Garmin API response structures
# ---------------------------------------------------------------------------


class TestMapProfile:
    @pytest.fixture
    def real_garmin_profile(self):
        """Profile data matching actual Garmin API responses."""
        return {
            "user_settings": {
                "id": 12345,
                "userData": {
                    "gender": "MALE",
                    "weight": 82580.0,
                    "height": 185.42,
                    "birthDate": "1995-11-27",
                    "lactateThresholdHeartRate": 166,
                    "lactateThresholdSpeed": 0.39444334,
                },
            },
            "user_profile": {
                "displayName": "testuser123",
                "preferredLocale": "en",
            },
            "body_composition": {
                "totalAverage": {"weight": None},
            },
            "max_metrics": [],
            "resting_hr": {
                "allMetrics": {
                    "metricsMap": {
                        "WELLNESS_RESTING_HEART_RATE": [
                            {"value": 38.0, "calendarDate": "2026-02-28"}
                        ],
                    },
                },
            },
            "lactate_threshold": {
                "speed_and_heart_rate": {
                    "speed": 0.39444334,
                    "heartRate": 166,
                },
            },
            "recent_activities": [],
            "training_readiness": [{"score": 85}],
            "hrv": {
                "hrvSummary": {
                    "weeklyAvg": 91,
                    "lastNightAvg": 104,
                },
            },
            "sleep": {
                "dailySleepDTO": {
                    "sleepScores": {
                        "overall": {"value": 75},
                    },
                },
            },
            "body_battery": [
                {
                    "charged": 65,
                    "bodyBatteryValuesArray": [
                        [1000, 30],
                        [2000, 95],
                    ],
                },
            ],
            "stats": {
                "restingHeartRate": 38,
                "lastSevenDaysAvgRestingHeartRate": 41,
            },
        }

    def test_sex_from_user_settings(self, real_garmin_profile):
        result = map_profile(real_garmin_profile)
        assert result["sex"] == "M"

    def test_age_from_user_settings(self, real_garmin_profile):
        result = map_profile(real_garmin_profile)
        assert result["age"] == 30

    def test_weight_from_user_settings_grams(self, real_garmin_profile):
        result = map_profile(real_garmin_profile)
        assert result["weight_kg"] == 82.6

    def test_name_skips_display_name(self, real_garmin_profile):
        result = map_profile(real_garmin_profile)
        # displayName is a username — should NOT be used as name
        assert "name" not in result

    def test_name_uses_real_name_when_available(self, real_garmin_profile):
        real_garmin_profile["user_profile"]["firstName"] = "John"
        real_garmin_profile["user_profile"]["lastName"] = "Doe"
        result = map_profile(real_garmin_profile)
        assert result["name"] == "John Doe"

    def test_max_hr_estimated_from_age(self, real_garmin_profile):
        # Tanaka: 208 - 0.7 * 30 = 187
        result = map_profile(real_garmin_profile)
        assert result["max_hr"] == 187

    def test_resting_hr_from_rhr_endpoint(self, real_garmin_profile):
        result = map_profile(real_garmin_profile)
        assert result["resting_hr"] == 38

    def test_resting_hr_fallback_to_stats(self):
        raw = {
            "resting_hr": None,
            "stats": {"lastSevenDaysAvgRestingHeartRate": 41},
        }
        result = map_profile(raw)
        assert result["resting_hr"] == 41

    def test_lthr_from_lactate_threshold_endpoint(self, real_garmin_profile):
        result = map_profile(real_garmin_profile)
        assert result["lthr_bpm"] == 166

    def test_lthr_pace_corrected_scaling(self, real_garmin_profile):
        result = map_profile(real_garmin_profile)
        # 0.394 * 10 = 3.94 m/s → 253.5 s/km → 4:13
        assert result["lthr_pace_min"] == 4
        assert result["lthr_pace_sec"] == 13

    def test_lthr_fallback_to_settings(self):
        raw = {
            "user_settings": {
                "userData": {
                    "lactateThresholdHeartRate": 170,
                    "lactateThresholdSpeed": 0.4,
                },
            },
            "lactate_threshold": {},
        }
        result = map_profile(raw)
        assert result["lthr_bpm"] == 170
        assert result["lthr_pace_min"] == 4
        assert result["lthr_pace_sec"] == 10

    def test_avg_weekly_km_zero_when_no_activities(self, real_garmin_profile):
        result = map_profile(real_garmin_profile)
        assert result["avg_weekly_km"] == 0.0

    def test_avg_weekly_km_from_activities(self, real_garmin_profile):
        real_garmin_profile["recent_activities"] = [
            {"distance": 10000},  # 10 km in meters
            {"distance": 8000},   # 8 km
            {"distance": 12000},  # 12 km
        ]
        result = map_profile(real_garmin_profile)
        # 30 km total / 6 weeks = 5.0
        assert result["avg_weekly_km"] == 5.0

    def test_readiness_metrics_extracted(self, real_garmin_profile):
        result = map_profile(real_garmin_profile)
        assert result["hrv_rmssd"] == 104
        assert result["hrv_baseline"] == 91
        assert result["sleep_score"] == 75.0
        assert result["body_battery"] == 95

    def test_vo2max_when_available(self):
        raw = {
            "max_metrics": [{"generic": {"vo2MaxPreciseValue": 52.3}}],
        }
        result = map_profile(raw)
        assert result["vo2max"] == 52.3

    def test_bounds_filter_out_of_range(self):
        raw = {
            "user_settings": {
                "userData": {"weight": 15000.0},  # 15 kg — below 30 min
            },
        }
        result = map_profile(raw)
        assert "weight_kg" not in result

    def test_empty_raw(self):
        result = map_profile({})
        assert result == {}
