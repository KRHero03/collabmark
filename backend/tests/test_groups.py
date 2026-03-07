"""Comprehensive tests for groups, logo upload/delete, group collaborators, and /me org context."""

import pytest
from app.auth.jwt import create_access_token
from app.models.document import Document_
from app.models.folder import Folder
from app.models.group import Group
from app.models.organization import Organization, OrgMembership, OrgRole
from app.models.user import User
from beanie import PydanticObjectId
from httpx import AsyncClient


def _auth_cookies(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"access_token": token}


@pytest.fixture
async def org_admin():
    """Create an org with an admin user."""
    admin = User(google_id="admin-g1", email="admin@testorg.com", name="Admin")
    await admin.insert()
    org = Organization(name="Test Org", slug="test-org", verified_domains=["testorg.com"])
    await org.insert()
    membership = OrgMembership(org_id=str(org.id), user_id=str(admin.id), role=OrgRole.ADMIN)
    await membership.insert()
    admin.org_id = str(org.id)
    await admin.save()
    return org, admin


@pytest.fixture
async def org_member(org_admin):
    """Create a regular member in the same org."""
    org, _ = org_admin
    member = User(google_id="member-g1", email="member@testorg.com", name="Member")
    await member.insert()
    membership = OrgMembership(org_id=str(org.id), user_id=str(member.id), role=OrgRole.MEMBER)
    await membership.insert()
    member.org_id = str(org.id)
    await member.save()
    return member


@pytest.fixture
async def test_group(org_admin):
    """Create a group in the test org."""
    org, _ = org_admin
    group = Group(name="Engineering", org_id=str(org.id), scim_synced=False)
    await group.insert()
    return group


@pytest.fixture
async def non_member_user():
    """User with no org (for 403 tests)."""
    user = User(google_id="stranger-g1", email="stranger@other.com", name="Stranger")
    await user.insert()
    return user


# Minimal valid 1x1 PNG
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ---------------------------------------------------------------------------
# 1. Group Search: GET /api/orgs/{org_id}/groups
# ---------------------------------------------------------------------------


class TestGroupSearch:
    @pytest.mark.asyncio
    async def test_search_as_org_member_returns_matching_groups(
        self, async_client: AsyncClient, org_admin, org_member, test_group
    ):
        org, _ = org_admin
        async_client.cookies.update(_auth_cookies(org_member))
        response = await async_client.get(f"/api/orgs/{org.id}/groups", params={"q": "Engineer"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Engineering"
        assert data[0]["org_id"] == str(org.id)
        assert data[0]["scim_synced"] is False
        assert "id" in data[0]
        assert "member_count" in data[0]

    @pytest.mark.asyncio
    async def test_search_as_non_member_returns_403(self, async_client: AsyncClient, org_admin, non_member_user):
        org, _ = org_admin
        async_client.cookies.update(_auth_cookies(non_member_user))
        response = await async_client.get(f"/api/orgs/{org.id}/groups", params={"q": "test"})
        assert response.status_code == 403
        err = response.json()
        assert "detail" in err
        assert "member" in err["detail"].lower() or "organization" in err["detail"].lower()

    @pytest.mark.asyncio
    async def test_empty_query_returns_all_groups(self, async_client: AsyncClient, org_admin, org_member, test_group):
        org, _ = org_admin
        group2 = Group(name="Design", org_id=str(org.id), scim_synced=False)
        await group2.insert()
        async_client.cookies.update(_auth_cookies(org_member))
        response = await async_client.get(f"/api/orgs/{org.id}/groups")
        assert response.status_code == 200
        data = response.json()
        names = {g["name"] for g in data}
        assert "Engineering" in names
        assert "Design" in names

    @pytest.mark.asyncio
    async def test_regex_special_chars_escaped_no_redos(self, async_client: AsyncClient, org_admin, org_member):
        org, _ = org_admin
        async_client.cookies.update(_auth_cookies(org_member))
        response = await async_client.get(f"/api/orgs/{org.id}/groups", params={"q": "test(.*"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# 2. Logo upload: POST /api/orgs/{org_id}/logo
# ---------------------------------------------------------------------------


class TestLogoUpload:
    @pytest.mark.asyncio
    async def test_successful_png_upload_returns_updated_org_with_logo_url(self, async_client: AsyncClient, org_admin):
        org, admin = org_admin
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.post(
            f"/api/orgs/{org.id}/logo",
            files={"file": ("logo.png", PNG_BYTES, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["logo_url"] is not None
        assert "logo" in data["logo_url"]
        assert data["id"] == str(org.id)
        assert data["name"] == "Test Org"

    @pytest.mark.asyncio
    async def test_unsupported_file_type_returns_400(self, async_client: AsyncClient, org_admin):
        org, admin = org_admin
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.post(
            f"/api/orgs/{org.id}/logo",
            files={"file": ("logo.exe", b"fake-binary", "application/octet-stream")},
        )
        assert response.status_code == 400
        err = response.json()
        assert "detail" in err
        assert "unsupported" in err["detail"].lower() or "allowed" in err["detail"].lower()

    @pytest.mark.asyncio
    async def test_file_too_large_returns_400(self, async_client: AsyncClient, org_admin):
        org, admin = org_admin
        large = b"x" * (2 * 1024 * 1024 + 1)
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.post(
            f"/api/orgs/{org.id}/logo",
            files={"file": ("logo.png", large, "image/png")},
        )
        assert response.status_code == 400
        err = response.json()
        assert "detail" in err
        assert "large" in err["detail"].lower() or "2MB" in err["detail"]

    @pytest.mark.asyncio
    async def test_non_admin_gets_403_on_logo_upload(self, async_client: AsyncClient, org_admin, org_member):
        org, _ = org_admin
        async_client.cookies.update(_auth_cookies(org_member))
        response = await async_client.post(
            f"/api/orgs/{org.id}/logo",
            files={"file": ("logo.png", PNG_BYTES, "image/png")},
        )
        assert response.status_code == 403
        err = response.json()
        assert "detail" in err


# ---------------------------------------------------------------------------
# 3. Logo delete: DELETE /api/orgs/{org_id}/logo
# ---------------------------------------------------------------------------


class TestLogoDelete:
    @pytest.mark.asyncio
    async def test_successful_deletion_returns_204_and_clears_logo_url(self, async_client: AsyncClient, org_admin):
        org, admin = org_admin
        org.logo_url = "/media/logos/test.png"
        await org.save()
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.delete(f"/api/orgs/{org.id}/logo")
        assert response.status_code == 204
        refreshed = await Organization.get(org.id)
        assert refreshed.logo_url is None

    @pytest.mark.asyncio
    async def test_non_admin_gets_403_on_logo_delete(self, async_client: AsyncClient, org_admin, org_member):
        org, _ = org_admin
        async_client.cookies.update(_auth_cookies(org_member))
        response = await async_client.delete(f"/api/orgs/{org.id}/logo")
        assert response.status_code == 403
        err = response.json()
        assert "detail" in err


# ---------------------------------------------------------------------------
# 4. Group collaborator endpoints (documents)
# ---------------------------------------------------------------------------


@pytest.fixture
async def owned_document(org_admin):
    """Document owned by the org admin."""
    org, admin = org_admin
    doc = Document_(
        title="Shared Doc",
        content="",
        owner_id=str(admin.id),
        org_id=str(org.id),
    )
    await doc.insert()
    return doc


class TestDocumentGroupCollaborators:
    @pytest.mark.asyncio
    async def test_add_group_to_document_returns_201(
        self, async_client: AsyncClient, org_admin, test_group, owned_document
    ):
        _org, admin = org_admin
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.post(
            f"/api/documents/{owned_document.id}/group-collaborators",
            json={"group_id": str(test_group.id), "permission": "view"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["group_id"] == str(test_group.id)
        assert data["group_name"] == "Engineering"
        assert data["permission"] == "view"
        assert "id" in data
        assert "granted_at" in data

    @pytest.mark.asyncio
    async def test_list_document_group_collaborators(
        self, async_client: AsyncClient, org_admin, test_group, owned_document
    ):
        _org, admin = org_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/documents/{owned_document.id}/group-collaborators",
            json={"group_id": str(test_group.id), "permission": "edit"},
        )
        response = await async_client.get(f"/api/documents/{owned_document.id}/group-collaborators")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["group_name"] == "Engineering"
        assert data[0]["permission"] == "edit"

    @pytest.mark.asyncio
    async def test_remove_document_group_collaborator(
        self, async_client: AsyncClient, org_admin, test_group, owned_document
    ):
        _org, admin = org_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/documents/{owned_document.id}/group-collaborators",
            json={"group_id": str(test_group.id), "permission": "view"},
        )
        response = await async_client.delete(f"/api/documents/{owned_document.id}/group-collaborators/{test_group.id}")
        assert response.status_code == 204
        list_resp = await async_client.get(f"/api/documents/{owned_document.id}/group-collaborators")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 0

    @pytest.mark.asyncio
    async def test_non_owner_gets_403_on_add_group_to_document(
        self, async_client: AsyncClient, org_admin, org_member, test_group, owned_document
    ):
        async_client.cookies.update(_auth_cookies(org_member))
        response = await async_client.post(
            f"/api/documents/{owned_document.id}/group-collaborators",
            json={"group_id": str(test_group.id), "permission": "view"},
        )
        assert response.status_code == 403
        err = response.json()
        assert "detail" in err

    @pytest.mark.asyncio
    async def test_non_owner_gets_403_on_remove_group_from_document(
        self, async_client: AsyncClient, org_admin, org_member, test_group, owned_document
    ):
        _org, admin = org_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/documents/{owned_document.id}/group-collaborators",
            json={"group_id": str(test_group.id), "permission": "view"},
        )
        async_client.cookies.update(_auth_cookies(org_member))
        response = await async_client.delete(f"/api/documents/{owned_document.id}/group-collaborators/{test_group.id}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_group_returns_404_on_add(self, async_client: AsyncClient, org_admin, owned_document):
        _org, admin = org_admin
        fake_id = str(PydanticObjectId())
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.post(
            f"/api/documents/{owned_document.id}/group-collaborators",
            json={"group_id": fake_id, "permission": "view"},
        )
        assert response.status_code == 404
        err = response.json()
        assert "detail" in err
        assert "not found" in err["detail"].lower() or "group" in err["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Group collaborator endpoints (folders)
# ---------------------------------------------------------------------------


@pytest.fixture
async def owned_folder(org_admin):
    """Folder owned by the org admin."""
    org, admin = org_admin
    folder = Folder(
        name="Shared Folder",
        owner_id=str(admin.id),
        org_id=str(org.id),
    )
    await folder.insert()
    return folder


class TestFolderGroupCollaborators:
    @pytest.mark.asyncio
    async def test_add_group_to_folder_returns_201(
        self, async_client: AsyncClient, org_admin, test_group, owned_folder
    ):
        _org, admin = org_admin
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.post(
            f"/api/folders/{owned_folder.id}/group-collaborators",
            json={"group_id": str(test_group.id), "permission": "view"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["group_id"] == str(test_group.id)
        assert data["group_name"] == "Engineering"
        assert data["permission"] == "view"
        assert "id" in data
        assert "granted_at" in data

    @pytest.mark.asyncio
    async def test_list_folder_group_collaborators(
        self, async_client: AsyncClient, org_admin, test_group, owned_folder
    ):
        _org, admin = org_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/folders/{owned_folder.id}/group-collaborators",
            json={"group_id": str(test_group.id), "permission": "edit"},
        )
        response = await async_client.get(f"/api/folders/{owned_folder.id}/group-collaborators")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["group_name"] == "Engineering"
        assert data[0]["permission"] == "edit"

    @pytest.mark.asyncio
    async def test_remove_folder_group_collaborator(
        self, async_client: AsyncClient, org_admin, test_group, owned_folder
    ):
        _org, admin = org_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/folders/{owned_folder.id}/group-collaborators",
            json={"group_id": str(test_group.id), "permission": "view"},
        )
        response = await async_client.delete(f"/api/folders/{owned_folder.id}/group-collaborators/{test_group.id}")
        assert response.status_code == 204
        list_resp = await async_client.get(f"/api/folders/{owned_folder.id}/group-collaborators")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 0

    @pytest.mark.asyncio
    async def test_non_owner_gets_403_on_add_group_to_folder(
        self, async_client: AsyncClient, org_admin, org_member, test_group, owned_folder
    ):
        async_client.cookies.update(_auth_cookies(org_member))
        response = await async_client.post(
            f"/api/folders/{owned_folder.id}/group-collaborators",
            json={"group_id": str(test_group.id), "permission": "view"},
        )
        assert response.status_code == 403
        err = response.json()
        assert "detail" in err

    @pytest.mark.asyncio
    async def test_non_owner_gets_403_on_remove_group_from_folder(
        self, async_client: AsyncClient, org_admin, org_member, test_group, owned_folder
    ):
        _org, admin = org_admin
        async_client.cookies.update(_auth_cookies(admin))
        await async_client.post(
            f"/api/folders/{owned_folder.id}/group-collaborators",
            json={"group_id": str(test_group.id), "permission": "view"},
        )
        async_client.cookies.update(_auth_cookies(org_member))
        response = await async_client.delete(f"/api/folders/{owned_folder.id}/group-collaborators/{test_group.id}")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# 6. User /me with org context
# ---------------------------------------------------------------------------


class TestUserMeOrgContext:
    @pytest.mark.asyncio
    async def test_me_returns_org_role_org_name_org_logo_url_when_user_has_org(
        self, async_client: AsyncClient, org_admin
    ):
        org, admin = org_admin
        org.logo_url = "/media/logos/test.png"
        await org.save()
        async_client.cookies.update(_auth_cookies(admin))
        response = await async_client.get("/api/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["org_role"] == "admin"
        assert data["org_name"] == "Test Org"
        assert data["org_logo_url"] == "/media/logos/test.png"
        assert data["org_id"] == str(org.id)
        assert data["email"] == "admin@testorg.com"
        assert data["name"] == "Admin"

    @pytest.mark.asyncio
    async def test_me_returns_org_context_for_member(self, async_client: AsyncClient, org_admin, org_member):
        org, _ = org_admin
        async_client.cookies.update(_auth_cookies(org_member))
        response = await async_client.get("/api/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["org_role"] == "member"
        assert data["org_name"] == "Test Org"
        assert data["org_id"] == str(org.id)
        assert data["email"] == "member@testorg.com"

    @pytest.mark.asyncio
    async def test_me_without_org_has_no_org_fields(self, async_client: AsyncClient, non_member_user):
        async_client.cookies.update(_auth_cookies(non_member_user))
        response = await async_client.get("/api/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["org_id"] is None
        assert data["org_role"] is None
        assert data["org_name"] is None
        assert data["org_logo_url"] is None
