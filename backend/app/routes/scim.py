"""SCIM 2.0 provisioning routes.

Implements the ``/scim/v2/Users`` REST endpoints per RFC 7644 along with
discovery endpoints (ServiceProviderConfig, ResourceTypes, Schemas) per
RFC 7644 Section 4.

All CRUD routes are authenticated via a per-organization bearer token
resolved by the :func:`get_scim_org` dependency.  Discovery endpoints
are public (no auth required per spec).
"""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.scim_auth import get_scim_org
from app.models.group import GroupMembership
from app.models.org_sso_config import OrgSSOConfig
from app.models.organization import Organization
from app.services import scim_service
from app.services.scim_service import SCIMError

router = APIRouter(prefix="/scim/v2", tags=["scim"])

SCIM_CONTENT_TYPE = "application/scim+json"

# ---------------------------------------------------------------------------
# Error handler — catches SCIMError from service and auth layers
# ---------------------------------------------------------------------------


# FastAPI doesn't support router-level exception handlers, so we register
# at the app level via ``register_scim_error_handler(app)``.


def register_scim_error_handler(app: Any) -> None:
    """Register the SCIM error handler on the FastAPI app."""

    @app.exception_handler(SCIMError)
    async def _handle(request: Request, exc: SCIMError) -> JSONResponse:
        return JSONResponse(
            content=exc.to_dict(),
            status_code=exc.status_code,
            media_type=SCIM_CONTENT_TYPE,
        )

    @app.middleware("http")
    async def _scim_500_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Catch unhandled exceptions on /scim/v2/ paths and return SCIM JSON."""
        if not request.url.path.startswith("/scim/v2"):
            return await call_next(request)
        try:
            return await call_next(request)
        except Exception:
            import logging
            import traceback

            logging.getLogger("scim").error("Unhandled SCIM error:\n%s", traceback.format_exc())
            body = SCIMError(500, "Internal server error").to_dict()
            return JSONResponse(content=body, status_code=500, media_type=SCIM_CONTENT_TYPE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scim_response(
    data: dict[str, Any],
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build a JSONResponse with the ``application/scim+json`` media type."""
    return JSONResponse(
        content=data,
        status_code=status_code,
        media_type=SCIM_CONTENT_TYPE,
        headers=headers,
    )


# ========================================================================
# Discovery endpoints (RFC 7644 Section 4) — no auth
# ========================================================================

SCIM_USER_SCHEMA_URN = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_GROUP_SCHEMA_URN = "urn:ietf:params:scim:schemas:core:2.0:Group"
SCIM_SP_CONFIG_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"
SCIM_RESOURCE_TYPE_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:ResourceType"
SCIM_SCHEMA_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Schema"


_USER_SCHEMA_ATTRIBUTES = [
    {
        "name": "userName",
        "type": "string",
        "multiValued": False,
        "required": True,
        "caseExact": False,
        "mutability": "readWrite",
        "returned": "always",
        "uniqueness": "server",
        "description": "User email address used as the unique login identifier.",
    },
    {
        "name": "name",
        "type": "complex",
        "multiValued": False,
        "required": True,
        "mutability": "readWrite",
        "returned": "always",
        "uniqueness": "none",
        "description": "The components of the user's real name. Required for display in the UI.",
        "subAttributes": [
            {
                "name": "formatted",
                "type": "string",
                "multiValued": False,
                "required": True,
                "caseExact": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
                "description": "The full display name.",
            },
            {
                "name": "givenName",
                "type": "string",
                "multiValued": False,
                "required": False,
                "caseExact": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
                "description": "The given (first) name.",
            },
            {
                "name": "familyName",
                "type": "string",
                "multiValued": False,
                "required": False,
                "caseExact": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
                "description": "The family (last) name.",
            },
        ],
    },
    {
        "name": "displayName",
        "type": "string",
        "multiValued": False,
        "required": True,
        "caseExact": False,
        "mutability": "readWrite",
        "returned": "always",
        "uniqueness": "none",
        "description": "Display name shown in comments, sharing dialogs, and cursor presence.",
    },
    {
        "name": "emails",
        "type": "complex",
        "multiValued": True,
        "required": True,
        "mutability": "readWrite",
        "returned": "always",
        "uniqueness": "none",
        "description": "Email addresses. At least one is required for login and email-based sharing.",
        "subAttributes": [
            {
                "name": "value",
                "type": "string",
                "multiValued": False,
                "required": True,
                "caseExact": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
            },
            {
                "name": "type",
                "type": "string",
                "multiValued": False,
                "required": False,
                "caseExact": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
                "canonicalValues": ["work", "home", "other"],
            },
            {
                "name": "primary",
                "type": "boolean",
                "multiValued": False,
                "required": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
            },
        ],
    },
    {
        "name": "photos",
        "type": "complex",
        "multiValued": True,
        "required": False,
        "mutability": "readWrite",
        "returned": "default",
        "uniqueness": "none",
        "description": "User avatar URLs. Optional; a default avatar is used when absent.",
        "subAttributes": [
            {
                "name": "value",
                "type": "string",
                "multiValued": False,
                "required": False,
                "caseExact": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
                "description": "URL of the photo.",
            },
            {
                "name": "type",
                "type": "string",
                "multiValued": False,
                "required": False,
                "caseExact": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
                "canonicalValues": ["photo", "thumbnail"],
            },
        ],
    },
    {
        "name": "active",
        "type": "boolean",
        "multiValued": False,
        "required": False,
        "mutability": "readOnly",
        "returned": "always",
        "uniqueness": "none",
        "description": "Derived from organization membership. Cannot be set directly.",
    },
    {
        "name": "externalId",
        "type": "string",
        "multiValued": False,
        "required": False,
        "caseExact": True,
        "mutability": "readWrite",
        "returned": "default",
        "uniqueness": "none",
        "description": "Identifier from the provisioning client (IdP).",
    },
]

_GROUP_SCHEMA_ATTRIBUTES = [
    {
        "name": "displayName",
        "type": "string",
        "multiValued": False,
        "required": True,
        "caseExact": False,
        "mutability": "readWrite",
        "returned": "always",
        "uniqueness": "none",
        "description": "Group display name.",
    },
    {
        "name": "members",
        "type": "complex",
        "multiValued": True,
        "required": False,
        "mutability": "readWrite",
        "returned": "default",
        "uniqueness": "none",
        "description": "Group members (user references).",
        "subAttributes": [
            {
                "name": "value",
                "type": "string",
                "multiValued": False,
                "required": True,
                "caseExact": False,
                "mutability": "readWrite",
                "returned": "default",
                "uniqueness": "none",
                "description": "User ID.",
            },
        ],
    },
    {
        "name": "externalId",
        "type": "string",
        "multiValued": False,
        "required": False,
        "caseExact": True,
        "mutability": "readWrite",
        "returned": "default",
        "uniqueness": "none",
        "description": "Identifier from the provisioning client (IdP).",
    },
]

_SERVICE_PROVIDER_CONFIG: dict[str, Any] = {
    "schemas": [SCIM_SP_CONFIG_SCHEMA],
    "documentationUri": "https://tools.ietf.org/html/rfc7644",
    "patch": {"supported": True},
    "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
    "filter": {"supported": True, "maxResults": 200},
    "changePassword": {"supported": False},
    "sort": {"supported": False},
    "etag": {"supported": False},
    "authenticationSchemes": [
        {
            "type": "oauthbearertoken",
            "name": "OAuth Bearer Token",
            "description": "Authentication scheme using the OAuth Bearer Token Standard",
            "specUri": "https://tools.ietf.org/html/rfc6750",
            "primary": True,
        }
    ],
    "meta": {
        "resourceType": "ServiceProviderConfig",
        "location": "/scim/v2/ServiceProviderConfig",
    },
}

_USER_RESOURCE_TYPE: dict[str, Any] = {
    "schemas": [SCIM_RESOURCE_TYPE_SCHEMA],
    "id": "User",
    "name": "User",
    "endpoint": "/Users",
    "description": "User Account",
    "schema": SCIM_USER_SCHEMA_URN,
    "meta": {
        "resourceType": "ResourceType",
        "location": "/scim/v2/ResourceTypes/User",
    },
}

_GROUP_RESOURCE_TYPE: dict[str, Any] = {
    "schemas": [SCIM_RESOURCE_TYPE_SCHEMA],
    "id": "Group",
    "name": "Group",
    "endpoint": "/Groups",
    "description": "Group",
    "schema": SCIM_GROUP_SCHEMA_URN,
    "meta": {
        "resourceType": "ResourceType",
        "location": "/scim/v2/ResourceTypes/Group",
    },
}

_USER_SCHEMA_DEF: dict[str, Any] = {
    "schemas": [SCIM_SCHEMA_SCHEMA],
    "id": SCIM_USER_SCHEMA_URN,
    "name": "User",
    "description": "User Account",
    "attributes": _USER_SCHEMA_ATTRIBUTES,
    "meta": {
        "resourceType": "Schema",
        "location": f"/scim/v2/Schemas/{SCIM_USER_SCHEMA_URN}",
    },
}

_GROUP_SCHEMA_DEF: dict[str, Any] = {
    "schemas": [SCIM_SCHEMA_SCHEMA],
    "id": SCIM_GROUP_SCHEMA_URN,
    "name": "Group",
    "description": "Group",
    "attributes": _GROUP_SCHEMA_ATTRIBUTES,
    "meta": {
        "resourceType": "Schema",
        "location": f"/scim/v2/Schemas/{SCIM_GROUP_SCHEMA_URN}",
    },
}


@router.get("/ServiceProviderConfig")
async def scim_service_provider_config() -> JSONResponse:
    """Return the SCIM ServiceProviderConfig (RFC 7644 Section 4)."""
    return _scim_response(_SERVICE_PROVIDER_CONFIG)


@router.get("/ResourceTypes")
async def scim_resource_types() -> JSONResponse:
    """Return supported resource types as a ListResponse."""
    return _scim_response(
        {
            "schemas": [scim_service.SCIM_LIST_SCHEMA],
            "totalResults": 2,
            "Resources": [_USER_RESOURCE_TYPE, _GROUP_RESOURCE_TYPE],
        }
    )


@router.get("/ResourceTypes/{resource_type}")
async def scim_resource_type(resource_type: str) -> JSONResponse:
    """Return a single resource type by name."""
    if resource_type == "User":
        return _scim_response(_USER_RESOURCE_TYPE)
    if resource_type == "Group":
        return _scim_response(_GROUP_RESOURCE_TYPE)
    raise SCIMError(404, f"ResourceType '{resource_type}' not found")


@router.get("/Schemas")
async def scim_schemas() -> JSONResponse:
    """Return all supported schemas as a ListResponse."""
    return _scim_response(
        {
            "schemas": [scim_service.SCIM_LIST_SCHEMA],
            "totalResults": 2,
            "Resources": [_USER_SCHEMA_DEF, _GROUP_SCHEMA_DEF],
        }
    )


@router.get("/Schemas/{schema_id:path}")
async def scim_schema(schema_id: str) -> JSONResponse:
    """Return a single schema by its URN."""
    if schema_id == SCIM_USER_SCHEMA_URN:
        return _scim_response(_USER_SCHEMA_DEF)
    if schema_id == SCIM_GROUP_SCHEMA_URN:
        return _scim_response(_GROUP_SCHEMA_DEF)
    raise SCIMError(404, f"Schema '{schema_id}' not found")


# ========================================================================
# CRUD endpoints (authenticated via SCIM bearer token)
# ========================================================================


@router.post("/Users")
async def scim_create_user(
    request: Request,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """Provision a new user in the organization.

    Returns:
        201 with SCIM User resource + Location header on success.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)

    body = await request.json()
    user = await scim_service.create_scim_user(org_id, body)
    resource = scim_service.user_to_scim(user, org_id)
    location = resource["meta"]["location"]
    return _scim_response(resource, status_code=201, headers={"Location": location})


@router.get("/Users")
async def scim_list_users(
    request: Request,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """List or filter users provisioned in the organization.

    Supports SCIM query parameters: ``filter``, ``startIndex``, ``count``,
    ``attributes``, ``excludedAttributes``.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)

    params = request.query_params
    filter_str = params.get("filter")
    start_index = int(params.get("startIndex", "1"))
    count = int(params.get("count", "100"))
    attributes = params.get("attributes")
    excluded_attributes = params.get("excludedAttributes")

    result = await scim_service.list_scim_users(
        org_id,
        filter_str=filter_str,
        start_index=start_index,
        count=count,
        attributes=attributes,
        excluded_attributes=excluded_attributes,
    )
    return _scim_response(result)


@router.get("/Users/{user_id}")
async def scim_get_user(
    user_id: str,
    request: Request,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """Retrieve a single SCIM user by ID."""
    org, _cfg = org_ctx
    org_id = str(org.id)

    params = request.query_params
    attributes = params.get("attributes")
    excluded_attributes = params.get("excludedAttributes")

    user = await scim_service.get_scim_user(org_id, user_id)
    resource = scim_service.user_to_scim(user, org_id)
    resource = scim_service.filter_scim_attributes(resource, attributes, excluded_attributes)
    location = resource.get("meta", {}).get("location", f"/scim/v2/Users/{user_id}")
    return _scim_response(resource, headers={"Content-Location": location})


@router.put("/Users/{user_id}")
async def scim_replace_user(
    user_id: str,
    request: Request,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """Full replacement of a user resource (RFC 7644 Section 3.5.1).

    Returns:
        200 with updated SCIM User resource + Content-Location header.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)

    body = await request.json()
    user = await scim_service.replace_scim_user(org_id, user_id, body)
    resource = scim_service.user_to_scim(user, org_id)
    location = resource["meta"]["location"]
    return _scim_response(resource, headers={"Content-Location": location})


@router.patch("/Users/{user_id}")
async def scim_update_user(
    user_id: str,
    request: Request,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """Update user attributes via SCIM PATCH operations.

    Returns:
        Updated SCIM User resource + Content-Location header.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)

    body = await request.json()
    user = await scim_service.update_scim_user(org_id, user_id, body)
    resource = scim_service.user_to_scim(user, org_id)
    location = resource["meta"]["location"]
    return _scim_response(resource, headers={"Content-Location": location})


@router.delete("/Users/{user_id}", status_code=204)
async def scim_delete_user(
    user_id: str,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> None:
    """Deactivate a user (remove org membership).

    Returns:
        204 No Content on success.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)
    await scim_service.delete_scim_user(org_id, user_id)


# ========================================================================
# Group CRUD endpoints
# ========================================================================


@router.post("/Groups")
async def scim_create_group(
    request: Request,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """Provision a new group in the organization.

    Returns:
        201 with SCIM Group resource + Location header on success.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)

    body = await request.json()
    group = await scim_service.create_scim_group(org_id, body)
    members = await GroupMembership.find(GroupMembership.group_id == str(group.id)).to_list()
    resource = scim_service.group_to_scim(group, org_id, members)
    location = resource["meta"]["location"]
    return _scim_response(resource, status_code=201, headers={"Location": location})


@router.get("/Groups")
async def scim_list_groups(
    request: Request,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """List or filter groups provisioned in the organization.

    Supports SCIM query parameters: filter, startIndex, count.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)

    params = request.query_params
    filter_str = params.get("filter")
    start_index = int(params.get("startIndex", "1"))
    count = int(params.get("count", "100"))

    result = await scim_service.list_scim_groups(
        org_id,
        filter_str=filter_str,
        start_index=start_index,
        count=count,
    )
    return _scim_response(result)


@router.get("/Groups/{group_id}")
async def scim_get_group(
    group_id: str,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """Retrieve a single SCIM group by ID."""
    org, _cfg = org_ctx
    org_id = str(org.id)

    group = await scim_service.get_scim_group(org_id, group_id)
    members = await GroupMembership.find(GroupMembership.group_id == str(group.id)).to_list()
    resource = scim_service.group_to_scim(group, org_id, members)
    location = resource.get("meta", {}).get("location", f"/scim/v2/Groups/{group_id}")
    return _scim_response(resource, headers={"Content-Location": location})


@router.put("/Groups/{group_id}")
async def scim_replace_group(
    group_id: str,
    request: Request,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """Full replacement of a group resource (RFC 7644 Section 3.5.1).

    Returns:
        200 with updated SCIM Group resource + Content-Location header.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)

    body = await request.json()
    group = await scim_service.replace_scim_group(org_id, group_id, body)
    members = await GroupMembership.find(GroupMembership.group_id == str(group.id)).to_list()
    resource = scim_service.group_to_scim(group, org_id, members)
    location = resource["meta"]["location"]
    return _scim_response(resource, headers={"Content-Location": location})


@router.patch("/Groups/{group_id}")
async def scim_update_group(
    group_id: str,
    request: Request,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """Update group attributes via SCIM PATCH operations.

    Returns:
        Updated SCIM Group resource + Content-Location header.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)

    body = await request.json()
    group = await scim_service.update_scim_group(org_id, group_id, body)
    members = await GroupMembership.find(GroupMembership.group_id == str(group.id)).to_list()
    resource = scim_service.group_to_scim(group, org_id, members)
    location = resource["meta"]["location"]
    return _scim_response(resource, headers={"Content-Location": location})


@router.delete("/Groups/{group_id}", status_code=204)
async def scim_delete_group(
    group_id: str,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> None:
    """Delete a group and all its memberships.

    Returns:
        204 No Content on success.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)
    await scim_service.delete_scim_group(org_id, group_id)


# ========================================================================
# Catch-all for unknown SCIM paths — returns SCIM 404 instead of SPA HTML
# ========================================================================


@router.api_route("/{scim_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def scim_catch_all(scim_path: str) -> JSONResponse:
    """Return a SCIM-formatted 404 for any unrecognised path under /scim/v2/."""
    return _scim_response(
        SCIMError(404, f"Resource '/{scim_path}' not found").to_dict(),
        status_code=404,
    )
