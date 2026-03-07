"""Tests for SCIM 2.0 discovery endpoints (RFC 7644 Section 4).

Discovery endpoints are public (no auth required) and provide metadata
about the service provider's capabilities and supported schemas.
"""

import pytest
from httpx import AsyncClient

SCIM_CONTENT_TYPE = "application/scim+json"
USER_SCHEMA_URN = "urn:ietf:params:scim:schemas:core:2.0:User"


# ---------------------------------------------------------------------------
# ServiceProviderConfig
# ---------------------------------------------------------------------------


class TestServiceProviderConfig:
    @pytest.mark.asyncio
    async def test_returns_200(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/ServiceProviderConfig")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_content_type(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/ServiceProviderConfig")
        assert response.headers["content-type"] == SCIM_CONTENT_TYPE

    @pytest.mark.asyncio
    async def test_no_auth_required(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/ServiceProviderConfig")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_contains_required_fields(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/ServiceProviderConfig")
        data = response.json()
        assert "schemas" in data
        assert "urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig" in data["schemas"]
        assert "patch" in data
        assert data["patch"]["supported"] is True
        assert "bulk" in data
        assert data["bulk"]["supported"] is False
        assert "filter" in data
        assert data["filter"]["supported"] is True
        assert "changePassword" in data
        assert data["changePassword"]["supported"] is False
        assert "sort" in data
        assert data["sort"]["supported"] is False
        assert "etag" in data
        assert data["etag"]["supported"] is False
        assert "authenticationSchemes" in data
        assert len(data["authenticationSchemes"]) >= 1

    @pytest.mark.asyncio
    async def test_meta_location(self, async_client: AsyncClient):
        data = (await async_client.get("/scim/v2/ServiceProviderConfig")).json()
        assert data["meta"]["location"] == "/scim/v2/ServiceProviderConfig"
        assert data["meta"]["resourceType"] == "ServiceProviderConfig"


# ---------------------------------------------------------------------------
# ResourceTypes
# ---------------------------------------------------------------------------


class TestResourceTypes:
    @pytest.mark.asyncio
    async def test_list_returns_200(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/ResourceTypes")
        assert response.status_code == 200
        data = response.json()
        assert data["totalResults"] == 2
        assert len(data["Resources"]) == 2
        names = {r["name"] for r in data["Resources"]}
        assert "User" in names
        assert "Group" in names

    @pytest.mark.asyncio
    async def test_list_no_auth_required(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/ResourceTypes")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_user_resource_type(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/ResourceTypes/User")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "User"
        assert data["name"] == "User"
        assert data["endpoint"] == "/Users"
        assert data["schema"] == USER_SCHEMA_URN
        assert data["meta"]["resourceType"] == "ResourceType"
        assert data["meta"]["location"] == "/scim/v2/ResourceTypes/User"

    @pytest.mark.asyncio
    async def test_get_group_resource_type(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/ResourceTypes/Group")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "Group"
        assert data["name"] == "Group"
        assert data["endpoint"] == "/Groups"
        assert data["schema"] == "urn:ietf:params:scim:schemas:core:2.0:Group"
        assert data["meta"]["resourceType"] == "ResourceType"
        assert data["meta"]["location"] == "/scim/v2/ResourceTypes/Group"

    @pytest.mark.asyncio
    async def test_get_unknown_resource_type_returns_404(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/ResourceTypes/UnknownResource")
        assert response.status_code == 404
        data = response.json()
        assert "urn:ietf:params:scim:api:messages:2.0:Error" in data["schemas"]
        assert data["status"] == "404"

    @pytest.mark.asyncio
    async def test_content_type(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/ResourceTypes")
        assert response.headers["content-type"] == SCIM_CONTENT_TYPE


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TestSchemas:
    @pytest.mark.asyncio
    async def test_list_returns_200(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/Schemas")
        assert response.status_code == 200
        data = response.json()
        assert data["totalResults"] == 2
        assert len(data["Resources"]) == 2
        schema_ids = {r["id"] for r in data["Resources"]}
        assert USER_SCHEMA_URN in schema_ids
        assert "urn:ietf:params:scim:schemas:core:2.0:Group" in schema_ids

    @pytest.mark.asyncio
    async def test_list_no_auth_required(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/Schemas")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_user_schema(self, async_client: AsyncClient):
        response = await async_client.get(f"/scim/v2/Schemas/{USER_SCHEMA_URN}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == USER_SCHEMA_URN
        assert data["name"] == "User"
        assert "attributes" in data
        assert len(data["attributes"]) > 0
        attr_names = {a["name"] for a in data["attributes"]}
        assert "userName" in attr_names
        assert "displayName" in attr_names
        assert "emails" in attr_names
        assert "externalId" in attr_names
        assert "active" in attr_names

    @pytest.mark.asyncio
    async def test_get_user_schema_has_meta(self, async_client: AsyncClient):
        data = (await async_client.get(f"/scim/v2/Schemas/{USER_SCHEMA_URN}")).json()
        assert data["meta"]["resourceType"] == "Schema"
        assert data["meta"]["location"] == f"/scim/v2/Schemas/{USER_SCHEMA_URN}"

    @pytest.mark.asyncio
    async def test_get_group_schema(self, async_client: AsyncClient):
        group_schema_urn = "urn:ietf:params:scim:schemas:core:2.0:Group"
        response = await async_client.get(f"/scim/v2/Schemas/{group_schema_urn}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == group_schema_urn
        assert data["name"] == "Group"
        assert "attributes" in data
        attr_names = {a["name"] for a in data["attributes"]}
        assert "displayName" in attr_names
        assert "members" in attr_names
        assert "externalId" in attr_names

    @pytest.mark.asyncio
    async def test_get_unknown_schema_returns_404(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/Schemas/urn:ietf:params:scim:schemas:core:2.0:Unknown")
        assert response.status_code == 404
        data = response.json()
        assert "urn:ietf:params:scim:api:messages:2.0:Error" in data["schemas"]

    @pytest.mark.asyncio
    async def test_content_type(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/Schemas")
        assert response.headers["content-type"] == SCIM_CONTENT_TYPE

    @pytest.mark.asyncio
    async def test_user_schema_attributes_structure(self, async_client: AsyncClient):
        """Each attribute has required RFC 7643 Section 7 properties."""
        data = (await async_client.get(f"/scim/v2/Schemas/{USER_SCHEMA_URN}")).json()
        for attr in data["attributes"]:
            assert "name" in attr
            assert "type" in attr
            assert "multiValued" in attr
            assert "mutability" in attr
            assert "returned" in attr


# ---------------------------------------------------------------------------
# Catch-all for unknown SCIM paths
# ---------------------------------------------------------------------------


class TestScimCatchAll:
    @pytest.mark.asyncio
    async def test_unknown_path_returns_scim_404(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/NonExistent")
        assert response.status_code == 404
        data = response.json()
        assert "urn:ietf:params:scim:api:messages:2.0:Error" in data["schemas"]
        assert data["status"] == "404"

    @pytest.mark.asyncio
    async def test_unknown_path_has_scim_content_type(self, async_client: AsyncClient):
        response = await async_client.get("/scim/v2/SomethingRandom")
        assert response.status_code == 404
        assert response.headers["content-type"] == SCIM_CONTENT_TYPE

    @pytest.mark.asyncio
    async def test_unknown_path_post_returns_scim_404(self, async_client: AsyncClient):
        response = await async_client.post("/scim/v2/Bogus", json={})
        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "404"
