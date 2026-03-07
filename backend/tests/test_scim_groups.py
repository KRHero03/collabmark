"""Tests for SCIM 2.0 Groups CRUD endpoints."""

import pytest
import pytest_asyncio
from app.auth.scim_auth import hash_scim_token
from app.models.group import Group, GroupMembership
from app.models.org_sso_config import OrgSSOConfig
from app.models.organization import Organization, OrgMembership, OrgRole
from app.models.user import User
from beanie import PydanticObjectId
from httpx import AsyncClient


def _scim_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/scim+json"}


@pytest_asyncio.fixture
async def scim_group_setup():
    """Create org, users, and SCIM token for group tests."""
    org = Organization(name="SCIM Group Org", slug="scim-group-org")
    await org.insert()
    token = "group-test-token"
    cfg = OrgSSOConfig(
        org_id=str(org.id),
        scim_enabled=True,
        scim_bearer_token=hash_scim_token(token),
    )
    await cfg.insert()

    user = User(
        google_id="scim-user-1",
        email="user1@scimgroup.com",
        name="User One",
        org_id=str(org.id),
    )
    await user.insert()
    mem = OrgMembership(org_id=str(org.id), user_id=str(user.id), role=OrgRole.MEMBER)
    await mem.insert()

    user2 = User(
        google_id="scim-user-2",
        email="user2@scimgroup.com",
        name="User Two",
        org_id=str(org.id),
    )
    await user2.insert()
    mem2 = OrgMembership(org_id=str(org.id), user_id=str(user2.id), role=OrgRole.MEMBER)
    await mem2.insert()

    return org, token, user, user2


# ---------------------------------------------------------------------------
# POST /scim/v2/Groups - Create
# ---------------------------------------------------------------------------


class TestScimCreateGroup:
    @pytest.mark.asyncio
    async def test_create_group_returns_201_and_schema(self, async_client: AsyncClient, scim_group_setup):
        _org, token, _user, _user2 = scim_group_setup
        response = await async_client.post(
            "/scim/v2/Groups",
            headers=_scim_headers(token),
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "displayName": "Engineering",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["displayName"] == "Engineering"
        assert "id" in data
        assert data["schemas"] == ["urn:ietf:params:scim:schemas:core:2.0:Group"]
        assert "meta" in data
        assert data["meta"]["resourceType"] == "Group"
        assert response.headers.get("content-type") == "application/scim+json"
        assert "Location" in response.headers

    @pytest.mark.asyncio
    async def test_create_duplicate_displayname_returns_409(self, async_client: AsyncClient, scim_group_setup):
        _org, token, _user, _user2 = scim_group_setup
        headers = _scim_headers(token)
        payload = {"displayName": "DuplicateGroup"}
        await async_client.post("/scim/v2/Groups", headers=headers, json=payload)
        response = await async_client.post("/scim/v2/Groups", headers=headers, json=payload)
        assert response.status_code == 409
        data = response.json()
        assert "urn:ietf:params:scim:api:messages:2.0:Error" in data["schemas"]
        assert data["status"] == "409"
        assert data.get("scimType") == "uniqueness"

    @pytest.mark.asyncio
    async def test_create_missing_displayname_returns_400(self, async_client: AsyncClient, scim_group_setup):
        _org, token, _user, _user2 = scim_group_setup
        response = await async_client.post(
            "/scim/v2/Groups",
            headers=_scim_headers(token),
            json={"schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"]},
        )
        assert response.status_code == 400
        data = response.json()
        assert "urn:ietf:params:scim:api:messages:2.0:Error" in data["schemas"]


# ---------------------------------------------------------------------------
# GET /scim/v2/Groups - List
# ---------------------------------------------------------------------------


class TestScimListGroups:
    @pytest.mark.asyncio
    async def test_list_groups_returns_totalresults(self, async_client: AsyncClient, scim_group_setup):
        _org, token, _user, _user2 = scim_group_setup
        headers = _scim_headers(token)
        await async_client.post(
            "/scim/v2/Groups",
            headers=headers,
            json={"displayName": "TeamA"},
        )
        await async_client.post(
            "/scim/v2/Groups",
            headers=headers,
            json={"displayName": "TeamB"},
        )
        response = await async_client.get("/scim/v2/Groups", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["totalResults"] == 2
        assert len(data["Resources"]) == 2

    @pytest.mark.asyncio
    async def test_list_groups_filter_by_displayname(self, async_client: AsyncClient, scim_group_setup):
        _org, token, _user, _user2 = scim_group_setup
        headers = _scim_headers(token)
        await async_client.post(
            "/scim/v2/Groups",
            headers=headers,
            json={"displayName": "FilteredGroup"},
        )
        await async_client.post(
            "/scim/v2/Groups",
            headers=headers,
            json={"displayName": "OtherGroup"},
        )
        response = await async_client.get(
            '/scim/v2/Groups?filter=displayName eq "FilteredGroup"',
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["totalResults"] == 1
        assert data["Resources"][0]["displayName"] == "FilteredGroup"


# ---------------------------------------------------------------------------
# GET /scim/v2/Groups/{id} - Get single
# ---------------------------------------------------------------------------


class TestScimGetGroup:
    @pytest.mark.asyncio
    async def test_get_single_group(self, async_client: AsyncClient, scim_group_setup):
        _org, token, _user, _user2 = scim_group_setup
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Groups",
            headers=headers,
            json={"displayName": "SingleGroup"},
        )
        group_id = create_resp.json()["id"]
        response = await async_client.get(f"/scim/v2/Groups/{group_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == group_id
        assert data["displayName"] == "SingleGroup"

    @pytest.mark.asyncio
    async def test_get_nonexistent_group_returns_404(self, async_client: AsyncClient, scim_group_setup):
        _org, token, _user, _user2 = scim_group_setup
        response = await async_client.get(
            "/scim/v2/Groups/000000000000000000000000",
            headers=_scim_headers(token),
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /scim/v2/Groups/{id} - Replace
# ---------------------------------------------------------------------------


class TestScimReplaceGroup:
    @pytest.mark.asyncio
    async def test_put_replaces_displayname(self, async_client: AsyncClient, scim_group_setup):
        _org, token, _user, _user2 = scim_group_setup
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Groups",
            headers=headers,
            json={"displayName": "OriginalName"},
        )
        group_id = create_resp.json()["id"]
        response = await async_client.put(
            f"/scim/v2/Groups/{group_id}",
            headers=headers,
            json={"displayName": "UpdatedName", "members": []},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["displayName"] == "UpdatedName"


# ---------------------------------------------------------------------------
# PATCH /scim/v2/Groups/{id} - Update
# ---------------------------------------------------------------------------


class TestScimPatchGroup:
    @pytest.mark.asyncio
    async def test_patch_replace_displayname(self, async_client: AsyncClient, scim_group_setup):
        _org, token, _user, _user2 = scim_group_setup
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Groups",
            headers=headers,
            json={"displayName": "PatchOriginal"},
        )
        group_id = create_resp.json()["id"]
        response = await async_client.patch(
            f"/scim/v2/Groups/{group_id}",
            headers=headers,
            json={"Operations": [{"op": "replace", "path": "displayName", "value": "PatchUpdated"}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["displayName"] == "PatchUpdated"

    @pytest.mark.asyncio
    async def test_patch_add_members(self, async_client: AsyncClient, scim_group_setup):
        _org, token, user, user2 = scim_group_setup
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Groups",
            headers=headers,
            json={"displayName": "GroupWithMembers", "members": []},
        )
        group_id = create_resp.json()["id"]
        response = await async_client.patch(
            f"/scim/v2/Groups/{group_id}",
            headers=headers,
            json={
                "Operations": [
                    {
                        "op": "add",
                        "path": "members",
                        "value": [
                            {"value": str(user.id)},
                            {"value": str(user2.id)},
                        ],
                    }
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["members"]) == 2
        member_values = {m["value"] for m in data["members"]}
        assert str(user.id) in member_values
        assert str(user2.id) in member_values

    @pytest.mark.asyncio
    async def test_patch_remove_members(self, async_client: AsyncClient, scim_group_setup):
        _org, token, user, user2 = scim_group_setup
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Groups",
            headers=headers,
            json={
                "displayName": "GroupToRemoveFrom",
                "members": [{"value": str(user.id)}, {"value": str(user2.id)}],
            },
        )
        group_id = create_resp.json()["id"]
        response = await async_client.patch(
            f"/scim/v2/Groups/{group_id}",
            headers=headers,
            json={
                "Operations": [
                    {
                        "op": "remove",
                        "path": "members",
                        "value": [{"value": str(user2.id)}],
                    }
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["members"]) == 1
        assert data["members"][0]["value"] == str(user.id)


# ---------------------------------------------------------------------------
# DELETE /scim/v2/Groups/{id}
# ---------------------------------------------------------------------------


class TestScimDeleteGroup:
    @pytest.mark.asyncio
    async def test_delete_removes_group_and_memberships(self, async_client: AsyncClient, scim_group_setup):
        _org, token, user, _user2 = scim_group_setup
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Groups",
            headers=headers,
            json={"displayName": "ToDelete", "members": [{"value": str(user.id)}]},
        )
        group_id = create_resp.json()["id"]
        response = await async_client.delete(
            f"/scim/v2/Groups/{group_id}",
            headers=headers,
        )
        assert response.status_code == 204
        try:
            group = await Group.get(PydanticObjectId(group_id))
        except Exception:
            group = None
        assert group is None
        memberships = await GroupMembership.find(GroupMembership.group_id == group_id).to_list()
        assert len(memberships) == 0
