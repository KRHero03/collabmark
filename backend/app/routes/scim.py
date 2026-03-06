"""SCIM 2.0 provisioning routes.

Implements the ``/scim/v2/Users`` REST endpoints per RFC 7644.  Enterprise
identity providers (Okta, Azure AD, Keycloak, etc.) call these endpoints to
automatically provision and deprovision users within an organization.

All routes are authenticated via a per-organization bearer token resolved
by the :func:`get_scim_org` dependency.
"""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.scim_auth import get_scim_org
from app.models.org_sso_config import OrgSSOConfig
from app.models.organization import Organization
from app.services import scim_service

router = APIRouter(prefix="/scim/v2", tags=["scim"])

SCIM_CONTENT_TYPE = "application/scim+json"


def _scim_response(data: dict[str, Any], status_code: int = 200) -> JSONResponse:
    """Build a JSONResponse with the ``application/scim+json`` media type."""
    return JSONResponse(content=data, status_code=status_code, media_type=SCIM_CONTENT_TYPE)


@router.post("/Users")
async def scim_create_user(
    request: Request,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """Provision a new user in the organization.

    The IdP sends a SCIM User resource; the handler creates the internal
    User document and org membership.

    Returns:
        201 with SCIM User resource on success, or SCIM error on failure.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)

    body = await request.json()
    user = await scim_service.create_scim_user(org_id, body)
    resource = scim_service.user_to_scim(user, org_id)
    return _scim_response(resource, status_code=201)


@router.get("/Users")
async def scim_list_users(
    request: Request,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """List or filter users provisioned in the organization.

    Supports SCIM query parameters: ``filter``, ``startIndex``, ``count``.

    Returns:
        SCIM ListResponse with paginated user resources.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)

    params = request.query_params
    filter_str = params.get("filter")
    start_index = int(params.get("startIndex", "1"))
    count = int(params.get("count", "100"))

    result = await scim_service.list_scim_users(org_id, filter_str=filter_str, start_index=start_index, count=count)
    return _scim_response(result)


@router.get("/Users/{user_id}")
async def scim_get_user(
    user_id: str,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """Retrieve a single SCIM user by ID.

    Returns:
        SCIM User resource, or 404 SCIM error if not found.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)

    user = await scim_service.get_scim_user(org_id, user_id)
    resource = scim_service.user_to_scim(user, org_id)
    return _scim_response(resource)


@router.patch("/Users/{user_id}")
async def scim_update_user(
    user_id: str,
    request: Request,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> JSONResponse:
    """Update user attributes via SCIM PATCH operations.

    Supports both RFC 7644 ``Operations`` array and direct attribute
    replacement (Azure AD-style).

    Returns:
        Updated SCIM User resource.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)

    body = await request.json()
    user = await scim_service.update_scim_user(org_id, user_id, body)
    resource = scim_service.user_to_scim(user, org_id)
    return _scim_response(resource)


@router.delete("/Users/{user_id}", status_code=204)
async def scim_delete_user(
    user_id: str,
    org_ctx: tuple[Organization, OrgSSOConfig] = Depends(get_scim_org),
) -> None:
    """Deactivate a user (remove org membership).

    The User document is preserved for document ownership; only the
    membership link is removed.

    Returns:
        204 No Content on success.
    """
    org, _cfg = org_ctx
    org_id = str(org.id)
    await scim_service.delete_scim_user(org_id, user_id)
