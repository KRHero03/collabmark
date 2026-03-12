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


async def _create_doc(client: AsyncClient, title: str = "Test Doc", content: str = "", folder_id: str | None = None) -> dict:
    payload: dict = {"title": title, "content": content}
    if folder_id is not None:
        payload["folder_id"] = folder_id
    resp = await client.post("/api/documents", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def _create_folder(client: AsyncClient, name: str = "Test Folder", parent_id: str | None = None) -> dict:
    payload: dict = {"name": name}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    resp = await client.post("/api/folders", json=payload)
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


class TestTrashExcludesFolderChildren:
    """list_trash should not show documents whose parent folder is also deleted."""

    @pytest.mark.asyncio
    async def test_folder_delete_hides_children_from_trash(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "MyFolder")
        doc = await _create_doc(async_client, "Child Doc", folder_id=folder["id"])
        standalone = await _create_doc(async_client, "Standalone")

        await async_client.delete(f"/api/folders/{folder['id']}")
        await async_client.delete(f"/api/documents/{standalone['id']}")

        resp = await async_client.get("/api/documents/trash")
        trash_ids = [d["id"] for d in resp.json()]
        assert standalone["id"] in trash_ids
        assert doc["id"] not in trash_ids

    @pytest.mark.asyncio
    async def test_individually_deleted_doc_still_shows(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "ActiveFolder")
        doc = await _create_doc(async_client, "Deleted Alone", folder_id=folder["id"])

        await async_client.delete(f"/api/documents/{doc['id']}")

        resp = await async_client.get("/api/documents/trash")
        trash_ids = [d["id"] for d in resp.json()]
        assert doc["id"] in trash_ids

    @pytest.mark.asyncio
    async def test_doc_without_folder_always_shows(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "Root Doc")
        await async_client.delete(f"/api/documents/{doc['id']}")

        resp = await async_client.get("/api/documents/trash")
        trash_ids = [d["id"] for d in resp.json()]
        assert doc["id"] in trash_ids


class TestRestoreDocumentOrphan:
    """Restoring a document whose parent folder is still deleted moves it to root."""

    @pytest.mark.asyncio
    async def test_restore_moves_to_root_when_parent_deleted(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "DeletedFolder")
        doc = await _create_doc(async_client, "Orphan", folder_id=folder["id"])

        await async_client.delete(f"/api/folders/{folder['id']}")

        resp = await async_client.post(f"/api/documents/{doc['id']}/restore")
        assert resp.status_code == 200
        restored = resp.json()
        assert restored["is_deleted"] is False
        assert restored["folder_id"] is None

    @pytest.mark.asyncio
    async def test_individually_deleted_doc_restores_to_root(self, async_client: AsyncClient, test_user: User):
        """Individual delete breaks folder_id, so restore always goes to root."""
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "AliveFolder")
        doc = await _create_doc(async_client, "InFolder", folder_id=folder["id"])

        await async_client.delete(f"/api/documents/{doc['id']}")

        resp = await async_client.post(f"/api/documents/{doc['id']}/restore")
        assert resp.status_code == 200
        restored = resp.json()
        assert restored["folder_id"] is None

    @pytest.mark.asyncio
    async def test_restored_doc_visible_in_root_list(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "GoneFolder")
        doc = await _create_doc(async_client, "WillBeRoot", folder_id=folder["id"])

        await async_client.delete(f"/api/folders/{folder['id']}")
        await async_client.post(f"/api/documents/{doc['id']}/restore")

        resp = await async_client.get("/api/folders/contents")
        root_doc_ids = [d["id"] for d in resp.json()["documents"]]
        assert doc["id"] in root_doc_ids


class TestTrashFolderContents:
    """GET /api/folders/trash/{folder_id}/contents should list children of a deleted folder."""

    @pytest.mark.asyncio
    async def test_lists_children_of_deleted_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "ParentInTrash")
        doc = await _create_doc(async_client, "ChildDoc", folder_id=folder["id"])
        subfolder = await _create_folder(async_client, "SubFolder", parent_id=folder["id"])

        await async_client.delete(f"/api/folders/{folder['id']}")

        resp = await async_client.get(f"/api/folders/trash/{folder['id']}/contents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["parent_name"] == "ParentInTrash"
        assert data["parent_id"] == folder["id"]
        doc_ids = [d["id"] for d in data["documents"]]
        folder_ids = [f["id"] for f in data["folders"]]
        assert doc["id"] in doc_ids
        assert subfolder["id"] in folder_ids

    @pytest.mark.asyncio
    async def test_empty_deleted_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "EmptyTrash")
        await async_client.delete(f"/api/folders/{folder['id']}")

        resp = await async_client.get(f"/api/folders/trash/{folder['id']}/contents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["documents"] == []
        assert data["folders"] == []

    @pytest.mark.asyncio
    async def test_unauthenticated(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "Secured")
        await async_client.delete(f"/api/folders/{folder['id']}")

        async_client.cookies.clear()
        resp = await async_client.get(f"/api/folders/trash/{folder['id']}/contents")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_non_owner_forbidden(self, async_client: AsyncClient, test_user: User):
        other = User(google_id="google-trash-other", email="trash-other@example.com", name="Other")
        await other.insert()

        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "Private")
        await async_client.delete(f"/api/folders/{folder['id']}")

        async_client.cookies.update(_auth_cookies(other))
        resp = await async_client.get(f"/api/folders/trash/{folder['id']}/contents")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_nonexistent_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.get("/api/folders/trash/000000000000000000000000/contents")
        assert resp.status_code == 404


class TestDeletedFolderContentsReturns410:
    """GET /api/folders/{deleted_folder}/contents should return 410 Gone."""

    @pytest.mark.asyncio
    async def test_deleted_folder_returns_410(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "WillBeDeleted")
        await _create_doc(async_client, "Child", folder_id=folder["id"])
        await async_client.delete(f"/api/folders/{folder['id']}")

        resp = await async_client.get("/api/folders/contents", params={"folder_id": folder["id"]})
        assert resp.status_code == 410
        data = resp.json()
        assert data["detail"]["folder_id"] == folder["id"]
        assert "trash" in data["detail"]["message"].lower()

    @pytest.mark.asyncio
    async def test_non_deleted_folder_returns_200(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "Active")
        resp = await async_client.get("/api/folders/contents", params={"folder_id": folder["id"]})
        assert resp.status_code == 200


class TestDocDeleteBreaksHierarchy:
    """Individually deleting a document breaks its folder_id link."""

    @pytest.mark.asyncio
    async def test_deleted_doc_has_null_folder_id(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "Parent")
        doc = await _create_doc(async_client, "Child", folder_id=folder["id"])

        resp = await async_client.delete(f"/api/documents/{doc['id']}")
        assert resp.status_code == 200
        assert resp.json()["folder_id"] is None

    @pytest.mark.asyncio
    async def test_cascade_deleted_doc_keeps_folder_id(self, async_client: AsyncClient, test_user: User):
        """Deleting a folder cascade-deletes children but keeps their folder_id."""
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "Cascade")
        doc = await _create_doc(async_client, "InsideDoc", folder_id=folder["id"])

        await async_client.delete(f"/api/folders/{folder['id']}")

        resp = await async_client.get("/api/documents/trash")
        trash_docs = resp.json()
        doc_in_trash = next((d for d in trash_docs if d["id"] == doc["id"]), None)
        assert doc_in_trash is None, "Cascade-deleted doc should NOT appear in root trash"


class TestDocRestoreScenarios:
    """Restore behavior for individually and cascade-deleted documents."""

    @pytest.mark.asyncio
    async def test_individually_deleted_doc_restores_to_root(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "F1")
        doc = await _create_doc(async_client, "D1", folder_id=folder["id"])

        await async_client.delete(f"/api/documents/{doc['id']}")
        resp = await async_client.post(f"/api/documents/{doc['id']}/restore")
        assert resp.status_code == 200
        assert resp.json()["folder_id"] is None

    @pytest.mark.asyncio
    async def test_cascade_deleted_doc_restores_to_root_when_parent_deleted(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "F2")
        doc = await _create_doc(async_client, "D2", folder_id=folder["id"])

        await async_client.delete(f"/api/folders/{folder['id']}")
        resp = await async_client.post(f"/api/documents/{doc['id']}/restore")
        assert resp.status_code == 200
        assert resp.json()["folder_id"] is None

        contents = (await async_client.get("/api/folders/contents")).json()
        assert doc["id"] in [d["id"] for d in contents["documents"]]

    @pytest.mark.asyncio
    async def test_cascade_deleted_doc_stays_in_folder_when_parent_restored_first(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "F3")
        doc = await _create_doc(async_client, "D3", folder_id=folder["id"])

        await async_client.delete(f"/api/folders/{folder['id']}")
        await async_client.post(f"/api/folders/{folder['id']}/restore")

        contents = (await async_client.get("/api/folders/contents", params={"folder_id": folder["id"]})).json()
        assert doc["id"] in [d["id"] for d in contents["documents"]]


class TestFolderRestoreScenarios:
    """Restore behavior for folders with hierarchy."""

    @pytest.mark.asyncio
    async def test_folder_restore_moves_to_root_when_parent_deleted(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        parent = await _create_folder(async_client, "GrandParent")
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])

        await async_client.delete(f"/api/folders/{parent['id']}")
        resp = await async_client.post(f"/api/folders/{child['id']}/restore")
        assert resp.status_code == 200
        assert resp.json()["parent_id"] is None

    @pytest.mark.asyncio
    async def test_folder_restore_cascade_restores_children(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "Root")
        subfolder = await _create_folder(async_client, "Sub", parent_id=folder["id"])
        doc = await _create_doc(async_client, "InSub", folder_id=subfolder["id"])

        await async_client.delete(f"/api/folders/{folder['id']}")

        await async_client.post(f"/api/folders/{folder['id']}/restore")

        contents = (await async_client.get("/api/folders/contents", params={"folder_id": folder["id"]})).json()
        assert subfolder["id"] in [f["id"] for f in contents["folders"]]

        sub_contents = (
            await async_client.get("/api/folders/contents", params={"folder_id": subfolder["id"]})
        ).json()
        assert doc["id"] in [d["id"] for d in sub_contents["documents"]]

    @pytest.mark.asyncio
    async def test_folder_restore_stays_in_parent_when_parent_alive(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        parent = await _create_folder(async_client, "Alive")
        child = await _create_folder(async_client, "Nested", parent_id=parent["id"])

        await async_client.delete(f"/api/folders/{child['id']}")
        resp = await async_client.post(f"/api/folders/{child['id']}/restore")
        assert resp.status_code == 200
        assert resp.json()["parent_id"] == parent["id"]


class TestDeletedItemAccessBlocked:
    """Non-owners cannot access deleted items; 410 returned for all users on get."""

    @pytest.mark.asyncio
    async def test_get_deleted_document_returns_410(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "WillDelete")
        await async_client.delete(f"/api/documents/{doc['id']}")

        resp = await async_client.get(f"/api/documents/{doc['id']}")
        assert resp.status_code == 410

    @pytest.mark.asyncio
    async def test_update_deleted_document_returns_410(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "WillDelete2")
        await async_client.delete(f"/api/documents/{doc['id']}")

        resp = await async_client.put(f"/api/documents/{doc['id']}", json={"title": "Nope"})
        assert resp.status_code == 410

    @pytest.mark.asyncio
    async def test_non_owner_cannot_access_deleted_doc_via_acl(
        self, async_client: AsyncClient, test_user: User
    ):
        other = User(google_id="acl-other", email="acl-other@test.com", name="Other")
        await other.insert()

        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _create_doc(async_client, "Shared")

        resp = await async_client.post(
            f"/api/documents/{doc['id']}/collaborators",
            json={"email": other.email, "permission": "edit"},
        )
        assert resp.status_code == 201

        async_client.cookies.update(_auth_cookies(other))
        resp = await async_client.get(f"/api/documents/{doc['id']}")
        assert resp.status_code == 200

        async_client.cookies.update(_auth_cookies(test_user))
        await async_client.delete(f"/api/documents/{doc['id']}")

        async_client.cookies.update(_auth_cookies(other))
        resp = await async_client.get(f"/api/documents/{doc['id']}")
        assert resp.status_code == 410

    @pytest.mark.asyncio
    async def test_get_deleted_folder_returns_410(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "DeleteMe")
        await async_client.delete(f"/api/folders/{folder['id']}")

        resp = await async_client.get(f"/api/folders/{folder['id']}")
        assert resp.status_code == 410


class TestAncestorBreadcrumbs:
    """Trash folder contents include ancestor chain for breadcrumbs."""

    @pytest.mark.asyncio
    async def test_single_level_ancestors(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        folder = await _create_folder(async_client, "TopLevel")
        await async_client.delete(f"/api/folders/{folder['id']}")

        resp = await async_client.get(f"/api/folders/trash/{folder['id']}/contents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ancestors"] == [{"id": folder["id"], "name": "TopLevel"}]

    @pytest.mark.asyncio
    async def test_nested_ancestors(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        grandparent = await _create_folder(async_client, "GP")
        parent = await _create_folder(async_client, "Parent", parent_id=grandparent["id"])
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])

        await async_client.delete(f"/api/folders/{grandparent['id']}")

        resp = await async_client.get(f"/api/folders/trash/{child['id']}/contents")
        assert resp.status_code == 200
        ancestors = resp.json()["ancestors"]
        assert len(ancestors) == 3
        assert ancestors[0]["name"] == "GP"
        assert ancestors[1]["name"] == "Parent"
        assert ancestors[2]["name"] == "Child"

    @pytest.mark.asyncio
    async def test_ancestors_stop_at_non_deleted_parent(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        alive = await _create_folder(async_client, "Alive")
        deleted = await _create_folder(async_client, "Deleted", parent_id=alive["id"])

        await async_client.delete(f"/api/folders/{deleted['id']}")

        resp = await async_client.get(f"/api/folders/trash/{deleted['id']}/contents")
        ancestors = resp.json()["ancestors"]
        assert len(ancestors) == 1
        assert ancestors[0]["name"] == "Deleted"
