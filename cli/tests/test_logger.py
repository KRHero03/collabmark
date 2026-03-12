"""Tests for collabmark.lib.logger — structured logging and credential masking."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

from collabmark.lib.logger import _JsonFormatter, _mask_sensitive, _MaskingFilter, setup_logging


class TestMaskSensitive:
    def test_masks_api_key(self) -> None:
        text = "Using key cm_abc123def456"
        assert "[REDACTED]" in _mask_sensitive(text)
        assert "cm_abc123def456" not in _mask_sensitive(text)

    def test_masks_jwt(self) -> None:
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
        assert "[REDACTED]" in _mask_sensitive(jwt)

    def test_masks_api_key_header(self) -> None:
        text = "X-API-Key: cm_secret123456"
        assert "[REDACTED]" in _mask_sensitive(text)

    def test_leaves_normal_text_unchanged(self) -> None:
        text = "Syncing file overview.md"
        assert _mask_sensitive(text) == text


class TestMaskingFilter:
    def test_redacts_message(self) -> None:
        f = _MaskingFilter()
        record = logging.LogRecord("test", logging.INFO, "", 0, "Key: cm_abc123def456", (), None)
        f.filter(record)
        assert "cm_abc123def456" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_redacts_tuple_args(self) -> None:
        f = _MaskingFilter()
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "Token: %s", ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.x.y",), None
        )
        f.filter(record)
        assert "[REDACTED]" in record.args[0]

    def test_passes_through_non_sensitive(self) -> None:
        f = _MaskingFilter()
        record = logging.LogRecord("test", logging.INFO, "", 0, "Normal message", (), None)
        f.filter(record)
        assert record.msg == "Normal message"


class TestJsonFormatter:
    def test_formats_as_json(self) -> None:
        fmt = _JsonFormatter()
        record = logging.LogRecord("collabmark.sync", logging.INFO, "", 0, "Pushed file.md", (), None)
        output = fmt.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "Pushed file.md"
        assert "ts" in data

    def test_includes_error_info(self) -> None:
        fmt = _JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            record = logging.LogRecord("collabmark", logging.ERROR, "", 0, "Failed", (), sys.exc_info())
        output = fmt.format(record)
        data = json.loads(output)
        assert "error" in data


class TestSetupLogging:
    def test_creates_log_directory(self, tmp_path: Path) -> None:
        log_name = "collabmark.test_setup_logging"
        test_logger = logging.getLogger(log_name)
        test_logger.handlers.clear()

        with patch("collabmark.lib.logger.get_log_dir", return_value=tmp_path / "logs"):
            with patch("collabmark.lib.logger.get_log_file", return_value=tmp_path / "logs" / "sync.log"):
                with patch("collabmark.lib.logger.logging.getLogger") as mock_get:
                    mock_get.return_value = test_logger
                    setup_logging(log_to_file=True)

        assert (tmp_path / "logs").is_dir()

    def test_no_file_handler_when_disabled(self) -> None:
        log_name = "collabmark.test_no_file"
        test_logger = logging.getLogger(log_name)
        test_logger.handlers.clear()

        with patch("collabmark.lib.logger.logging.getLogger") as mock_get:
            mock_get.return_value = test_logger
            setup_logging(log_to_file=False)

        from logging.handlers import RotatingFileHandler

        file_handlers = [h for h in test_logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 0
