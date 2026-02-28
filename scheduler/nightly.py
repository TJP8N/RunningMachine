"""Nightly scheduler — auto-generates and pushes workouts to Garmin Connect.

Usage:
    python -m scheduler.nightly --once      # single run (for cron)
    python -m scheduler.nightly --daemon    # APScheduler loop
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, timedelta

from garmin_client import GarminClient, map_daily_metrics
from garmin_client.auth import resume_session
from science_engine.engine import ScienceEngine
from science_engine.serialization import to_garmin_json

from scheduler.config import (
    ATHLETE_PROFILE_PATH,
    GARMIN_EMAIL,
    GARMIN_PASSWORD,
    NIGHTLY_HOUR,
    NIGHTLY_MINUTE,
    TOKEN_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _load_profile() -> dict:
    """Load athlete profile from disk."""
    with open(ATHLETE_PROFILE_PATH) as f:
        return json.load(f)


def _next_monday(from_date: date) -> date:
    """Return the date of the next Monday on or after *from_date*."""
    days_ahead = (7 - from_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return from_date + timedelta(days=days_ahead)


def nightly_job() -> None:
    """Execute one nightly cycle: pull metrics, generate, push a week of workouts."""
    logger.info("Starting nightly job")

    # 1. Connect to Garmin
    try:
        client = GarminClient(
            email=GARMIN_EMAIL,
            password=GARMIN_PASSWORD,
            token_dir=TOKEN_DIR,
        )
    except Exception as exc:
        logger.error("Failed to connect to Garmin: %s", exc)
        return

    # 2. Pull today's metrics
    today = date.today()
    try:
        raw_metrics = client.pull_daily_metrics(today)
        garmin_metrics = map_daily_metrics(raw_metrics)
        logger.info("Pulled metrics: %s", garmin_metrics)
    except Exception as exc:
        logger.warning("Failed to pull metrics, continuing without: %s", exc)
        garmin_metrics = {}

    # 3. Load athlete profile
    try:
        profile = _load_profile()
    except FileNotFoundError:
        logger.error("Profile not found at %s", ATHLETE_PROFILE_PATH)
        return

    # 4. Build AthleteState with Garmin overrides
    # Import here to avoid circular dependency at module level
    sys.path.insert(0, "streamlit_app")
    from helpers import build_athlete_state, build_athlete_state_with_garmin

    if garmin_metrics:
        state = build_athlete_state_with_garmin(profile, garmin_metrics)
    else:
        state = build_athlete_state(profile)

    # 5. Generate a week of structured workouts
    engine = ScienceEngine()
    workouts, plan = engine.prescribe_week_structured(state)
    logger.info(
        "Generated %d workouts for week %d (%s phase)",
        len(workouts),
        plan.week_number,
        plan.phase.name,
    )

    # 6. Convert to Garmin JSON and upload
    start_date = _next_monday(today)
    garmin_jsons = [to_garmin_json(wo) for wo in workouts]

    try:
        ids = client.upload_week(garmin_jsons, start_date)
        logger.info(
            "Uploaded %d workouts starting %s, IDs: %s",
            len(ids),
            start_date.isoformat(),
            ids,
        )
    except Exception as exc:
        logger.error("Failed to upload workouts: %s", exc)
        return

    logger.info("Nightly job complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="AIEnduranceBeater nightly scheduler")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Run once and exit")
    group.add_argument("--daemon", action="store_true", help="Run as APScheduler daemon")
    args = parser.parse_args()

    if args.once:
        nightly_job()
    else:
        from apscheduler.schedulers.blocking import BlockingScheduler

        scheduler = BlockingScheduler()
        scheduler.add_job(
            nightly_job,
            "cron",
            hour=NIGHTLY_HOUR,
            minute=NIGHTLY_MINUTE,
            id="nightly_job",
        )
        logger.info(
            "Scheduler started — nightly job at %02d:%02d",
            NIGHTLY_HOUR,
            NIGHTLY_MINUTE,
        )
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
