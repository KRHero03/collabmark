"""Tests verifying server-controlled fields cannot be tampered with via API.

Covers mass-assignment protection, cross-org move prevention, and
schema-level input validation for all create/update endpoints.
"""

import pytest
from app.auth.jwt import create_access_token
from app.config import settings as cfg
from app.models.document import DocumentCreate, DocumentUpdate
from app.models.folder import FolderAccess, FolderCreate, FolderUpdate
from app.models.organization import Organization, OrgMembership, OrgRole
from app.models.share_link import DocumentAccess, Permission
from app.models.user import User
from app.services import document_service, folder_service
from fastapi import HTTPException
from httpx import AsyncClient


def _cookies(user: User) -> dict[str, str]:
    return {"access_token": create_access_token(str(user.id))}


async def _make_user(email: str, org_id: str | None = None) -> User:
    user = User(email=email, name=email.split("@")[0], avatar_url=None, org_id=org_id)
    await user.insert()
    return user


async def _make_org(slug: str) -> Organization:
    org = Organization(name=f"Org {slug}", slug=slug, verified_domains=[f"{slug}.com"])
    await org.insert()
    return org


# ---------------------------------------------------------------------------
# Mass assignment: readonly fields ignored by Pydantic schemas
# ---------------------------------------------------------------------------


class TestDocumentMassAssignment:
    """Extra fields in document create/update payloads should be silently ignored."""

    @pytest.mark.asyncio
    async def test_create_ignores_owner_id(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_cookies(test_user))
        resp = await async_client.post(
            "/api/documents",
            json={"title": "Hijack", "owner_id": "injected-id", "org_id": "injected-org"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["owner_id"] == str(test_user.id)
        assert "injected-id" not in data["owner_id"]

    @pytest.mark.asyncio
    async def test_update_ignores_owner_id(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_cookies(test_user))
        create = await async_client.post(
            "/api/documents",
            json={"title": "Doc"},
        )
        doc_id = create.json()["id"]
        resp = await async_client.put(
            f"/api/documents/{doc_id}",
            json={"title": "Updated", "owner_id": "hacked", "is_deleted": True, "general_access": "anyone_edit"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["owner_id"] == str(test_user.id)
        assert data["is_deleted"] is False
        assert data["general_access"] == "restricted"


class TestFolderMassAssignment:
    @pytest.mark.asyncio
    async def test_create_ignores_owner_id(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_cookies(test_user))
        resp = await async_client.post(
            "/api/folders",
            json={"name": "Hijack", "owner_id": "injected", "org_id": "injected"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["owner_id"] == str(test_user.id)

    @pytest.mark.asyncio
    async def test_update_ignores_owner_id(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_cookies(test_user))
        create = await async_client.post(
            "/api/folders",
            json={"name": "Folder"},
        )
        folder_id = create.json()["id"]
        resp = await async_client.put(
            f"/api/folders/{folder_id}",
            json={"name": "Renamed", "owner_id": "hacked", "is_deleted": True, "org_id": "hacked"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["owner_id"] == str(test_user.id)
        assert data["is_deleted"] is False


class TestUserMassAssignment:
    @pytest.mark.asyncio
    async def test_update_ignores_email_and_org(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_cookies(test_user))
        resp = await async_client.put(
            "/api/users/me",
            json={"name": "New Name", "email": "hacked@evil.com", "org_id": "hacked", "auth_provider": "hacked"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == test_user.email
        assert data["name"] == "New Name"
        assert data["org_id"] is None
        assert data["auth_provider"] == "google"


# ---------------------------------------------------------------------------
# Document folder_id: must validate access and org on move
# ---------------------------------------------------------------------------


class TestDocumentFolderIdValidation:
    @pytest.mark.asyncio
    async def test_update_folder_id_validates_access(self):
        """Moving a doc to a folder the user can't access should fail."""
        owner_a = await _make_user("own-a@test.com")
        owner_b = await _make_user("own-b@test.com")
        doc = await document_service.create_document(owner_a, DocumentCreate(title="MyDoc"))
        folder = await folder_service.create_folder(owner_b, FolderCreate(name="Private"))

        with pytest.raises(HTTPException) as exc_info:
            await document_service.update_document(str(doc.id), owner_a, DocumentUpdate(folder_id=str(folder.id)))
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_update_folder_id_blocks_cross_org(self):
        """Moving an org doc to a folder in a different org should fail."""
        org_a = await _make_org("move-a")
        org_b = await _make_org("move-b")
        owner = await _make_user("own@move-a.com", org_id=str(org_a.id))
        other_owner = await _make_user("own@move-b.com", org_id=str(org_b.id))

        doc = await document_service.create_document(owner, DocumentCreate(title="OrgDoc"))
        folder = await folder_service.create_folder(other_owner, FolderCreate(name="OtherOrgFolder"))

        from app.models.folder import FolderAccess

        access = FolderAccess(
            folder_id=str(folder.id),
            user_id=str(owner.id),
            permission=Permission.EDIT,
            granted_by=str(other_owner.id),
        )
        await access.insert()

        with pytest.raises(HTTPException) as exc_info:
            await document_service.update_document(str(doc.id), owner, DocumentUpdate(folder_id=str(folder.id)))
        assert exc_info.value.status_code == 403
        assert "different organization" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_folder_id_same_org_allowed(self):
        org = await _make_org("move-c")
        owner = await _make_user("own@move-c.com", org_id=str(org.id))
        doc = await document_service.create_document(owner, DocumentCreate(title="OrgDoc"))
        folder = await folder_service.create_folder(owner, FolderCreate(name="MyFolder"))

        updated = await document_service.update_document(str(doc.id), owner, DocumentUpdate(folder_id=str(folder.id)))
        assert updated.folder_id == str(folder.id)
        assert updated.root_folder_id is not None


# ---------------------------------------------------------------------------
# Folder parent_id: must validate access and org on move
# ---------------------------------------------------------------------------


class TestFolderParentIdValidation:
    @pytest.mark.asyncio
    async def test_move_folder_validates_target_access(self):
        owner_a = await _make_user("fown-a@test.com")
        owner_b = await _make_user("fown-b@test.com")
        folder = await folder_service.create_folder(owner_a, FolderCreate(name="MyFolder"))
        target = await folder_service.create_folder(owner_b, FolderCreate(name="Private"))

        with pytest.raises(HTTPException) as exc_info:
            await folder_service.update_folder(str(folder.id), owner_a, FolderUpdate(parent_id=str(target.id)))
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_move_folder_blocks_cross_org(self):
        org_a = await _make_org("fmove-a")
        org_b = await _make_org("fmove-b")
        owner = await _make_user("fown@fmove-a.com", org_id=str(org_a.id))
        other = await _make_user("fown@fmove-b.com", org_id=str(org_b.id))

        folder = await folder_service.create_folder(owner, FolderCreate(name="A"))
        target = await folder_service.create_folder(other, FolderCreate(name="B"))

        access = FolderAccess(
            folder_id=str(target.id),
            user_id=str(owner.id),
            permission=Permission.EDIT,
            granted_by=str(other.id),
        )
        await access.insert()

        with pytest.raises(HTTPException) as exc_info:
            await folder_service.update_folder(str(folder.id), owner, FolderUpdate(parent_id=str(target.id)))
        assert exc_info.value.status_code == 403
        assert "different organization" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_folder_blocks_cross_org_parent(self):
        org_a = await _make_org("fcreate-a")
        org_b = await _make_org("fcreate-b")
        owner = await _make_user("fown@fcreate-a.com", org_id=str(org_a.id))
        other = await _make_user("fown@fcreate-b.com", org_id=str(org_b.id))

        parent = await folder_service.create_folder(other, FolderCreate(name="OtherOrgParent"))

        access = FolderAccess(
            folder_id=str(parent.id),
            user_id=str(owner.id),
            permission=Permission.EDIT,
            granted_by=str(other.id),
        )
        await access.insert()

        with pytest.raises(HTTPException) as exc_info:
            await folder_service.create_folder(owner, FolderCreate(name="Nested", parent_id=str(parent.id)))
        assert exc_info.value.status_code == 403
        assert "different organization" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_doc_blocks_cross_org_folder(self):
        org_a = await _make_org("dcreate-a")
        org_b = await _make_org("dcreate-b")
        owner = await _make_user("down@dcreate-a.com", org_id=str(org_a.id))
        other = await _make_user("down@dcreate-b.com", org_id=str(org_b.id))

        folder = await folder_service.create_folder(other, FolderCreate(name="OtherOrgFolder"))

        access = FolderAccess(
            folder_id=str(folder.id),
            user_id=str(owner.id),
            permission=Permission.EDIT,
            granted_by=str(other.id),
        )
        await access.insert()

        with pytest.raises(HTTPException) as exc_info:
            await document_service.create_document(owner, DocumentCreate(title="Doc", folder_id=str(folder.id)))
        assert exc_info.value.status_code == 403
        assert "different organization" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Org member add: proper schema validation (no raw dict)
# ---------------------------------------------------------------------------


class TestOrgMemberAddSchema:
    @pytest.mark.asyncio
    async def test_add_member_rejects_invalid_role(self, async_client: AsyncClient):
        admin = await _make_user("superadmin@test.com")
        cfg.super_admin_emails = [admin.email]

        org = await _make_org("schema-test")
        await OrgMembership(org_id=str(org.id), user_id=str(admin.id), role=OrgRole.ADMIN).insert()
        admin.org_id = str(org.id)
        await admin.save()

        async_client.cookies.update(_cookies(admin))
        resp = await async_client.post(
            f"/api/orgs/{org.id}/members",
            json={"user_id": "someid", "role": "superduper"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_add_member_rejects_missing_user_id(self, async_client: AsyncClient):
        admin = await _make_user("superadmin2@test.com")
        cfg.super_admin_emails = [admin.email]

        org = await _make_org("schema-test-2")
        await OrgMembership(org_id=str(org.id), user_id=str(admin.id), role=OrgRole.ADMIN).insert()
        admin.org_id = str(org.id)
        await admin.save()

        async_client.cookies.update(_cookies(admin))
        resp = await async_client.post(
            f"/api/orgs/{org.id}/members",
            json={"role": "member"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# General access update: cannot set owner-only fields via document update
# ---------------------------------------------------------------------------


class TestGeneralAccessProtection:
    @pytest.mark.asyncio
    async def test_editor_cannot_change_general_access_via_doc_update(self, async_client: AsyncClient):
        """An editor (non-owner) should not be able to change general_access via PUT /api/documents."""
        owner = await _make_user("ga-own@test.com")
        editor = await _make_user("ga-edit@test.com")

        async_client.cookies.update(_cookies(owner))
        resp = await async_client.post(
            "/api/documents",
            json={"title": "Protected"},
        )
        doc_id = resp.json()["id"]

        access = DocumentAccess(
            document_id=doc_id,
            user_id=str(editor.id),
            permission=Permission.EDIT,
            granted_by=str(owner.id),
        )
        await access.insert()

        async_client.cookies.update(_cookies(editor))
        resp = await async_client.put(
            f"/api/documents/{doc_id}",
            json={"title": "Edited", "general_access": "anyone_edit"},
        )
        assert resp.status_code == 200
        assert resp.json()["general_access"] == "restricted"
        assert resp.json()["title"] == "Edited"
