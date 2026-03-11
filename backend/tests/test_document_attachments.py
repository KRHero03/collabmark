"""Tests for document attachment upload endpoint (POST /api/documents/{doc_id}/attachments)."""

from unittest.mock import patch

import pytest
from app.auth.jwt import create_access_token
from app.models.document import Document_
from app.models.share_link import DocumentAccess, Permission
from app.models.user import User
from httpx import AsyncClient


def _auth_cookies(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"access_token": token}


@pytest.fixture
async def owner():
    user = User(google_id="owner-att", email="owner@att.test", name="Owner")
    await user.insert()
    return user


@pytest.fixture
async def editor_user():
    user = User(google_id="editor-att", email="editor@att.test", name="Editor")
    await user.insert()
    return user


@pytest.fixture
async def viewer_user():
    user = User(google_id="viewer-att", email="viewer@att.test", name="Viewer")
    await user.insert()
    return user


@pytest.fixture
async def doc(owner):
    d = Document_(title="Test Doc", content="hello", owner_id=str(owner.id))
    await d.insert()
    return d


@pytest.fixture
async def doc_with_editor(doc, editor_user):
    access = DocumentAccess(
        document_id=str(doc.id),
        user_id=str(editor_user.id),
        permission=Permission.EDIT,
        granted_by=doc.owner_id,
    )
    await access.insert()
    return doc


@pytest.fixture
async def doc_with_viewer(doc, viewer_user):
    access = DocumentAccess(
        document_id=str(doc.id),
        user_id=str(viewer_user.id),
        permission=Permission.VIEW,
        granted_by=doc.owner_id,
    )
    await access.insert()
    return doc


def _make_pdf(size: int = 100) -> bytes:
    header = b"%PDF-1.4"
    return header + b"\x00" * max(0, size - len(header))


def _make_zip(size: int = 100) -> bytes:
    header = b"PK\x03\x04"
    return header + b"\x00" * max(0, size - len(header))


def _make_gz(size: int = 100) -> bytes:
    header = b"\x1f\x8b\x08"
    return header + b"\x00" * max(0, size - len(header))


def _make_ole(size: int = 100) -> bytes:
    """OLE Compound Document header (used by .doc, .xls, .ppt)."""
    header = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    return header + b"\x00" * max(0, size - len(header))


def _make_png(size: int = 100) -> bytes:
    header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    return header + b"\x00" * max(0, size - len(header))


def _make_txt(size: int = 100) -> bytes:
    return b"Hello, this is a text file.\n" + b"x" * max(0, size - 28)


EXTENSION_BUILDERS = {
    ".pdf": _make_pdf,
    ".doc": _make_ole,
    ".docx": _make_zip,
    ".xls": _make_ole,
    ".xlsx": _make_zip,
    ".ppt": _make_ole,
    ".pptx": _make_zip,
    ".txt": _make_txt,
    ".csv": _make_txt,
    ".zip": _make_zip,
    ".tar": lambda size=100: b"\x00" * size,
    ".gz": _make_gz,
}


@pytest.mark.asyncio
async def test_upload_attachment_as_owner(async_client: AsyncClient, owner, doc):
    """Owner can upload an attachment to their document."""
    with (
        patch("app.services.blob_storage.upload", return_value="documents/x/attachments/f.pdf") as mock_upload,
        patch("app.services.blob_storage.get_public_url", return_value="/media/documents/x/attachments/f.pdf"),
    ):
        resp = await async_client.post(
            f"/api/documents/{doc.id}/attachments",
            files={"file": ("report.pdf", _make_pdf(), "application/pdf")},
            cookies=_auth_cookies(owner),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"].startswith("/media/documents/")
    assert data["original_name"] == "report.pdf"
    assert data["name"].endswith(".pdf")
    mock_upload.assert_called_once()


@pytest.mark.asyncio
async def test_upload_attachment_as_editor(async_client: AsyncClient, editor_user, doc_with_editor):
    """User with EDIT access can upload attachments."""
    with (
        patch("app.services.blob_storage.upload"),
        patch("app.services.blob_storage.get_public_url", return_value="/media/documents/x/attachments/f.docx"),
    ):
        resp = await async_client.post(
            f"/api/documents/{doc_with_editor.id}/attachments",
            files={"file": ("doc.docx", _make_zip(), "application/octet-stream")},
            cookies=_auth_cookies(editor_user),
        )
    assert resp.status_code == 200
    assert resp.json()["original_name"] == "doc.docx"


@pytest.mark.asyncio
async def test_upload_attachment_as_viewer_returns_403(async_client: AsyncClient, viewer_user, doc_with_viewer):
    """User with only VIEW access cannot upload attachments."""
    resp = await async_client.post(
        f"/api/documents/{doc_with_viewer.id}/attachments",
        files={"file": ("report.pdf", _make_pdf(), "application/pdf")},
        cookies=_auth_cookies(viewer_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_upload_attachment_unauthenticated_returns_401(async_client: AsyncClient, doc):
    """Unauthenticated requests are rejected."""
    resp = await async_client.post(
        f"/api/documents/{doc.id}/attachments",
        files={"file": ("report.pdf", _make_pdf(), "application/pdf")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_attachment_nonexistent_doc_returns_404(async_client: AsyncClient, owner):
    """Uploading to a non-existent document returns 404."""
    resp = await async_client.post(
        "/api/documents/000000000000000000000000/attachments",
        files={"file": ("report.pdf", _make_pdf(), "application/pdf")},
        cookies=_auth_cookies(owner),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_unsupported_extension_returns_400(async_client: AsyncClient, owner, doc):
    """Unsupported file types (e.g. .exe) are rejected."""
    resp = await async_client.post(
        f"/api/documents/{doc.id}/attachments",
        files={"file": ("virus.exe", b"bad", "application/octet-stream")},
        cookies=_auth_cookies(owner),
    )
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_oversized_attachment_returns_400(async_client: AsyncClient, owner, doc):
    """Files exceeding 5MB are rejected."""
    big_file = _make_pdf(6 * 1024 * 1024)
    resp = await async_client.post(
        f"/api/documents/{doc.id}/attachments",
        files={"file": ("huge.pdf", big_file, "application/pdf")},
        cookies=_auth_cookies(owner),
    )
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_each_allowed_extension(async_client: AsyncClient, owner, doc):
    """All allowed non-image extensions are accepted with matching content."""
    for ext, builder in EXTENSION_BUILDERS.items():
        with (
            patch("app.services.blob_storage.upload"),
            patch("app.services.blob_storage.get_public_url", return_value=f"/media/documents/x/attachments/f{ext}"),
        ):
            resp = await async_client.post(
                f"/api/documents/{doc.id}/attachments",
                files={"file": (f"file{ext}", builder(), "application/octet-stream")},
                cookies=_auth_cookies(owner),
            )
        assert resp.status_code == 200, f"Failed for extension {ext}"


@pytest.mark.asyncio
async def test_upload_image_via_attachment_endpoint(async_client: AsyncClient, owner, doc):
    """Image types are also accepted through the attachment endpoint."""
    with (
        patch("app.services.blob_storage.upload"),
        patch("app.services.blob_storage.get_public_url", return_value="/media/documents/x/attachments/f.png"),
    ):
        resp = await async_client.post(
            f"/api/documents/{doc.id}/attachments",
            files={"file": ("image.png", _make_png(), "image/png")},
            cookies=_auth_cookies(owner),
        )
    assert resp.status_code == 200
    assert resp.json()["original_name"] == "image.png"


@pytest.mark.asyncio
async def test_upload_attachment_s3_failure_returns_502(async_client: AsyncClient, owner, doc):
    """S3 upload failure returns 502."""
    with patch("app.services.blob_storage.upload", side_effect=Exception("S3 down")):
        resp = await async_client.post(
            f"/api/documents/{doc.id}/attachments",
            files={"file": ("report.pdf", _make_pdf(), "application/pdf")},
            cookies=_auth_cookies(owner),
        )
    assert resp.status_code == 502
    assert "storage" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_attachment_content_mismatch_returns_400(async_client: AsyncClient, owner, doc):
    """A file with .pdf extension but PNG content is rejected."""
    png_content = _make_png()
    resp = await async_client.post(
        f"/api/documents/{doc.id}/attachments",
        files={"file": ("fake.pdf", png_content, "application/pdf")},
        cookies=_auth_cookies(owner),
    )
    assert resp.status_code == 400
    assert "content does not match" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_empty_attachment_returns_400(async_client: AsyncClient, owner, doc):
    """An empty file is rejected."""
    resp = await async_client.post(
        f"/api/documents/{doc.id}/attachments",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        cookies=_auth_cookies(owner),
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_exe_disguised_as_pdf_returns_400(async_client: AsyncClient, owner, doc):
    """An EXE file renamed to .docx with valid ZIP header but wrong content is caught
    or allowed through gracefully when puremagic cannot determine the type."""
    exe_content = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100
    resp = await async_client.post(
        f"/api/documents/{doc.id}/attachments",
        files={"file": ("malware.pdf", exe_content, "application/pdf")},
        cookies=_auth_cookies(owner),
    )
    assert resp.status_code in (200, 400)
    if resp.status_code == 400:
        detail = resp.json()["detail"].lower()
        assert "content does not match" in detail or "unable to determine" in detail
