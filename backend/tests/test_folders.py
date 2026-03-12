"""Comprehensive tests for folder (Spaces) CRUD, nesting, cascade delete/restore, access, sharing."""

import pytest
import pytest_asyncio
from app.auth.jwt import create_access_token
from app.models.comment import Comment
from app.models.document import Document_
from app.models.document_version import DocumentVersion
from app.models.document_view import DocumentView
from app.models.folder import Folder, FolderAccess, FolderView
from app.models.share_link import DocumentAccess, Permission
from app.models.user import User
from httpx import AsyncClient


def _auth(user: User) -> dict[str, str]:
    return {"access_token": create_access_token(str(user.id))}


async def _create_folder(client: AsyncClient, name: str = "Test Folder", parent_id: str | None = None) -> dict:
    payload: dict = {"name": name}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    resp = await client.post("/api/folders", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def _create_doc(client: AsyncClient, title: str = "Test Doc", folder_id: str | None = None) -> dict:
    payload: dict = {"title": title}
    if folder_id is not None:
        payload["folder_id"] = folder_id
    resp = await client.post("/api/documents", json=payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def other_user() -> User:
    user = User(
        google_id="google-other-folder-user",
        email="other-folder@example.com",
        name="Other Folder User",
    )
    await user.insert()
    return user


# =====================================================================
# CRUD
# =====================================================================


class TestFolderCreate:
    @pytest.mark.asyncio
    async def test_create_folder_default_name(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.post("/api/folders", json={})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Untitled Folder"
        assert data["owner_id"] == str(test_user.id)
        assert data["parent_id"] is None
        assert data["is_deleted"] is False

    @pytest.mark.asyncio
    async def test_create_folder_custom_name(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "My Folder")
        assert f["name"] == "My Folder"

    @pytest.mark.asyncio
    async def test_create_nested_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])
        assert child["parent_id"] == parent["id"]

    @pytest.mark.asyncio
    async def test_create_folder_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.post("/api/folders", json={"name": "Nope"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_folder_nonexistent_parent(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.post(
            "/api/folders",
            json={"name": "Orphan", "parent_id": "000000000000000000000000"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_folder_returns_owner_info(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Info Folder")
        assert f["owner_name"] == test_user.name
        assert f["owner_email"] == test_user.email


class TestFolderGet:
    @pytest.mark.asyncio
    async def test_get_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Get Me")
        resp = await async_client.get(f"/api/folders/{f['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    @pytest.mark.asyncio
    async def test_get_folder_not_found(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.get("/api/folders/000000000000000000000000")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_folder_invalid_id(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.get("/api/folders/not-an-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_folder_no_access(self, async_client: AsyncClient, test_user: User, other_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Private")
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/folders/{f['id']}")
        assert resp.status_code == 403


class TestFolderUpdate:
    @pytest.mark.asyncio
    async def test_rename_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Old Name")
        resp = await async_client.put(f"/api/folders/{f['id']}", json={"name": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_move_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Target Parent")
        child = await _create_folder(async_client, "Moving Folder")
        resp = await async_client.put(f"/api/folders/{child['id']}", json={"parent_id": parent["id"]})
        assert resp.status_code == 200
        assert resp.json()["parent_id"] == parent["id"]

    @pytest.mark.asyncio
    async def test_cannot_move_folder_into_itself(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Self Loop")
        resp = await async_client.put(f"/api/folders/{f['id']}", json={"parent_id": f["id"]})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_cannot_move_folder_into_descendant(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        grandparent = await _create_folder(async_client, "GP")
        parent = await _create_folder(async_client, "P", parent_id=grandparent["id"])
        child = await _create_folder(async_client, "C", parent_id=parent["id"])
        resp = await async_client.put(f"/api/folders/{grandparent['id']}", json={"parent_id": child["id"]})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_folder_non_owner(self, async_client: AsyncClient, test_user: User, other_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Owner Only")
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.put(f"/api/folders/{f['id']}", json={"name": "Hacked"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_update_general_access(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Access Folder")
        assert f["general_access"] == "restricted"

        resp = await async_client.put(f"/api/folders/{f['id']}", json={"general_access": "anyone_view"})
        assert resp.status_code == 200
        assert resp.json()["general_access"] == "anyone_view"

        resp = await async_client.put(f"/api/folders/{f['id']}", json={"general_access": "anyone_edit"})
        assert resp.status_code == 200
        assert resp.json()["general_access"] == "anyone_edit"

    @pytest.mark.asyncio
    async def test_update_general_access_non_owner_forbidden(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Owner Access")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "edit"},
        )
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.put(f"/api/folders/{f['id']}", json={"general_access": "anyone_view"})
        assert resp.status_code == 403


# =====================================================================
# Contents & Breadcrumbs
# =====================================================================


class TestFolderContents:
    @pytest.mark.asyncio
    async def test_list_root_contents(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Root Folder")
        d = await _create_doc(async_client, "Root Doc")

        resp = await async_client.get("/api/folders/contents")
        assert resp.status_code == 200
        data = resp.json()
        folder_ids = [x["id"] for x in data["folders"]]
        doc_ids = [x["id"] for x in data["documents"]]
        assert f["id"] in folder_ids
        assert d["id"] in doc_ids

    @pytest.mark.asyncio
    async def test_list_folder_contents(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        child_folder = await _create_folder(async_client, "Child", parent_id=parent["id"])
        child_doc = await _create_doc(async_client, "Child Doc", folder_id=parent["id"])
        root_doc = await _create_doc(async_client, "Root Doc")

        resp = await async_client.get(f"/api/folders/contents?folder_id={parent['id']}")
        assert resp.status_code == 200
        data = resp.json()
        folder_ids = [x["id"] for x in data["folders"]]
        doc_ids = [x["id"] for x in data["documents"]]
        assert child_folder["id"] in folder_ids
        assert child_doc["id"] in doc_ids
        assert root_doc["id"] not in doc_ids

    @pytest.mark.asyncio
    async def test_empty_folder_contents(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Empty")
        resp = await async_client.get(f"/api/folders/contents?folder_id={f['id']}")
        data = resp.json()
        assert data["folders"] == []
        assert data["documents"] == []

    @pytest.mark.asyncio
    async def test_deleted_items_excluded_from_contents(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])
        doc = await _create_doc(async_client, "Doc", folder_id=parent["id"])

        await async_client.delete(f"/api/folders/{child['id']}")
        await async_client.delete(f"/api/documents/{doc['id']}")

        resp = await async_client.get(f"/api/folders/contents?folder_id={parent['id']}")
        data = resp.json()
        assert data["folders"] == []
        assert data["documents"] == []


class TestBreadcrumbs:
    @pytest.mark.asyncio
    async def test_single_level_breadcrumb(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Solo")
        resp = await async_client.get(f"/api/folders/breadcrumbs?folder_id={f['id']}")
        assert resp.status_code == 200
        crumbs = resp.json()
        assert len(crumbs) == 1
        assert crumbs[0]["name"] == "Solo"

    @pytest.mark.asyncio
    async def test_nested_breadcrumbs(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        a = await _create_folder(async_client, "A")
        b = await _create_folder(async_client, "B", parent_id=a["id"])
        c = await _create_folder(async_client, "C", parent_id=b["id"])
        resp = await async_client.get(f"/api/folders/breadcrumbs?folder_id={c['id']}")
        crumbs = resp.json()
        assert len(crumbs) == 3
        assert crumbs[0]["name"] == "A"
        assert crumbs[1]["name"] == "B"
        assert crumbs[2]["name"] == "C"


# =====================================================================
# Soft Delete / Restore (Cascade)
# =====================================================================


class TestFolderSoftDelete:
    @pytest.mark.asyncio
    async def test_soft_delete_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Delete Me")
        resp = await async_client.delete(f"/api/folders/{f['id']}")
        assert resp.status_code == 200
        assert resp.json()["is_deleted"] is True

    @pytest.mark.asyncio
    async def test_soft_delete_removes_from_contents(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Gone")
        await async_client.delete(f"/api/folders/{f['id']}")
        resp = await async_client.get("/api/folders/contents")
        folder_ids = [x["id"] for x in resp.json()["folders"]]
        assert f["id"] not in folder_ids

    @pytest.mark.asyncio
    async def test_cascade_soft_delete_child_folders(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])
        await async_client.delete(f"/api/folders/{parent['id']}")

        child_folder = await Folder.get(child["id"])
        assert child_folder.is_deleted is True

    @pytest.mark.asyncio
    async def test_cascade_soft_delete_documents(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        doc = await _create_doc(async_client, "Doc In Folder", folder_id=parent["id"])
        await async_client.delete(f"/api/folders/{parent['id']}")

        d = await Document_.get(doc["id"])
        assert d.is_deleted is True

    @pytest.mark.asyncio
    async def test_cascade_soft_delete_deep_nesting(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        a = await _create_folder(async_client, "A")
        b = await _create_folder(async_client, "B", parent_id=a["id"])
        c = await _create_folder(async_client, "C", parent_id=b["id"])
        doc = await _create_doc(async_client, "Deep Doc", folder_id=c["id"])

        await async_client.delete(f"/api/folders/{a['id']}")

        for fid in [a["id"], b["id"], c["id"]]:
            folder = await Folder.get(fid)
            assert folder.is_deleted is True
        d = await Document_.get(doc["id"])
        assert d.is_deleted is True

    @pytest.mark.asyncio
    async def test_soft_delete_non_owner(self, async_client: AsyncClient, test_user: User, other_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Mine")
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.delete(f"/api/folders/{f['id']}")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_soft_delete_unauthenticated(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Auth Required")
        async_client.cookies.clear()
        resp = await async_client.delete(f"/api/folders/{f['id']}")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_soft_delete_nonexistent(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.delete("/api/folders/000000000000000000000000")
        assert resp.status_code == 404


class TestFolderRestore:
    @pytest.mark.asyncio
    async def test_restore_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Restore Me")
        await async_client.delete(f"/api/folders/{f['id']}")
        resp = await async_client.post(f"/api/folders/{f['id']}/restore")
        assert resp.status_code == 200
        assert resp.json()["is_deleted"] is False

    @pytest.mark.asyncio
    async def test_cascade_restore_child_folders(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])
        await async_client.delete(f"/api/folders/{parent['id']}")
        await async_client.post(f"/api/folders/{parent['id']}/restore")

        child_folder = await Folder.get(child["id"])
        assert child_folder.is_deleted is False

    @pytest.mark.asyncio
    async def test_cascade_restore_documents(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        doc = await _create_doc(async_client, "Doc", folder_id=parent["id"])
        await async_client.delete(f"/api/folders/{parent['id']}")
        await async_client.post(f"/api/folders/{parent['id']}/restore")

        d = await Document_.get(doc["id"])
        assert d.is_deleted is False

    @pytest.mark.asyncio
    async def test_restore_folder_with_deleted_parent_restores_to_root(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])

        await async_client.delete(f"/api/folders/{parent['id']}")

        resp = await async_client.post(f"/api/folders/{child['id']}/restore")
        assert resp.status_code == 200
        assert resp.json()["parent_id"] is None

    @pytest.mark.asyncio
    async def test_restore_non_owner(self, async_client: AsyncClient, test_user: User, other_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Owner Only")
        await async_client.delete(f"/api/folders/{f['id']}")
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.post(f"/api/folders/{f['id']}/restore")
        assert resp.status_code == 403


# =====================================================================
# Trash
# =====================================================================


class TestFolderTrash:
    @pytest.mark.asyncio
    async def test_empty_trash(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.get("/api/folders/trash")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_trash_shows_deleted_folders(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Trashed")
        await async_client.delete(f"/api/folders/{f['id']}")
        resp = await async_client.get("/api/folders/trash")
        ids = [x["id"] for x in resp.json()]
        assert f["id"] in ids

    @pytest.mark.asyncio
    async def test_trash_shows_only_top_level_deleted(self, async_client: AsyncClient, test_user: User):
        """When a parent is deleted, only the parent appears in trash, not children."""
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])
        await async_client.delete(f"/api/folders/{parent['id']}")

        resp = await async_client.get("/api/folders/trash")
        ids = [x["id"] for x in resp.json()]
        assert parent["id"] in ids
        assert child["id"] not in ids

    @pytest.mark.asyncio
    async def test_trash_excludes_other_users(self, async_client: AsyncClient, test_user: User, other_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "My Folder")
        await async_client.delete(f"/api/folders/{f['id']}")

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get("/api/folders/trash")
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_trash_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.get("/api/folders/trash")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_restored_folder_disappears_from_trash(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Restoring")
        await async_client.delete(f"/api/folders/{f['id']}")
        await async_client.post(f"/api/folders/{f['id']}/restore")
        resp = await async_client.get("/api/folders/trash")
        assert resp.json() == []


# =====================================================================
# Hard Delete
# =====================================================================


class TestFolderHardDelete:
    @pytest.mark.asyncio
    async def test_hard_delete_removes_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Permanent Delete")
        resp = await async_client.delete(f"/api/folders/{f['id']}/permanent")
        assert resp.status_code == 204
        assert await Folder.get(f["id"]) is None

    @pytest.mark.asyncio
    async def test_hard_delete_cascade_documents(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Folder")
        doc = await _create_doc(async_client, "Nested Doc", folder_id=f["id"])
        await async_client.delete(f"/api/folders/{f['id']}/permanent")
        assert await Document_.get(doc["id"]) is None

    @pytest.mark.asyncio
    async def test_hard_delete_cascade_subfolders(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])
        grandchild_doc = await _create_doc(async_client, "GC Doc", folder_id=child["id"])

        await async_client.delete(f"/api/folders/{parent['id']}/permanent")
        assert await Folder.get(parent["id"]) is None
        assert await Folder.get(child["id"]) is None
        assert await Document_.get(grandchild_doc["id"]) is None

    @pytest.mark.asyncio
    async def test_hard_delete_cleans_folder_access(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Shared Folder")
        fa = FolderAccess(
            folder_id=f["id"],
            user_id="some-user",
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await fa.insert()
        assert await FolderAccess.find(FolderAccess.folder_id == f["id"]).count() == 1

        await async_client.delete(f"/api/folders/{f['id']}/permanent")
        assert await FolderAccess.find(FolderAccess.folder_id == f["id"]).count() == 0

    @pytest.mark.asyncio
    async def test_hard_delete_cleans_nested_doc_related_data(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Folder")
        doc = await _create_doc(async_client, "Doc", folder_id=f["id"])
        doc_id = doc["id"]

        await Comment(
            document_id=doc_id,
            author_id=str(test_user.id),
            author_name="Test",
            content="Hi",
        ).insert()
        await DocumentVersion(
            document_id=doc_id,
            version_number=1,
            author_id=str(test_user.id),
            author_name="Test",
            content="v1",
        ).insert()
        await DocumentAccess(
            document_id=doc_id,
            user_id="viewer",
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        ).insert()
        await DocumentView(user_id="viewer", document_id=doc_id).insert()

        await async_client.delete(f"/api/folders/{f['id']}/permanent")

        assert await Comment.find(Comment.document_id == doc_id).count() == 0
        assert await DocumentVersion.find(DocumentVersion.document_id == doc_id).count() == 0
        assert await DocumentAccess.find(DocumentAccess.document_id == doc_id).count() == 0
        assert await DocumentView.find(DocumentView.document_id == doc_id).count() == 0

    @pytest.mark.asyncio
    async def test_hard_delete_non_owner(self, async_client: AsyncClient, test_user: User, other_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Protected")
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.delete(f"/api/folders/{f['id']}/permanent")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_hard_delete_nonexistent(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.delete("/api/folders/000000000000000000000000/permanent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_hard_delete_invalid_id(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.delete("/api/folders/bad-id/permanent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_hard_delete_does_not_affect_siblings(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        child1 = await _create_folder(async_client, "Keep", parent_id=parent["id"])
        child2 = await _create_folder(async_client, "Delete", parent_id=parent["id"])

        await async_client.delete(f"/api/folders/{child2['id']}/permanent")
        assert await Folder.get(child1["id"]) is not None
        assert await Folder.get(parent["id"]) is not None


# =====================================================================
# Sharing / Collaborators
# =====================================================================


class TestFolderSharing:
    @pytest.mark.asyncio
    async def test_add_collaborator(self, async_client: AsyncClient, test_user: User, other_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Shared Folder")
        resp = await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "edit"},
        )
        assert resp.status_code == 201
        assert resp.json()["user_id"] == str(other_user.id)
        assert resp.json()["permission"] == "edit"

    @pytest.mark.asyncio
    async def test_list_collaborators(self, async_client: AsyncClient, test_user: User, other_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Shared")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        resp = await async_client.get(f"/api/folders/{f['id']}/collaborators")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_remove_collaborator(self, async_client: AsyncClient, test_user: User, other_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Remove")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        resp = await async_client.delete(f"/api/folders/{f['id']}/collaborators/{other_user.id!s}")
        assert resp.status_code == 204
        collabs = await async_client.get(f"/api/folders/{f['id']}/collaborators")
        assert len(collabs.json()) == 0

    @pytest.mark.asyncio
    async def test_cannot_add_self_as_collaborator(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Self")
        resp = await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": test_user.email, "permission": "view"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_add_collaborator_non_owner(self, async_client: AsyncClient, test_user: User, other_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Mine")
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": "someone@example.com", "permission": "view"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_add_collaborator_nonexistent_email(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "NoUser")
        resp = await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": "doesnotexist@example.com", "permission": "view"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_shared_folder_visible_to_collaborator(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Shared Visible")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get("/api/folders/shared")
        assert resp.status_code == 200
        ids = [x["id"] for x in resp.json()]
        assert f["id"] in ids

    @pytest.mark.asyncio
    async def test_shared_folders_empty_for_new_user(self, async_client: AsyncClient, other_user: User):
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get("/api/folders/shared")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_update_collaborator_permission(self, async_client: AsyncClient, test_user: User, other_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Perm Update")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        resp = await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "edit"},
        )
        assert resp.status_code == 201
        assert resp.json()["permission"] == "edit"


# =====================================================================
# Access Inheritance (Folder -> Document)
# =====================================================================


class TestAccessInheritance:
    @pytest.mark.asyncio
    async def test_folder_collaborator_can_view_doc_inside(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Inherited Access")
        doc = await _create_doc(async_client, "Nested Doc", folder_id=f["id"])
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/documents/{doc['id']}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_folder_collaborator_cannot_edit_with_view_perm(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "View Only")
        doc = await _create_doc(async_client, "Nested", folder_id=f["id"])
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.put(f"/api/documents/{doc['id']}", json={"title": "Hacked"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_folder_edit_collaborator_can_edit_doc(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Edit Access")
        doc = await _create_doc(async_client, "Editable", folder_id=f["id"])
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "edit"},
        )
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.put(f"/api/documents/{doc['id']}", json={"title": "Updated by Collab"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated by Collab"

    @pytest.mark.asyncio
    async def test_grandparent_folder_access_inherited(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        gp = await _create_folder(async_client, "GP")
        p = await _create_folder(async_client, "P", parent_id=gp["id"])
        doc = await _create_doc(async_client, "Deep Doc", folder_id=p["id"])
        await async_client.post(
            f"/api/folders/{gp['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/documents/{doc['id']}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_no_access_without_folder_sharing(self, async_client: AsyncClient, test_user: User, other_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Private")
        doc = await _create_doc(async_client, "Private Doc", folder_id=f["id"])
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/documents/{doc['id']}")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_collaborator_can_view_shared_folder(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Viewable Folder")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/folders/{f['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Viewable Folder"


# =====================================================================
# Document folder_id
# =====================================================================


class TestDocumentFolderId:
    @pytest.mark.asyncio
    async def test_create_doc_in_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Container")
        doc = await _create_doc(async_client, "Inside", folder_id=f["id"])
        assert doc["folder_id"] == f["id"]

    @pytest.mark.asyncio
    async def test_create_doc_at_root(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        doc = await _create_doc(async_client, "Root Doc")
        assert doc["folder_id"] is None

    @pytest.mark.asyncio
    async def test_move_doc_to_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Destination")
        doc = await _create_doc(async_client, "Moving Doc")
        resp = await async_client.put(f"/api/documents/{doc['id']}", json={"folder_id": f["id"]})
        assert resp.status_code == 200
        assert resp.json()["folder_id"] == f["id"]


# =====================================================================
# Edge Cases
# =====================================================================


class TestFolderEdgeCases:
    @pytest.mark.asyncio
    async def test_delete_already_deleted_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Double Delete")
        await async_client.delete(f"/api/folders/{f['id']}")
        resp = await async_client.delete(f"/api/folders/{f['id']}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_restore_non_deleted_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Not Deleted")
        resp = await async_client.post(f"/api/folders/{f['id']}/restore")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_folder_timestamps_updated(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Timestamped")
        original_updated = f["updated_at"]
        resp = await async_client.put(f"/api/folders/{f['id']}", json={"name": "Renamed"})
        assert resp.json()["updated_at"] >= original_updated

    @pytest.mark.asyncio
    async def test_deleted_folder_has_deleted_at(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "With Timestamp")
        resp = await async_client.delete(f"/api/folders/{f['id']}")
        assert resp.json()["deleted_at"] is not None

    @pytest.mark.asyncio
    async def test_restored_folder_clears_deleted_at(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Clear Timestamp")
        await async_client.delete(f"/api/folders/{f['id']}")
        resp = await async_client.post(f"/api/folders/{f['id']}/restore")
        assert resp.json()["deleted_at"] is None


# =====================================================================
# Folder View Recording & Recently Viewed
# =====================================================================


class TestFolderViews:
    @pytest.mark.asyncio
    async def test_record_folder_view(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "View Me")
        resp = await async_client.post(f"/api/folders/{f['id']}/view")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_record_folder_view_creates_folder_view(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Track View")
        await async_client.post(f"/api/folders/{f['id']}/view")
        views = await FolderView.find(
            FolderView.user_id == str(test_user.id),
            FolderView.folder_id == f["id"],
        ).to_list()
        assert len(views) == 1

    @pytest.mark.asyncio
    async def test_record_folder_view_updates_timestamp(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Update Timestamp")
        await async_client.post(f"/api/folders/{f['id']}/view")
        view1 = await FolderView.find_one(
            FolderView.user_id == str(test_user.id),
            FolderView.folder_id == f["id"],
        )
        first_viewed = view1.viewed_at

        await async_client.post(f"/api/folders/{f['id']}/view")
        view2 = await FolderView.find_one(
            FolderView.user_id == str(test_user.id),
            FolderView.folder_id == f["id"],
        )
        assert view2.viewed_at >= first_viewed
        views_count = await FolderView.find(
            FolderView.user_id == str(test_user.id),
            FolderView.folder_id == f["id"],
        ).count()
        assert views_count == 1

    @pytest.mark.asyncio
    async def test_recently_viewed_folders_empty(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.get("/api/folders/recent")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_recently_viewed_folders_after_view(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Recently Viewed")
        await async_client.post(f"/api/folders/{f['id']}/view")
        resp = await async_client.get("/api/folders/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        ids = [x["id"] for x in data]
        assert f["id"] in ids

    @pytest.mark.asyncio
    async def test_recently_viewed_includes_owner_info(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Owner Info")
        await async_client.post(f"/api/folders/{f['id']}/view")
        resp = await async_client.get("/api/folders/recent")
        item = resp.json()[0]
        assert item["owner_name"] == test_user.name
        assert item["owner_email"] == test_user.email
        assert "permission" in item
        assert "viewed_at" in item

    @pytest.mark.asyncio
    async def test_recently_viewed_excludes_deleted_folders(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Will Delete")
        await async_client.post(f"/api/folders/{f['id']}/view")
        await async_client.delete(f"/api/folders/{f['id']}")
        resp = await async_client.get("/api/folders/recent")
        ids = [x["id"] for x in resp.json()]
        assert f["id"] not in ids

    @pytest.mark.asyncio
    async def test_recently_viewed_excludes_no_access(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Private Folder")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        async_client.cookies.update(_auth(other_user))
        await async_client.post(f"/api/folders/{f['id']}/view")

        resp = await async_client.get("/api/folders/recent")
        ids = [x["id"] for x in resp.json()]
        assert f["id"] in ids

        async_client.cookies.update(_auth(test_user))
        await async_client.delete(f"/api/folders/{f['id']}/collaborators/{other_user.id!s}")

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get("/api/folders/recent")
        ids = [x["id"] for x in resp.json()]
        assert f["id"] not in ids

    @pytest.mark.asyncio
    async def test_record_view_unauthenticated(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Auth Needed")
        async_client.cookies.clear()
        resp = await async_client.post(f"/api/folders/{f['id']}/view")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_hard_delete_cleans_folder_views(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "View Cleanup")
        await async_client.post(f"/api/folders/{f['id']}/view")
        assert await FolderView.find(FolderView.folder_id == f["id"]).count() == 1
        await async_client.delete(f"/api/folders/{f['id']}/permanent")
        assert await FolderView.find(FolderView.folder_id == f["id"]).count() == 0


# =====================================================================
# Shared Folder Browsing & Permission-Aware Contents
# =====================================================================


class TestSharedFolderBrowsing:
    @pytest.mark.asyncio
    async def test_shared_folder_contents_visible_to_collaborator(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Shared Browsing")
        await _create_doc(async_client, "Doc Inside", folder_id=f["id"])
        await _create_folder(async_client, "Sub Folder", parent_id=f["id"])
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/folders/contents?folder_id={f['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["title"] == "Doc Inside"
        assert len(data["folders"]) == 1
        assert data["folders"][0]["name"] == "Sub Folder"
        assert data["permission"] == "view"

    @pytest.mark.asyncio
    async def test_shared_folder_contents_returns_edit_permission(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Edit Shared")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "edit"},
        )

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/folders/contents?folder_id={f['id']}")
        assert resp.status_code == 200
        assert resp.json()["permission"] == "edit"

    @pytest.mark.asyncio
    async def test_shared_folder_contents_denied_without_access(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Private Contents")

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/folders/contents?folder_id={f['id']}")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_root_contents_return_edit_permission(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.get("/api/folders/contents")
        assert resp.status_code == 200
        assert resp.json()["permission"] == "edit"

    @pytest.mark.asyncio
    async def test_general_access_anyone_view_allows_browsing(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Public View")
        await _create_doc(async_client, "Public Doc", folder_id=f["id"])
        await async_client.put(f"/api/folders/{f['id']}", json={"general_access": "anyone_view"})

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/folders/contents?folder_id={f['id']}")
        assert resp.status_code == 200
        assert len(resp.json()["documents"]) == 1
        assert resp.json()["permission"] == "view"

    @pytest.mark.asyncio
    async def test_general_access_anyone_edit_allows_browsing(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Public Edit")
        await async_client.put(f"/api/folders/{f['id']}", json={"general_access": "anyone_edit"})

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/folders/contents?folder_id={f['id']}")
        assert resp.status_code == 200
        assert resp.json()["permission"] == "edit"

    @pytest.mark.asyncio
    async def test_shared_folder_list_includes_owner_info(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Shared Info")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get("/api/folders/shared")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        item = next(x for x in data if x["id"] == f["id"])
        assert item["owner_name"] == test_user.name
        assert item["owner_email"] == test_user.email
        assert item["permission"] == "view"
        assert "last_accessed_at" in item


# =====================================================================
# Permission Enforcement for Create in Shared Folders
# =====================================================================


class TestSharedFolderPermissionEnforcement:
    @pytest.mark.asyncio
    async def test_view_only_cannot_create_folder_inside(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "View Only Parent")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.post("/api/folders", json={"name": "Unauthorized", "parent_id": f["id"]})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_edit_collaborator_can_create_folder_inside(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Edit Parent")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "edit"},
        )

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.post("/api/folders", json={"name": "Authorized", "parent_id": f["id"]})
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_view_only_cannot_create_doc_inside(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "View Only Doc Parent")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.post("/api/documents", json={"title": "No Access", "folder_id": f["id"]})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_edit_collaborator_can_create_doc_inside(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Edit Doc Parent")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "edit"},
        )

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.post("/api/documents", json={"title": "Allowed", "folder_id": f["id"]})
        assert resp.status_code == 201


# =====================================================================
# Coverage: folder_service edge cases
# =====================================================================


class TestFolderServiceEdgeCases:
    """Tests for folder_service edge cases and missing branches."""

    @pytest.mark.asyncio
    async def test_create_folder_exceeds_max_per_user(self, async_client: AsyncClient, test_user: User):
        from unittest.mock import patch

        from app.models.folder import FolderCreate
        from app.services.folder_service import create_folder

        with patch("app.services.folder_service.MAX_FOLDERS_PER_USER", 2):
            await create_folder(test_user, FolderCreate(name="F1"))
            await create_folder(test_user, FolderCreate(name="F2"))
            with pytest.raises(Exception) as exc_info:
                await create_folder(test_user, FolderCreate(name="F3"))
            assert exc_info.value.status_code == 403
            assert "Folder limit reached" in exc_info.value.detail
            assert "2" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_list_shared_folders_invalid_folder_id_in_access(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        from app.models.folder import FolderAccess
        from app.services.folder_service import list_shared_folders

        fa = FolderAccess(
            folder_id="invalid-folder-id",
            user_id=str(other_user.id),
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await fa.insert()
        results = await list_shared_folders(other_user)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_list_shared_folders_deleted_folder_skipped(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Shared")
        await async_client.post(
            f"/api/folders/{f['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        await async_client.delete(f"/api/folders/{f['id']}")
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get("/api/folders/shared")
        assert resp.status_code == 200
        ids = [x["id"] for x in resp.json()]
        assert f["id"] not in ids

    @pytest.mark.asyncio
    async def test_list_shared_folders_owner_not_found(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        from app.models.folder import Folder, FolderAccess
        from app.services.folder_service import list_shared_folders

        folder = Folder(
            name="Orphan",
            owner_id="000000000000000000000001",
        )
        await folder.insert()
        folder.root_folder_id = str(folder.id)
        await folder.save()

        fa = FolderAccess(
            folder_id=str(folder.id),
            user_id=str(other_user.id),
            permission=Permission.VIEW,
            granted_by="000000000000000000000001",
        )
        await fa.insert()

        results = await list_shared_folders(other_user)
        assert len(results) == 1
        assert results[0]["owner_name"] == "Unknown"
        assert results[0]["owner_email"] == ""

    @pytest.mark.asyncio
    async def test_restore_folder_parent_still_deleted_restores_to_root(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])
        await async_client.delete(f"/api/folders/{parent['id']}")
        resp = await async_client.post(f"/api/folders/{child['id']}/restore")
        assert resp.status_code == 200
        assert resp.json()["parent_id"] is None

    @pytest.mark.asyncio
    async def test_list_trash_filters_nested_trashed_folders(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])
        await async_client.delete(f"/api/folders/{parent['id']}")
        resp = await async_client.get("/api/folders/trash")
        ids = [x["id"] for x in resp.json()]
        assert parent["id"] in ids
        assert child["id"] not in ids

    @pytest.mark.asyncio
    async def test_get_breadcrumbs_missing_folder_in_chain(self, async_client: AsyncClient, test_user: User):
        from app.models.folder import Folder
        from app.services.folder_service import get_breadcrumbs

        folder = Folder(name="Solo", owner_id=str(test_user.id))
        await folder.insert()
        folder.parent_id = "000000000000000000000000"
        await folder.save()

        crumbs = await get_breadcrumbs(str(folder.id), test_user)
        assert len(crumbs) == 1
        assert crumbs[0]["name"] == "Solo"

    @pytest.mark.asyncio
    async def test_list_folder_collaborators_invalid_user_id_skipped(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Collabs")
        fa = FolderAccess(
            folder_id=f["id"],
            user_id="000000000000000000000001",
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await fa.insert()
        resp = await async_client.get(f"/api/folders/{f['id']}/collaborators")
        assert resp.status_code == 200
        collabs = resp.json()
        assert len(collabs) == 0

    @pytest.mark.asyncio
    async def test_remove_folder_collaborator_nonexistent_access_404(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Remove")
        resp = await async_client.delete(f"/api/folders/{f['id']}/collaborators/000000000000000000000001")
        assert resp.status_code == 404
        assert "Collaborator access record not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_record_folder_view_invalid_id_no_error(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.post("/api/folders/invalid-id/view")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_list_recently_viewed_skips_deleted_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Viewed")
        await async_client.post(f"/api/folders/{f['id']}/view")
        await async_client.delete(f"/api/folders/{f['id']}")
        resp = await async_client.get("/api/folders/recent")
        ids = [x["id"] for x in resp.json()]
        assert f["id"] not in ids

    @pytest.mark.asyncio
    async def test_list_recently_viewed_owner_not_found(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        from app.models.folder import Folder, FolderView

        folder = Folder(name="Orphan", owner_id="000000000000000000000001")
        await folder.insert()
        folder.root_folder_id = str(folder.id)
        await folder.save()

        await FolderAccess(
            folder_id=str(folder.id),
            user_id=str(other_user.id),
            permission=Permission.VIEW,
            granted_by="000000000000000000000001",
        ).insert()

        fv = FolderView(user_id=str(other_user.id), folder_id=str(folder.id))
        await fv.insert()

        from app.services.folder_service import list_recently_viewed_folders

        results = await list_recently_viewed_folders(other_user)
        assert len(results) >= 1
        item = next((r for r in results if str(r["folder"].id) == str(folder.id)), None)
        assert item is not None
        assert item.get("owner_name") == "Unknown"
        assert item.get("owner_email") == ""

    @pytest.mark.asyncio
    async def test_create_folder_exceeds_depth(self, async_client: AsyncClient, test_user: User):
        from app.services.folder_service import MAX_FOLDER_DEPTH

        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "L1")
        for i in range(MAX_FOLDER_DEPTH - 1):
            child = await _create_folder(async_client, f"L{i + 2}", parent_id=parent["id"])
            parent = child

        resp = await async_client.post(
            "/api/folders",
            json={"name": "TooDeep", "parent_id": parent["id"]},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "depth" in detail.lower() or "nesting" in detail.lower()

    @pytest.mark.asyncio
    async def test_access_via_parent_chain_inheritance(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        await async_client.post(
            f"/api/folders/{parent['id']}/collaborators",
            json={"email": other_user.email, "permission": "edit"},
        )
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/folders/{child['id']}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_access_via_general_access_anyone_edit(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Public")
        await async_client.put(
            f"/api/folders/{f['id']}",
            json={"general_access": "anyone_edit"},
        )
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/folders/{f['id']}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_access_via_general_access_anyone_view(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        f = await _create_folder(async_client, "Public View")
        await async_client.put(
            f"/api/folders/{f['id']}",
            json={"general_access": "anyone_view"},
        )
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/folders/{f['id']}")
        assert resp.status_code == 200


class TestFolderBranchCoverage:
    """Targeted tests for remaining uncovered branches."""

    @pytest_asyncio.fixture
    async def other_user(self) -> User:
        u = User(google_id="branch-other-456", email="branchother@example.com", name="Branch Other")
        await u.insert()
        return u

    @pytest.mark.asyncio
    async def test_restore_folder_with_deleted_parent_restores_to_root_branch(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Parent")
        child = await _create_folder(async_client, "Child", parent_id=parent["id"])
        await async_client.delete(f"/api/folders/{parent['id']}")
        resp = await async_client.post(f"/api/folders/{child['id']}/restore")
        assert resp.status_code == 200
        assert resp.json()["parent_id"] is None

    @pytest.mark.asyncio
    async def test_trash_listing_excludes_nested_deleted_folders(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "TrashParent")
        child = await _create_folder(async_client, "TrashChild", parent_id=parent["id"])
        await async_client.delete(f"/api/folders/{parent['id']}")
        resp = await async_client.get("/api/folders/trash")
        assert resp.status_code == 200
        trash_ids = [f["id"] for f in resp.json()]
        assert parent["id"] in trash_ids
        assert child["id"] not in trash_ids

    @pytest.mark.asyncio
    async def test_list_collaborators_skips_invalid_user_ids(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        folder = await _create_folder(async_client, "CollabFolder")
        folder_id = folder["id"]
        await async_client.post(
            f"/api/folders/{folder_id}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        bogus = FolderAccess(
            folder_id=folder_id,
            user_id="not-a-valid-objectid",
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await bogus.insert()
        resp = await async_client.get(f"/api/folders/{folder_id}/collaborators")
        assert resp.status_code == 200
        user_ids = [c["user_id"] for c in resp.json()]
        assert str(other_user.id) in user_ids
        assert "not-a-valid-objectid" not in user_ids

    @pytest.mark.asyncio
    async def test_remove_nonexistent_collaborator_returns_404(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        folder = await _create_folder(async_client, "NoCollab")
        resp = await async_client.delete(f"/api/folders/{folder['id']}/collaborators/000000000000000000000000")
        assert resp.status_code == 404
        assert "Collaborator access record not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_record_view_with_invalid_folder_id_is_noop(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.post("/api/folders/not-valid-id/view")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_record_view_with_nonexistent_folder_is_noop(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.post("/api/folders/000000000000000000000000/view")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_recently_viewed_skips_no_access_folders(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        folder = await _create_folder(async_client, "WillLoseAccess")
        folder_id = folder["id"]
        await async_client.post(
            f"/api/folders/{folder_id}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        async_client.cookies.update(_auth(other_user))
        await async_client.post(f"/api/folders/{folder_id}/view")
        async_client.cookies.update(_auth(test_user))
        await async_client.delete(f"/api/folders/{folder_id}/collaborators/{other_user.id!s}")
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get("/api/folders/recent")
        assert resp.status_code == 200
        ids = [x["id"] for x in resp.json()]
        assert folder_id not in ids

    @pytest.mark.asyncio
    async def test_list_shared_folders_with_invalid_owner(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        folder = await _create_folder(async_client, "BadOwnerFolder")
        folder_id = folder["id"]
        await async_client.post(
            f"/api/folders/{folder_id}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        from app.models.folder import Folder as FolderModel
        from beanie import PydanticObjectId

        db_folder = await FolderModel.get(PydanticObjectId(folder_id))
        db_folder.owner_id = "invalid-owner-id"
        await db_folder.save()
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get("/api/folders/shared")
        assert resp.status_code == 200
        shared = resp.json()
        match = [s for s in shared if s["id"] == folder_id]
        assert len(match) == 1
        assert match[0]["owner_name"] == "Unknown"

    @pytest.mark.asyncio
    async def test_find_folder_with_invalid_id_format(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.get("/api/folders/totally-invalid!!!")
        assert resp.status_code == 404
        assert "Folder not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_view_only_access_blocks_edit_operations(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        folder = await _create_folder(async_client, "ViewOnlyFolder")
        folder_id = folder["id"]
        await async_client.post(
            f"/api/folders/{folder_id}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.put(
            f"/api/folders/{folder_id}",
            json={"name": "Renamed"},
        )
        assert resp.status_code == 403
        assert "view access" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_general_access_change_by_non_owner_forbidden(
        self, async_client: AsyncClient, test_user: User, other_user: User
    ):
        async_client.cookies.update(_auth(test_user))
        folder = await _create_folder(async_client, "GAFolder")
        folder_id = folder["id"]
        await async_client.post(
            f"/api/folders/{folder_id}/collaborators",
            json={"email": other_user.email, "permission": "edit"},
        )
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.put(
            f"/api/folders/{folder_id}",
            json={"general_access": "anyone_view"},
        )
        assert resp.status_code == 403
        assert "owner" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_folder_cannot_be_its_own_parent(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        folder = await _create_folder(async_client, "SelfParent")
        resp = await async_client.put(
            f"/api/folders/{folder['id']}",
            json={"parent_id": folder["id"]},
        )
        assert resp.status_code == 400
        assert "its own parent" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_folder_cannot_move_into_descendant(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        parent = await _create_folder(async_client, "Ancestor")
        child = await _create_folder(async_client, "Descendant", parent_id=parent["id"])
        resp = await async_client.put(
            f"/api/folders/{parent['id']}",
            json={"parent_id": child["id"]},
        )
        assert resp.status_code == 400
        assert "descendants" in resp.json()["detail"].lower()


# =====================================================================
# Folder Tree
# =====================================================================


class TestFolderTree:
    @pytest.mark.asyncio
    async def test_tree_flat_folder(self, async_client: AsyncClient, test_user: User):
        """Single folder with two docs returns a flat tree."""
        async_client.cookies.update(_auth(test_user))
        folder = await _create_folder(async_client, "TreeRoot")
        await _create_doc(async_client, "Doc A", folder_id=folder["id"])
        await _create_doc(async_client, "Doc B", folder_id=folder["id"])

        resp = await async_client.get(f"/api/folders/{folder['id']}/tree")
        assert resp.status_code == 200
        tree = resp.json()
        assert tree["id"] == folder["id"]
        assert tree["name"] == "TreeRoot"
        assert len(tree["documents"]) == 2
        assert tree["folders"] == []
        assert tree["permission"] == "edit"

    @pytest.mark.asyncio
    async def test_tree_nested_structure(self, async_client: AsyncClient, test_user: User):
        """Nested folders and docs appear recursively in the tree."""
        async_client.cookies.update(_auth(test_user))
        root = await _create_folder(async_client, "Root")
        child = await _create_folder(async_client, "Child", parent_id=root["id"])
        await _create_doc(async_client, "Root Doc", folder_id=root["id"])
        await _create_doc(async_client, "Child Doc", folder_id=child["id"])

        resp = await async_client.get(f"/api/folders/{root['id']}/tree")
        assert resp.status_code == 200
        tree = resp.json()
        assert tree["name"] == "Root"
        assert len(tree["documents"]) == 1
        assert tree["documents"][0]["title"] == "Root Doc"
        assert len(tree["folders"]) == 1
        assert tree["folders"][0]["name"] == "Child"
        assert len(tree["folders"][0]["documents"]) == 1
        assert tree["folders"][0]["documents"][0]["title"] == "Child Doc"

    @pytest.mark.asyncio
    async def test_tree_unauthenticated(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        folder = await _create_folder(async_client, "Priv")
        async_client.cookies.clear()
        resp = await async_client.get(f"/api/folders/{folder['id']}/tree")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_tree_no_access(self, async_client: AsyncClient, test_user: User, other_user: User):
        """Non-owner without explicit access gets 403."""
        async_client.cookies.update(_auth(test_user))
        folder = await _create_folder(async_client, "Private")
        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/folders/{folder['id']}/tree")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_tree_shared_view_permission(self, async_client: AsyncClient, test_user: User, other_user: User):
        """Shared folder shows correct 'view' permission in tree."""
        async_client.cookies.update(_auth(test_user))
        folder = await _create_folder(async_client, "SharedTree")
        await _create_doc(async_client, "Shared Doc", folder_id=folder["id"])
        await async_client.post(
            f"/api/folders/{folder['id']}/collaborators",
            json={"email": other_user.email, "permission": "view"},
        )

        async_client.cookies.update(_auth(other_user))
        resp = await async_client.get(f"/api/folders/{folder['id']}/tree")
        assert resp.status_code == 200
        tree = resp.json()
        assert tree["permission"] == "view"
        assert len(tree["documents"]) == 1

    @pytest.mark.asyncio
    async def test_tree_nonexistent_folder(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        resp = await async_client.get("/api/folders/000000000000000000000000/tree")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_tree_documents_have_expected_fields(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth(test_user))
        folder = await _create_folder(async_client, "FieldCheck")
        await _create_doc(async_client, "Field Doc", folder_id=folder["id"])

        resp = await async_client.get(f"/api/folders/{folder['id']}/tree")
        tree = resp.json()
        doc = tree["documents"][0]
        assert "id" in doc
        assert "title" in doc
        assert "content_length" in doc
        assert "updated_at" in doc
