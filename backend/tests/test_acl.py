"""Comprehensive tests for the ACL service: permission resolution, delete constraints,
hierarchy scenarios, consolidated ACL summary, and API endpoints.

Covers the User1/User2/User3 hierarchy scenario:
  User1 creates FolderA
  User1 shares FolderA with User2 (EDIT)
  User2 creates SubFolderB inside FolderA
  User2 creates DocX inside SubFolderB
  User3 gets VIEW on SubFolderB from User2
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.models.document import Document_, GeneralAccess
from app.models.folder import Folder, FolderAccess
from app.models.share_link import DocumentAccess, Permission
from app.models.user import User
from app.services.acl_service import (
    EffectivePermission,
    all_children_owned_by,
    find_root_folder_by_walk,
    find_root_folder_from_id,
    get_acl_summary,
    get_base_permission,
    get_root_owner_id,
    resolve_effective_permission,
)


def _auth(user: User) -> dict[str, str]:
    return {"access_token": create_access_token(str(user.id))}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def user1() -> User:
    u = User(google_id="acl-user1", email="user1@example.com", name="User One")
    await u.insert()
    return u


@pytest_asyncio.fixture
async def user2() -> User:
    u = User(google_id="acl-user2", email="user2@example.com", name="User Two")
    await u.insert()
    return u


@pytest_asyncio.fixture
async def user3() -> User:
    u = User(google_id="acl-user3", email="user3@example.com", name="User Three")
    await u.insert()
    return u


@pytest_asyncio.fixture
async def user4() -> User:
    """A user with absolutely no access."""
    u = User(google_id="acl-user4", email="user4@example.com", name="User Four")
    await u.insert()
    return u


@pytest_asyncio.fixture
async def hierarchy(user1: User, user2: User, user3: User):
    """Build the User1/User2/User3 test hierarchy:
    FolderA (User1) -> SubFolderB (User2) -> DocX (User2)
    User2 has EDIT on FolderA; User3 has VIEW on SubFolderB.
    """
    folder_a = Folder(
        name="FolderA",
        owner_id=str(user1.id),
        root_folder_id=None,
    )
    await folder_a.insert()
    folder_a.root_folder_id = str(folder_a.id)
    await folder_a.save()

    await FolderAccess(
        folder_id=str(folder_a.id),
        user_id=str(user2.id),
        permission=Permission.EDIT,
        granted_by=str(user1.id),
    ).insert()

    sub_folder_b = Folder(
        name="SubFolderB",
        owner_id=str(user2.id),
        parent_id=str(folder_a.id),
        root_folder_id=str(folder_a.id),
    )
    await sub_folder_b.insert()

    await FolderAccess(
        folder_id=str(sub_folder_b.id),
        user_id=str(user3.id),
        permission=Permission.VIEW,
        granted_by=str(user2.id),
    ).insert()

    doc_x = Document_(
        title="DocX",
        content="test content",
        owner_id=str(user2.id),
        folder_id=str(sub_folder_b.id),
        root_folder_id=str(folder_a.id),
    )
    await doc_x.insert()

    return {
        "folder_a": folder_a,
        "sub_folder_b": sub_folder_b,
        "doc_x": doc_x,
    }


# =====================================================================
# find_root_folder helpers
# =====================================================================

class TestFindRootFolder:
    @pytest.mark.asyncio
    async def test_find_root_via_denormalized_id(self, hierarchy, user1):
        root = await find_root_folder_from_id(hierarchy["sub_folder_b"].root_folder_id)
        assert root is not None
        assert str(root.id) == str(hierarchy["folder_a"].id)
        assert root.owner_id == str(user1.id)

    @pytest.mark.asyncio
    async def test_find_root_by_walk(self, hierarchy, user1):
        root = await find_root_folder_by_walk(str(hierarchy["sub_folder_b"].id))
        assert root is not None
        assert str(root.id) == str(hierarchy["folder_a"].id)

    @pytest.mark.asyncio
    async def test_find_root_returns_none_for_invalid(self):
        result = await find_root_folder_from_id("000000000000000000000000")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_root_owner_id_for_doc(self, hierarchy, user1):
        doc = hierarchy["doc_x"]
        root_owner = await get_root_owner_id(doc, "document")
        assert root_owner == str(user1.id)

    @pytest.mark.asyncio
    async def test_get_root_owner_id_for_subfolder(self, hierarchy, user1):
        sf = hierarchy["sub_folder_b"]
        root_owner = await get_root_owner_id(sf, "folder")
        assert root_owner == str(user1.id)

    @pytest.mark.asyncio
    async def test_get_root_owner_id_for_root_folder(self, hierarchy, user1):
        fa = hierarchy["folder_a"]
        root_owner = await get_root_owner_id(fa, "folder")
        assert root_owner == str(user1.id)


# =====================================================================
# all_children_owned_by
# =====================================================================

class TestAllChildrenOwnedBy:
    @pytest.mark.asyncio
    async def test_folder_with_foreign_children(self, hierarchy, user1, user2):
        assert await all_children_owned_by(str(hierarchy["folder_a"].id), str(user1.id)) is False

    @pytest.mark.asyncio
    async def test_subfolder_owned_by_creator(self, hierarchy, user2):
        assert await all_children_owned_by(str(hierarchy["sub_folder_b"].id), str(user2.id)) is True

    @pytest.mark.asyncio
    async def test_empty_folder(self, user1):
        empty = Folder(name="Empty", owner_id=str(user1.id))
        await empty.insert()
        assert await all_children_owned_by(str(empty.id), str(user1.id)) is True


# =====================================================================
# get_base_permission
# =====================================================================

class TestGetBasePermission:
    @pytest.mark.asyncio
    async def test_owner_gets_edit(self, hierarchy, user2):
        perm = await get_base_permission("document", str(hierarchy["doc_x"].id), str(user2.id))
        assert perm == Permission.EDIT

    @pytest.mark.asyncio
    async def test_folder_chain_inheritance(self, hierarchy, user2):
        perm = await get_base_permission("folder", str(hierarchy["sub_folder_b"].id), str(user2.id))
        assert perm == Permission.EDIT

    @pytest.mark.asyncio
    async def test_viewer_via_folder_access(self, hierarchy, user3):
        perm = await get_base_permission("folder", str(hierarchy["sub_folder_b"].id), str(user3.id))
        assert perm == Permission.VIEW

    @pytest.mark.asyncio
    async def test_no_access_returns_none(self, hierarchy, user4):
        perm = await get_base_permission("document", str(hierarchy["doc_x"].id), str(user4.id))
        assert perm is None

    @pytest.mark.asyncio
    async def test_doc_inherits_from_parent_folder(self, hierarchy, user3):
        perm = await get_base_permission("document", str(hierarchy["doc_x"].id), str(user3.id))
        assert perm == Permission.VIEW

    @pytest.mark.asyncio
    async def test_general_access_anyone_view(self, user1, user4):
        doc = Document_(
            title="Public",
            content="",
            owner_id=str(user1.id),
            general_access=GeneralAccess.ANYONE_VIEW,
        )
        await doc.insert()
        perm = await get_base_permission("document", str(doc.id), str(user4.id))
        assert perm == Permission.VIEW

    @pytest.mark.asyncio
    async def test_general_access_anyone_edit(self, user1, user4):
        doc = Document_(
            title="Editable",
            content="",
            owner_id=str(user1.id),
            general_access=GeneralAccess.ANYONE_EDIT,
        )
        await doc.insert()
        perm = await get_base_permission("document", str(doc.id), str(user4.id))
        assert perm == Permission.EDIT


# =====================================================================
# resolve_effective_permission
# =====================================================================

class TestResolveEffectivePermission:
    """Tests for the core permission resolver covering all roles."""

    @pytest.mark.asyncio
    async def test_root_owner_on_subfolder(self, hierarchy, user1):
        """User1 (root owner of FolderA) should have full control on SubFolderB."""
        perm = await resolve_effective_permission("folder", str(hierarchy["sub_folder_b"].id), user1)
        assert perm.can_view is True
        assert perm.can_edit is True
        assert perm.can_delete is True
        assert perm.can_share is True
        assert perm.role == "root_owner"

    @pytest.mark.asyncio
    async def test_root_owner_on_doc(self, hierarchy, user1):
        """User1 (root owner) has full control on DocX created by User2."""
        perm = await resolve_effective_permission("document", str(hierarchy["doc_x"].id), user1)
        assert perm.can_view is True
        assert perm.can_edit is True
        assert perm.can_delete is True
        assert perm.role == "root_owner"

    @pytest.mark.asyncio
    async def test_entity_owner_at_root(self, hierarchy, user1):
        """User1 is the owner of FolderA (which is at root level) -> full control."""
        perm = await resolve_effective_permission("folder", str(hierarchy["folder_a"].id), user1)
        assert perm.can_view is True
        assert perm.can_edit is True
        assert perm.can_delete is True
        assert perm.can_share is True
        assert perm.role == "owner"

    @pytest.mark.asyncio
    async def test_entity_owner_nested_can_delete_own_content(self, hierarchy, user2):
        """User2 owns SubFolderB and all its content -> can_delete=True."""
        perm = await resolve_effective_permission("folder", str(hierarchy["sub_folder_b"].id), user2)
        assert perm.can_view is True
        assert perm.can_edit is True
        assert perm.can_delete is True
        assert perm.can_share is True
        assert perm.role == "owner"

    @pytest.mark.asyncio
    async def test_entity_owner_nested_cannot_delete_mixed_content(self, user1, user2):
        """Entity owner cannot delete a folder if children belong to another user."""
        root = Folder(name="Root", owner_id=str(user1.id))
        await root.insert()
        root.root_folder_id = str(root.id)
        await root.save()

        await FolderAccess(
            folder_id=str(root.id),
            user_id=str(user2.id),
            permission=Permission.EDIT,
            granted_by=str(user1.id),
        ).insert()

        sub = Folder(
            name="Sub",
            owner_id=str(user2.id),
            parent_id=str(root.id),
            root_folder_id=str(root.id),
        )
        await sub.insert()

        doc_by_user1 = Document_(
            title="Alien",
            content="",
            owner_id=str(user1.id),
            folder_id=str(sub.id),
            root_folder_id=str(root.id),
        )
        await doc_by_user1.insert()

        perm = await resolve_effective_permission("folder", str(sub.id), user2)
        assert perm.role == "owner"
        assert perm.can_delete is False

    @pytest.mark.asyncio
    async def test_doc_owner_can_always_delete_doc(self, hierarchy, user2):
        """Document owners can always delete their own documents."""
        perm = await resolve_effective_permission("document", str(hierarchy["doc_x"].id), user2)
        assert perm.can_delete is True
        assert perm.role == "owner"

    @pytest.mark.asyncio
    async def test_editor_via_folder_access(self, hierarchy, user2):
        """User2 has EDIT on FolderA (the root folder). Check as editor on FolderA itself."""
        perm = await resolve_effective_permission("folder", str(hierarchy["folder_a"].id), user2)
        assert perm.can_view is True
        assert perm.can_edit is True
        assert perm.can_delete is False
        assert perm.can_share is False
        assert perm.role == "editor"

    @pytest.mark.asyncio
    async def test_viewer_on_subfolder(self, hierarchy, user3):
        """User3 has VIEW on SubFolderB."""
        perm = await resolve_effective_permission("folder", str(hierarchy["sub_folder_b"].id), user3)
        assert perm.can_view is True
        assert perm.can_edit is False
        assert perm.can_delete is False
        assert perm.can_share is False
        assert perm.role == "viewer"

    @pytest.mark.asyncio
    async def test_viewer_on_doc_via_inheritance(self, hierarchy, user3):
        """User3 has VIEW on SubFolderB, so DocX inside it should be viewable."""
        perm = await resolve_effective_permission("document", str(hierarchy["doc_x"].id), user3)
        assert perm.can_view is True
        assert perm.can_edit is False
        assert perm.can_delete is False
        assert perm.role == "viewer"

    @pytest.mark.asyncio
    async def test_no_access_user(self, hierarchy, user4):
        """User4 has zero access."""
        perm = await resolve_effective_permission("folder", str(hierarchy["folder_a"].id), user4)
        assert perm.can_view is False
        assert perm.can_edit is False
        assert perm.role == "none"

    @pytest.mark.asyncio
    async def test_root_level_doc_owner(self, user1):
        """A doc at root level (no folder) -> owner has full control."""
        doc = Document_(title="Root Doc", content="", owner_id=str(user1.id))
        await doc.insert()
        perm = await resolve_effective_permission("document", str(doc.id), user1)
        assert perm.can_view is True
        assert perm.can_edit is True
        assert perm.can_delete is True
        assert perm.can_share is True
        assert perm.role == "owner"

    @pytest.mark.asyncio
    async def test_invalid_entity_id_returns_no_access(self, user1):
        perm = await resolve_effective_permission("document", "invalid", user1)
        assert perm.role == "none"

    @pytest.mark.asyncio
    async def test_nonexistent_entity_returns_no_access(self, user1):
        perm = await resolve_effective_permission("document", "000000000000000000000000", user1)
        assert perm.role == "none"


# =====================================================================
# ACL Summary
# =====================================================================

class TestAclSummary:
    @pytest.mark.asyncio
    async def test_folder_acl_summary(self, hierarchy, user1, user2, user3):
        """ACL summary for SubFolderB should include User1 (root_owner),
        User2 (owner), and User3 (viewer)."""
        entries = await get_acl_summary("folder", str(hierarchy["sub_folder_b"].id))
        user_ids = {e.user_id for e in entries}
        assert str(user2.id) in user_ids  # owner
        assert str(user1.id) in user_ids  # root owner via chain
        assert str(user3.id) in user_ids  # viewer

        roles = {e.user_id: e.role for e in entries}
        assert roles[str(user2.id)] == "owner"
        assert roles[str(user1.id)] == "root_owner"
        assert roles[str(user3.id)] == "viewer"

    @pytest.mark.asyncio
    async def test_doc_acl_summary(self, hierarchy, user1, user2, user3):
        """ACL summary for DocX should include all three users."""
        entries = await get_acl_summary("document", str(hierarchy["doc_x"].id))
        user_ids = {e.user_id for e in entries}
        assert str(user2.id) in user_ids
        assert str(user1.id) in user_ids
        assert str(user3.id) in user_ids

    @pytest.mark.asyncio
    async def test_root_folder_acl_summary(self, hierarchy, user1, user2):
        """ACL summary for FolderA should include User1 (owner) and User2 (editor)."""
        entries = await get_acl_summary("folder", str(hierarchy["folder_a"].id))
        user_ids = {e.user_id for e in entries}
        assert str(user1.id) in user_ids
        assert str(user2.id) in user_ids

    @pytest.mark.asyncio
    async def test_acl_summary_with_doc_access(self, user1, user2):
        """Direct DocumentAccess should appear in summary."""
        doc = Document_(title="Shared", content="", owner_id=str(user1.id))
        await doc.insert()
        await DocumentAccess(
            document_id=str(doc.id),
            user_id=str(user2.id),
            permission=Permission.VIEW,
            granted_by=str(user1.id),
        ).insert()

        entries = await get_acl_summary("document", str(doc.id))
        user_ids = {e.user_id for e in entries}
        assert str(user1.id) in user_ids
        assert str(user2.id) in user_ids

    @pytest.mark.asyncio
    async def test_acl_summary_empty_for_invalid(self):
        entries = await get_acl_summary("document", "000000000000000000000000")
        assert entries == []


# =====================================================================
# ACL API Endpoints
# =====================================================================

class TestAclEndpoints:
    @pytest.mark.asyncio
    async def test_folder_acl_endpoint(self, async_client: AsyncClient, hierarchy, user1):
        async_client.cookies.update(_auth(user1))
        resp = await async_client.get(f"/api/folders/{hierarchy['folder_a'].id}/acl")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    @pytest.mark.asyncio
    async def test_document_acl_endpoint(self, async_client: AsyncClient, hierarchy, user1):
        async_client.cookies.update(_auth(user1))
        resp = await async_client.get(f"/api/documents/{hierarchy['doc_x'].id}/acl")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

    @pytest.mark.asyncio
    async def test_acl_endpoint_no_access(self, async_client: AsyncClient, hierarchy, user4):
        async_client.cookies.update(_auth(user4))
        resp = await async_client.get(f"/api/folders/{hierarchy['folder_a'].id}/acl")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_acl_endpoint_viewer_can_view(self, async_client: AsyncClient, hierarchy, user3):
        async_client.cookies.update(_auth(user3))
        resp = await async_client.get(f"/api/folders/{hierarchy['sub_folder_b'].id}/acl")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_acl_response_shape(self, async_client: AsyncClient, hierarchy, user1):
        async_client.cookies.update(_auth(user1))
        resp = await async_client.get(f"/api/folders/{hierarchy['sub_folder_b'].id}/acl")
        assert resp.status_code == 200
        for entry in resp.json():
            assert "user_id" in entry
            assert "can_view" in entry
            assert "can_edit" in entry
            assert "can_delete" in entry
            assert "can_share" in entry
            assert "role" in entry


# =====================================================================
# Delete Permission Integration
# =====================================================================

class TestDeletePermission:
    @pytest.mark.asyncio
    async def test_editor_cannot_delete_folder(self, async_client: AsyncClient, hierarchy, user2):
        """User2 has EDIT on FolderA but is not owner -> cannot delete FolderA."""
        async_client.cookies.update(_auth(user2))
        resp = await async_client.delete(f"/api/folders/{hierarchy['folder_a'].id}")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_root_owner_can_delete_subfolder(self, async_client: AsyncClient, hierarchy, user1):
        """User1 (root owner) can always delete SubFolderB."""
        async_client.cookies.update(_auth(user1))
        resp = await async_client.delete(f"/api/folders/{hierarchy['sub_folder_b'].id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_owner_can_delete_own_doc(self, async_client: AsyncClient, hierarchy, user2):
        """User2 owns DocX -> can delete it."""
        async_client.cookies.update(_auth(user2))
        resp = await async_client.delete(f"/api/documents/{hierarchy['doc_x'].id}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_cannot_delete(self, async_client: AsyncClient, hierarchy, user3):
        """User3 has only VIEW -> cannot delete."""
        async_client.cookies.update(_auth(user3))
        resp = await async_client.delete(f"/api/folders/{hierarchy['sub_folder_b'].id}")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_no_access_user_cannot_delete(self, async_client: AsyncClient, hierarchy, user4):
        async_client.cookies.update(_auth(user4))
        resp = await async_client.delete(f"/api/folders/{hierarchy['folder_a'].id}")
        assert resp.status_code == 403


# =====================================================================
# root_folder_id denormalization
# =====================================================================

class TestRootFolderIdDenormalization:
    @pytest.mark.asyncio
    async def test_root_folder_id_set_on_root_folder(self, async_client: AsyncClient, user1: User):
        """Root folder should have root_folder_id = its own id."""
        async_client.cookies.update(_auth(user1))
        resp = await async_client.post("/api/folders", json={"name": "Root"})
        assert resp.status_code == 201
        f = await Folder.get(resp.json()["id"])
        assert f.root_folder_id == str(f.id)

    @pytest.mark.asyncio
    async def test_root_folder_id_inherited_on_child(self, async_client: AsyncClient, user1: User):
        """Child folder should inherit root_folder_id from parent."""
        async_client.cookies.update(_auth(user1))
        parent = (await async_client.post("/api/folders", json={"name": "Parent"})).json()
        child = (await async_client.post("/api/folders", json={"name": "Child", "parent_id": parent["id"]})).json()
        cf = await Folder.get(child["id"])
        assert cf.root_folder_id == parent["id"]

    @pytest.mark.asyncio
    async def test_root_folder_id_on_document(self, async_client: AsyncClient, user1: User):
        """Document inside folder should get root_folder_id from the folder."""
        async_client.cookies.update(_auth(user1))
        folder = (await async_client.post("/api/folders", json={"name": "F"})).json()
        doc = (await async_client.post("/api/documents", json={"title": "D", "folder_id": folder["id"]})).json()
        d = await Document_.get(doc["id"])
        assert d.root_folder_id == folder["id"]

    @pytest.mark.asyncio
    async def test_root_level_doc_has_no_root_folder_id(self, async_client: AsyncClient, user1: User):
        """A document at root level (no folder) should have root_folder_id=None."""
        async_client.cookies.update(_auth(user1))
        doc = (await async_client.post("/api/documents", json={"title": "Orphan"})).json()
        d = await Document_.get(doc["id"])
        assert d.root_folder_id is None


# =====================================================================
# Coverage: _get_folder, find_root_folder_from_id(None), find_root_folder_by_walk
# =====================================================================

class TestAclServiceEdgeCases:
    """Tests for ACL service edge cases and missing branches."""

    @pytest.mark.asyncio
    async def test_find_root_folder_from_id_none_returns_none(self):
        result = await find_root_folder_from_id(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_find_root_folder_by_walk_invalid_id_returns_none(self):
        result = await find_root_folder_by_walk("invalid-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_root_folder_by_walk_nonexistent_id_returns_none(self):
        result = await find_root_folder_by_walk("000000000000000000000000")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_root_folder_by_walk_cycle_detection(self, user1):
        """Cycle in parent_id chain: A->B->A. Should exit via visited check, return last folder."""
        folder_a = Folder(name="A", owner_id=str(user1.id))
        await folder_a.insert()
        folder_b = Folder(
            name="B",
            owner_id=str(user1.id),
            parent_id=str(folder_a.id),
        )
        await folder_b.insert()
        folder_a.parent_id = str(folder_b.id)
        await folder_a.save()

        result = await find_root_folder_by_walk(str(folder_a.id))
        assert result is not None
        assert result.name == "B"

    @pytest.mark.asyncio
    async def test_get_root_owner_id_doc_no_folder_no_root_returns_none(self, user1):
        """Document with folder_id=None and root_folder_id=None -> returns None."""
        doc = Document_(title="Orphan", content="", owner_id=str(user1.id))
        await doc.insert()
        result = await get_root_owner_id(doc, "document")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_root_owner_id_folder_at_root_returns_owner(self, user1):
        """Folder at root (parent_id=None) -> returns entity.owner_id."""
        folder = Folder(name="Root", owner_id=str(user1.id))
        await folder.insert()
        result = await get_root_owner_id(folder, "folder")
        assert result == str(user1.id)

    @pytest.mark.asyncio
    async def test_get_root_owner_id_doc_invalid_root_folder_id(self, user1):
        """Document with root_folder_id pointing to nonexistent folder -> returns None."""
        doc = Document_(
            title="Bad Root",
            content="",
            owner_id=str(user1.id),
            root_folder_id="000000000000000000000000",
        )
        await doc.insert()
        result = await get_root_owner_id(doc, "document")
        assert result is None

    @pytest.mark.asyncio
    async def test_all_children_owned_by_deep_nested_mixed_ownership(self, user1, user2):
        """Folder with grandchild doc owned by different user -> returns False."""
        root = Folder(name="R", owner_id=str(user1.id))
        await root.insert()
        root.root_folder_id = str(root.id)
        await root.save()

        await FolderAccess(
            folder_id=str(root.id),
            user_id=str(user2.id),
            permission=Permission.EDIT,
            granted_by=str(user1.id),
        ).insert()

        sub = Folder(
            name="Sub",
            owner_id=str(user2.id),
            parent_id=str(root.id),
            root_folder_id=str(root.id),
        )
        await sub.insert()

        doc_in_sub = Document_(
            title="Alien",
            content="",
            owner_id=str(user1.id),
            folder_id=str(sub.id),
            root_folder_id=str(root.id),
        )
        await doc_in_sub.insert()

        assert await all_children_owned_by(str(sub.id), str(user2.id)) is False

    @pytest.mark.asyncio
    async def test_get_base_permission_invalid_document_id(self, user1):
        perm = await get_base_permission("document", "invalid", str(user1.id))
        assert perm is None

    @pytest.mark.asyncio
    async def test_get_base_permission_nonexistent_document_id(self, user1):
        perm = await get_base_permission("document", "000000000000000000000000", str(user1.id))
        assert perm is None

    @pytest.mark.asyncio
    async def test_get_base_permission_invalid_folder_id(self, user1):
        perm = await get_base_permission("folder", "invalid", str(user1.id))
        assert perm is None

    @pytest.mark.asyncio
    async def test_get_base_permission_nonexistent_folder_id(self, user1):
        perm = await get_base_permission("folder", "000000000000000000000000", str(user1.id))
        assert perm is None

    @pytest.mark.asyncio
    async def test_get_base_permission_folder_general_access_anyone_edit(self, user1, user4):
        folder = Folder(
            name="Public Edit",
            owner_id=str(user1.id),
            general_access=GeneralAccess.ANYONE_EDIT,
        )
        await folder.insert()
        perm = await get_base_permission("folder", str(folder.id), str(user4.id))
        assert perm == Permission.EDIT

    @pytest.mark.asyncio
    async def test_get_base_permission_folder_general_access_anyone_view(self, user1, user4):
        folder = Folder(
            name="Public View",
            owner_id=str(user1.id),
            general_access=GeneralAccess.ANYONE_VIEW,
        )
        await folder.insert()
        perm = await get_base_permission("folder", str(folder.id), str(user4.id))
        assert perm == Permission.VIEW

    @pytest.mark.asyncio
    async def test_resolve_effective_permission_invalid_folder_id_returns_no_access(self, user1):
        perm = await resolve_effective_permission("folder", "invalid", user1)
        assert perm.role == "none"
        assert perm.can_view is False

    @pytest.mark.asyncio
    async def test_resolve_effective_permission_nonexistent_folder_id_returns_no_access(self, user1):
        perm = await resolve_effective_permission("folder", "000000000000000000000000", user1)
        assert perm.role == "none"

    @pytest.mark.asyncio
    async def test_get_acl_summary_invalid_folder_id_returns_empty(self):
        entries = await get_acl_summary("folder", "invalid")
        assert entries == []

    @pytest.mark.asyncio
    async def test_get_acl_summary_invalid_document_id_returns_empty(self):
        entries = await get_acl_summary("document", "invalid")
        assert entries == []

    @pytest.mark.asyncio
    async def test_get_acl_summary_nonexistent_folder_id_returns_empty(self):
        entries = await get_acl_summary("folder", "000000000000000000000000")
        assert entries == []

    @pytest.mark.asyncio
    async def test_get_acl_summary_skips_invalid_user_ids_in_chain(self, user1):
        """Folder chain with FolderAccess containing invalid user_id -> skips that user."""
        folder = Folder(name="F", owner_id=str(user1.id))
        await folder.insert()
        folder.root_folder_id = str(folder.id)
        await folder.save()

        await FolderAccess(
            folder_id=str(folder.id),
            user_id="000000000000000000000001",
            permission=Permission.VIEW,
            granted_by=str(user1.id),
        ).insert()

        entries = await get_acl_summary("folder", str(folder.id))
        user_ids = {e.user_id for e in entries}
        assert str(user1.id) in user_ids
        assert "000000000000000000000001" not in user_ids

    @pytest.mark.asyncio
    async def test_get_acl_summary_skips_invalid_owner_in_parent_chain(self, user1, user2):
        """Document in folder whose parent folder has owner_id pointing to deleted/invalid user."""
        folder = Folder(name="Parent", owner_id=str(user1.id))
        await folder.insert()
        folder.root_folder_id = str(folder.id)
        await folder.save()

        sub = Folder(
            name="Child",
            owner_id=str(user2.id),
            parent_id=str(folder.id),
            root_folder_id=str(folder.id),
        )
        await sub.insert()

        doc = Document_(
            title="Doc",
            content="",
            owner_id=str(user2.id),
            folder_id=str(sub.id),
            root_folder_id=str(folder.id),
        )
        await doc.insert()

        await FolderAccess(
            folder_id=str(sub.id),
            user_id="invalid-user-id-xyz",
            permission=Permission.VIEW,
            granted_by=str(user2.id),
        ).insert()

        entries = await get_acl_summary("document", str(doc.id))
        assert len(entries) >= 2
        invalid_ids = [e for e in entries if e.user_id == "invalid-user-id-xyz"]
        assert len(invalid_ids) == 0
