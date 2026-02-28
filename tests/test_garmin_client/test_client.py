"""Tests for garmin_client.client — mock-based, no real network calls."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from garmin_client.client import GarminClient
from garmin_client.exceptions import GarminAPIError, GarminRateLimitError


@pytest.fixture
def mock_garmin():
    """Create a mock Garmin instance."""
    mock = MagicMock()
    mock.garth = MagicMock()
    return mock


@pytest.fixture
def client(mock_garmin):
    """Create a GarminClient with a mocked Garmin session."""
    with patch("garmin_client.client.create_session", return_value=mock_garmin):
        c = GarminClient(email="test@test.com", password="pass")
    return c


# ---------------------------------------------------------------------------
# upload_workout
# ---------------------------------------------------------------------------


class TestUploadWorkout:
    def test_returns_workout_id(self, client, mock_garmin):
        mock_garmin.add_workout.return_value = {"workoutId": 12345}
        wid = client.upload_workout({"workoutName": "Test"})
        assert wid == 12345
        mock_garmin.add_workout.assert_called_once_with({"workoutName": "Test"})

    def test_raises_on_unexpected_response(self, client, mock_garmin):
        mock_garmin.add_workout.return_value = {"error": "bad"}
        with pytest.raises(GarminAPIError, match="Unexpected upload response"):
            client.upload_workout({"workoutName": "Test"})

    def test_raises_on_api_error(self, client, mock_garmin):
        exc = Exception("Server error")
        exc.status = 500
        mock_garmin.add_workout.side_effect = exc
        with pytest.raises(GarminAPIError):
            client.upload_workout({"workoutName": "Test"})


# ---------------------------------------------------------------------------
# schedule_workout
# ---------------------------------------------------------------------------


class TestScheduleWorkout:
    def test_calls_garth_post(self, client, mock_garmin):
        client.schedule_workout(12345, date(2025, 3, 10))
        mock_garmin.garth.post.assert_called_once_with(
            "connectapi",
            "/workout-service/schedule/12345",
            json={"date": "2025-03-10"},
            api=True,
        )


# ---------------------------------------------------------------------------
# upload_and_schedule
# ---------------------------------------------------------------------------


class TestUploadAndSchedule:
    def test_combines_upload_and_schedule(self, client, mock_garmin):
        mock_garmin.add_workout.return_value = {"workoutId": 99}
        wid = client.upload_and_schedule({"workoutName": "X"}, date(2025, 3, 10))
        assert wid == 99
        mock_garmin.add_workout.assert_called_once()
        mock_garmin.garth.post.assert_called_once()


# ---------------------------------------------------------------------------
# upload_week
# ---------------------------------------------------------------------------


class TestUploadWeek:
    def test_uploads_7_days(self, client, mock_garmin):
        mock_garmin.add_workout.side_effect = [
            {"workoutId": i} for i in range(7)
        ]
        jsons = [{"workoutName": f"Day {i}"} for i in range(7)]
        ids = client.upload_week(jsons, date(2025, 3, 10))
        assert ids == [0, 1, 2, 3, 4, 5, 6]
        assert mock_garmin.add_workout.call_count == 7
        assert mock_garmin.garth.post.call_count == 7


# ---------------------------------------------------------------------------
# pull_daily_metrics
# ---------------------------------------------------------------------------


class TestPullDailyMetrics:
    def test_calls_all_endpoints(self, client, mock_garmin):
        mock_garmin.get_training_readiness.return_value = [{"score": 70}]
        mock_garmin.get_hrv_data.return_value = {"hrvSummary": {}}
        mock_garmin.get_body_battery.return_value = []
        mock_garmin.get_sleep_data.return_value = {}
        mock_garmin.get_stress_data.return_value = {}
        mock_garmin.get_max_metrics.return_value = []
        mock_garmin.get_stats.return_value = {}

        result = client.pull_daily_metrics(date(2025, 1, 15))

        assert "training_readiness" in result
        assert "hrv" in result
        assert "body_battery" in result
        assert "sleep" in result
        assert "stress" in result
        assert "max_metrics" in result
        assert "stats" in result

    def test_handles_partial_failures(self, client, mock_garmin):
        mock_garmin.get_training_readiness.side_effect = Exception("fail")
        mock_garmin.get_hrv_data.return_value = {"hrvSummary": {"lastNightAvg": 50}}
        mock_garmin.get_body_battery.side_effect = Exception("fail")
        mock_garmin.get_sleep_data.return_value = {}
        mock_garmin.get_stress_data.return_value = {}
        mock_garmin.get_max_metrics.return_value = []
        mock_garmin.get_stats.return_value = {}

        result = client.pull_daily_metrics(date(2025, 1, 15))
        assert result["training_readiness"] is None  # failed
        assert result["hrv"] is not None  # succeeded
        assert result["body_battery"] is None  # failed


# ---------------------------------------------------------------------------
# Retry on 429
# ---------------------------------------------------------------------------


class TestRetryLogic:
    @patch("garmin_client.client.time.sleep")
    def test_retries_on_429(self, mock_sleep, client, mock_garmin):
        exc_429 = Exception("rate limited")
        exc_429.status = 429
        mock_garmin.add_workout.side_effect = [
            exc_429,
            exc_429,
            {"workoutId": 42},
        ]
        wid = client.upload_workout({"workoutName": "Retry Test"})
        assert wid == 42
        assert mock_sleep.call_count == 2

    @patch("garmin_client.client.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep, client, mock_garmin):
        exc_429 = Exception("rate limited")
        exc_429.status = 429
        mock_garmin.add_workout.side_effect = [exc_429] * 3
        with pytest.raises(GarminRateLimitError):
            client.upload_workout({"workoutName": "Fail"})


# ---------------------------------------------------------------------------
# get_workouts / delete_workout
# ---------------------------------------------------------------------------


class TestWorkoutOps:
    def test_get_workouts(self, client, mock_garmin):
        mock_garmin.get_workouts.return_value = [{"workoutId": 1}]
        result = client.get_workouts(limit=10)
        assert len(result) == 1
        mock_garmin.get_workouts.assert_called_once_with(0, 10)

    def test_delete_workout(self, client, mock_garmin):
        client.delete_workout(123)
        mock_garmin.delete_workout.assert_called_once_with(123)
