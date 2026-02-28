"""Environment-variable-based configuration for the nightly scheduler."""

from __future__ import annotations

import os
from pathlib import Path

GARMIN_EMAIL: str = os.environ.get("GARMIN_EMAIL", "")
GARMIN_PASSWORD: str = os.environ.get("GARMIN_PASSWORD", "")
TOKEN_DIR: Path = Path(os.environ.get("GARMIN_TOKEN_DIR", "~/.garminconnect")).expanduser()
NIGHTLY_HOUR: int = int(os.environ.get("SCHEDULER_HOUR", "21"))
NIGHTLY_MINUTE: int = int(os.environ.get("SCHEDULER_MINUTE", "0"))
ATHLETE_PROFILE_PATH: Path = Path(
    os.environ.get("ATHLETE_PROFILE", "streamlit_app/profiles/my_profile.json")
)
