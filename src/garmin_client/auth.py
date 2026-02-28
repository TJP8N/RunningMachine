"""Garmin Connect authentication helpers.

Wraps garminconnect / garth token management with a clean error hierarchy.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from garminconnect import Garmin

from garmin_client.exceptions import GarminAuthError, GarminMFARequired

logger = logging.getLogger(__name__)

_DEFAULT_TOKEN_DIR = Path("~/.garminconnect").expanduser()


def create_session(
    email: str,
    password: str,
    token_dir: Path | str = _DEFAULT_TOKEN_DIR,
    prompt_mfa: Optional[Callable[[], str]] = None,
) -> Garmin:
    """Authenticate with Garmin Connect and return a session.

    Tries token-based resume first (fast, no network if tokens are fresh).
    Falls back to email/password login if tokens are missing or expired.
    Saves tokens to *token_dir* on success.

    Parameters
    ----------
    email : str
        Garmin Connect account email.
    password : str
        Garmin Connect account password.
    token_dir : Path | str
        Directory where garth tokens are persisted.
    prompt_mfa : callable, optional
        Called when MFA is required. Must return the MFA code string.
        If None and MFA is required, raises ``GarminMFARequired``.

    Returns
    -------
    Garmin
        Authenticated session.
    """
    token_dir = Path(token_dir)

    # Try token-based resume first
    try:
        return resume_session(token_dir)
    except GarminAuthError:
        logger.debug("Token resume failed, falling back to email/password login.")

    # Full login
    try:
        client = Garmin(email=email, password=password)
        client.login()
        token_dir.mkdir(parents=True, exist_ok=True)
        client.garth.dump(str(token_dir))
        logger.info("Logged in and saved tokens to %s", token_dir)
        return client
    except Exception as exc:
        _msg = str(exc).lower()
        if "mfa" in _msg or "verification" in _msg or "two-factor" in _msg:
            if prompt_mfa is not None:
                try:
                    code = prompt_mfa()
                    client = Garmin(email=email, password=password)
                    client.login(mfa_code=code)
                    token_dir.mkdir(parents=True, exist_ok=True)
                    client.garth.dump(str(token_dir))
                    return client
                except Exception as mfa_exc:
                    raise GarminAuthError(f"MFA login failed: {mfa_exc}") from mfa_exc
            raise GarminMFARequired(str(exc)) from exc
        raise GarminAuthError(f"Login failed: {exc}") from exc


def resume_session(token_dir: Path | str = _DEFAULT_TOKEN_DIR) -> Garmin:
    """Resume a session from saved tokens (no credentials needed).

    Raises ``GarminAuthError`` if tokens are missing or expired.
    """
    token_dir = Path(token_dir)
    if not token_dir.exists():
        raise GarminAuthError(f"Token directory does not exist: {token_dir}")

    try:
        client = Garmin()
        client.garth.load(str(token_dir))
        client.display_name = client.garth.profile["displayName"]
        client.full_name = client.garth.profile["userName"]
        logger.debug("Resumed session from %s", token_dir)
        return client
    except Exception as exc:
        raise GarminAuthError(f"Token resume failed: {exc}") from exc


def is_authenticated(token_dir: Path | str = _DEFAULT_TOKEN_DIR) -> bool:
    """Return True if valid tokens exist at *token_dir*."""
    try:
        resume_session(token_dir)
        return True
    except GarminAuthError:
        return False


def clear_tokens(token_dir: Path | str = _DEFAULT_TOKEN_DIR) -> None:
    """Delete saved tokens."""
    token_dir = Path(token_dir)
    if token_dir.exists():
        import shutil

        shutil.rmtree(token_dir)
        logger.info("Cleared tokens at %s", token_dir)
