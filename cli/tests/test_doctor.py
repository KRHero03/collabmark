"""Tests for the collabmark doctor command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from collabmark.commands.doctor import (
    _check_active_syncs,
    _check_config_dir,
    _check_credentials,
    _check_keyring,
    doctor,
)


class TestCheckConfigDir:
    def test_returns_true_when_dir_exists(self, tmp_path: Path):
        with patch("collabmark.commands.doctor.COLLABMARK_HOME", tmp_path):
            assert _check_config_dir() is True

    def test_returns_false_when_dir_missing(self, tmp_path: Path):
        missing = tmp_path / "nonexistent"
        with patch("collabmark.commands.doctor.COLLABMARK_HOME", missing):
            assert _check_config_dir() is False


class TestCheckCredentials:
    def test_returns_true_when_logged_in(self):
        with (
            patch("collabmark.commands.doctor.load_metadata", return_value={"email": "test@example.com"}),
            patch("collabmark.commands.doctor.load_api_key", return_value="cm_test_key"),
        ):
            ok, key = _check_credentials()
            assert ok is True
            assert key == "cm_test_key"

    def test_returns_false_when_not_logged_in(self):
        with (
            patch("collabmark.commands.doctor.load_metadata", return_value=None),
            patch("collabmark.commands.doctor.load_api_key", return_value=None),
        ):
            ok, key = _check_credentials()
            assert ok is False
            assert key is None

    def test_returns_false_when_no_api_key(self):
        with (
            patch("collabmark.commands.doctor.load_metadata", return_value={"email": "test@example.com"}),
            patch("collabmark.commands.doctor.load_api_key", return_value=None),
        ):
            ok, _key = _check_credentials()
            assert ok is False


class TestCheckKeyring:
    def test_returns_true_when_keyring_available(self):
        mock_kr = MagicMock()
        mock_kr.get_keyring.return_value = MagicMock()
        with patch.dict("sys.modules", {"keyring": mock_kr}):
            result = _check_keyring()
            assert result is True

    def test_returns_false_when_keyring_import_fails(self):
        mock_kr = MagicMock(get_keyring=MagicMock(side_effect=Exception("no backend")))
        with patch.dict("sys.modules", {"keyring": mock_kr}):
            result = _check_keyring()
            assert result is False


class TestCheckActiveSyncs:
    def test_no_running_syncs(self):
        mock_reg = MagicMock()
        mock_reg.syncs = []
        with patch("collabmark.commands.doctor.load_registry", return_value=mock_reg):
            assert _check_active_syncs() is True

    def test_detects_dead_pid(self):
        mock_entry = MagicMock()
        mock_entry.status = "running"
        mock_entry.pid = 999999999
        mock_entry.local_path = "/tmp/test"
        mock_entry.folder_id = "f1"
        mock_entry.last_error = None
        mock_reg = MagicMock()
        mock_reg.syncs = [mock_entry]
        with patch("collabmark.commands.doctor.load_registry", return_value=mock_reg):
            assert _check_active_syncs() is False


class TestDoctorCommand:
    def test_exits_with_zero_when_all_pass(self):
        runner = CliRunner()
        with (
            patch("collabmark.commands.doctor._check_config_dir", return_value=True),
            patch("collabmark.commands.doctor._check_keyring", return_value=True),
            patch("collabmark.commands.doctor._check_credentials", return_value=(True, "cm_key")),
            patch("collabmark.commands.doctor._check_server", new_callable=AsyncMock, return_value=True),
            patch("collabmark.commands.doctor._check_websocket", new_callable=AsyncMock, return_value=True),
            patch("collabmark.commands.doctor._check_active_syncs", return_value=True),
        ):
            result = runner.invoke(doctor)
            assert result.exit_code == 0
            assert "All checks passed" in result.output

    def test_exits_with_one_on_failure(self):
        runner = CliRunner()
        with (
            patch("collabmark.commands.doctor._check_config_dir", return_value=False),
            patch("collabmark.commands.doctor._check_keyring", return_value=True),
            patch("collabmark.commands.doctor._check_credentials", return_value=(False, None)),
            patch("collabmark.commands.doctor._check_active_syncs", return_value=True),
        ):
            result = runner.invoke(doctor)
            assert result.exit_code == 1
            assert "failed" in result.output
