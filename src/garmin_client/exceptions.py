"""Custom exception hierarchy for the Garmin Connect client."""

from __future__ import annotations


class GarminClientError(Exception):
    """Base exception for all garmin_client errors."""


class GarminAuthError(GarminClientError):
    """Authentication failed (bad credentials, expired tokens, etc.)."""


class GarminMFARequired(GarminAuthError):
    """Multi-factor authentication is required to complete login."""


class GarminAPIError(GarminClientError):
    """A Garmin Connect API call returned an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GarminRateLimitError(GarminAPIError):
    """HTTP 429 — too many requests."""

    def __init__(self, message: str = "Rate limited by Garmin Connect") -> None:
        super().__init__(message, status_code=429)
