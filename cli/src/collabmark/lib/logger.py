"""Structured logging for the CollabMark CLI.

Provides both console (rich-formatted) and file (JSON lines) logging,
with automatic credential masking and log rotation.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from collabmark.lib.config import get_cli_home

_LOG_DIR_NAME = "logs"
_LOG_FILE_NAME = "sync.log"
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_BACKUP_COUNT = 5

_SENSITIVE_PATTERN = re.compile(
    r"(cm_[a-zA-Z0-9]{6,}|"
    r"eyJ[a-zA-Z0-9_-]{20,}|"
    r"X-API-Key:\s*\S+)",
    re.IGNORECASE,
)


def _mask_sensitive(text: str) -> str:
    """Replace API keys and JWTs with masked placeholders."""
    return _SENSITIVE_PATTERN.sub("[REDACTED]", text)


class _MaskingFilter(logging.Filter):
    """Logging filter that redacts sensitive data from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _mask_sensitive(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _mask_sensitive(str(v)) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(_mask_sensitive(str(a)) if isinstance(a, str) else a for a in record.args)
        return True


class _JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["error"] = str(record.exc_info[1])
        return json.dumps(entry, default=str)


def get_log_dir() -> Path:
    return get_cli_home() / _LOG_DIR_NAME


def get_log_file() -> Path:
    return get_log_dir() / _LOG_FILE_NAME


def setup_logging(*, verbose: bool = False, log_to_file: bool = True) -> None:
    """Configure logging for the CLI process.

    Args:
        verbose: If True, set console level to DEBUG instead of INFO.
        log_to_file: If True, also write JSON logs to ``~/.collabmark/logs/sync.log``.
    """
    root = logging.getLogger("collabmark")
    root.setLevel(logging.DEBUG)

    if root.handlers:
        return

    masking = _MaskingFilter()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    console_handler.addFilter(masking)
    root.addHandler(console_handler)

    if log_to_file:
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            get_log_file(),
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(_JsonFormatter())
        file_handler.addFilter(masking)
        root.addHandler(file_handler)
