"""Configuration and path management for the CollabMark CLI.

Global paths:
    ~/.collabmark/              — CLI home (credentials, global config)
    .collabmark/                — per-project sync state (created in working dir)

Environment overrides:
    COLLABMARK_API_URL          — base URL for the CollabMark API
    COLLABMARK_FRONTEND_URL     — base URL for the CollabMark frontend
    COLLABMARK_HOME             — override ~/.collabmark location
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_API_URL = "http://localhost:8000"
_DEFAULT_FRONTEND_URL = "http://localhost:5173"

API_KEY_HEADER = "X-API-Key"


def get_api_url() -> str:
    return os.environ.get("COLLABMARK_API_URL", _DEFAULT_API_URL).rstrip("/")


def get_frontend_url() -> str:
    return os.environ.get("COLLABMARK_FRONTEND_URL", _DEFAULT_FRONTEND_URL).rstrip("/")


def get_cli_home() -> Path:
    override = os.environ.get("COLLABMARK_HOME")
    if override:
        return Path(override)
    return Path.home() / ".collabmark"


def get_credentials_path() -> Path:
    return get_cli_home() / "credentials.json"


def get_project_dir() -> Path:
    """Return the .collabmark/ directory in the current working directory."""
    return Path.cwd() / ".collabmark"
