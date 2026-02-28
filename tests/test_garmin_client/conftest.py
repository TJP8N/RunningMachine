"""Fixtures with realistic Garmin API response dicts for testing."""

from __future__ import annotations

import pytest


@pytest.fixture
def garmin_hrv_data() -> dict:
    """Realistic Garmin HRV API response."""
    return {
        "hrvSummary": {
            "calendarDate": "2025-01-15",
            "weeklyAvg": 52.0,
            "lastNight": 48.0,
            "lastNightAvg": 48.0,
            "lastNight5MinHigh": 65.0,
            "baseline": {
                "lowUpper": 40,
                "balancedLow": 45,
                "balancedUpper": 60,
                "markerValue": None,
            },
            "status": "BALANCED",
            "startTimestampGMT": 1705276800000,
            "endTimestampGMT": 1705305600000,
            "startTimestampLocal": 1705258800000,
            "endTimestampLocal": 1705287600000,
        },
        "hrvReadings": [
            {"readingTimeGMT": "2025-01-15T02:00:00.0", "hrvValue": 45},
            {"readingTimeGMT": "2025-01-15T03:00:00.0", "hrvValue": 50},
            {"readingTimeGMT": "2025-01-15T04:00:00.0", "hrvValue": 48},
        ],
    }


@pytest.fixture
def garmin_sleep_data() -> dict:
    """Realistic Garmin sleep API response."""
    return {
        "dailySleepDTO": {
            "calendarDate": "2025-01-15",
            "sleepTimeSeconds": 27000,  # 7.5 hours
            "sleepStartTimestampGMT": 1705276800000,
            "sleepEndTimestampGMT": 1705305600000,
            "unmeasurableSleepSeconds": 0,
            "deepSleepSeconds": 5400,
            "lightSleepSeconds": 14400,
            "remSleepSeconds": 5400,
            "awakeSleepSeconds": 1800,
            "sleepScores": {
                "overall": {"value": 82.0, "qualifierKey": "GOOD"},
                "totalDuration": {"value": 75.0, "qualifierKey": "GOOD"},
                "stress": {"value": 85.0, "qualifierKey": "GOOD"},
                "awakeCount": {"value": 90.0, "qualifierKey": "EXCELLENT"},
                "remPercentage": {"value": 70.0, "qualifierKey": "FAIR"},
                "restlessness": {"value": 80.0, "qualifierKey": "GOOD"},
                "lightPercentage": {"value": 65.0, "qualifierKey": "FAIR"},
                "deepPercentage": {"value": 88.0, "qualifierKey": "GOOD"},
            },
        }
    }


@pytest.fixture
def garmin_body_battery_data() -> dict:
    """Realistic Garmin body battery API response."""
    return {
        "bodyBatteryValuesArray": [
            [1705276800000, 85, 85, 0, "MEASURED"],
            [1705280400000, 90, 5, 0, "MEASURED"],
            [1705284000000, 78, 0, 12, "MEASURED"],
            [1705287600000, 65, 0, 13, "MEASURED"],
        ]
    }


@pytest.fixture
def garmin_max_metrics_data() -> list:
    """Realistic Garmin max metrics API response."""
    return [
        {
            "calendarDate": "2025-01-15",
            "generic": {
                "vo2MaxPreciseValue": 48.5,
                "fitnessAge": 32,
                "fitnessAgeDescription": "EXCELLENT",
            },
            "cycling": None,
        }
    ]


@pytest.fixture
def garmin_stats_data() -> dict:
    """Realistic Garmin daily stats API response."""
    return {
        "calendarDate": "2025-01-15",
        "totalSteps": 12345,
        "restingHeartRate": 52,
        "maxHeartRate": 178,
        "minHeartRate": 48,
        "averageStressLevel": 35,
        "highlyActiveSeconds": 3600,
    }


@pytest.fixture
def garmin_training_readiness_data() -> list:
    """Realistic Garmin Training Readiness API response."""
    return [
        {
            "calendarDate": "2025-01-15",
            "score": 72.0,
            "level": "MODERATE",
            "sleepScore": 80,
            "recoveryScore": 65,
            "activityHistoryScore": 70,
        }
    ]


@pytest.fixture
def garmin_full_metrics(
    garmin_hrv_data,
    garmin_sleep_data,
    garmin_body_battery_data,
    garmin_max_metrics_data,
    garmin_stats_data,
    garmin_training_readiness_data,
) -> dict:
    """Full pull_daily_metrics() return value with all endpoints populated."""
    return {
        "training_readiness": garmin_training_readiness_data,
        "hrv": garmin_hrv_data,
        "body_battery": garmin_body_battery_data,
        "sleep": garmin_sleep_data,
        "stress": {"overall": 35},
        "max_metrics": garmin_max_metrics_data,
        "stats": garmin_stats_data,
    }
