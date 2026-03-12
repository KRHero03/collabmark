"""Shared fixtures for CollabMark CLI tests."""

from __future__ import annotations

import pytest
from click.testing import CliRunner


@pytest.fixture()
def cli_runner() -> CliRunner:
    """Pre-configured Click test runner with isolated filesystem."""
    return CliRunner()
