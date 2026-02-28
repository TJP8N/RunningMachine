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

    Two-phase login:
    1. If saved tokens exist, try token-based resume (fast, no MFA).
    2. If no tokens or resume fails, do fresh SSO login.

    When *prompt_mfa* is ``None`` (the default, suitable for Streamlit),
    ``return_on_mfa=True`` is used so that the library returns early
    instead of blocking on input.  If MFA is required,
    ``GarminMFARequired`` is raised with ``.garmin_client`` and
    ``.mfa_state`` attributes attached — call :func:`complete_mfa_login`
    with the user's verification code to finish authentication.

    When *prompt_mfa* is a callable (e.g. for CLI / scheduler use),
    garminconnect handles MFA internally via the callback.

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

    has_tokens = (token_dir / "oauth1_token.json").exists()

    # Phase 1: Try token-based resume (no MFA needed)
    if has_tokens:
        try:
            client = Garmin(email=email, password=password)
            client.login(tokenstore=tokenstore)
            client.garth.dump(tokenstore)
            logger.info("Resumed session from saved tokens at %s", token_dir)
            return client
        except Exception:
            logger.info("Token resume failed, trying fresh SSO login")

    # Phase 2: Fresh SSO login
    # When prompt_mfa is None (Streamlit), use return_on_mfa so garth
    # returns ("needs_mfa", state) instead of blocking / crashing.
    use_mfa_return = prompt_mfa is None

    try:
        client = Garmin(
            email=email,
            password=password,
            prompt_mfa=prompt_mfa,
            return_on_mfa=use_mfa_return,
        )
        result = client.login()

        # When return_on_mfa=True, login() returns a tuple.
        # ("needs_mfa", {client_state}) means MFA is required.
        if use_mfa_return and isinstance(result, tuple) and len(result) >= 2:
            if result[0] == "needs_mfa":
                exc = GarminMFARequired("MFA verification required")
                exc.garmin_client = client  # type: ignore[attr-defined]
                exc.mfa_state = result[1]  # type: ignore[attr-defined]
                exc.token_dir = token_dir  # type: ignore[attr-defined]
                raise exc

        # Login succeeded — save tokens
        client.garth.dump(tokenstore)
        logger.info("Logged in via SSO and saved tokens to %s", token_dir)
        return client
    except GarminMFARequired:
        raise
    except Exception as exc:
        _msg = str(exc).lower()
        if "mfa" in _msg or "verification" in _msg or "two-factor" in _msg:
            raise GarminMFARequired(str(exc)) from exc
        if "authentication" in _msg or "unauthorized" in _msg or "401" in _msg:
            raise GarminAuthError(f"Login failed: {exc}") from exc
        raise GarminAuthError(f"Login failed: {exc}") from exc


def complete_mfa_login(
    garmin_client: Garmin,
    mfa_state: dict,
    mfa_code: str,
    token_dir: Path | str = _DEFAULT_TOKEN_DIR,
) -> Garmin:
    """Complete MFA login with the verification code.

    After :func:`create_session` raises ``GarminMFARequired``, call this
    with the partially-authenticated client, the MFA state dict, and the
    code the user received via email.

    Parameters
    ----------
    garmin_client : Garmin
        The partially-authenticated client (from ``exc.garmin_client``).
    mfa_state : dict
        MFA state dict (from ``exc.mfa_state``).
    mfa_code : str
        The verification code from the user's email.
    token_dir : Path | str
        Where to save tokens on success.

    Returns
    -------
    Garmin
        Fully authenticated session.
    """
    token_dir = Path(token_dir)
    token_dir.mkdir(parents=True, exist_ok=True)
    tokenstore = str(token_dir)

    try:
        garmin_client.resume_login(mfa_state, mfa_code)
        garmin_client.garth.dump(tokenstore)
        logger.info("MFA login completed, tokens saved to %s", token_dir)
        return garmin_client
    except Exception as exc:
        raise GarminAuthError(f"MFA verification failed: {exc}") from exc


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
