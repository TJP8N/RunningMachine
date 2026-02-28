"""Tests for garmin_client.auth — mock-based, no real network calls."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from garmin_client.auth import clear_tokens, create_session, is_authenticated, resume_session
from garmin_client.exceptions import GarminAuthError, GarminMFARequired


@pytest.fixture
def tmp_token_dir(tmp_path):
    """Provide a temporary directory for token storage."""
    return tmp_path / "tokens"


# ---------------------------------------------------------------------------
# resume_session
# ---------------------------------------------------------------------------


class TestResumeSession:
    def test_raises_when_dir_missing(self, tmp_token_dir):
        with pytest.raises(GarminAuthError, match="does not exist"):
            resume_session(tmp_token_dir)

    @patch("garmin_client.auth.Garmin")
    def test_resumes_with_tokens(self, MockGarmin, tmp_token_dir):
        tmp_token_dir.mkdir(parents=True)
        mock_instance = MagicMock()
        mock_instance.garth.profile = {
            "displayName": "Test User",
            "userName": "testuser",
        }
        MockGarmin.return_value = mock_instance

        client = resume_session(tmp_token_dir)
        assert client is mock_instance
        mock_instance.garth.load.assert_called_once_with(str(tmp_token_dir))

    @patch("garmin_client.auth.Garmin")
    def test_raises_on_load_failure(self, MockGarmin, tmp_token_dir):
        tmp_token_dir.mkdir(parents=True)
        mock_instance = MagicMock()
        mock_instance.garth.load.side_effect = Exception("corrupt")
        MockGarmin.return_value = mock_instance

        with pytest.raises(GarminAuthError, match="Token resume failed"):
            resume_session(tmp_token_dir)


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------


class TestCreateSession:
    @patch("garmin_client.auth.resume_session")
    def test_uses_tokens_when_available(self, mock_resume, tmp_token_dir):
        mock_client = MagicMock()
        mock_resume.return_value = mock_client

        result = create_session("a@b.com", "pw", token_dir=tmp_token_dir)
        assert result is mock_client

    @patch("garmin_client.auth.Garmin")
    @patch("garmin_client.auth.resume_session", side_effect=GarminAuthError("no tokens"))
    def test_falls_back_to_login(self, mock_resume, MockGarmin, tmp_token_dir):
        mock_instance = MagicMock()
        MockGarmin.return_value = mock_instance

        result = create_session("a@b.com", "pw", token_dir=tmp_token_dir)
        assert result is mock_instance
        mock_instance.login.assert_called_once()
        mock_instance.garth.dump.assert_called_once_with(str(tmp_token_dir))

    @patch("garmin_client.auth.Garmin")
    @patch("garmin_client.auth.resume_session", side_effect=GarminAuthError("no tokens"))
    def test_raises_on_bad_credentials(self, mock_resume, MockGarmin, tmp_token_dir):
        mock_instance = MagicMock()
        mock_instance.login.side_effect = Exception("invalid credentials")
        MockGarmin.return_value = mock_instance

        with pytest.raises(GarminAuthError, match="Login failed"):
            create_session("a@b.com", "wrong", token_dir=tmp_token_dir)

    @patch("garmin_client.auth.Garmin")
    @patch("garmin_client.auth.resume_session", side_effect=GarminAuthError("no tokens"))
    def test_raises_mfa_required(self, mock_resume, MockGarmin, tmp_token_dir):
        mock_instance = MagicMock()
        mock_instance.login.side_effect = Exception("MFA verification required")
        MockGarmin.return_value = mock_instance

        with pytest.raises(GarminMFARequired):
            create_session("a@b.com", "pw", token_dir=tmp_token_dir)


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
        tmp_token_dir.mkdir(parents=True)
        (tmp_token_dir / "oauth1_token.json").write_text("{}")
        clear_tokens(tmp_token_dir)
        assert not tmp_token_dir.exists()

    def test_noop_when_dir_missing(self, tmp_token_dir):
        # Should not raise
        clear_tokens(tmp_token_dir)
