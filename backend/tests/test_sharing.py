"""Tests for sharing: general access, collaborators, permissions."""

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.models.document import Document_, GeneralAccess
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
    title: str = "Shared Doc",
    general_access: GeneralAccess = GeneralAccess.RESTRICTED,
) -> Document_:
    doc = Document_(
        title=title,
        content="# Hello",
        owner_id=str(owner.id),
        general_access=general_access,
    )
    await doc.insert()
    return doc


class TestGeneralAccess:
    """Tests for the general_access field and its effects on access control."""

    @pytest.mark.asyncio
    async def test_default_general_access_is_restricted(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.post(
            "/api/documents", json={"title": "New Doc"}
        )
        assert resp.status_code == 201
        assert resp.json()["general_access"] == "restricted"

    @pytest.mark.asyncio
    async def test_owner_can_update_general_access(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp = await async_client.put(
            f"/api/documents/{doc.id}/access",
            json={"general_access": "anyone_view"},
        )
        assert resp.status_code == 200
        assert resp.json()["general_access"] == "anyone_view"

    @pytest.mark.asyncio
    async def test_non_owner_cannot_update_general_access(
        self, async_client: AsyncClient, test_user: User
    ):
        other = await _make_user("g-other-ga", "other-ga@test.com", "Other")
        doc = await _make_doc(test_user)

        async_client.cookies.update(_auth_cookies(other))
        resp = await async_client.put(
            f"/api/documents/{doc.id}/access",
            json={"general_access": "anyone_edit"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_general_access_value(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp = await async_client.put(
            f"/api/documents/{doc.id}/access",
            json={"general_access": "invalid_value"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_anyone_view_grants_read_to_strangers(
        self, async_client: AsyncClient, test_user: User
    ):
        doc = await _make_doc(
            test_user, title="Public Doc", general_access=GeneralAccess.ANYONE_VIEW
        )
        stranger = await _make_user("g-stranger-av", "stranger-av@test.com", "Stranger")

        async_client.cookies.update(_auth_cookies(stranger))
        resp = await async_client.get(f"/api/documents/{doc.id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Public Doc"

    @pytest.mark.asyncio
    async def test_anyone_view_denies_edit_to_strangers(
        self, async_client: AsyncClient, test_user: User
    ):
        doc = await _make_doc(
            test_user, general_access=GeneralAccess.ANYONE_VIEW
        )
        stranger = await _make_user("g-stranger-av2", "stranger-av2@test.com", "Stranger2")

        async_client.cookies.update(_auth_cookies(stranger))
        resp = await async_client.put(
            f"/api/documents/{doc.id}",
            json={"title": "Hacked"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_anyone_edit_grants_edit_to_strangers(
        self, async_client: AsyncClient, test_user: User
    ):
        doc = await _make_doc(
            test_user, title="Open Doc", general_access=GeneralAccess.ANYONE_EDIT
        )
        stranger = await _make_user("g-stranger-ae", "stranger-ae@test.com", "Stranger3")

        async_client.cookies.update(_auth_cookies(stranger))
        resp = await async_client.put(
            f"/api/documents/{doc.id}",
            json={"title": "Updated by Stranger"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated by Stranger"

    @pytest.mark.asyncio
    async def test_restricted_denies_access_to_strangers(
        self, async_client: AsyncClient, test_user: User
    ):
        doc = await _make_doc(test_user)
        stranger = await _make_user("g-stranger-r", "stranger-r@test.com", "Stranger4")

        async_client.cookies.update(_auth_cookies(stranger))
        resp = await async_client.get(f"/api/documents/{doc.id}")
        assert resp.status_code == 403


class TestCollaboratorManagement:
    """Tests for adding, listing, and removing collaborators by email."""

    @pytest.mark.asyncio
    async def test_add_collaborator_by_email(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)
        collab = await _make_user("g-collab1", "collab1@test.com", "Collab One")

        resp = await async_client.post(
            f"/api/documents/{doc.id}/collaborators",
            json={"email": "collab1@test.com", "permission": "edit"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "collab1@test.com"
        assert data["name"] == "Collab One"
        assert data["permission"] == "edit"
        assert data["user_id"] == str(collab.id)

    @pytest.mark.asyncio
    async def test_add_nonexistent_email_returns_404(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp = await async_client.post(
            f"/api/documents/{doc.id}/collaborators",
            json={"email": "nobody@test.com", "permission": "view"},
        )
        assert resp.status_code == 404
        assert "No user found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_cannot_add_self_as_collaborator(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp = await async_client.post(
            f"/api/documents/{doc.id}/collaborators",
            json={"email": test_user.email, "permission": "edit"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_non_owner_cannot_add_collaborator(
        self, async_client: AsyncClient, test_user: User
    ):
        other = await _make_user("g-other-add", "other-add@test.com", "Other")
        doc = await _make_doc(test_user)

        async_client.cookies.update(_auth_cookies(other))
        resp = await async_client.post(
            f"/api/documents/{doc.id}/collaborators",
            json={"email": "someone@test.com", "permission": "view"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_collaborators(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)
        await _make_user("g-collab-list1", "clist1@test.com", "CList1")
        await _make_user("g-collab-list2", "clist2@test.com", "CList2")

        await async_client.post(
            f"/api/documents/{doc.id}/collaborators",
            json={"email": "clist1@test.com", "permission": "view"},
        )
        await async_client.post(
            f"/api/documents/{doc.id}/collaborators",
            json={"email": "clist2@test.com", "permission": "edit"},
        )

        resp = await async_client.get(f"/api/documents/{doc.id}/collaborators")
        assert resp.status_code == 200
        collabs = resp.json()
        assert len(collabs) == 2
        emails = {c["email"] for c in collabs}
        assert emails == {"clist1@test.com", "clist2@test.com"}

    @pytest.mark.asyncio
    async def test_remove_collaborator(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)
        collab = await _make_user("g-collab-rm", "crm@test.com", "CRemove")

        await async_client.post(
            f"/api/documents/{doc.id}/collaborators",
            json={"email": "crm@test.com", "permission": "view"},
        )

        resp = await async_client.delete(
            f"/api/documents/{doc.id}/collaborators/{collab.id}"
        )
        assert resp.status_code == 204

        list_resp = await async_client.get(
            f"/api/documents/{doc.id}/collaborators"
        )
        assert len(list_resp.json()) == 0

    @pytest.mark.asyncio
    async def test_update_existing_collaborator_permission(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)
        await _make_user("g-collab-upd", "cupd@test.com", "CUpdate")

        await async_client.post(
            f"/api/documents/{doc.id}/collaborators",
            json={"email": "cupd@test.com", "permission": "view"},
        )

        resp = await async_client.post(
            f"/api/documents/{doc.id}/collaborators",
            json={"email": "cupd@test.com", "permission": "edit"},
        )
        assert resp.status_code == 201
        assert resp.json()["permission"] == "edit"

        list_resp = await async_client.get(
            f"/api/documents/{doc.id}/collaborators"
        )
        assert len(list_resp.json()) == 1
        assert list_resp.json()[0]["permission"] == "edit"


class TestPermissionAwareAccess:
    """Tests for document access using explicit access and general_access."""

    @pytest.mark.asyncio
    async def test_shared_user_can_read_document(
        self, async_client: AsyncClient, test_user: User
    ):
        doc = await _make_doc(test_user, title="Readable")
        viewer = await _make_user("g-reader", "reader@test.com", "Reader")

        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(viewer.id),
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await access.insert()

        async_client.cookies.update(_auth_cookies(viewer))
        resp = await async_client.get(f"/api/documents/{doc.id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Readable"

    @pytest.mark.asyncio
    async def test_view_only_cannot_update(
        self, async_client: AsyncClient, test_user: User
    ):
        doc = await _make_doc(test_user, title="Read Only")
        viewer = await _make_user("g-viewonly", "viewonly@test.com", "ViewOnly")

        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(viewer.id),
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await access.insert()

        async_client.cookies.update(_auth_cookies(viewer))
        resp = await async_client.put(
            f"/api/documents/{doc.id}",
            json={"title": "Hacked"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_edit_user_can_update(
        self, async_client: AsyncClient, test_user: User
    ):
        doc = await _make_doc(test_user, title="Editable")
        editor = await _make_user("g-editor", "editor@test.com", "Editor")

        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(editor.id),
            permission=Permission.EDIT,
            granted_by=str(test_user.id),
        )
        await access.insert()

        async_client.cookies.update(_auth_cookies(editor))
        resp = await async_client.put(
            f"/api/documents/{doc.id}",
            json={"title": "Updated by Editor"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated by Editor"

    @pytest.mark.asyncio
    async def test_no_access_user_forbidden(
        self, async_client: AsyncClient, test_user: User
    ):
        doc = await _make_doc(test_user)
        stranger = await _make_user("g-stranger", "stranger@test.com", "Stranger")

        async_client.cookies.update(_auth_cookies(stranger))
        resp = await async_client.get(f"/api/documents/{doc.id}")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_explicit_access_overrides_general_access(
        self, async_client: AsyncClient, test_user: User
    ):
        """A user with explicit EDIT access should be able to edit even
        if general_access is restricted."""
        doc = await _make_doc(test_user, general_access=GeneralAccess.RESTRICTED)
        editor = await _make_user("g-explicit-e", "explicit-e@test.com", "ExplicitEditor")

        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(editor.id),
            permission=Permission.EDIT,
            granted_by=str(test_user.id),
        )
        await access.insert()

        async_client.cookies.update(_auth_cookies(editor))
        resp = await async_client.put(
            f"/api/documents/{doc.id}",
            json={"title": "Explicit Edit"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Explicit Edit"


class TestSharedDocumentsList:
    @pytest.mark.asyncio
    async def test_list_shared_with_me(
        self, async_client: AsyncClient, test_user: User
    ):
        doc = await _make_doc(test_user, title="Shared for List")
        viewer = await _make_user("g-lister", "lister@test.com", "Lister")

        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(viewer.id),
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await access.insert()

        async_client.cookies.update(_auth_cookies(viewer))
        resp = await async_client.get("/api/documents/shared")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Shared for List"
        assert data[0]["permission"] == "view"

    @pytest.mark.asyncio
    async def test_shared_list_empty(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.get("/api/documents/shared")
        assert resp.status_code == 200
        assert resp.json() == []
