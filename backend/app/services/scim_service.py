"""SCIM 2.0 user provisioning service.

Implements the business logic for SCIM user lifecycle operations: create,
list, get, update (PATCH/PUT), and deactivate.  Maps between the SCIM
``urn:ietf:params:scim:schemas:core:2.0:User`` schema and the internal
:class:`User` model.

Reuses :mod:`app.services.org_service` for membership management (DRY).

Complies with RFC 7644 (Protocol) and RFC 7643 (Core Schema).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from beanie import PydanticObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from app.models.group import Group, GroupMembership
from app.models.organization import Organization, OrgMembership, OrgRole
from app.models.user import User

logger = logging.getLogger(__name__)

SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
SCIM_LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"
SCIM_ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"


# ---------------------------------------------------------------------------
# SCIM error helper
# ---------------------------------------------------------------------------


class SCIMError(Exception):
    """Raised by SCIM service functions; caught by the route-level handler."""

    def __init__(self, status_code: int, detail: str, scim_type: str | None = None):
        self.status_code = status_code
        self.detail = detail
        self.scim_type = scim_type
        super().__init__(detail)

    def to_dict(self) -> dict[str, Any]:
        """Build a SCIM-compliant error response body (RFC 7644 Section 3.12)."""
        body: dict[str, Any] = {
            "schemas": [SCIM_ERROR_SCHEMA],
            "status": str(self.status_code),
            "detail": self.detail,
        }
        if self.scim_type:
            body["scimType"] = self.scim_type
        return body


# ---------------------------------------------------------------------------
# Schema / attribute mapping
# ---------------------------------------------------------------------------

# Attributes with returned=always (immune to excludedAttributes)
_ALWAYS_RETURNED = {"schemas", "id"}


def scim_to_user_fields(resource: dict[str, Any]) -> dict[str, Any]:
    """Extract internal User fields from a SCIM User resource.

    Resolves email from ``userName`` or the ``emails`` array.
    Resolves display name from ``displayName``, ``name.formatted``,
    or ``givenName``+``familyName``, falling back to the email local part.

    Raises:
        SCIMError: 400 if no email can be resolved.
    """
    email = _extract_email(resource)
    name_obj = resource.get("name") if isinstance(resource.get("name"), dict) else {}
    given_name = name_obj.get("givenName")
    family_name = name_obj.get("familyName")

    display_name = resource.get("displayName") or ""
    if not display_name:
        display_name = name_obj.get("formatted") or ""
    if not display_name and (given_name or family_name):
        display_name = f"{given_name or ''} {family_name or ''}".strip()
    if not display_name:
        display_name = email.split("@")[0]

    avatar_url = None
    photos = resource.get("photos", [])
    if photos and isinstance(photos[0], dict):
        avatar_url = photos[0].get("value")

    result: dict[str, Any] = {
        "email": email,
        "name": display_name,
        "avatar_url": avatar_url,
        "given_name": given_name,
        "family_name": family_name,
        "scim_emails": resource.get("emails"),
        "scim_photos": resource.get("photos"),
    }
    if "externalId" in resource:
        result["external_id"] = resource["externalId"]
    return result


def _extract_email(resource: dict[str, Any]) -> str:
    """Resolve email from userName or the emails array.

    Raises:
        SCIMError: 400 if no email can be found.
    """
    email = resource.get("userName")
    if email:
        return email

    emails_list = resource.get("emails", [])
    for entry in emails_list:
        if isinstance(entry, dict) and entry.get("primary"):
            email = entry.get("value")
            if email:
                return email

    if emails_list and isinstance(emails_list[0], dict):
        email = emails_list[0].get("value")
        if email:
            return email

    raise SCIMError(400, "userName or emails[].value is required")


def user_to_scim(user: User, org_id: str) -> dict[str, Any]:
    """Convert an internal User document to a SCIM User resource."""
    active = user.org_id == org_id

    name_obj: dict[str, Any] = {"formatted": user.name}
    if user.given_name is not None:
        name_obj["givenName"] = user.given_name
    if user.family_name is not None:
        name_obj["familyName"] = user.family_name

    if user.scim_emails is not None:
        emails = user.scim_emails
    else:
        emails = [{"value": user.email, "primary": True, "type": "work"}]

    resource: dict[str, Any] = {
        "schemas": [SCIM_USER_SCHEMA],
        "id": str(user.id),
        "userName": user.email,
        "name": name_obj,
        "displayName": user.name,
        "emails": emails,
        "active": active,
        "meta": {
            "resourceType": "User",
            "created": user.created_at.isoformat(),
            "lastModified": user.updated_at.isoformat(),
            "location": f"/scim/v2/Users/{user.id}",
        },
    }

    if user.scim_photos is not None:
        if user.scim_photos:
            resource["photos"] = user.scim_photos
    elif user.avatar_url:
        resource["photos"] = [{"value": user.avatar_url, "type": "photo"}]
    if user.external_id is not None:
        resource["externalId"] = user.external_id
    return resource


def filter_scim_attributes(
    resource: dict[str, Any],
    attributes: str | None = None,
    excluded_attributes: str | None = None,
) -> dict[str, Any]:
    """Apply ``attributes`` / ``excludedAttributes`` filtering per RFC 7644 Section 3.4.2.5."""
    if not attributes and not excluded_attributes:
        return resource

    if attributes:
        include = {a.strip().lower() for a in attributes.split(",")} | _ALWAYS_RETURNED
        return {k: v for k, v in resource.items() if k.lower() in include}

    if excluded_attributes:
        exclude = {a.strip().lower() for a in excluded_attributes.split(",")}
        exclude -= {a.lower() for a in _ALWAYS_RETURNED}
        return {k: v for k, v in resource.items() if k.lower() not in exclude}

    return resource


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


async def create_scim_user(org_id: str, resource: dict[str, Any]) -> User:
    """Provision a new user via SCIM.

    Raises:
        SCIMError: 400 for missing fields, 409 if email already exists.
    """
    fields = scim_to_user_fields(resource)

    existing = await User.find_one(User.email == fields["email"])
    if existing is not None:
        if existing.org_id == org_id:
            raise SCIMError(
                409,
                f"User with email '{fields['email']}' already exists in this organization",
                scim_type="uniqueness",
            )
        raise SCIMError(
            409,
            f"User with email '{fields['email']}' already exists",
            scim_type="uniqueness",
        )

    user = User(
        email=fields["email"],
        name=fields["name"],
        org_id=org_id,
        auth_provider="scim",
    )
    _apply_fields_to_user(user, fields)
    try:
        await user.insert()
    except DuplicateKeyError as exc:
        raise SCIMError(
            409,
            f"User with identifier '{fields['email']}' already exists",
            scim_type="uniqueness",
        ) from exc

    membership = OrgMembership(
        org_id=org_id,
        user_id=str(user.id),
        role=OrgRole.MEMBER,
    )
    await membership.insert()

    logger.info("SCIM: Created user %s (%s) in org %s", user.id, user.email, org_id)
    return user


# ---------------------------------------------------------------------------
# Filter parsing (RFC 7644 Section 3.4.2.2)
# ---------------------------------------------------------------------------

_FILTER_RE = re.compile(
    r"^(\w[\w.]*)\s+(eq|ne|co|sw|ew|gt|ge|lt|le)\s+\"([^\"]*)\"$",
    re.IGNORECASE,
)
_FILTER_PR_RE = re.compile(r"^(\w[\w.]*)\s+pr$", re.IGNORECASE)


def _parse_scim_filter(filter_str: str) -> tuple[str, str, str] | tuple[str, str] | None:
    """Parse a SCIM filter expression.

    Supports: ``attr op "value"`` and ``attr pr``.

    Returns:
        (attr, op, value) or (attr, "pr") or None.

    Raises:
        SCIMError: 400 with scimType=invalidFilter for unsupported operators.
    """
    stripped = filter_str.strip()

    pr_match = _FILTER_PR_RE.match(stripped)
    if pr_match:
        return pr_match.group(1), "pr"

    match = _FILTER_RE.match(stripped)
    if match:
        attr, op, value = match.group(1), match.group(2).lower(), match.group(3)
        supported = {"eq", "ne", "co", "sw", "ew"}
        if op not in supported:
            raise SCIMError(400, f"Filter operator '{op}' is not supported", scim_type="invalidFilter")
        return attr, op, value

    raise SCIMError(400, f"Invalid filter expression: {filter_str}", scim_type="invalidFilter")


def _apply_string_filter(query_value: str, op: str, filter_value: str) -> bool:
    """Evaluate a string filter comparison (case-insensitive)."""
    qv = query_value.lower()
    fv = filter_value.lower()
    if op == "eq":
        return qv == fv
    if op == "ne":
        return qv != fv
    if op == "co":
        return fv in qv
    if op == "sw":
        return qv.startswith(fv)
    if op == "ew":
        return qv.endswith(fv)
    return False


async def list_scim_users(
    org_id: str,
    filter_str: Optional[str] = None,
    start_index: int = 1,
    count: int = 100,
    attributes: str | None = None,
    excluded_attributes: str | None = None,
) -> dict[str, Any]:
    """List SCIM users with pagination, filtering, and attribute selection."""
    if start_index < 1:
        start_index = 1
    if count < 0:
        count = 0

    all_users = await User.find(User.org_id == org_id).to_list()

    if filter_str:
        parsed = _parse_scim_filter(filter_str)
        filtered: list[User] = []
        for u in all_users:
            attr = parsed[0].lower()
            if len(parsed) == 2 and parsed[1] == "pr":
                val = _resolve_user_attr(u, attr)
                if val is not None and val != "":
                    filtered.append(u)
            elif len(parsed) == 3:
                _, op, fval = parsed  # type: ignore[misc]
                uval = _resolve_user_attr(u, attr)
                if uval is not None and _apply_string_filter(str(uval), op, fval):
                    filtered.append(u)
        all_users = filtered

    total = len(all_users)
    skip = max(0, start_index - 1)
    page = all_users[skip : skip + count]

    resources = [filter_scim_attributes(user_to_scim(u, org_id), attributes, excluded_attributes) for u in page]

    return {
        "schemas": [SCIM_LIST_SCHEMA],
        "totalResults": total,
        "startIndex": start_index,
        "itemsPerPage": len(page),
        "Resources": resources,
    }


def _resolve_user_attr(user: User, scim_attr: str) -> str | None:
    """Resolve a SCIM attribute name to the user's value."""
    attr = scim_attr.lower()
    if attr == "username":
        return user.email
    if attr == "displayname":
        return user.name
    if attr == "name.formatted":
        return user.name
    if attr == "externalid":
        return user.external_id
    if attr == "active":
        return str(user.org_id is not None).lower()
    return None


async def get_scim_user(org_id: str, user_id: str) -> User:
    """Fetch a single SCIM-provisioned user, verifying org membership.

    Raises:
        SCIMError: 404 if user not found or not in the org.
    """
    try:
        user = await User.get(PydanticObjectId(user_id))
    except (InvalidId, ValueError):
        user = None

    if user is None or user.org_id != org_id:
        raise SCIMError(404, "User not found")
    return user


# ---------------------------------------------------------------------------
# PUT (full replacement)
# ---------------------------------------------------------------------------


async def replace_scim_user(org_id: str, user_id: str, resource: dict[str, Any]) -> User:
    """Full replacement of a SCIM user (RFC 7644 Section 3.5.1).

    readOnly attributes (id, meta) are ignored. Omitted readWrite
    attributes are cleared.

    Raises:
        SCIMError: 404 if user not found, 400 for invalid input.
    """
    user = await get_scim_user(org_id, user_id)
    fields = scim_to_user_fields(resource)

    user.email = fields["email"]
    user.name = fields["name"]
    _apply_fields_to_user(user, fields)

    user.touch()
    await user.save()
    return user


# ---------------------------------------------------------------------------
# PATCH operations (RFC 7644 Section 3.5.2)
# ---------------------------------------------------------------------------


async def update_scim_user(org_id: str, user_id: str, payload: dict[str, Any]) -> User:
    """Update a SCIM user via PATCH operations or direct attribute replacement.

    Supports RFC 7644 PATCH ``Operations`` and simple top-level
    attribute replacement (used by some IdPs like Azure AD).

    Raises:
        SCIMError: 404 if user not found.
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
    """Apply a single SCIM PATCH operation to a User."""
    operation = op.get("op", "").lower()
    path = op.get("path", "")
    value = op.get("value")
    path_lower = path.lower() if path else ""

    if operation == "replace":
        _patch_replace(user, org_id, path_lower, value)
    elif operation == "add":
        _patch_add(user, org_id, path_lower, value)
    elif operation == "remove":
        _patch_remove(user, path_lower)
    else:
        raise SCIMError(400, f"Unsupported PATCH op: {operation}")


def _set_attr_by_path(user: User, path: str, value: Any) -> None:
    """Set a single user attribute by its lowercased SCIM path.

    Shared by both PATCH add and PATCH replace operations since the
    path-based logic is identical for both (RFC 7644 Section 3.5.2).
    """
    if path in ("username", 'emails[type eq "work"].value'):
        if isinstance(value, str):
            user.email = value
    elif path in ("displayname", "name.formatted"):
        if isinstance(value, str):
            user.name = value
    elif path == "name":
        if isinstance(value, dict):
            _set_name_from_dict(user, value)
    elif path == "name.givenname":
        if isinstance(value, str):
            user.given_name = value
    elif path == "name.familyname":
        if isinstance(value, str):
            user.family_name = value
    elif path == "externalid":
        user.external_id = value if isinstance(value, str) else None
    elif path == "emails":
        if isinstance(value, list):
            user.scim_emails = value
            _sync_primary_email(user, value)
    elif path == "photos":
        if isinstance(value, list):
            user.scim_photos = value
            _sync_avatar_url(user, value)
    elif path == "active":
        pass


def _patch_replace(user: User, org_id: str, path: str, value: Any) -> None:
    """Handle PATCH replace operation."""
    if not path and isinstance(value, dict):
        _apply_direct_attrs(user, org_id, value)
    else:
        _set_attr_by_path(user, path, value)


def _patch_add(user: User, org_id: str, path: str, value: Any) -> None:
    """Handle PATCH add operation (RFC 7644 Section 3.5.2.1)."""
    if not path and isinstance(value, dict):
        _apply_direct_attrs(user, org_id, value)
    else:
        _set_attr_by_path(user, path, value)


def _patch_remove(user: User, path: str) -> None:
    """Handle PATCH remove operation (RFC 7644 Section 3.5.2.2).

    Raises:
        SCIMError: 400 if path is empty or targets a required attribute.
    """
    if not path:
        raise SCIMError(400, "Path is required for remove operations", scim_type="noTarget")

    if path == "username":
        raise SCIMError(400, "Cannot remove required attribute 'userName'", scim_type="mutability")

    if path in ("displayname", "name.formatted"):
        user.name = ""
    elif path == "externalid":
        user.external_id = None
    elif path == "name":
        user.name = ""
        user.given_name = None
        user.family_name = None
    elif path == "name.givenname":
        user.given_name = None
    elif path == "name.familyname":
        user.family_name = None
    elif path == "emails":
        user.scim_emails = []
    elif path == "photos":
        user.scim_photos = []
        user.avatar_url = None
    elif path == "active":
        pass
    else:
        raise SCIMError(400, f"No attribute found for path '{path}'", scim_type="noTarget")


def _apply_fields_to_user(user: User, fields: dict[str, Any]) -> None:
    """Apply optional SCIM-derived fields to a User document.

    Used by both create and replace to avoid duplicating field assignments.
    Required fields (email, name) are set by the caller since create uses
    the constructor while replace uses direct assignment.
    """
    user.given_name = fields.get("given_name")
    user.family_name = fields.get("family_name")
    user.avatar_url = fields.get("avatar_url")
    user.external_id = fields.get("external_id")
    user.scim_emails = fields.get("scim_emails")
    user.scim_photos = fields.get("scim_photos")


def _sync_primary_email(user: User, emails: list[Any]) -> None:
    """Sync user.email from a SCIM emails array (primary or first entry)."""
    for entry in emails:
        if isinstance(entry, dict) and entry.get("primary"):
            if entry.get("value"):
                user.email = entry["value"]
            return
    if emails and isinstance(emails[0], dict) and emails[0].get("value"):
        user.email = emails[0]["value"]


def _sync_avatar_url(user: User, photos: list[Any]) -> None:
    """Sync user.avatar_url from a SCIM photos array (first entry)."""
    if photos and isinstance(photos[0], dict):
        user.avatar_url = photos[0].get("value")
    else:
        user.avatar_url = None


def _set_name_from_dict(user: User, name_obj: dict[str, Any]) -> None:
    """Set user name from a SCIM name object, including givenName/familyName."""
    if "givenName" in name_obj:
        user.given_name = name_obj["givenName"]
    if "familyName" in name_obj:
        user.family_name = name_obj["familyName"]

    formatted = name_obj.get("formatted")
    if formatted:
        user.name = formatted
    else:
        given = name_obj.get("givenName", "")
        family = name_obj.get("familyName", "")
        combined = f"{given} {family}".strip()
        if combined:
            user.name = combined


def _apply_direct_attrs(user: User, org_id: str, attrs: dict[str, Any]) -> None:
    """Apply top-level SCIM attributes directly to a User."""
    if "userName" in attrs:
        user.email = attrs["userName"]
    if "displayName" in attrs:
        user.name = attrs["displayName"]
    if "externalId" in attrs:
        user.external_id = attrs["externalId"]
    if "name" in attrs and isinstance(attrs["name"], dict):
        _set_name_from_dict(user, attrs["name"])
    emails = attrs.get("emails")
    if isinstance(emails, list):
        user.scim_emails = emails
        _sync_primary_email(user, emails)
    photos = attrs.get("photos")
    if isinstance(photos, list):
        user.scim_photos = photos
        _sync_avatar_url(user, photos)


async def delete_scim_user(org_id: str, user_id: str) -> None:
    """Deactivate a SCIM user by removing their org membership.

    The User document is preserved (they may own documents) but their
    ``org_id`` is cleared and the :class:`OrgMembership` is deleted.

    Raises:
        SCIMError: 404 if user not found or not in the org.
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


# ---------------------------------------------------------------------------
# SCIM Group operations
# ---------------------------------------------------------------------------


def group_to_scim(group: Group, org_id: str, members: list[GroupMembership] | None = None) -> dict[str, Any]:
    """Convert a Group document to a SCIM Group resource."""
    resource: dict[str, Any] = {
        "schemas": [SCIM_GROUP_SCHEMA],
        "id": str(group.id),
        "displayName": group.name,
        "meta": {
            "resourceType": "Group",
            "created": group.created_at.isoformat(),
            "lastModified": group.updated_at.isoformat(),
            "location": f"/scim/v2/Groups/{group.id}",
        },
    }
    if group.external_id:
        resource["externalId"] = group.external_id
    if group.scim_members:
        resource["members"] = group.scim_members
    elif members:
        resource["members"] = [{"value": m.user_id} for m in members]
    return resource


async def _sync_group_members(group: Group, org_id: str, members_data: list[dict[str, Any]]) -> list[GroupMembership]:
    """Sync group membership from SCIM members array. Returns final membership list."""
    group_id = str(group.id)

    group.scim_members = [{"value": m["value"]} for m in members_data if m.get("value")]
    await group.save()

    desired_user_ids = {m.get("value") for m in members_data if m.get("value")}

    existing = await GroupMembership.find(GroupMembership.group_id == group_id).to_list()
    existing_map = {m.user_id: m for m in existing}

    for uid, membership in existing_map.items():
        if uid not in desired_user_ids:
            await membership.delete()

    for uid in desired_user_ids:
        if uid not in existing_map:
            try:
                u = await User.get(PydanticObjectId(uid))
            except (InvalidId, ValueError):
                continue
            if u is None or u.org_id != org_id:
                continue
            gm = GroupMembership(group_id=group_id, user_id=uid)
            await gm.insert()

    await _apply_role_mapping(org_id, group.name)

    return await GroupMembership.find(GroupMembership.group_id == group_id).to_list()


async def _apply_role_mapping(org_id: str, group_name: str) -> None:
    """If group matches org's admin_group_name, set members to ADMIN role."""
    try:
        org = await Organization.get(PydanticObjectId(org_id))
    except (InvalidId, ValueError):
        return
    if org is None or not org.admin_group_name:
        return
    if group_name != org.admin_group_name:
        return

    group = await Group.find_one(Group.org_id == org_id, Group.name == group_name)
    if group is None:
        return

    memberships = await GroupMembership.find(GroupMembership.group_id == str(group.id)).to_list()
    for gm in memberships:
        org_membership = await OrgMembership.find_one(
            OrgMembership.org_id == org_id,
            OrgMembership.user_id == gm.user_id,
        )
        if org_membership and org_membership.role != OrgRole.ADMIN:
            org_membership.role = OrgRole.ADMIN
            await org_membership.save()


async def create_scim_group(org_id: str, resource: dict[str, Any]) -> Group:
    """Provision a new group via SCIM."""
    display_name = resource.get("displayName")
    if not display_name:
        raise SCIMError(400, "displayName is required")

    existing = await Group.find_one(Group.org_id == org_id, Group.name == display_name)
    if existing:
        raise SCIMError(409, f"Group '{display_name}' already exists", scim_type="uniqueness")

    group = Group(
        name=display_name,
        org_id=org_id,
        external_id=resource.get("externalId"),
        scim_synced=True,
    )
    await group.insert()

    members_data = resource.get("members", [])
    if members_data:
        await _sync_group_members(group, org_id, members_data)

    logger.info("SCIM: Created group %s (%s) in org %s", group.id, group.name, org_id)
    return group


async def list_scim_groups(
    org_id: str,
    filter_str: str | None = None,
    start_index: int = 1,
    count: int = 100,
) -> dict[str, Any]:
    """List SCIM groups with pagination and filtering."""
    if start_index < 1:
        start_index = 1
    if count < 0:
        count = 0

    all_groups = await Group.find(Group.org_id == org_id).to_list()

    if filter_str:
        parsed = _parse_scim_filter(filter_str)
        filtered: list[Group] = []
        for g in all_groups:
            attr = parsed[0].lower()
            if attr == "displayname":
                val = g.name
            elif attr == "externalid":
                val = g.external_id
            else:
                val = None

            if len(parsed) == 2 and parsed[1] == "pr":
                if val is not None and val != "":
                    filtered.append(g)
            elif len(parsed) == 3 and val is not None:
                _, op, fval = parsed
                if _apply_string_filter(str(val), op, fval):
                    filtered.append(g)
        all_groups = filtered

    total = len(all_groups)
    skip = max(0, start_index - 1)
    page = all_groups[skip : skip + count]

    resources = []
    for g in page:
        members = await GroupMembership.find(GroupMembership.group_id == str(g.id)).to_list()
        resources.append(group_to_scim(g, org_id, members))

    return {
        "schemas": [SCIM_LIST_SCHEMA],
        "totalResults": total,
        "startIndex": start_index,
        "itemsPerPage": len(page),
        "Resources": resources,
    }


async def get_scim_group(org_id: str, group_id: str) -> Group:
    """Fetch a single SCIM group, verifying org membership."""
    try:
        group = await Group.get(PydanticObjectId(group_id))
    except (InvalidId, ValueError):
        group = None
    if group is None or group.org_id != org_id:
        raise SCIMError(404, "Group not found")
    return group


async def replace_scim_group(org_id: str, group_id: str, resource: dict[str, Any]) -> Group:
    """Full replacement of a SCIM group."""
    group = await get_scim_group(org_id, group_id)

    display_name = resource.get("displayName")
    if not display_name:
        raise SCIMError(400, "displayName is required")

    group.name = display_name
    group.external_id = resource.get("externalId")
    group.touch()
    await group.save()

    members_data = resource.get("members", [])
    await _sync_group_members(group, org_id, members_data)

    return group


async def _handle_group_member_add(group: Group, org_id: str, members: list[dict]) -> None:
    """Add members to a group from SCIM PATCH add operation."""
    current = list(group.scim_members or [])
    existing_vals = {m.get("value") for m in current}

    for m in members:
        uid = m.get("value")
        if not uid or uid in existing_vals:
            continue
        current.append({"value": uid})
        existing_vals.add(uid)

        existing_gm = await GroupMembership.find_one(
            GroupMembership.group_id == str(group.id),
            GroupMembership.user_id == uid,
        )
        if not existing_gm:
            try:
                u = await User.get(PydanticObjectId(uid))
            except (InvalidId, ValueError):
                continue
            if u and u.org_id == org_id:
                gm = GroupMembership(group_id=str(group.id), user_id=uid)
                await gm.insert()

    group.scim_members = current
    await _apply_role_mapping(org_id, group.name)


async def _handle_group_member_remove(group: Group, members: list[dict] | None = None, uid: str | None = None) -> None:
    """Remove members from a group. Either pass a list of member dicts or a single uid."""
    uids_to_remove: set[str] = set()
    if uid:
        uids_to_remove.add(uid)
    elif members:
        for m in members:
            v = m.get("value")
            if v:
                uids_to_remove.add(v)

    for remove_uid in uids_to_remove:
        gm = await GroupMembership.find_one(
            GroupMembership.group_id == str(group.id),
            GroupMembership.user_id == remove_uid,
        )
        if gm:
            await gm.delete()

    if group.scim_members:
        remaining = [m for m in group.scim_members if m.get("value") not in uids_to_remove]
        group.scim_members = remaining or None


async def _remove_all_group_members(group: Group) -> None:
    """Remove all memberships from a group."""
    memberships = await GroupMembership.find(GroupMembership.group_id == str(group.id)).to_list()
    for m in memberships:
        await m.delete()


async def update_scim_group(org_id: str, group_id: str, payload: dict[str, Any]) -> Group:
    """Update a SCIM group via PATCH operations."""
    group = await get_scim_group(org_id, group_id)

    operations = payload.get("Operations", [])
    for op in operations:
        operation = op.get("op", "").lower()
        path = (op.get("path") or "").lower()
        value = op.get("value")

        if operation == "replace":
            if path == "displayname" and isinstance(value, str):
                group.name = value
            elif path == "externalid" and isinstance(value, str):
                group.external_id = value
            elif path == "members" and isinstance(value, list):
                await _sync_group_members(group, org_id, value)
            elif not path and isinstance(value, dict):
                if "displayName" in value:
                    group.name = value["displayName"]
                if "externalId" in value:
                    group.external_id = value["externalId"]
                if "members" in value and isinstance(value["members"], list):
                    await _sync_group_members(group, org_id, value["members"])
        elif operation == "add":
            if path == "externalid" and isinstance(value, str):
                group.external_id = value
            elif path == "members" and isinstance(value, list):
                await _handle_group_member_add(group, org_id, value)
            elif not path and isinstance(value, dict):
                if "externalId" in value:
                    group.external_id = value["externalId"]
                if "members" in value and isinstance(value["members"], list):
                    await _handle_group_member_add(group, org_id, value["members"])
        elif operation == "remove":
            if path == "externalid":
                group.external_id = None
            elif path == "members":
                if isinstance(value, list):
                    await _handle_group_member_remove(group, members=value)
                else:
                    group.scim_members = None
                    await _remove_all_group_members(group)
            elif path.startswith("members[value eq"):
                match = re.search(r'"([^"]+)"', path)
                if match:
                    await _handle_group_member_remove(group, uid=match.group(1))

    group.touch()
    await group.save()
    return group


async def delete_scim_group(org_id: str, group_id: str) -> None:
    """Delete a SCIM group and all its memberships."""
    group = await get_scim_group(org_id, group_id)

    memberships = await GroupMembership.find(GroupMembership.group_id == str(group.id)).to_list()
    for m in memberships:
        await m.delete()

    await group.delete()
    logger.info("SCIM: Deleted group %s (%s) from org %s", group.id, group.name, org_id)
