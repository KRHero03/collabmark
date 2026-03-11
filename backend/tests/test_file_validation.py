"""Unit tests for validate_file_content (puremagic-based content validation)."""

import struct

import pytest
from app.services.document_service import validate_file_content
from fastapi import HTTPException


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"


def _jpeg() -> bytes:
    return b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100


def _gif() -> bytes:
    return b"GIF87a" + b"\x00" * 100


def _webp() -> bytes:
    body = b"\x00" * 88
    return b"RIFF" + struct.pack("<I", len(body) + 4) + b"WEBP" + body


def _pdf() -> bytes:
    return b"%PDF-1.4" + b"\x00" * 100


def _zip() -> bytes:
    return b"PK\x03\x04" + b"\x00" * 100


def _ole() -> bytes:
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100


def _gz() -> bytes:
    return b"\x1f\x8b\x08" + b"\x00" * 100


class TestValidFileContent:
    """Content that matches its claimed extension passes validation."""

    def test_png(self):
        validate_file_content(_png(), ".png")

    def test_jpeg_as_jpg(self):
        validate_file_content(_jpeg(), ".jpg")

    def test_jpeg_as_jpeg(self):
        validate_file_content(_jpeg(), ".jpeg")

    def test_gif(self):
        validate_file_content(_gif(), ".gif")

    def test_webp(self):
        validate_file_content(_webp(), ".webp")

    def test_pdf(self):
        validate_file_content(_pdf(), ".pdf")

    def test_zip(self):
        validate_file_content(_zip(), ".zip")

    def test_docx_zip_header(self):
        validate_file_content(_zip(), ".docx")

    def test_xlsx_zip_header(self):
        validate_file_content(_zip(), ".xlsx")

    def test_pptx_zip_header(self):
        validate_file_content(_zip(), ".pptx")

    def test_doc_ole(self):
        validate_file_content(_ole(), ".doc")

    def test_xls_ole(self):
        validate_file_content(_ole(), ".xls")

    def test_ppt_ole(self):
        validate_file_content(_ole(), ".ppt")

    def test_gz(self):
        validate_file_content(_gz(), ".gz")


class TestTextFormatsSkipped:
    """Text-based formats with weak magic signatures are skipped."""

    def test_txt_passes(self):
        validate_file_content(b"Hello world\n", ".txt")

    def test_csv_passes(self):
        validate_file_content(b"a,b,c\n1,2,3\n", ".csv")

    def test_tar_passes(self):
        validate_file_content(b"\x00" * 300, ".tar")


class TestContentMismatch:
    """Content that does NOT match its claimed extension is rejected."""

    def test_pdf_content_claimed_png(self):
        with pytest.raises(HTTPException) as exc:
            validate_file_content(_pdf(), ".png")
        assert exc.value.status_code == 400
        assert "content does not match" in exc.value.detail.lower()

    def test_png_content_claimed_pdf(self):
        with pytest.raises(HTTPException) as exc:
            validate_file_content(_png(), ".pdf")
        assert exc.value.status_code == 400
        assert "content does not match" in exc.value.detail.lower()

    def test_gif_content_claimed_jpeg(self):
        with pytest.raises(HTTPException) as exc:
            validate_file_content(_gif(), ".jpg")
        assert exc.value.status_code == 400
        assert "content does not match" in exc.value.detail.lower()

    def test_gz_content_claimed_zip(self):
        with pytest.raises(HTTPException) as exc:
            validate_file_content(_gz(), ".zip")
        assert exc.value.status_code == 400
        assert "content does not match" in exc.value.detail.lower()


class TestEmptyFile:
    """Empty file content is always rejected."""

    def test_empty_png(self):
        with pytest.raises(HTTPException) as exc:
            validate_file_content(b"", ".png")
        assert exc.value.status_code == 400
        assert "empty" in exc.value.detail.lower()

    def test_empty_pdf(self):
        with pytest.raises(HTTPException) as exc:
            validate_file_content(b"", ".pdf")
        assert exc.value.status_code == 400
        assert "empty" in exc.value.detail.lower()


class TestUnknownExtension:
    """Extensions not in the MIME map are allowed through (the allowlist already filters them)."""

    def test_unknown_extension_passes(self):
        validate_file_content(b"some random data", ".xyz")
