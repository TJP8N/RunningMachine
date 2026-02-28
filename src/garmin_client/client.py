"""High-level Garmin Connect client facade.

All methods wrap raw garminconnect calls with error handling and retry logic.
"""

from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional

from garminconnect import Garmin

from garmin_client.auth import create_session
from garmin_client.exceptions import (
    GarminAPIError,
    GarminRateLimitError,
)

logger = logging.getLogger(__name__)

_DEFAULT_TOKEN_DIR = Path("~/.garminconnect").expanduser()
_MAX_RETRIES = 3
_BASE_BACKOFF_S = 2


class GarminClient:
    """Facade for Garmin Connect workout and metrics operations."""

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        token_dir: Path | str = _DEFAULT_TOKEN_DIR,
        prompt_mfa: Optional[Callable[[], str]] = None,
    ) -> None:
        self._token_dir = Path(token_dir)
        self._garmin = create_session(
            email=email or "",
            password=password or "",
            token_dir=self._token_dir,
            prompt_mfa=prompt_mfa,
        )

    @classmethod
    def from_garmin(cls, garmin: Garmin, token_dir: Path | str = _DEFAULT_TOKEN_DIR) -> "GarminClient":
        """Construct from an already-authenticated Garmin object.

        Used after completing MFA login via :func:`complete_mfa_login`.
        """
        obj = cls.__new__(cls)
        obj._token_dir = Path(token_dir)
        obj._garmin = garmin
        return obj

    # ------------------------------------------------------------------
    # Workout operations
    # ------------------------------------------------------------------

    def upload_workout(self, workout_json: dict) -> int:
        """Upload a workout to Garmin Connect.

        Returns the workoutId assigned by Garmin.
        """
        resp = self._safe_call(self._garmin.upload_workout, workout_json)
        if isinstance(resp, dict) and "workoutId" in resp:
            workout_id = int(resp["workoutId"])
            logger.info("Uploaded workout id=%d", workout_id)
            return workout_id
        raise GarminAPIError(f"Unexpected upload response: {resp}")

    def schedule_workout(self, workout_id: int, target_date: date) -> None:
        """Schedule an uploaded workout on a specific date.

        Uses garth directly since python-garminconnect has no schedule method.
        """
        date_str = target_date.isoformat()
        self._safe_call(
            self._garmin.garth.post,
            "connectapi",
            f"/workout-service/schedule/{workout_id}",
            json={"date": date_str},
            api=True,
        )
        logger.info("Scheduled workout %d for %s", workout_id, date_str)

    def upload_and_schedule(self, workout_json: dict, target_date: date) -> int:
        """Upload a workout and schedule it on a date. Returns workoutId."""
        workout_id = self.upload_workout(workout_json)
        self.schedule_workout(workout_id, target_date)
        return workout_id

    def upload_week(
        self, week_jsons: list[dict], start_date: date
    ) -> list[int]:
        """Upload and schedule a list of daily workouts starting at *start_date*.

        Returns a list of workoutIds in order.
        """
        from datetime import timedelta

        ids: list[int] = []
        for i, wj in enumerate(week_jsons):
            target = start_date + timedelta(days=i)
            wid = self.upload_and_schedule(wj, target)
            ids.append(wid)
        return ids

    def get_workouts(self, limit: int = 100) -> list[dict]:
        """List existing workouts from Garmin Connect."""
        return self._safe_call(self._garmin.get_workouts, 0, limit) or []

    def delete_workout(self, workout_id: int) -> None:
        """Delete a workout from Garmin Connect."""
        self._safe_call(self._garmin.delete_workout, workout_id)
        logger.info("Deleted workout %d", workout_id)

    # ------------------------------------------------------------------
    # Metrics pull
    # ------------------------------------------------------------------

    def pull_daily_metrics(self, cdate: date) -> dict[str, Any]:
        """Pull all available daily metrics from Garmin Connect.

        Returns a dict with keys: training_readiness, hrv, body_battery,
        sleep, stress, max_metrics, stats.  Individual keys may be None if
        the endpoint fails (partial data is OK).
        """
        date_str = cdate.isoformat()
        endpoints: dict[str, tuple] = {
            "training_readiness": (self._garmin.get_training_readiness, date_str),
            "hrv": (self._garmin.get_hrv_data, date_str),
            "body_battery": (self._garmin.get_body_battery, date_str),
            "sleep": (self._garmin.get_sleep_data, date_str),
            "stress": (self._garmin.get_stress_data, date_str),
            "max_metrics": (self._garmin.get_max_metrics, date_str),
            "stats": (self._garmin.get_stats, date_str),
        }

        result: dict[str, Any] = {}
        for key, (fn, *args) in endpoints.items():
            try:
                result[key] = self._safe_call(fn, *args)
            except Exception:
                logger.warning("Failed to pull %s for %s", key, date_str)
                result[key] = None
        return result

    # ------------------------------------------------------------------
    # Profile pull
    # ------------------------------------------------------------------

    def pull_profile(self, cdate: date | None = None) -> dict[str, Any]:
        """Pull user profile, biometrics, and recent training data.

        Returns a dict with keys: user_profile, user_settings,
        body_composition, max_metrics, resting_hr, lactate_threshold,
        recent_activities, training_readiness, hrv, sleep, body_battery.
        Individual keys may be None on failure.
        """
        from datetime import timedelta

        if cdate is None:
            cdate = date.today()
        date_str = cdate.isoformat()

        # Date range for recent activities (last 6 weeks)
        start_date = (cdate - timedelta(days=42)).isoformat()

        result: dict[str, Any] = {}

        # Simple single-arg-or-no-arg endpoints
        simple: dict[str, tuple] = {
            "user_profile": (self._garmin.get_user_profile,),
            "user_settings": (self._garmin.get_userprofile_settings,),
            "body_composition": (self._garmin.get_body_composition, date_str),
            "max_metrics": (self._garmin.get_max_metrics, date_str),
            "resting_hr": (self._garmin.get_rhr_day, date_str),
            "training_readiness": (self._garmin.get_training_readiness, date_str),
            "hrv": (self._garmin.get_hrv_data, date_str),
            "sleep": (self._garmin.get_sleep_data, date_str),
            "body_battery": (self._garmin.get_body_battery, date_str),
            "stats": (self._garmin.get_stats, date_str),
        }
        for key, (fn, *args) in simple.items():
            try:
                result[key] = self._safe_call(fn, *args)
            except Exception:
                logger.warning("Failed to pull %s", key)
                result[key] = None

        # Lactate threshold (keyword arg)
        try:
            result["lactate_threshold"] = self._safe_call(
                self._garmin.get_lactate_threshold, latest=True
            )
        except Exception:
            logger.warning("Failed to pull lactate_threshold")
            result["lactate_threshold"] = None

        # Recent running activities for weekly volume
        try:
            activities = self._safe_call(
                self._garmin.get_activities_by_date,
                start_date,
                date_str,
                "running",
            )
            result["recent_activities"] = activities
        except Exception:
            logger.warning("Failed to pull recent_activities")
            result["recent_activities"] = None

        # All recent activities (any type) — used for observed max HR
        try:
            result["all_activities"] = self._safe_call(
                self._garmin.get_activities, 0, 100
            )
        except Exception:
            logger.warning("Failed to pull all_activities")
            result["all_activities"] = None

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _safe_call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Call *fn* with retry + exponential backoff on 429 / transient errors."""
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                status = getattr(exc, "status", None) or getattr(
                    exc, "status_code", None
                )
                if status == 429:
                    wait = _BASE_BACKOFF_S * (2 ** attempt)
                    logger.warning(
                        "Rate limited (attempt %d/%d), retrying in %ds",
                        attempt + 1,
                        _MAX_RETRIES,
                        wait,
                    )
                    time.sleep(wait)
                    continue
                # Non-retryable error
                raise GarminAPIError(str(exc), status_code=status) from exc

        raise GarminRateLimitError(
            f"Rate limited after {_MAX_RETRIES} retries: {last_exc}"
        )
