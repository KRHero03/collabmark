"""Comprehensive tests for Organization feature: CRUD, membership, SSO config, model fields, and service helpers."""

import pytest
from app.auth.jwt import create_access_token
from app.config import settings
from app.models.document import Document_
from app.models.folder import Folder
from app.models.organization import Organization, OrgMembership, OrgRole
from app.models.user import User
from app.services import org_service
from beanie import PydanticObjectId
from fastapi import HTTPException
from httpx import AsyncClient


def _auth_cookies(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"access_token": token}


# ---------------------------------------------------------------------------
# Organization CRUD (super admin)
# ---------------------------------------------------------------------------


class TestOrganizationCRUD:
    @pytest.mark.asyncio
    async def test_create_org_returns_201_with_correct_data(self, async_client: AsyncClient, test_user: User):
        original = settings.super_admin_emails
        settings.super_admin_emails = ["test@example.com"]
        try:
            async_client.cookies.update(_auth_cookies(test_user))
            response = await async_client.post(
                "/api/orgs",
                json={
                    "name": "Acme Corp",
                    "slug": "acme",
                    "verified_domains": ["acme.com"],
                },
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "Acme Corp"
            assert data["slug"] == "acme"
            assert data["verified_domains"] == ["acme.com"]
            assert data["member_count"] == 1
            assert "id" in data
        finally:
            settings.super_admin_emails = original

    @pytest.mark.asyncio
    async def test_create_org_with_duplicate_slug_returns_409(self, async_client: AsyncClient, test_user: User):
        original = settings.super_admin_emails
        settings.super_admin_emails = ["test@example.com"]
        try:
            async_client.cookies.update(_auth_cookies(test_user))
            await async_client.post(
                "/api/orgs",
                json={"name": "First Org", "slug": "dupe"},
            )
            response = await async_client.post(
                "/api/orgs",
                json={"name": "Second Org", "slug": "dupe"},
            )
            assert response.status_code == 409
        finally:
            settings.super_admin_emails = original

    @pytest.mark.asyncio
    async def test_list_orgs_returns_all_orgs(self, async_client: AsyncClient, test_user: User):
        original = settings.super_admin_emails
        settings.super_admin_emails = ["test@example.com"]
        try:
            async_client.cookies.update(_auth_cookies(test_user))
            await async_client.post(
                "/api/orgs",
                json={"name": "Org A", "slug": "org-a"},
            )
            await async_client.post(
                "/api/orgs",
                json={"name": "Org B", "slug": "org-b"},
            )
            response = await async_client.get("/api/orgs")
            assert response.status_code == 200
            orgs = response.json()
            assert len(orgs) >= 2
            slugs = {o["slug"] for o in orgs}
            assert "org-a" in slugs
            assert "org-b" in slugs
        finally:
            settings.super_admin_emails = original

    @pytest.mark.asyncio
    async def test_get_org_by_id_returns_org(self, async_client: AsyncClient, test_user: User):
        original = settings.super_admin_emails
        settings.super_admin_emails = ["test@example.com"]
        try:
            async_client.cookies.update(_auth_cookies(test_user))
            create_resp = await async_client.post(
                "/api/orgs",
                json={"name": "Get Me Org", "slug": "get-me"},
            )
            org_id = create_resp.json()["id"]
            response = await async_client.get(f"/api/orgs/{org_id}")
            assert response.status_code == 200
            assert response.json()["name"] == "Get Me Org"
            assert response.json()["slug"] == "get-me"
        finally:
            settings.super_admin_emails = original

    @pytest.mark.asyncio
    async def test_update_org_name_and_slug(self, async_client: AsyncClient, test_user: User):
        original = settings.super_admin_emails
        settings.super_admin_emails = ["test@example.com"]
        try:
            async_client.cookies.update(_auth_cookies(test_user))
            create_resp = await async_client.post(
                "/api/orgs",
                json={"name": "Original", "slug": "original"},
            )
            org_id = create_resp.json()["id"]
            response = await async_client.put(
                f"/api/orgs/{org_id}",
                json={"name": "Updated Name", "slug": "updated-slug"},
            )
            assert response.status_code == 200
            assert response.json()["name"] == "Updated Name"
            assert response.json()["slug"] == "updated-slug"
        finally:
            settings.super_admin_emails = original

    @pytest.mark.asyncio
    async def test_update_org_with_conflicting_slug_returns_409(self, async_client: AsyncClient, test_user: User):
        original = settings.super_admin_emails
        settings.super_admin_emails = ["test@example.com"]
        try:
            async_client.cookies.update(_auth_cookies(test_user))
            await async_client.post(
                "/api/orgs",
                json={"name": "Org One", "slug": "taken"},
            )
            create_resp = await async_client.post(
                "/api/orgs",
                json={"name": "Org Two", "slug": "mine"},
            )
            org_id = create_resp.json()["id"]
            response = await async_client.put(
                f"/api/orgs/{org_id}",
                json={"slug": "taken"},
            )
            assert response.status_code == 409
        finally:
            settings.super_admin_emails = original

    @pytest.mark.asyncio
    async def test_non_super_admin_gets_403_on_create(self, async_client: AsyncClient, test_user: User):
        # test_user is NOT in super_admin_emails (default empty)
        async_client.cookies.update(_auth_cookies(test_user))
        response = await async_client.post(
            "/api/orgs",
            json={"name": "Hacker Org", "slug": "hacker"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_non_super_admin_gets_403_on_list(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        response = await async_client.get("/api/orgs")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Member management (org admin)
# ---------------------------------------------------------------------------


@pytest.fixture
async def org_with_admin(async_client: AsyncClient, test_user: User) -> tuple[str, User]:
    """Create an org with test_user as admin. Returns (org_id, admin_user)."""
    original = settings.super_admin_emails
    settings.super_admin_emails = ["test@example.com"]
    try:
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.post(
            "/api/orgs",
            json={"name": "Admin Org", "slug": "admin-org"},
        )
        org_id = resp.json()["id"]
        return org_id, test_user
    finally:
        settings.super_admin_emails = original


@pytest.fixture
async def other_user_for_org() -> User:
    user = User(
        google_id="google-other-org",
        email="other-org@example.com",
        name="Other Org User",
    )
    await user.insert()
    return user


class TestMemberManagement:
    @pytest.mark.asyncio
    async def test_add_member_returns_201(self, async_client: AsyncClient, org_with_admin, other_user_for_org: User):
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(other_user_for_org.id), "role": "member"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == str(other_user_for_org.id)
        assert data["role"] == "member"

    @pytest.mark.asyncio
    async def test_add_member_already_member_returns_409(
        self, async_client: AsyncClient, org_with_admin, other_user_for_org: User
    ):
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(other_user_for_org.id), "role": "member"},
        )
        response = await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(other_user_for_org.id), "role": "admin"},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_add_member_belongs_to_another_org_returns_409(
        self, async_client: AsyncClient, test_user: User, other_user_for_org: User
    ):
        original = settings.super_admin_emails
        settings.super_admin_emails = ["test@example.com"]
        try:
            async_client.cookies.update(_auth_cookies(test_user))
            org1_resp = await async_client.post(
                "/api/orgs",
                json={"name": "Org 1", "slug": "org-1"},
            )
            org1_id = org1_resp.json()["id"]
            org2_resp = await async_client.post(
                "/api/orgs",
                json={"name": "Org 2", "slug": "org-2"},
            )
            org2_id = org2_resp.json()["id"]
            # Add other_user to org2
            await async_client.post(
                f"/api/orgs/{org2_id}/members",
                json={"user_id": str(other_user_for_org.id), "role": "member"},
            )
            # Try to add same user to org1
            response = await async_client.post(
                f"/api/orgs/{org1_id}/members",
                json={"user_id": str(other_user_for_org.id), "role": "member"},
            )
            assert response.status_code == 409
        finally:
            settings.super_admin_emails = original

    @pytest.mark.asyncio
    async def test_list_members_returns_all_members(
        self, async_client: AsyncClient, org_with_admin, other_user_for_org: User
    ):
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(other_user_for_org.id), "role": "member"},
        )
        response = await async_client.get(f"/api/orgs/{org_id}/members")
        assert response.status_code == 200
        members = response.json()
        assert len(members) == 2  # admin + other_user
        user_ids = {m["user_id"] for m in members}
        assert str(admin.id) in user_ids
        assert str(other_user_for_org.id) in user_ids

    @pytest.mark.asyncio
    async def test_remove_member_returns_204(self, async_client: AsyncClient, org_with_admin, other_user_for_org: User):
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(other_user_for_org.id), "role": "member"},
        )
        response = await async_client.delete(
            f"/api/orgs/{org_id}/members/{other_user_for_org.id}",
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_remove_nonexistent_member_returns_404(self, async_client: AsyncClient, org_with_admin):
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.delete(
            f"/api/orgs/{org_id}/members/000000000000000000000000",
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_non_org_admin_gets_403_on_member_ops(
        self, async_client: AsyncClient, org_with_admin, other_user_for_org: User
    ):
        org_id, admin = org_with_admin
        # Add other_user as member (using admin)
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(other_user_for_org.id), "role": "member"},
        )
        # Now other_user is a member (not admin). Try to add stranger as non-admin
        stranger = User(
            google_id="stranger",
            email="stranger@example.com",
            name="Stranger",
        )
        await stranger.insert()
        async_client.cookies.update(_auth_cookies(other_user_for_org))
        response = await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(stranger.id), "role": "member"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# SSO config
# ---------------------------------------------------------------------------


class TestSSOConfig:
    @pytest.mark.asyncio
    async def test_get_sso_config_returns_null_when_none_exists(self, async_client: AsyncClient, org_with_admin):
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.get(f"/api/orgs/{org_id}/sso")
        assert response.status_code == 200
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_put_sso_config_returns_config(self, async_client: AsyncClient, org_with_admin):
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.put(
            f"/api/orgs/{org_id}/sso",
            json={
                "protocol": "oidc",
                "enabled": True,
                "oidc_discovery_url": "https://idp.example.com/.well-known/openid-configuration",
                "oidc_client_id": "client-123",
                "oidc_client_secret": "secret-456",
                "idp_certificate": "-----BEGIN CERT-----",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["protocol"] == "oidc"
        assert data["enabled"] is True
        assert data["oidc_client_id"] == "client-123"
        assert "idp_certificate" not in data
        assert "oidc_client_secret" not in data

    @pytest.mark.asyncio
    async def test_update_existing_sso_config(self, async_client: AsyncClient, org_with_admin):
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.put(
            f"/api/orgs/{org_id}/sso",
            json={
                "protocol": "oidc",
                "enabled": False,
                "oidc_client_id": "old-client",
            },
        )
        response = await async_client.put(
            f"/api/orgs/{org_id}/sso",
            json={"enabled": True, "oidc_client_id": "new-client"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["oidc_client_id"] == "new-client"


# ---------------------------------------------------------------------------
# Model field tests
# ---------------------------------------------------------------------------


class TestModelFields:
    @pytest.mark.asyncio
    async def test_user_org_id_defaults_to_none(self):
        user = User(
            google_id="g1",
            email="default-org@example.com",
            name="Default User",
        )
        await user.insert()
        try:
            assert user.org_id is None
        finally:
            await user.delete()

    @pytest.mark.asyncio
    async def test_user_auth_provider_defaults_to_google(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        response = await async_client.get("/api/users/me")
        assert response.status_code == 200
        assert response.json()["auth_provider"] == "google"

    @pytest.mark.asyncio
    async def test_document_gets_org_id_from_creator(self, async_client: AsyncClient, test_user: User):
        original = settings.super_admin_emails
        settings.super_admin_emails = ["test@example.com"]
        try:
            async_client.cookies.update(_auth_cookies(test_user))
            create_org_resp = await async_client.post(
                "/api/orgs",
                json={"name": "Doc Org", "slug": "doc-org"},
            )
            org_id = create_org_resp.json()["id"]
            create_doc_resp = await async_client.post(
                "/api/documents",
                json={"title": "Org Doc"},
            )
            doc_id = create_doc_resp.json()["id"]
            doc = await Document_.get(PydanticObjectId(doc_id))
            assert doc.org_id == org_id
        finally:
            settings.super_admin_emails = original

    @pytest.mark.asyncio
    async def test_folder_gets_org_id_from_creator(self, async_client: AsyncClient, test_user: User):
        original = settings.super_admin_emails
        settings.super_admin_emails = ["test@example.com"]
        try:
            async_client.cookies.update(_auth_cookies(test_user))
            create_org_resp = await async_client.post(
                "/api/orgs",
                json={"name": "Folder Org", "slug": "folder-org"},
            )
            org_id = create_org_resp.json()["id"]
            create_folder_resp = await async_client.post(
                "/api/folders",
                json={"name": "Org Folder"},
            )
            folder_id = create_folder_resp.json()["id"]
            folder = await Folder.get(PydanticObjectId(folder_id))
            assert folder.org_id == org_id
        finally:
            settings.super_admin_emails = original


# ---------------------------------------------------------------------------
# Service tests (unit)
# ---------------------------------------------------------------------------


class TestOrgServiceUnit:
    @pytest.mark.asyncio
    async def test_is_same_org_fast_both_none(self):
        assert org_service.is_same_org_fast(None, None) is True

    @pytest.mark.asyncio
    async def test_is_same_org_fast_same_org(self):
        assert org_service.is_same_org_fast("org-123", "org-123") is True

    @pytest.mark.asyncio
    async def test_is_same_org_fast_different_org(self):
        assert org_service.is_same_org_fast("org-123", "org-456") is False

    @pytest.mark.asyncio
    async def test_is_same_org_fast_one_none_one_not(self):
        assert org_service.is_same_org_fast(None, "org-123") is False
        assert org_service.is_same_org_fast("org-123", None) is False

    @pytest.mark.asyncio
    async def test_is_org_admin_admin_returns_true(self, test_user: User):
        org = Organization(name="Test", slug="is-org-admin-test")
        await org.insert()
        try:
            membership = OrgMembership(
                org_id=str(org.id),
                user_id=str(test_user.id),
                role=OrgRole.ADMIN,
            )
            await membership.insert()
            result = await org_service.is_org_admin(str(test_user.id), str(org.id))
            assert result is True
        finally:
            await membership.delete()
            await org.delete()

    @pytest.mark.asyncio
    async def test_is_org_admin_member_returns_false(self, test_user: User):
        org = Organization(name="Test", slug="is-org-member-test")
        await org.insert()
        try:
            membership = OrgMembership(
                org_id=str(org.id),
                user_id=str(test_user.id),
                role=OrgRole.MEMBER,
            )
            await membership.insert()
            result = await org_service.is_org_admin(str(test_user.id), str(org.id))
            assert result is False
        finally:
            await membership.delete()
            await org.delete()

    @pytest.mark.asyncio
    async def test_is_org_admin_non_member_returns_false(self, test_user: User):
        org = Organization(name="Test", slug="is-org-nonmember-test")
        await org.insert()
        try:
            result = await org_service.is_org_admin(str(test_user.id), str(org.id))
            assert result is False
        finally:
            await org.delete()


# ---------------------------------------------------------------------------
# Edge case tests (invalid IDs, get_user_org, remove_member side effects)
# ---------------------------------------------------------------------------


class TestOrgEdgeCases:
    @pytest.mark.asyncio
    async def test_get_org_with_invalid_id_returns_404(self):
        """Service get_org raises 404 for invalid org_id (HTTP layer returns 403 first)."""
        with pytest.raises(HTTPException) as exc_info:
            await org_service.get_org("invalid-id")
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_update_org_with_invalid_id_returns_404(self):
        """Service update_org raises 404 for invalid org_id (HTTP layer returns 403 first)."""
        from app.models.organization import OrganizationUpdate

        with pytest.raises(HTTPException) as exc_info:
            await org_service.update_org("invalid-id", OrganizationUpdate(name="Updated"))
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_remove_member_clears_user_org_id(self, test_user: User, other_user_for_org: User):
        org = Organization(name="Remove Member Org", slug="remove-member-org")
        await org.insert()
        try:
            await org_service.add_member(str(org.id), str(other_user_for_org.id), OrgRole.MEMBER)
            user_before = await User.get(other_user_for_org.id)
            assert user_before.org_id == str(org.id)

            await org_service.remove_member(str(org.id), str(other_user_for_org.id))
            user_after = await User.get(other_user_for_org.id)
            assert user_after.org_id is None
        finally:
            await OrgMembership.find(OrgMembership.org_id == str(org.id)).delete()
            await org.delete()

    @pytest.mark.asyncio
    async def test_get_user_org_returns_none_for_personal_user(self, test_user: User):
        assert test_user.org_id is None
        result = await org_service.get_user_org(str(test_user.id))
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_org_returns_org_for_org_user(self, test_user: User):
        org = Organization(name="User Org", slug="user-org-test")
        await org.insert()
        try:
            membership = OrgMembership(
                org_id=str(org.id),
                user_id=str(test_user.id),
                role=OrgRole.ADMIN,
            )
            await membership.insert()
            test_user.org_id = str(org.id)
            await test_user.save()

            result = await org_service.get_user_org(str(test_user.id))
            assert result is not None
            assert result.id == org.id
            assert result.slug == "user-org-test"
        finally:
            test_user.org_id = None
            await test_user.save()
            await membership.delete()
            await org.delete()

    @pytest.mark.asyncio
    async def test_get_user_org_returns_none_for_invalid_user(self):
        result = await org_service.get_user_org("invalid-user-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_add_member_with_invalid_user_id_returns_404(self, test_user: User):
        org = Organization(name="Add Member Org", slug="add-member-org")
        await org.insert()
        try:
            with pytest.raises(HTTPException) as exc_info:
                await org_service.add_member(str(org.id), "000000000000000000000000", OrgRole.MEMBER)
            assert exc_info.value.status_code == 404
            assert "user" in exc_info.value.detail.lower()
        finally:
            await org.delete()

    @pytest.mark.asyncio
    async def test_create_org_sets_creator_org_id(self, test_user: User):
        from app.models.organization import OrganizationCreate

        payload = OrganizationCreate(name="Creator Org", slug="creator-org")
        org = await org_service.create_org(payload, test_user)
        try:
            creator = await User.get(test_user.id)
            assert creator.org_id == str(org.id)
        finally:
            await OrgMembership.find(OrgMembership.org_id == str(org.id)).delete()
            await org.delete()

    @pytest.mark.asyncio
    async def test_update_org_with_verified_domains_and_plan(self, test_user: User):
        from app.models.organization import OrganizationCreate, OrganizationUpdate

        payload = OrganizationCreate(name="Update Org", slug="update-org")
        org = await org_service.create_org(payload, test_user)
        try:
            update = OrganizationUpdate(
                verified_domains=["new.com", "other.com"],
                plan="enterprise",
            )
            updated = await org_service.update_org(str(org.id), update)
            assert updated.verified_domains == ["new.com", "other.com"]
            assert updated.plan == "enterprise"
        finally:
            await OrgMembership.find(OrgMembership.org_id == str(org.id)).delete()
            await org.delete()

    @pytest.mark.asyncio
    async def test_add_member_user_belongs_to_another_org_returns_409(self, test_user: User, other_user_for_org: User):
        org1 = Organization(name="Org 1", slug="org-1-add")
        org2 = Organization(name="Org 2", slug="org-2-add")
        await org1.insert()
        await org2.insert()
        try:
            await org_service.add_member(str(org1.id), str(other_user_for_org.id))
            with pytest.raises(HTTPException) as exc_info:
                await org_service.add_member(str(org2.id), str(other_user_for_org.id))
            assert exc_info.value.status_code == 409
            assert "another organization" in exc_info.value.detail.lower()
        finally:
            await OrgMembership.find(OrgMembership.org_id == str(org1.id)).delete()
            await OrgMembership.find(OrgMembership.org_id == str(org2.id)).delete()
            other_user_for_org.org_id = None
            await other_user_for_org.save()
            await org1.delete()
            await org2.delete()

    @pytest.mark.asyncio
    async def test_remove_member_with_invalid_user_id_skips_org_clear(self, test_user: User):
        """When user_id is invalid, remove_member still deletes membership but skips user.org_id clear."""
        org = Organization(name="Remove Invalid Org", slug="remove-invalid-org")
        await org.insert()
        membership = OrgMembership(
            org_id=str(org.id),
            user_id="not-a-valid-objectid",
            role=OrgRole.MEMBER,
        )
        await membership.insert()
        try:
            await org_service.remove_member(str(org.id), "not-a-valid-objectid")
            memberships = await OrgMembership.find(OrgMembership.org_id == str(org.id)).to_list()
            assert len(memberships) == 0
        finally:
            await org.delete()

    @pytest.mark.asyncio
    async def test_get_user_org_returns_none_when_org_id_is_invalid(self, test_user: User):
        """User has org_id with invalid format; Organization.get raises, get_user_org returns None."""
        test_user.org_id = "invalid-org-id-format"
        await test_user.save()
        try:
            result = await org_service.get_user_org(str(test_user.id))
            assert result is None
        finally:
            test_user.org_id = None
            await test_user.save()


# ---------------------------------------------------------------------------
# GET /api/orgs/my - Current user's org
# ---------------------------------------------------------------------------


class TestGetMyOrg:
    @pytest.mark.asyncio
    async def test_personal_user_returns_null(self, async_client: AsyncClient, test_user: User):
        """User with no org_id returns null."""
        async_client.cookies.update(_auth_cookies(test_user))
        response = await async_client.get("/api/orgs/my")
        assert response.status_code == 200
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_org_member_returns_org_details(self, async_client: AsyncClient, org_with_admin):
        """Org member returns their org details."""
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.get("/api/orgs/my")
        assert response.status_code == 200
        data = response.json()
        assert data is not None
        assert data["id"] == org_id
        assert data["name"] == "Admin Org"
        assert data["slug"] == "admin-org"
        assert data["member_count"] >= 1

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, async_client: AsyncClient):
        """Unauthenticated request returns 401."""
        response = await async_client.get("/api/orgs/my")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/orgs/{org_id}/members/invite - Invite by email
# ---------------------------------------------------------------------------


class TestInviteMember:
    @pytest.mark.asyncio
    async def test_invite_by_email_success(self, async_client: AsyncClient, org_with_admin, other_user_for_org: User):
        """Successfully invite a user by email."""
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.post(
            f"/api/orgs/{org_id}/members/invite",
            json={"email": other_user_for_org.email, "role": "member"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == str(other_user_for_org.id)
        assert data["user_email"] == other_user_for_org.email
        assert data["role"] == "member"

    @pytest.mark.asyncio
    async def test_invite_email_not_found_returns_404(self, async_client: AsyncClient, org_with_admin):
        """Invite with non-existent email returns 404."""
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.post(
            f"/api/orgs/{org_id}/members/invite",
            json={"email": "nonexistent@example.com", "role": "member"},
        )
        assert response.status_code == 404
        detail = response.json()["detail"].lower()
        assert "user" in detail or "found" in detail

    @pytest.mark.asyncio
    async def test_invite_already_member_returns_409(
        self, async_client: AsyncClient, org_with_admin, other_user_for_org: User
    ):
        """Invite user who is already a member returns 409."""
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(other_user_for_org.id), "role": "member"},
        )
        response = await async_client.post(
            f"/api/orgs/{org_id}/members/invite",
            json={"email": other_user_for_org.email, "role": "admin"},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_invite_non_admin_gets_403(self, async_client: AsyncClient, org_with_admin, other_user_for_org: User):
        """Non-admin member cannot invite (403)."""
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(other_user_for_org.id), "role": "member"},
        )
        stranger = User(
            google_id="stranger-invite",
            email="stranger-invite@example.com",
            name="Stranger",
        )
        await stranger.insert()
        async_client.cookies.update(_auth_cookies(other_user_for_org))
        response = await async_client.post(
            f"/api/orgs/{org_id}/members/invite",
            json={"email": stranger.email, "role": "member"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_invite_user_in_another_org_returns_409(
        self, async_client: AsyncClient, test_user: User, other_user_for_org: User
    ):
        """Invite user who belongs to another org returns 409."""
        original = settings.super_admin_emails
        settings.super_admin_emails = ["test@example.com"]
        try:
            async_client.cookies.update(_auth_cookies(test_user))
            org1_resp = await async_client.post(
                "/api/orgs",
                json={"name": "Org 1", "slug": "invite-org-1"},
            )
            org1_id = org1_resp.json()["id"]
            org2_resp = await async_client.post(
                "/api/orgs",
                json={"name": "Org 2", "slug": "invite-org-2"},
            )
            org2_id = org2_resp.json()["id"]
            await async_client.post(
                f"/api/orgs/{org2_id}/members",
                json={"user_id": str(other_user_for_org.id), "role": "member"},
            )
            response = await async_client.post(
                f"/api/orgs/{org1_id}/members/invite",
                json={"email": other_user_for_org.email, "role": "member"},
            )
            assert response.status_code == 409
        finally:
            settings.super_admin_emails = original


# ---------------------------------------------------------------------------
# PATCH /api/orgs/{org_id}/members/{user_id}/role - Change member role
# ---------------------------------------------------------------------------


class TestUpdateMemberRole:
    @pytest.mark.asyncio
    async def test_change_role_member_to_admin(
        self, async_client: AsyncClient, org_with_admin, other_user_for_org: User
    ):
        """Successfully change role from member to admin."""
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(other_user_for_org.id), "role": "member"},
        )
        response = await async_client.patch(
            f"/api/orgs/{org_id}/members/{other_user_for_org.id}/role",
            json={"role": "admin"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(other_user_for_org.id)
        assert data["role"] == "admin"

    @pytest.mark.asyncio
    async def test_change_role_admin_to_member(
        self, async_client: AsyncClient, org_with_admin, other_user_for_org: User
    ):
        """Successfully change role from admin to member."""
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(other_user_for_org.id), "role": "admin"},
        )
        response = await async_client.patch(
            f"/api/orgs/{org_id}/members/{other_user_for_org.id}/role",
            json={"role": "member"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(other_user_for_org.id)
        assert data["role"] == "member"

    @pytest.mark.asyncio
    async def test_update_role_membership_not_found_returns_404(self, async_client: AsyncClient, org_with_admin):
        """Update role for non-member returns 404."""
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.patch(
            f"/api/orgs/{org_id}/members/000000000000000000000000/role",
            json={"role": "admin"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_role_non_admin_gets_403(
        self, async_client: AsyncClient, org_with_admin, other_user_for_org: User
    ):
        """Non-admin member cannot change role (403)."""
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(other_user_for_org.id), "role": "member"},
        )
        async_client.cookies.update(_auth_cookies(other_user_for_org))
        response = await async_client.patch(
            f"/api/orgs/{org_id}/members/{admin.id}/role",
            json={"role": "member"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_role_invalid_role_returns_422(
        self, async_client: AsyncClient, org_with_admin, other_user_for_org: User
    ):
        """Invalid role value returns 422."""
        org_id, admin = org_with_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/orgs/{org_id}/members",
            json={"user_id": str(other_user_for_org.id), "role": "member"},
        )
        response = await async_client.patch(
            f"/api/orgs/{org_id}/members/{other_user_for_org.id}/role",
            json={"role": "owner"},
        )
        assert response.status_code == 422
