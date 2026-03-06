"""Tests for SCIM 2.0 provisioning routes (HTTP-level)."""

import pytest
from app.auth.scim_auth import hash_scim_token
from app.models.org_sso_config import OrgSSOConfig
from app.models.organization import Organization, OrgMembership
from app.models.user import User
from httpx import AsyncClient


@pytest.fixture
async def scim_org_with_token():
    """Create an org with SCIM enabled and a bearer token.

    Returns:
        Tuple of (org, plaintext_token).
    """
    org = Organization(name="SCIM Route Org", slug="scim-route-org")
    await org.insert()
    token = "scim-test-bearer-token"
    cfg = OrgSSOConfig(
        org_id=str(org.id),
        scim_enabled=True,
        scim_bearer_token=hash_scim_token(token),
    )
    await cfg.insert()
    return org, token


def _scim_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/scim+json",
    }


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestScimAuth:
    @pytest.mark.asyncio
    async def test_no_auth_header_returns_401(self, async_client: AsyncClient, scim_org_with_token):
        response = await async_client.get("/scim/v2/Users")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_token_returns_401(self, async_client: AsyncClient, scim_org_with_token):
        response = await async_client.get(
            "/scim/v2/Users",
            headers=_scim_headers("wrong-token"),
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_returns_200(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        response = await async_client.get(
            "/scim/v2/Users",
            headers=_scim_headers(token),
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /scim/v2/Users - Create
# ---------------------------------------------------------------------------


class TestScimCreateUser:
    @pytest.mark.asyncio
    async def test_create_user_returns_201(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        response = await async_client.post(
            "/scim/v2/Users",
            headers=_scim_headers(token),
            json={
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                "userName": "alice@acme.com",
                "displayName": "Alice Smith",
                "emails": [{"value": "alice@acme.com", "primary": True, "type": "work"}],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["userName"] == "alice@acme.com"
        assert data["displayName"] == "Alice Smith"
        assert data["active"] is True
        assert "id" in data
        assert response.headers["content-type"] == "application/scim+json"

    @pytest.mark.asyncio
    async def test_create_user_sets_auth_provider_scim(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        response = await async_client.post(
            "/scim/v2/Users",
            headers=_scim_headers(token),
            json={"userName": "provider-check@acme.com", "displayName": "Provider Check"},
        )
        user_id = response.json()["id"]
        from beanie import PydanticObjectId

        user = await User.get(PydanticObjectId(user_id))
        assert user.auth_provider == "scim"

    @pytest.mark.asyncio
    async def test_create_duplicate_returns_409(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        payload = {"userName": "dup-route@acme.com", "displayName": "Dup"}
        await async_client.post("/scim/v2/Users", headers=_scim_headers(token), json=payload)
        response = await async_client.post("/scim/v2/Users", headers=_scim_headers(token), json=payload)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_missing_email_returns_400(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        response = await async_client.post(
            "/scim/v2/Users",
            headers=_scim_headers(token),
            json={"displayName": "No Email"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_user_creates_membership(self, async_client: AsyncClient, scim_org_with_token):
        org, token = scim_org_with_token
        response = await async_client.post(
            "/scim/v2/Users",
            headers=_scim_headers(token),
            json={"userName": "member-check@acme.com", "displayName": "Member Check"},
        )
        user_id = response.json()["id"]
        membership = await OrgMembership.find_one(
            OrgMembership.org_id == str(org.id),
            OrgMembership.user_id == user_id,
        )
        assert membership is not None


# ---------------------------------------------------------------------------
# GET /scim/v2/Users - List
# ---------------------------------------------------------------------------


class TestScimListUsers:
    @pytest.mark.asyncio
    async def test_list_empty_returns_zero(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        response = await async_client.get("/scim/v2/Users", headers=_scim_headers(token))
        assert response.status_code == 200
        data = response.json()
        assert data["totalResults"] == 0
        assert data["Resources"] == []

    @pytest.mark.asyncio
    async def test_list_returns_created_users(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        headers = _scim_headers(token)
        await async_client.post(
            "/scim/v2/Users", headers=headers, json={"userName": "l1@acme.com", "displayName": "L1"}
        )
        await async_client.post(
            "/scim/v2/Users", headers=headers, json={"userName": "l2@acme.com", "displayName": "L2"}
        )
        response = await async_client.get("/scim/v2/Users", headers=headers)
        data = response.json()
        assert data["totalResults"] == 2
        assert len(data["Resources"]) == 2

    @pytest.mark.asyncio
    async def test_list_with_filter(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        headers = _scim_headers(token)
        await async_client.post(
            "/scim/v2/Users", headers=headers, json={"userName": "f1@acme.com", "displayName": "F1"}
        )
        await async_client.post(
            "/scim/v2/Users", headers=headers, json={"userName": "f2@acme.com", "displayName": "F2"}
        )
        response = await async_client.get(
            '/scim/v2/Users?filter=userName eq "f1@acme.com"',
            headers=headers,
        )
        data = response.json()
        assert data["totalResults"] == 1
        assert data["Resources"][0]["userName"] == "f1@acme.com"

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        headers = _scim_headers(token)
        for i in range(5):
            await async_client.post(
                "/scim/v2/Users",
                headers=headers,
                json={"userName": f"p{i}@acme.com", "displayName": f"P{i}"},
            )

        response = await async_client.get("/scim/v2/Users?startIndex=1&count=2", headers=headers)
        data = response.json()
        assert data["totalResults"] == 5
        assert data["itemsPerPage"] == 2
        assert data["startIndex"] == 1

    @pytest.mark.asyncio
    async def test_list_scim_content_type(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        response = await async_client.get("/scim/v2/Users", headers=_scim_headers(token))
        assert response.headers["content-type"] == "application/scim+json"


# ---------------------------------------------------------------------------
# GET /scim/v2/Users/{user_id} - Get
# ---------------------------------------------------------------------------


class TestScimGetUser:
    @pytest.mark.asyncio
    async def test_get_user_returns_resource(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Users", headers=headers, json={"userName": "get-rt@acme.com", "displayName": "Get RT"}
        )
        user_id = create_resp.json()["id"]

        response = await async_client.get(f"/scim/v2/Users/{user_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["userName"] == "get-rt@acme.com"
        assert data["id"] == user_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        response = await async_client.get(
            "/scim/v2/Users/000000000000000000000000",
            headers=_scim_headers(token),
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_invalid_id_returns_404(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        response = await async_client.get(
            "/scim/v2/Users/bad-id",
            headers=_scim_headers(token),
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /scim/v2/Users/{user_id} - Update
# ---------------------------------------------------------------------------


class TestScimUpdateUser:
    @pytest.mark.asyncio
    async def test_patch_updates_display_name(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Users", headers=headers, json={"userName": "patch-me@acme.com", "displayName": "Before"}
        )
        user_id = create_resp.json()["id"]

        response = await async_client.patch(
            f"/scim/v2/Users/{user_id}",
            headers=headers,
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{"op": "replace", "path": "displayName", "value": "After"}],
            },
        )
        assert response.status_code == 200
        assert response.json()["displayName"] == "After"

    @pytest.mark.asyncio
    async def test_patch_direct_attributes(self, async_client: AsyncClient, scim_org_with_token):
        """Azure AD-style direct attribute replacement."""
        _org, token = scim_org_with_token
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Users", headers=headers, json={"userName": "azure@acme.com", "displayName": "Azure"}
        )
        user_id = create_resp.json()["id"]

        response = await async_client.patch(
            f"/scim/v2/Users/{user_id}",
            headers=headers,
            json={"displayName": "Azure Updated"},
        )
        assert response.status_code == 200
        assert response.json()["displayName"] == "Azure Updated"

    @pytest.mark.asyncio
    async def test_patch_nonexistent_returns_404(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        response = await async_client.patch(
            "/scim/v2/Users/000000000000000000000000",
            headers=_scim_headers(token),
            json={"displayName": "Ghost"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /scim/v2/Users/{user_id} - Delete
# ---------------------------------------------------------------------------


class TestScimDeleteUser:
    @pytest.mark.asyncio
    async def test_delete_returns_204(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Users", headers=headers, json={"userName": "del@acme.com", "displayName": "Del"}
        )
        user_id = create_resp.json()["id"]

        response = await async_client.delete(f"/scim/v2/Users/{user_id}", headers=headers)
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_removes_membership(self, async_client: AsyncClient, scim_org_with_token):
        org, token = scim_org_with_token
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Users", headers=headers, json={"userName": "del-m@acme.com", "displayName": "Del M"}
        )
        user_id = create_resp.json()["id"]

        await async_client.delete(f"/scim/v2/Users/{user_id}", headers=headers)

        membership = await OrgMembership.find_one(
            OrgMembership.org_id == str(org.id),
            OrgMembership.user_id == user_id,
        )
        assert membership is None

    @pytest.mark.asyncio
    async def test_delete_preserves_user_document(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Users", headers=headers, json={"userName": "keep@acme.com", "displayName": "Keep"}
        )
        user_id = create_resp.json()["id"]

        await async_client.delete(f"/scim/v2/Users/{user_id}", headers=headers)

        from beanie import PydanticObjectId

        user = await User.get(PydanticObjectId(user_id))
        assert user is not None
        assert user.org_id is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, async_client: AsyncClient, scim_org_with_token):
        _org, token = scim_org_with_token
        response = await async_client.delete(
            "/scim/v2/Users/000000000000000000000000",
            headers=_scim_headers(token),
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_deleted_user_appears_inactive(self, async_client: AsyncClient, scim_org_with_token):
        """After deletion, if we re-add the user and check, the original should show as inactive."""
        org, token = scim_org_with_token
        headers = _scim_headers(token)
        create_resp = await async_client.post(
            "/scim/v2/Users", headers=headers, json={"userName": "ghost@acme.com", "displayName": "Ghost"}
        )
        user_id = create_resp.json()["id"]
        await async_client.delete(f"/scim/v2/Users/{user_id}", headers=headers)

        from app.services.scim_service import user_to_scim
        from beanie import PydanticObjectId

        user = await User.get(PydanticObjectId(user_id))
        scim_resource = user_to_scim(user, str(org.id))
        assert scim_resource["active"] is False


# ---------------------------------------------------------------------------
# SCIM Token Management (via org admin routes)
# ---------------------------------------------------------------------------


class TestScimTokenManagement:
    @pytest.fixture
    async def admin_org(self, async_client: AsyncClient, test_user: User):
        """Create org with test_user as admin, return (org_id, cookies)."""
        from app.auth.jwt import create_access_token
        from app.config import settings

        original = settings.super_admin_emails
        settings.super_admin_emails = [test_user.email]
        try:
            cookies = {"access_token": create_access_token(str(test_user.id))}
            async_client.cookies.update(cookies)
            resp = await async_client.post(
                "/api/orgs",
                json={"name": "Token Mgmt Org", "slug": "token-mgmt-org"},
            )
            org_id = resp.json()["id"]
            return org_id, cookies
        finally:
            settings.super_admin_emails = original

    @pytest.mark.asyncio
    async def test_generate_token_returns_201(self, async_client: AsyncClient, admin_org):
        org_id, cookies = admin_org
        async_client.cookies.update(cookies)
        response = await async_client.post(f"/api/orgs/{org_id}/scim/token")
        assert response.status_code == 201
        data = response.json()
        assert "token" in data
        assert len(data["token"]) > 20
        assert data["scim_enabled"] is True

    @pytest.mark.asyncio
    async def test_generated_token_works_for_scim(self, async_client: AsyncClient, admin_org):
        org_id, cookies = admin_org
        async_client.cookies.update(cookies)
        token_resp = await async_client.post(f"/api/orgs/{org_id}/scim/token")
        scim_token = token_resp.json()["token"]

        async_client.cookies.clear()
        response = await async_client.get(
            "/scim/v2/Users",
            headers=_scim_headers(scim_token),
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_revoke_token_returns_204(self, async_client: AsyncClient, admin_org):
        org_id, cookies = admin_org
        async_client.cookies.update(cookies)
        await async_client.post(f"/api/orgs/{org_id}/scim/token")

        response = await async_client.delete(f"/api/orgs/{org_id}/scim/token")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_revoked_token_no_longer_works(self, async_client: AsyncClient, admin_org):
        org_id, cookies = admin_org
        async_client.cookies.update(cookies)
        token_resp = await async_client.post(f"/api/orgs/{org_id}/scim/token")
        scim_token = token_resp.json()["token"]

        await async_client.delete(f"/api/orgs/{org_id}/scim/token")

        async_client.cookies.clear()
        response = await async_client.get(
            "/scim/v2/Users",
            headers=_scim_headers(scim_token),
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_regenerate_token_invalidates_old(self, async_client: AsyncClient, admin_org):
        org_id, cookies = admin_org
        async_client.cookies.update(cookies)
        first_resp = await async_client.post(f"/api/orgs/{org_id}/scim/token")
        first_token = first_resp.json()["token"]

        second_resp = await async_client.post(f"/api/orgs/{org_id}/scim/token")
        second_token = second_resp.json()["token"]

        async_client.cookies.clear()
        resp_old = await async_client.get("/scim/v2/Users", headers=_scim_headers(first_token))
        assert resp_old.status_code == 401

        resp_new = await async_client.get("/scim/v2/Users", headers=_scim_headers(second_token))
        assert resp_new.status_code == 200

    @pytest.mark.asyncio
    async def test_revoke_without_config_returns_404(self, async_client: AsyncClient, admin_org):
        """Revoke when no SSO config exists returns 404."""
        org_id, cookies = admin_org
        async_client.cookies.update(cookies)

        cfg = await OrgSSOConfig.find_one(OrgSSOConfig.org_id == org_id)
        if cfg:
            await cfg.delete()

        response = await async_client.delete(f"/api/orgs/{org_id}/scim/token")
        assert response.status_code == 404
