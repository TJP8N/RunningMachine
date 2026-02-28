"""Tests for garmin_client.auth — mock-based, no real network calls."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from garmin_client.auth import (
    clear_tokens,
    complete_mfa_login,
    create_session,
    is_authenticated,
    resume_session,
)
from garmin_client.exceptions import GarminAuthError, GarminMFARequired


@pytest.fixture
def tmp_token_dir(tmp_path):
    """Provide a temporary directory for token storage."""
    return tmp_path / "tokens"


def _seed_tokens(token_dir: Path) -> None:
    """Create a fake oauth1_token.json so auth code detects existing tokens."""
    token_dir.mkdir(parents=True, exist_ok=True)
    (token_dir / "oauth1_token.json").write_text("{}")


# ---------------------------------------------------------------------------
# resume_session
# ---------------------------------------------------------------------------


class TestResumeSession:
    def test_raises_when_no_tokens(self, tmp_token_dir):
        with pytest.raises(GarminAuthError, match="No saved tokens"):
            resume_session(tmp_token_dir)

    @patch("garmin_client.auth.Garmin")
    def test_resumes_with_tokens(self, MockGarmin, tmp_token_dir):
        _seed_tokens(tmp_token_dir)
        mock_instance = MagicMock()
        MockGarmin.return_value = mock_instance

        client = resume_session(tmp_token_dir)
        assert client is mock_instance
        mock_instance.login.assert_called_once_with(tokenstore=str(tmp_token_dir))

    @patch("garmin_client.auth.Garmin")
    def test_raises_on_load_failure(self, MockGarmin, tmp_token_dir):
        _seed_tokens(tmp_token_dir)
        mock_instance = MagicMock()
        mock_instance.login.side_effect = Exception("corrupt")
        MockGarmin.return_value = mock_instance

        with pytest.raises(GarminAuthError, match="Token resume failed"):
            resume_session(tmp_token_dir)


# ---------------------------------------------------------------------------
# create_session — Phase 1: token resume
# ---------------------------------------------------------------------------


class TestCreateSessionTokenResume:
    @patch("garmin_client.auth.Garmin")
    def test_resumes_from_tokens_when_present(self, MockGarmin, tmp_token_dir):
        """Phase 1: saved tokens exist → resumes via tokenstore, skips SSO."""
        _seed_tokens(tmp_token_dir)
        mock_instance = MagicMock()
        mock_instance.login.return_value = None
        MockGarmin.return_value = mock_instance

        result = create_session("a@b.com", "pw", token_dir=tmp_token_dir)
        assert result is mock_instance
        # Phase 1 constructor: no return_on_mfa
        MockGarmin.assert_called_once_with(email="a@b.com", password="pw")
        mock_instance.login.assert_called_once_with(tokenstore=str(tmp_token_dir))
        mock_instance.garth.dump.assert_called_once_with(str(tmp_token_dir))

    @patch("garmin_client.auth.Garmin")
    def test_falls_through_to_sso_on_token_failure(self, MockGarmin, tmp_token_dir):
        """Phase 1 fails → falls through to Phase 2 SSO login."""
        _seed_tokens(tmp_token_dir)

        # Track which Garmin() calls get which mock
        phase1_mock = MagicMock()
        phase1_mock.login.side_effect = Exception("corrupt tokens")

        phase2_mock = MagicMock()
        phase2_mock.login.return_value = None  # SSO success

        MockGarmin.side_effect = [phase1_mock, phase2_mock]

        result = create_session("a@b.com", "pw", token_dir=tmp_token_dir)
        assert result is phase2_mock
        # Phase 1 tried tokenstore, then Phase 2 did fresh login
        assert MockGarmin.call_count == 2
        phase2_mock.login.assert_called_once_with()
        phase2_mock.garth.dump.assert_called_once_with(str(tmp_token_dir))


# ---------------------------------------------------------------------------
# create_session — Phase 2: SSO login
# ---------------------------------------------------------------------------


class TestCreateSessionSSO:
    @patch("garmin_client.auth.Garmin")
    def test_sso_login_without_tokens(self, MockGarmin, tmp_token_dir):
        """No saved tokens → skips Phase 1, goes straight to SSO."""
        mock_instance = MagicMock()
        mock_instance.login.return_value = None  # success, no MFA
        MockGarmin.return_value = mock_instance

        result = create_session("a@b.com", "pw", token_dir=tmp_token_dir)
        assert result is mock_instance
        # Phase 2: return_on_mfa=True (since prompt_mfa is None)
        MockGarmin.assert_called_once_with(
            email="a@b.com", password="pw", prompt_mfa=None, return_on_mfa=True
        )
        mock_instance.login.assert_called_once_with()
        mock_instance.garth.dump.assert_called_once_with(str(tmp_token_dir))

    @patch("garmin_client.auth.Garmin")
    def test_raises_on_bad_credentials(self, MockGarmin, tmp_token_dir):
        mock_instance = MagicMock()
        mock_instance.login.side_effect = Exception(
            "Authentication failed: invalid credentials"
        )
        MockGarmin.return_value = mock_instance

        with pytest.raises(GarminAuthError, match="Login failed"):
            create_session("a@b.com", "wrong", token_dir=tmp_token_dir)

    @patch("garmin_client.auth.Garmin")
    def test_raises_mfa_on_needs_mfa_tuple(self, MockGarmin, tmp_token_dir):
        """When login() returns ("needs_mfa", state), raises GarminMFARequired."""
        mock_instance = MagicMock()
        mfa_state = {"signin_params": {}, "client": "fake"}
        mock_instance.login.return_value = ("needs_mfa", mfa_state)
        MockGarmin.return_value = mock_instance

        with pytest.raises(GarminMFARequired) as exc_info:
            create_session("a@b.com", "pw", token_dir=tmp_token_dir)

        exc = exc_info.value
        assert exc.garmin_client is mock_instance
        assert exc.mfa_state is mfa_state
        assert exc.token_dir == tmp_token_dir

    @patch("garmin_client.auth.Garmin")
    def test_raises_mfa_on_mfa_exception_message(self, MockGarmin, tmp_token_dir):
        """Falls back to string detection for MFA-related exceptions."""
        mock_instance = MagicMock()
        mock_instance.login.side_effect = Exception("MFA verification required")
        MockGarmin.return_value = mock_instance

        with pytest.raises(GarminMFARequired):
            create_session("a@b.com", "pw", token_dir=tmp_token_dir)

    @patch("garmin_client.auth.Garmin")
    def test_prompt_mfa_callback_disables_return_on_mfa(self, MockGarmin, tmp_token_dir):
        """When prompt_mfa is provided, return_on_mfa=False."""
        mock_instance = MagicMock()
        mock_instance.login.return_value = None
        MockGarmin.return_value = mock_instance

        mfa_cb = lambda: "123456"
        create_session("a@b.com", "pw", token_dir=tmp_token_dir, prompt_mfa=mfa_cb)

        MockGarmin.assert_called_once_with(
            email="a@b.com", password="pw", prompt_mfa=mfa_cb, return_on_mfa=False
        )

    @patch("garmin_client.auth.Garmin")
    def test_creates_token_dir(self, MockGarmin, tmp_token_dir):
        mock_instance = MagicMock()
        mock_instance.login.return_value = None
        MockGarmin.return_value = mock_instance

        assert not tmp_token_dir.exists()
        create_session("a@b.com", "pw", token_dir=tmp_token_dir)
        assert tmp_token_dir.exists()


# ---------------------------------------------------------------------------
# complete_mfa_login
# ---------------------------------------------------------------------------


class TestCompleteMfaLogin:
    def test_calls_resume_login_and_saves_tokens(self, tmp_token_dir):
        mock_garmin = MagicMock()
        mfa_state = {"signin_params": {}, "client": "fake"}

        result = complete_mfa_login(mock_garmin, mfa_state, "123456", tmp_token_dir)

        assert result is mock_garmin
        mock_garmin.resume_login.assert_called_once_with(mfa_state, "123456")
        mock_garmin.garth.dump.assert_called_once_with(str(tmp_token_dir))

    def test_creates_token_dir(self, tmp_token_dir):
        mock_garmin = MagicMock()
        assert not tmp_token_dir.exists()
        complete_mfa_login(mock_garmin, {}, "123456", tmp_token_dir)
        assert tmp_token_dir.exists()

    def test_raises_on_failure(self, tmp_token_dir):
        mock_garmin = MagicMock()
        mock_garmin.resume_login.side_effect = Exception("invalid code")

        with pytest.raises(GarminAuthError, match="MFA verification failed"):
            complete_mfa_login(mock_garmin, {}, "000000", tmp_token_dir)


# ---------------------------------------------------------------------------
# is_authenticated
# ---------------------------------------------------------------------------


class TestIsAuthenticated:
    @patch("garmin_client.auth.resume_session")
    def test_returns_true_when_tokens_valid(self, mock_resume, tmp_token_dir):
        mock_resume.return_value = MagicMock()
        assert is_authenticated(tmp_token_dir) is True

    @patch("garmin_client.auth.resume_session", side_effect=GarminAuthError("nope"))
    def test_returns_false_when_no_tokens(self, mock_resume, tmp_token_dir):
        assert is_authenticated(tmp_token_dir) is False


# ---------------------------------------------------------------------------
# clear_tokens
# ---------------------------------------------------------------------------


class TestClearTokens:
    def test_clears_existing_dir(self, tmp_token_dir):
        _seed_tokens(tmp_token_dir)
        clear_tokens(tmp_token_dir)
        assert not tmp_token_dir.exists()

    def test_noop_when_dir_missing(self, tmp_token_dir):
        # Should not raise
        clear_tokens(tmp_token_dir)
