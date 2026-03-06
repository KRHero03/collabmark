"""Tests for the recently viewed feature: record views and list recently viewed docs."""

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.models.document import Document_, GeneralAccess
from app.models.document_view import DocumentView
from app.models.share_link import DocumentAccess, Permission
from app.models.user import User


def _auth_cookies(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"access_token": token}


async def _make_user(google_id: str, email: str, name: str) -> User:
    user = User(google_id=google_id, email=email, name=name)
    await user.insert()
    return user


async def _make_doc(
    owner: User,
    title: str = "Test Doc",
    general_access: GeneralAccess = GeneralAccess.ANYONE_VIEW,
) -> Document_:
    doc = Document_(
        title=title,
        content="# Hello",
        owner_id=str(owner.id),
        general_access=general_access,
    )
    await doc.insert()
    return doc


class TestRecordView:
    """Tests for POST /api/documents/{doc_id}/view."""

    @pytest.mark.asyncio
    async def test_record_view_returns_204(
        self, async_client: AsyncClient, test_user: User
    ):
        owner = await _make_user("owner-1", "owner@test.com", "Owner")
        doc = await _make_doc(owner)
        async_client.cookies.update(_auth_cookies(test_user))

        resp = await async_client.post(f"/api/documents/{doc.id}/view")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_record_view_creates_document_view_record(
        self, async_client: AsyncClient, test_user: User
    ):
        owner = await _make_user("owner-2", "owner2@test.com", "Owner2")
        doc = await _make_doc(owner)
        async_client.cookies.update(_auth_cookies(test_user))

        await async_client.post(f"/api/documents/{doc.id}/view")

        view = await DocumentView.find_one(
            DocumentView.user_id == str(test_user.id),
            DocumentView.document_id == str(doc.id),
        )
        assert view is not None
        assert view.user_id == str(test_user.id)
        assert view.document_id == str(doc.id)

    @pytest.mark.asyncio
    async def test_record_view_records_own_document(
        self, async_client: AsyncClient, test_user: User
    ):
        doc = await _make_doc(test_user, title="My Own Doc")
        async_client.cookies.update(_auth_cookies(test_user))

        await async_client.post(f"/api/documents/{doc.id}/view")

        count = await DocumentView.find(
            DocumentView.user_id == str(test_user.id),
        ).count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_record_view_updates_timestamp_on_revisit(
        self, async_client: AsyncClient, test_user: User
    ):
        owner = await _make_user("owner-3", "owner3@test.com", "Owner3")
        doc = await _make_doc(owner)
        async_client.cookies.update(_auth_cookies(test_user))

        await async_client.post(f"/api/documents/{doc.id}/view")
        view1 = await DocumentView.find_one(
            DocumentView.user_id == str(test_user.id),
            DocumentView.document_id == str(doc.id),
        )
        first_viewed_at = view1.viewed_at

        await async_client.post(f"/api/documents/{doc.id}/view")
        view2 = await DocumentView.find_one(
            DocumentView.user_id == str(test_user.id),
            DocumentView.document_id == str(doc.id),
        )
        assert view2.viewed_at >= first_viewed_at

        total = await DocumentView.find(
            DocumentView.user_id == str(test_user.id),
            DocumentView.document_id == str(doc.id),
        ).count()
        assert total == 1

    @pytest.mark.asyncio
    async def test_record_view_nonexistent_doc_returns_403(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.post("/api/documents/000000000000000000000000/view")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_record_view_invalid_doc_id_returns_403(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.post("/api/documents/not-a-valid-id/view")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_record_view_unauthenticated_returns_401(
        self, async_client: AsyncClient
    ):
        resp = await async_client.post("/api/documents/000000000000000000000000/view")
        assert resp.status_code == 401


class TestListRecentlyViewed:
    """Tests for GET /api/documents/recent."""

    @pytest.mark.asyncio
    async def test_empty_list_when_no_views(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.get("/api/documents/recent")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_lists_viewed_documents(
        self, async_client: AsyncClient, test_user: User
    ):
        owner = await _make_user("owner-4", "owner4@test.com", "Owner4")
        doc = await _make_doc(owner, title="Viewed Doc")
        async_client.cookies.update(_auth_cookies(test_user))

        await async_client.post(f"/api/documents/{doc.id}/view")
        resp = await async_client.get("/api/documents/recent")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == str(doc.id)
        assert data[0]["title"] == "Viewed Doc"
        assert data[0]["owner_name"] == "Owner4"
        assert data[0]["owner_email"] == "owner4@test.com"
        assert data[0]["permission"] == "view"

    @pytest.mark.asyncio
    async def test_sorted_by_most_recently_viewed(
        self, async_client: AsyncClient, test_user: User
    ):
        owner = await _make_user("owner-5", "owner5@test.com", "Owner5")
        doc_a = await _make_doc(owner, title="Doc A")
        doc_b = await _make_doc(owner, title="Doc B")
        async_client.cookies.update(_auth_cookies(test_user))

        await async_client.post(f"/api/documents/{doc_a.id}/view")
        await async_client.post(f"/api/documents/{doc_b.id}/view")

        resp = await async_client.get("/api/documents/recent")
        data = resp.json()
        assert len(data) == 2
        assert data[0]["title"] == "Doc B"
        assert data[1]["title"] == "Doc A"

    @pytest.mark.asyncio
    async def test_includes_own_documents(
        self, async_client: AsyncClient, test_user: User
    ):
        doc = await _make_doc(test_user, title="My Doc")
        async_client.cookies.update(_auth_cookies(test_user))

        await async_client.post(f"/api/documents/{doc.id}/view")
        resp = await async_client.get("/api/documents/recent")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == str(doc.id)
        assert data[0]["title"] == "My Doc"

    @pytest.mark.asyncio
    async def test_does_not_include_deleted_documents(
        self, async_client: AsyncClient, test_user: User
    ):
        owner = await _make_user("owner-6", "owner6@test.com", "Owner6")
        doc = await _make_doc(owner, title="Deleted Doc")
        async_client.cookies.update(_auth_cookies(test_user))

        await async_client.post(f"/api/documents/{doc.id}/view")

        doc.soft_delete()
        await doc.save()

        resp = await async_client.get("/api/documents/recent")
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_does_not_include_docs_user_lost_access_to(
        self, async_client: AsyncClient, test_user: User
    ):
        owner = await _make_user("owner-7", "owner7@test.com", "Owner7")
        doc = await _make_doc(owner, title="Was Public", general_access=GeneralAccess.ANYONE_VIEW)
        async_client.cookies.update(_auth_cookies(test_user))

        await async_client.post(f"/api/documents/{doc.id}/view")

        doc.general_access = GeneralAccess.RESTRICTED
        await doc.save()

        resp = await async_client.get("/api/documents/recent")
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_shows_edit_permission_for_anyone_edit_doc(
        self, async_client: AsyncClient, test_user: User
    ):
        owner = await _make_user("owner-8", "owner8@test.com", "Owner8")
        doc = await _make_doc(owner, title="Editable Doc", general_access=GeneralAccess.ANYONE_EDIT)
        async_client.cookies.update(_auth_cookies(test_user))

        await async_client.post(f"/api/documents/{doc.id}/view")
        resp = await async_client.get("/api/documents/recent")

        data = resp.json()
        assert len(data) == 1
        assert data[0]["permission"] == "edit"

    @pytest.mark.asyncio
    async def test_own_document_shows_edit_permission(
        self, async_client: AsyncClient, test_user: User
    ):
        doc = await _make_doc(test_user, title="My Own Doc")
        async_client.cookies.update(_auth_cookies(test_user))

        await async_client.post(f"/api/documents/{doc.id}/view")
        resp = await async_client.get("/api/documents/recent")

        data = resp.json()
        assert len(data) == 1
        assert data[0]["permission"] == "edit"

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, async_client: AsyncClient):
        resp = await async_client.get("/api/documents/recent")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_explicit_collaborator_doc_appears_in_recent(
        self, async_client: AsyncClient, test_user: User
    ):
        owner = await _make_user("owner-9", "owner9@test.com", "Owner9")
        doc = await _make_doc(owner, title="Collab Doc", general_access=GeneralAccess.RESTRICTED)
        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(test_user.id),
            permission=Permission.EDIT,
            granted_by=str(owner.id),
        )
        await access.insert()
        async_client.cookies.update(_auth_cookies(test_user))

        await async_client.post(f"/api/documents/{doc.id}/view")
        resp = await async_client.get("/api/documents/recent")

        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Collab Doc"
        assert data[0]["permission"] == "edit"

    @pytest.mark.asyncio
    async def test_revisit_moves_doc_to_top(
        self, async_client: AsyncClient, test_user: User
    ):
        owner = await _make_user("owner-10", "owner10@test.com", "Owner10")
        doc_a = await _make_doc(owner, title="First Doc")
        doc_b = await _make_doc(owner, title="Second Doc")
        async_client.cookies.update(_auth_cookies(test_user))

        await async_client.post(f"/api/documents/{doc_a.id}/view")
        await async_client.post(f"/api/documents/{doc_b.id}/view")
        await async_client.post(f"/api/documents/{doc_a.id}/view")

        resp = await async_client.get("/api/documents/recent")
        data = resp.json()
        assert data[0]["title"] == "First Doc"
        assert data[1]["title"] == "Second Doc"
