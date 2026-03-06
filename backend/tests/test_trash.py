"""Tests for trash list, hard delete, and related cleanup."""

import pytest
from app.auth.jwt import create_access_token
from app.models.comment import Comment
from app.models.document_version import DocumentVersion
from app.models.document_view import DocumentView
from app.models.share_link import DocumentAccess, Permission
from app.models.user import User
from httpx import AsyncClient


def _auth_cookies(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"access_token": token}


async def _create_doc(client: AsyncClient, title: str = "Test Doc", content: str = "") -> dict:
    resp = await client.post("/api/documents", json={"title": title, "content": content})
    assert resp.status_code == 201
    return resp.json()


class TestListTrash:
    @pytest.mark.asyncio
    async def test_empty_trash(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.get("/api/documents/trash")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_trash_returns_only_deleted_docs(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc1 = await _create_doc(async_client, "Active Doc")
        doc2 = await _create_doc(async_client, "Trashed Doc")

        await async_client.delete(f"/api/documents/{doc2['id']}")

        resp = await async_client.get("/api/documents/trash")
        assert resp.status_code == 200
        trash = resp.json()
        assert len(trash) == 1
        assert trash[0]["id"] == doc2["id"]
        assert trash[0]["title"] == "Trashed Doc"
        assert trash[0]["is_deleted"] is True

        active_resp = await async_client.get("/api/documents")
        active_ids = [d["id"] for d in active_resp.json()]
        assert doc1["id"] in active_ids
        assert doc2["id"] not in active_ids

    @pytest.mark.asyncio
    async def test_trash_sorted_by_deleted_at_desc(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc1 = await _create_doc(async_client, "First Deleted")
        doc2 = await _create_doc(async_client, "Second Deleted")
        doc3 = await _create_doc(async_client, "Third Deleted")

        await async_client.delete(f"/api/documents/{doc1['id']}")
        await async_client.delete(f"/api/documents/{doc2['id']}")
        await async_client.delete(f"/api/documents/{doc3['id']}")

        resp = await async_client.get("/api/documents/trash")
        trash = resp.json()
        assert len(trash) == 3
        assert trash[0]["id"] == doc3["id"]
        assert trash[1]["id"] == doc2["id"]
        assert trash[2]["id"] == doc1["id"]

    @pytest.mark.asyncio
    async def test_trash_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.get("/api/documents/trash")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_trash_excludes_other_users_docs(self, async_client: AsyncClient, test_user: User):
        other_user = User(
            google_id="google-other-456",
            email="other@example.com",
            name="Other User",
        )
        await other_user.insert()

        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "My Doc")
        await async_client.delete(f"/api/documents/{doc['id']}")

        async_client.cookies.update(_auth_cookies(other_user))
        resp = await async_client.get("/api/documents/trash")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_trash_includes_deleted_at_and_content_length(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "Info Doc", content="Hello World")
        await async_client.delete(f"/api/documents/{doc['id']}")

        resp = await async_client.get("/api/documents/trash")
        trash = resp.json()
        assert len(trash) == 1
        assert trash[0]["deleted_at"] is not None
        assert trash[0]["content_length"] == len("Hello World")

    @pytest.mark.asyncio
    async def test_restored_doc_disappears_from_trash(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "Restore Me")
        await async_client.delete(f"/api/documents/{doc['id']}")

        trash_resp = await async_client.get("/api/documents/trash")
        assert len(trash_resp.json()) == 1

        await async_client.post(f"/api/documents/{doc['id']}/restore")

        trash_resp = await async_client.get("/api/documents/trash")
        assert trash_resp.json() == []


class TestHardDelete:
    @pytest.mark.asyncio
    async def test_hard_delete_removes_document(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "Delete Me Forever")

        resp = await async_client.delete(f"/api/documents/{doc['id']}/permanent")
        assert resp.status_code == 204

        get_resp = await async_client.get(f"/api/documents/{doc['id']}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_hard_delete_trashed_doc(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "Trash Then Nuke")
        await async_client.delete(f"/api/documents/{doc['id']}")

        resp = await async_client.delete(f"/api/documents/{doc['id']}/permanent")
        assert resp.status_code == 204

        trash_resp = await async_client.get("/api/documents/trash")
        assert doc["id"] not in [d["id"] for d in trash_resp.json()]

    @pytest.mark.asyncio
    async def test_hard_delete_nonexistent(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.delete("/api/documents/000000000000000000000000/permanent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_hard_delete_non_owner(self, async_client: AsyncClient, test_user: User):
        other_user = User(
            google_id="google-nonowner-789",
            email="nonowner@example.com",
            name="Non Owner",
        )
        await other_user.insert()

        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "Not Yours")

        async_client.cookies.update(_auth_cookies(other_user))
        resp = await async_client.delete(f"/api/documents/{doc['id']}/permanent")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_hard_delete_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.delete("/api/documents/000000000000000000000000/permanent")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_hard_delete_invalid_id(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.delete("/api/documents/not-an-id/permanent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_hard_delete_does_not_affect_other_docs(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc1 = await _create_doc(async_client, "Keep Me")
        doc2 = await _create_doc(async_client, "Delete Me")

        await async_client.delete(f"/api/documents/{doc2['id']}/permanent")

        get_resp = await async_client.get(f"/api/documents/{doc1['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "Keep Me"


class TestHardDeleteCleanup:
    @pytest.mark.asyncio
    async def test_cleans_up_comments(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client)
        doc_id = doc["id"]

        comment = Comment(
            document_id=doc_id,
            author_id=str(test_user.id),
            author_name="Test User",
            content="A comment",
        )
        await comment.insert()
        assert await Comment.find(Comment.document_id == doc_id).count() == 1

        await async_client.delete(f"/api/documents/{doc_id}/permanent")
        assert await Comment.find(Comment.document_id == doc_id).count() == 0

    @pytest.mark.asyncio
    async def test_cleans_up_versions(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client)
        doc_id = doc["id"]

        version = DocumentVersion(
            document_id=doc_id,
            version_number=1,
            author_id=str(test_user.id),
            author_name="Test User",
            content="snapshot",
        )
        await version.insert()
        assert await DocumentVersion.find(DocumentVersion.document_id == doc_id).count() == 1

        await async_client.delete(f"/api/documents/{doc_id}/permanent")
        assert await DocumentVersion.find(DocumentVersion.document_id == doc_id).count() == 0

    @pytest.mark.asyncio
    async def test_cleans_up_access_records(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client)
        doc_id = doc["id"]

        access = DocumentAccess(
            document_id=doc_id,
            user_id="some-other-user",
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await access.insert()
        assert await DocumentAccess.find(DocumentAccess.document_id == doc_id).count() == 1

        await async_client.delete(f"/api/documents/{doc_id}/permanent")
        assert await DocumentAccess.find(DocumentAccess.document_id == doc_id).count() == 0

    @pytest.mark.asyncio
    async def test_cleans_up_view_records(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client)
        doc_id = doc["id"]

        view = DocumentView(user_id="viewer-123", document_id=doc_id)
        await view.insert()
        assert await DocumentView.find(DocumentView.document_id == doc_id).count() == 1

        await async_client.delete(f"/api/documents/{doc_id}/permanent")
        assert await DocumentView.find(DocumentView.document_id == doc_id).count() == 0

    @pytest.mark.asyncio
    async def test_cleans_up_multiple_related_records(self, async_client: AsyncClient, test_user: User):
        """Hard delete should remove all related data even when there are many records."""
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client)
        doc_id = doc["id"]

        for i in range(3):
            await Comment(
                document_id=doc_id,
                author_id=str(test_user.id),
                author_name="Test User",
                content=f"Comment {i}",
            ).insert()
        for i in range(2):
            await DocumentVersion(
                document_id=doc_id,
                version_number=i + 1,
                author_id=str(test_user.id),
                author_name="Test User",
                content=f"Version {i}",
            ).insert()

        await async_client.delete(f"/api/documents/{doc_id}/permanent")

        assert await Comment.find(Comment.document_id == doc_id).count() == 0
        assert await DocumentVersion.find(DocumentVersion.document_id == doc_id).count() == 0


class TestContentLength:
    @pytest.mark.asyncio
    async def test_content_length_in_response(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "Sized", content="Hello, World!")
        assert doc["content_length"] == 13

    @pytest.mark.asyncio
    async def test_content_length_empty(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "Empty")
        assert doc["content_length"] == 0

    @pytest.mark.asyncio
    async def test_content_length_updates_after_edit(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "Editable", content="short")
        assert doc["content_length"] == 5

        resp = await async_client.put(
            f"/api/documents/{doc['id']}",
            json={"content": "a much longer piece of content"},
        )
        assert resp.json()["content_length"] == 30

    @pytest.mark.asyncio
    async def test_content_length_in_list(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        await _create_doc(async_client, "Doc1", content="abc")
        await _create_doc(async_client, "Doc2", content="abcdef")

        resp = await async_client.get("/api/documents")
        docs = resp.json()
        lengths = {d["title"]: d["content_length"] for d in docs}
        assert lengths["Doc1"] == 3
        assert lengths["Doc2"] == 6
