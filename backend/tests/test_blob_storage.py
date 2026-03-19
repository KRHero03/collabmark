"""Tests for blob storage local filesystem fallback."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from app.services import blob_storage

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _mock_blob_storage():
    """Override conftest's autouse mock so we test the real implementation."""
    yield


class TestLocalFileStore:
    """Verify upload/get/delete when S3 is disabled (local filesystem)."""

    @pytest.fixture(autouse=True)
    def _use_local_backend(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(blob_storage, "_is_local", lambda: True)
        monkeypatch.setattr(blob_storage, "_LOCAL_MEDIA_ROOT", tmp_path)
        return tmp_path

    def test_upload_creates_file(self, _use_local_backend: Path):
        root = _use_local_backend
        key = blob_storage.upload("logos/org1.png", b"PNG_DATA", "image/png")
        assert key == "logos/org1.png"
        assert (root / "logos" / "org1.png").read_bytes() == b"PNG_DATA"

    def test_get_object_returns_content(self, _use_local_backend: Path):
        root = _use_local_backend
        (root / "docs").mkdir()
        (root / "docs" / "test.txt").write_bytes(b"hello")
        result = blob_storage.get_object("docs/test.txt")
        assert result is not None
        assert result["Body"].read() == b"hello"

    def test_get_object_returns_none_for_missing(self):
        result = blob_storage.get_object("nonexistent/file.txt")
        assert result is None

    def test_delete_prefix_removes_files(self, _use_local_backend: Path):
        root = _use_local_backend
        (root / "logos").mkdir()
        (root / "logos" / "org1.png").write_bytes(b"A")
        (root / "logos" / "org1.svg").write_bytes(b"B")
        (root / "logos" / "org2.png").write_bytes(b"C")

        blob_storage.delete_prefix("logos/org1")

        assert not (root / "logos" / "org1.png").exists()
        assert not (root / "logos" / "org1.svg").exists()
        assert (root / "logos" / "org2.png").exists()

    def test_delete_prefix_handles_missing_dir(self):
        blob_storage.delete_prefix("nonexistent/path")

    def test_get_public_url_format(self):
        url = blob_storage.get_public_url("logos/test.png")
        assert url == "/media/logos/test.png"

    def test_upload_creates_nested_directories(self, _use_local_backend: Path):
        root = _use_local_backend
        blob_storage.upload("a/b/c/file.txt", b"deep", "text/plain")
        assert (root / "a" / "b" / "c" / "file.txt").read_bytes() == b"deep"

    def test_upload_overwrites_existing(self, _use_local_backend: Path):
        root = _use_local_backend
        blob_storage.upload("file.bin", b"first", "application/octet-stream")
        blob_storage.upload("file.bin", b"second", "application/octet-stream")
        assert (root / "file.bin").read_bytes() == b"second"
