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

    Uses the garminconnect library's built-in token management:
    pass *token_dir* as the tokenstore so it automatically tries
    saved tokens first, then falls back to email/password.
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
    token_dir.mkdir(parents=True, exist_ok=True)
    tokenstore = str(token_dir)

    # Only pass tokenstore if token files actually exist inside it
    has_tokens = (token_dir / "oauth1_token.json").exists()

    try:
        client = Garmin(email=email, password=password, prompt_mfa=prompt_mfa)
        if has_tokens:
            client.login(tokenstore=tokenstore)
        else:
            client.login()
        # Save tokens for future sessions
        client.garth.dump(tokenstore)
        logger.info("Logged in and saved tokens to %s", token_dir)
        return client
    except Exception as exc:
        _msg = str(exc).lower()
        if "mfa" in _msg or "verification" in _msg or "two-factor" in _msg:
            raise GarminMFARequired(str(exc)) from exc
        if "authentication" in _msg or "unauthorized" in _msg or "401" in _msg:
            raise GarminAuthError(f"Login failed: {exc}") from exc
        raise GarminAuthError(f"Login failed: {exc}") from exc


def resume_session(token_dir: Path | str = _DEFAULT_TOKEN_DIR) -> Garmin:
    """Resume a session from saved tokens (no credentials needed).

    Raises ``GarminAuthError`` if tokens are missing or expired.
    """
    token_dir = Path(token_dir)
    if not (token_dir / "oauth1_token.json").exists():
        raise GarminAuthError(f"No saved tokens at {token_dir}")

    tokenstore = str(token_dir)
    try:
        client = Garmin()
        client.login(tokenstore=tokenstore)
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
