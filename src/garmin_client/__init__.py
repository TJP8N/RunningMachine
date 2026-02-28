"""Garmin Connect API client — all Garmin network I/O lives here."""

from garmin_client.client import GarminClient
from garmin_client.exceptions import (
    GarminAPIError,
    GarminAuthError,
    GarminClientError,
    GarminMFARequired,
    GarminRateLimitError,
)
from garmin_client.metrics_mapper import map_daily_metrics

__all__ = [
    "GarminClient",
    "GarminAPIError",
    "GarminAuthError",
    "GarminClientError",
    "GarminMFARequired",
    "GarminRateLimitError",
    "map_daily_metrics",
]
