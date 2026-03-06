"""Organization lifecycle and membership management.

Provides helpers for creating organizations, managing members, and checking
org relationships.  All DB operations go through Beanie document methods.
"""

from __future__ import annotations

import logging
from typing import Optional

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.models.organization import (
    Organization,
    OrganizationCreate,
    OrganizationUpdate,
    OrgMembership,
    OrgRole,
)
from app.models.user import User

logger = logging.getLogger(__name__)


async def create_org(payload: OrganizationCreate, creator: User) -> Organization:
    """Create an organization and add the creator as its admin.

    Args:
        payload: Organization name, slug, and optional domains.
        creator: The user who will become the first admin.

    Returns:
        The newly created Organization.

    Raises:
        HTTPException: 409 if slug is already taken.
    """
    existing = await Organization.find_one(Organization.slug == payload.slug)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization slug '{payload.slug}' is already taken",
        )

    org = Organization(
        name=payload.name,
        slug=payload.slug,
        verified_domains=payload.verified_domains,
        plan=payload.plan,
    )
    await org.insert()

    membership = OrgMembership(
        org_id=str(org.id),
        user_id=str(creator.id),
        role=OrgRole.ADMIN,
    )
    await membership.insert()

    creator.org_id = str(org.id)
    creator.touch()
    await creator.save()

    logger.info("Created org %s (slug=%s) by user %s", org.id, org.slug, creator.id)
    return org


async def get_org(org_id: str) -> Organization:
    """Fetch an organization by ID or raise 404.

    Args:
        org_id: Organization document ID.

    Returns:
        The Organization document.

    Raises:
        HTTPException: 404 if not found.
    """
    try:
        org = await Organization.get(PydanticObjectId(org_id))
    except (InvalidId, ValueError):
        org = None
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return org


async def list_orgs() -> list[Organization]:
    """List all organizations, ordered by creation date descending."""
    return await Organization.find().sort("-created_at").to_list()


async def update_org(org_id: str, payload: OrganizationUpdate) -> Organization:
    """Update organization fields.

    Args:
        org_id: Organization document ID.
        payload: Fields to update (all optional).

    Returns:
        The updated Organization.

    Raises:
        HTTPException: 404 if not found, 409 if new slug conflicts.
    """
    org = await get_org(org_id)

    if payload.slug is not None and payload.slug != org.slug:
        conflict = await Organization.find_one(Organization.slug == payload.slug)
        if conflict is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slug '{payload.slug}' is already taken",
            )
        org.slug = payload.slug

    if payload.name is not None:
        org.name = payload.name
    if payload.verified_domains is not None:
        org.verified_domains = payload.verified_domains
    if payload.plan is not None:
        org.plan = payload.plan

    org.touch()
    await org.save()
    return org


async def get_org_member_count(org_id: str) -> int:
    """Return the number of members in an organization."""
    return await OrgMembership.find(OrgMembership.org_id == org_id).count()


async def add_member(org_id: str, user_id: str, role: OrgRole = OrgRole.MEMBER) -> OrgMembership:
    """Add a user to an organization.

    Args:
        org_id: Organization ID.
        user_id: User ID to add.
        role: Role to assign (default: member).

    Returns:
        The created OrgMembership.

    Raises:
        HTTPException: 404 if org or user not found, 409 if already a member.
    """
    await get_org(org_id)

    try:
        user = await User.get(PydanticObjectId(user_id))
    except (InvalidId, ValueError):
        user = None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    existing = await OrgMembership.find_one(
        OrgMembership.org_id == org_id,
        OrgMembership.user_id == user_id,
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this organization",
        )

    if user.org_id is not None and user.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already belongs to another organization",
        )

    membership = OrgMembership(org_id=org_id, user_id=user_id, role=role)
    await membership.insert()

    user.org_id = org_id
    user.touch()
    await user.save()

    return membership


async def remove_member(org_id: str, user_id: str) -> None:
    """Remove a user from an organization.

    Args:
        org_id: Organization ID.
        user_id: User ID to remove.

    Raises:
        HTTPException: 404 if membership not found.
    """
    membership = await OrgMembership.find_one(
        OrgMembership.org_id == org_id,
        OrgMembership.user_id == user_id,
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    await membership.delete()

    try:
        user = await User.get(PydanticObjectId(user_id))
    except (InvalidId, ValueError):
        user = None
    if user is not None and user.org_id == org_id:
        user.org_id = None
        user.touch()
        await user.save()


async def list_members(org_id: str) -> list[OrgMembership]:
    """List all memberships for an organization."""
    return await OrgMembership.find(OrgMembership.org_id == org_id).to_list()


async def get_user_org(user_id: str) -> Optional[Organization]:
    """Get the organization a user belongs to, or None for personal users."""
    try:
        user = await User.get(PydanticObjectId(user_id))
    except (InvalidId, ValueError):
        return None
    if user is None or user.org_id is None:
        return None
    try:
        return await Organization.get(PydanticObjectId(user.org_id))
    except (InvalidId, ValueError):
        return None


def is_same_org_fast(user_a_org_id: Optional[str], user_b_org_id: Optional[str]) -> bool:
    """O(1) org comparison using denormalized org_id fields.

    Both None (personal users) is considered same-context for backward
    compatibility — personal users can share with anyone.
    """
    if user_a_org_id is None and user_b_org_id is None:
        return True
    return user_a_org_id == user_b_org_id


async def is_org_admin(user_id: str, org_id: str) -> bool:
    """Check whether a user is an admin of the given organization."""
    membership = await OrgMembership.find_one(
        OrgMembership.org_id == org_id,
        OrgMembership.user_id == user_id,
    )
    return membership is not None and membership.role == OrgRole.ADMIN
