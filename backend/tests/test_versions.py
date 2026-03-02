"""Tests for version history: create snapshots, list, retrieve versions."""

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.models.document import Document_
from app.models.user import User


def _auth_cookies(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"access_token": token}


async def _make_doc(owner: User, title: str = "Versioned Doc") -> Document_:
    doc = Document_(title=title, content="# Initial", owner_id=str(owner.id))
    await doc.insert()
    return doc


class TestCreateVersion:
    @pytest.mark.asyncio
    async def test_create_version(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp = await async_client.post(
            f"/api/documents/{doc.id}/versions",
            json={"content": "# Version 1", "summary": "First save"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["version_number"] == 1
        assert data["content"] == "# Version 1"
        assert data["author_name"] == "Test User"
        assert data["summary"] == "First save"

    @pytest.mark.asyncio
    async def test_version_numbers_increment(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp1 = await async_client.post(
            f"/api/documents/{doc.id}/versions",
            json={"content": "v1"},
        )
        assert resp1.json()["version_number"] == 1

        resp2 = await async_client.post(
            f"/api/documents/{doc.id}/versions",
            json={"content": "v2"},
        )
        assert resp2.json()["version_number"] == 2

        resp3 = await async_client.post(
            f"/api/documents/{doc.id}/versions",
            json={"content": "v3"},
        )
        assert resp3.json()["version_number"] == 3

    @pytest.mark.asyncio
    async def test_auto_summary_when_empty(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp = await async_client.post(
            f"/api/documents/{doc.id}/versions",
            json={"content": "auto summary test"},
        )
        assert "Version 1 by Test User" in resp.json()["summary"]


class TestListVersions:
    @pytest.mark.asyncio
    async def test_list_versions_descending(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        for i in range(3):
            await async_client.post(
                f"/api/documents/{doc.id}/versions",
                json={"content": f"content-{i}"},
            )

        resp = await async_client.get(f"/api/documents/{doc.id}/versions")
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) == 3
        assert versions[0]["version_number"] == 3
        assert versions[1]["version_number"] == 2
        assert versions[2]["version_number"] == 1

    @pytest.mark.asyncio
    async def test_list_excludes_content(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        await async_client.post(
            f"/api/documents/{doc.id}/versions",
            json={"content": "should not appear in list"},
        )

        resp = await async_client.get(f"/api/documents/{doc.id}/versions")
        item = resp.json()[0]
        assert "content" not in item
        assert "version_number" in item
        assert "author_name" in item

    @pytest.mark.asyncio
    async def test_empty_version_list(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp = await async_client.get(f"/api/documents/{doc.id}/versions")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetVersion:
    @pytest.mark.asyncio
    async def test_get_specific_version(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        await async_client.post(
            f"/api/documents/{doc.id}/versions",
            json={"content": "v1-content"},
        )
        await async_client.post(
            f"/api/documents/{doc.id}/versions",
            json={"content": "v2-content"},
        )

        resp = await async_client.get(f"/api/documents/{doc.id}/versions/1")
        assert resp.status_code == 200
        assert resp.json()["content"] == "v1-content"
        assert resp.json()["version_number"] == 1

        resp2 = await async_client.get(f"/api/documents/{doc.id}/versions/2")
        assert resp2.json()["content"] == "v2-content"

    @pytest.mark.asyncio
    async def test_get_nonexistent_version(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp = await async_client.get(f"/api/documents/{doc.id}/versions/999")
        assert resp.status_code == 404


class TestAutoVersionOnSave:
    @pytest.mark.asyncio
    async def test_update_content_creates_version(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        await async_client.put(
            f"/api/documents/{doc.id}",
            json={"content": "Updated content"},
        )

        resp = await async_client.get(f"/api/documents/{doc.id}/versions")
        versions = resp.json()
        assert len(versions) == 1
        assert versions[0]["version_number"] == 1

    @pytest.mark.asyncio
    async def test_title_only_update_no_version(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        await async_client.put(
            f"/api/documents/{doc.id}",
            json={"title": "New Title"},
        )

        resp = await async_client.get(f"/api/documents/{doc.id}/versions")
        assert resp.json() == []
