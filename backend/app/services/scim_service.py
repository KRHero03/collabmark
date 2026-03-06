"""SCIM 2.0 user provisioning service.

Implements the business logic for SCIM user lifecycle operations: create,
list, get, update (PATCH), and deactivate.  Maps between the SCIM
``urn:ietf:params:scim:schemas:core:2.0:User`` schema and the internal
:class:`User` model.

Reuses :mod:`app.services.org_service` for membership management (DRY).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.models.organization import OrgMembership, OrgRole
from app.models.user import User

logger = logging.getLogger(__name__)

SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
SCIM_ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"


def scim_error(status_code: int, detail: str) -> dict[str, Any]:
    """Build a SCIM-compliant error response body (RFC 7644 Section 3.12).

    Args:
        status_code: HTTP status code.
        detail: Human-readable error description.

    Returns:
        SCIM error dict with ``schemas``, ``status``, and ``detail``.
    """
    return {
        "schemas": [SCIM_ERROR_SCHEMA],
        "status": str(status_code),
        "detail": detail,
    }


def scim_to_user_fields(resource: dict[str, Any]) -> dict[str, Any]:
    """Extract internal User fields from a SCIM User resource.

    Handles both ``userName`` (used as email) and the ``emails`` array.
    Display name is resolved from ``displayName``, ``name.formatted``,
    or ``name.givenName``+``name.familyName``.

    Args:
        resource: SCIM User resource dict from the IdP.

    Returns:
        Dict with keys ``email``, ``name``, and optionally ``avatar_url``.

    Raises:
        HTTPException: 400 if required fields are missing.
    """
    email = resource.get("userName")
    if not email:
        emails_list = resource.get("emails", [])
        for entry in emails_list:
            if isinstance(entry, dict) and entry.get("primary"):
                email = entry.get("value")
                break
        if not email and emails_list:
            first = emails_list[0]
            email = first.get("value") if isinstance(first, dict) else None

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="userName or emails[].value is required",
        )

    name = resource.get("displayName") or ""
    if not name:
        name_obj = resource.get("name", {})
        if isinstance(name_obj, dict):
            name = name_obj.get("formatted") or ""
            if not name:
                given = name_obj.get("givenName", "")
                family = name_obj.get("familyName", "")
                name = f"{given} {family}".strip()

    if not name:
        name = email.split("@")[0]

    avatar_url = None
    photos = resource.get("photos", [])
    if photos and isinstance(photos[0], dict):
        avatar_url = photos[0].get("value")

    return {"email": email, "name": name, "avatar_url": avatar_url}


def user_to_scim(user: User, org_id: str) -> dict[str, Any]:
    """Convert an internal User document to a SCIM User resource.

    Args:
        user: The User document.
        org_id: The organization ID for membership context.

    Returns:
        SCIM-formatted User resource dict.
    """
    active = user.org_id == org_id

    return {
        "schemas": [SCIM_USER_SCHEMA],
        "id": str(user.id),
        "userName": user.email,
        "name": {
            "formatted": user.name,
        },
        "displayName": user.name,
        "emails": [
            {
                "value": user.email,
                "primary": True,
                "type": "work",
            }
        ],
        "photos": [{"value": user.avatar_url, "type": "photo"}] if user.avatar_url else [],
        "active": active,
        "meta": {
            "resourceType": "User",
            "created": user.created_at.isoformat(),
            "lastModified": user.updated_at.isoformat(),
            "location": f"/scim/v2/Users/{user.id}",
        },
    }


async def create_scim_user(org_id: str, resource: dict[str, Any]) -> User:
    """Provision a new user via SCIM.

    Creates the :class:`User` document with ``auth_provider="scim"`` and adds
    an :class:`OrgMembership` for the target organization.

    Args:
        org_id: Target organization ID.
        resource: SCIM User resource from the IdP request body.

    Returns:
        The newly created User.

    Raises:
        HTTPException: 400 for missing fields, 409 if email already exists.
    """
    fields = scim_to_user_fields(resource)

    existing = await User.find_one(User.email == fields["email"])
    if existing is not None:
        if existing.org_id == org_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{fields['email']}' already exists in this organization",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{fields['email']}' already exists",
        )

    user = User(
        email=fields["email"],
        name=fields["name"],
        avatar_url=fields.get("avatar_url"),
        org_id=org_id,
        auth_provider="scim",
    )
    await user.insert()

    membership = OrgMembership(
        org_id=org_id,
        user_id=str(user.id),
        role=OrgRole.MEMBER,
    )
    await membership.insert()

    logger.info("SCIM: Created user %s (%s) in org %s", user.id, user.email, org_id)
    return user


def _parse_scim_filter(filter_str: str) -> tuple[str, str] | None:
    """Parse a simple SCIM filter expression (``attr eq "value"``).

    Only supports the ``eq`` operator on a single attribute, which covers
    the vast majority of IdP filter queries.

    Args:
        filter_str: Raw SCIM filter string.

    Returns:
        Tuple of (attribute, value) or None if unparseable.
    """
    match = re.match(r'^(\w+)\s+eq\s+"([^"]*)"$', filter_str.strip(), re.IGNORECASE)
    if match:
        return match.group(1), match.group(2)
    return None


async def list_scim_users(
    org_id: str,
    filter_str: Optional[str] = None,
    start_index: int = 1,
    count: int = 100,
) -> dict[str, Any]:
    """List SCIM users with pagination and optional filter.

    Supports ``userName eq "..."`` filter for IdP user lookups.

    Args:
        org_id: Organization ID to scope the listing.
        filter_str: Optional SCIM filter expression.
        start_index: 1-based start index for pagination.
        count: Maximum number of results to return.

    Returns:
        SCIM ListResponse dict with ``schemas``, ``totalResults``,
        ``startIndex``, ``itemsPerPage``, and ``Resources``.
    """
    query = User.find(User.org_id == org_id, User.auth_provider == "scim")

    if filter_str:
        parsed = _parse_scim_filter(filter_str)
        if parsed:
            attr, value = parsed
            if attr.lower() == "username":
                query = User.find(User.org_id == org_id, User.email == value)
            elif attr.lower() == "displayname":
                query = User.find(User.org_id == org_id, User.name == value)

    total = await query.count()

    skip = max(0, start_index - 1)
    users = await query.skip(skip).limit(count).to_list()

    return {
        "schemas": [SCIM_LIST_SCHEMA],
        "totalResults": total,
        "startIndex": start_index,
        "itemsPerPage": len(users),
        "Resources": [user_to_scim(u, org_id) for u in users],
    }


async def get_scim_user(org_id: str, user_id: str) -> User:
    """Fetch a single SCIM-provisioned user, verifying org membership.

    Args:
        org_id: Organization ID for scoping.
        user_id: User document ID.

    Returns:
        The User document.

    Raises:
        HTTPException: 404 if user not found or not in the org.
    """
    try:
        user = await User.get(PydanticObjectId(user_id))
    except (InvalidId, ValueError):
        user = None

    if user is None or user.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


async def update_scim_user(org_id: str, user_id: str, payload: dict[str, Any]) -> User:
    """Update a SCIM user via PATCH operations or direct attribute replacement.

    Supports both RFC 7644 PATCH ``Operations`` and simple top-level
    attribute replacement (used by some IdPs like Azure AD).

    Args:
        org_id: Organization ID for scoping.
        user_id: User document ID.
        payload: SCIM PATCH request body.

    Returns:
        The updated User document.

    Raises:
        HTTPException: 404 if user not found.
    """
    user = await get_scim_user(org_id, user_id)

    operations = payload.get("Operations", [])
    if operations:
        for op in operations:
            _apply_patch_op(user, org_id, op)
    else:
        _apply_direct_attrs(user, org_id, payload)

    user.touch()
    await user.save()
    return user


def _apply_patch_op(user: User, org_id: str, op: dict[str, Any]) -> None:
    """Apply a single SCIM PATCH operation to a User.

    Args:
        user: The User document to modify in-place.
        org_id: Organization ID for active-state management.
        op: A single SCIM PATCH operation dict (op, path, value).
    """
    operation = op.get("op", "").lower()
    path = op.get("path", "").lower()
    value = op.get("value")

    if operation == "replace":
        if path == "username" or path == 'emails[type eq "work"].value':
            if isinstance(value, str):
                user.email = value
        elif path == "displayname" or path == "name.formatted":
            if isinstance(value, str):
                user.name = value
        elif path == "name":
            if isinstance(value, dict):
                formatted = value.get("formatted")
                if formatted:
                    user.name = formatted
                else:
                    given = value.get("givenName", "")
                    family = value.get("familyName", "")
                    combined = f"{given} {family}".strip()
                    if combined:
                        user.name = combined
        elif path == "active":
            pass
        elif not path and isinstance(value, dict):
            _apply_direct_attrs(user, org_id, value)


def _apply_direct_attrs(user: User, org_id: str, attrs: dict[str, Any]) -> None:
    """Apply top-level SCIM attributes directly to a User.

    Args:
        user: The User document to modify in-place.
        org_id: Organization ID for context.
        attrs: Dict of SCIM attributes to apply.
    """
    if "userName" in attrs:
        user.email = attrs["userName"]
    if "displayName" in attrs:
        user.name = attrs["displayName"]
    if "name" in attrs and isinstance(attrs["name"], dict):
        formatted = attrs["name"].get("formatted")
        if formatted:
            user.name = formatted
        else:
            given = attrs["name"].get("givenName", "")
            family = attrs["name"].get("familyName", "")
            combined = f"{given} {family}".strip()
            if combined:
                user.name = combined
    emails = attrs.get("emails")
    if isinstance(emails, list) and emails:
        primary_email = None
        for entry in emails:
            if isinstance(entry, dict) and entry.get("primary"):
                primary_email = entry.get("value")
                break
        if primary_email:
            user.email = primary_email


async def delete_scim_user(org_id: str, user_id: str) -> None:
    """Deactivate a SCIM user by removing their org membership.

    The User document is preserved (they may own documents) but their
    ``org_id`` is cleared and the :class:`OrgMembership` is deleted.

    Args:
        org_id: Organization ID.
        user_id: User document ID.

    Raises:
        HTTPException: 404 if user not found or not in the org.
    """
    user = await get_scim_user(org_id, user_id)

    membership = await OrgMembership.find_one(
        OrgMembership.org_id == org_id,
        OrgMembership.user_id == str(user.id),
    )
    if membership is not None:
        await membership.delete()

    user.org_id = None
    user.touch()
    await user.save()

    logger.info("SCIM: Deactivated user %s (%s) from org %s", user.id, user.email, org_id)
