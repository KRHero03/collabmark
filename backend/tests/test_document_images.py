"""Tests for document image upload endpoint (POST /api/documents/{doc_id}/images)."""

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
    user = User(google_id="owner-img", email="owner@img.test", name="Owner")
    await user.insert()
    return user


@pytest.fixture
async def editor_user():
    user = User(google_id="editor-img", email="editor@img.test", name="Editor")
    await user.insert()
    return user


@pytest.fixture
async def viewer_user():
    user = User(google_id="viewer-img", email="viewer@img.test", name="Viewer")
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


def _make_png(size: int = 100) -> bytes:
    """Create a minimal valid PNG-like blob of a given size."""
    header = b"\x89PNG\r\n\x1a\n"
    return header + b"\x00" * (size - len(header))


@pytest.mark.asyncio
async def test_upload_image_as_owner(async_client: AsyncClient, owner, doc):
    """Owner can upload an image to their document."""
    with (
        patch("app.services.blob_storage.upload", return_value="documents/x/img.png") as mock_upload,
        patch("app.services.blob_storage.get_public_url", return_value="/media/documents/x/img.png"),
    ):
        resp = await async_client.post(
            f"/api/documents/{doc.id}/images",
            files={"file": ("screenshot.png", _make_png(), "image/png")},
            cookies=_auth_cookies(owner),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "url" in data
    assert "name" in data
    assert data["url"].startswith("/media/documents/")
    assert data["name"].endswith(".png")
    mock_upload.assert_called_once()


@pytest.mark.asyncio
async def test_upload_image_as_editor(async_client: AsyncClient, editor_user, doc_with_editor):
    """User with EDIT access can upload images."""
    with (
        patch("app.services.blob_storage.upload", return_value="documents/x/img.png"),
        patch("app.services.blob_storage.get_public_url", return_value="/media/documents/x/img.png"),
    ):
        resp = await async_client.post(
            f"/api/documents/{doc_with_editor.id}/images",
            files={"file": ("photo.jpg", _make_png(), "image/jpeg")},
            cookies=_auth_cookies(editor_user),
        )
    assert resp.status_code == 200
    assert resp.json()["name"].endswith(".jpg")


@pytest.mark.asyncio
async def test_upload_image_as_viewer_returns_403(async_client: AsyncClient, viewer_user, doc_with_viewer):
    """User with only VIEW access cannot upload images."""
    resp = await async_client.post(
        f"/api/documents/{doc_with_viewer.id}/images",
        files={"file": ("screenshot.png", _make_png(), "image/png")},
        cookies=_auth_cookies(viewer_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_upload_image_unauthenticated_returns_401(async_client: AsyncClient, doc):
    """Unauthenticated requests are rejected."""
    resp = await async_client.post(
        f"/api/documents/{doc.id}/images",
        files={"file": ("screenshot.png", _make_png(), "image/png")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_image_nonexistent_doc_returns_404(async_client: AsyncClient, owner):
    """Uploading to a non-existent document returns 404."""
    resp = await async_client.post(
        "/api/documents/000000000000000000000000/images",
        files={"file": ("screenshot.png", _make_png(), "image/png")},
        cookies=_auth_cookies(owner),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_unsupported_extension_returns_400(async_client: AsyncClient, owner, doc):
    """Unsupported file types are rejected."""
    resp = await async_client.post(
        f"/api/documents/{doc.id}/images",
        files={"file": ("script.exe", b"malware", "application/octet-stream")},
        cookies=_auth_cookies(owner),
    )
    assert resp.status_code == 400
    assert "Unsupported image type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_oversized_image_returns_400(async_client: AsyncClient, owner, doc):
    """Images exceeding 5MB are rejected."""
    big_image = _make_png(6 * 1024 * 1024)
    resp = await async_client.post(
        f"/api/documents/{doc.id}/images",
        files={"file": ("huge.png", big_image, "image/png")},
        cookies=_auth_cookies(owner),
    )
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_each_allowed_extension(async_client: AsyncClient, owner, doc):
    """All allowed extensions are accepted."""
    for ext, mime in [
        (".png", "image/png"),
        (".jpg", "image/jpeg"),
        (".jpeg", "image/jpeg"),
        (".gif", "image/gif"),
        (".webp", "image/webp"),
    ]:
        with (
            patch("app.services.blob_storage.upload"),
            patch("app.services.blob_storage.get_public_url", return_value=f"/media/documents/x/img{ext}"),
        ):
            resp = await async_client.post(
                f"/api/documents/{doc.id}/images",
                files={"file": (f"img{ext}", _make_png(), mime)},
                cookies=_auth_cookies(owner),
            )
        assert resp.status_code == 200, f"Failed for extension {ext}"


@pytest.mark.asyncio
async def test_upload_image_uuid_filename(async_client: AsyncClient, owner, doc):
    """Returned name is a UUID-based filename, not the original."""
    with (
        patch("app.services.blob_storage.upload"),
        patch("app.services.blob_storage.get_public_url", return_value="/media/documents/x/abc.png"),
    ):
        resp = await async_client.post(
            f"/api/documents/{doc.id}/images",
            files={"file": ("my_screenshot_2024.png", _make_png(), "image/png")},
            cookies=_auth_cookies(owner),
        )
    data = resp.json()
    assert data["name"] != "my_screenshot_2024.png"
    assert len(data["name"]) > 10
