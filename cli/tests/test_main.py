"""Tests for the root CLI entry point."""

from __future__ import annotations

from click.testing import CliRunner

from collabmark import __version__
from collabmark.main import cli


class TestCLIEntryPoint:
    """Verify the CLI group boots correctly."""

    def test_help_exits_zero(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "CollabMark" in result.output

    def test_version_flag(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output


class TestStartCommand:
    """Verify the start command is wired up correctly."""

    def test_start_help(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(cli, ["start", "--help"])
        assert result.exit_code == 0
        assert "Start syncing" in result.output

    def test_start_shows_options(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(cli, ["start", "--help"])
        assert "--daemon" in result.output
        assert "--path" in result.output
        assert "--interval" in result.output

    def test_start_without_auth_exits_with_error(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(cli, ["start"])
        assert result.exit_code == 1


class TestStatusCommandStub:
    def test_status_help(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0

    def test_status_runs(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(cli, ["status"])
        assert result.exit_code == 0


class TestStopCommandStub:
    def test_stop_help(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(cli, ["stop", "--help"])
        assert result.exit_code == 0

    def test_stop_runs(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(cli, ["stop"])
        assert result.exit_code == 0


class TestLogsCommandStub:
    def test_logs_help(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(cli, ["logs", "--help"])
        assert result.exit_code == 0
        assert "--follow" in result.output
        assert "--lines" in result.output

    def test_logs_runs(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(cli, ["logs"])
        assert result.exit_code == 0
