"""Organization management routes: CRUD, membership, and SSO configuration.

Super admin routes require the user's email to be in SUPER_ADMIN_EMAILS.
Org admin routes require the user to be an admin of the target organization.
Member routes only require the user to belong to the target organization.
"""

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.auth.dependencies import get_current_user, get_org_admin_user, get_super_admin_user
from app.models.org_sso_config import OrgSSOConfig, OrgSSOConfigRead, OrgSSOConfigUpdate
from app.models.organization import (
    AddMemberPayload,
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
    OrgMemberRead,
    OrgMembership,
    OrgRole,
)
from app.models.user import User
from app.services import org_service

router = APIRouter(prefix="/api/orgs", tags=["organizations"])


class InviteMemberPayload(BaseModel):
    """Payload for inviting a member by email."""

    email: EmailStr
    role: OrgRole = OrgRole.MEMBER


class UpdateRolePayload(BaseModel):
    """Payload for changing a member's role."""

    role: OrgRole


# ---------------------------------------------------------------------------
# Current user's org (any authenticated user)
# ---------------------------------------------------------------------------


@router.get("/my", response_model=OrganizationRead | None)
async def get_my_org(user: User = Depends(get_current_user)):
    """Get the current user's organization, or null if personal user."""
    if user.org_id is None:
        return None
    org = await org_service.get_user_org(str(user.id))
    if org is None:
        return None
    count = await org_service.get_org_member_count(str(org.id))
    return OrganizationRead.from_doc(org, member_count=count)


# ---------------------------------------------------------------------------
# Organization CRUD (super admin)
# ---------------------------------------------------------------------------


@router.post("", response_model=OrganizationRead, status_code=201)
async def create_org(
    payload: OrganizationCreate,
    user: User = Depends(get_super_admin_user),
):
    """Create a new organization. The requesting super admin becomes the first admin member."""
    org = await org_service.create_org(payload, user)
    count = await org_service.get_org_member_count(str(org.id))
    return OrganizationRead.from_doc(org, member_count=count)


@router.get("", response_model=list[OrganizationRead])
async def list_orgs(user: User = Depends(get_super_admin_user)):
    """List all organizations. Super admin only."""
    orgs = await org_service.list_orgs()
    result = []
    for o in orgs:
        count = await org_service.get_org_member_count(str(o.id))
        result.append(OrganizationRead.from_doc(o, member_count=count))
    return result


@router.get("/{org_id}", response_model=OrganizationRead)
async def get_org(org_id: str, user: User = Depends(get_org_admin_user)):
    """Get organization details. Org admin only (must be admin of this org)."""
    org = await org_service.get_org(org_id)
    count = await org_service.get_org_member_count(org_id)
    return OrganizationRead.from_doc(org, member_count=count)


@router.put("/{org_id}", response_model=OrganizationRead)
async def update_org(
    org_id: str,
    payload: OrganizationUpdate,
    user: User = Depends(get_org_admin_user),
):
    """Update organization details. Org admin only."""
    org = await org_service.update_org(org_id, payload)
    count = await org_service.get_org_member_count(org_id)
    return OrganizationRead.from_doc(org, member_count=count)


# ---------------------------------------------------------------------------
# Member management (org admin)
# ---------------------------------------------------------------------------


@router.get("/{org_id}/members", response_model=list[OrgMemberRead])
async def list_members(org_id: str, user: User = Depends(get_org_admin_user)):
    """List all members of an organization. Org admin only."""
    memberships = await org_service.list_members(org_id)
    result = []
    for m in memberships:
        try:
            u = await User.get(PydanticObjectId(m.user_id))
        except Exception:
            continue
        if u is None:
            continue
        result.append(
            OrgMemberRead(
                id=str(m.id),
                user_id=m.user_id,
                user_name=u.name or "",
                user_email=u.email or "",
                avatar_url=u.avatar_url,
                role=m.role,
                joined_at=m.joined_at,
            )
        )
    return result


@router.post("/{org_id}/members", response_model=OrgMemberRead, status_code=201)
async def add_member(
    org_id: str,
    payload: AddMemberPayload,
    user: User = Depends(get_org_admin_user),
):
    """Add a member to the organization by user_id. Org admin only."""
    membership = await org_service.add_member(org_id, payload.user_id, payload.role)
    target = await User.get(PydanticObjectId(payload.user_id))
    return OrgMemberRead(
        id=str(membership.id),
        user_id=membership.user_id,
        user_name=target.name if target else "",
        user_email=target.email if target else "",
        avatar_url=target.avatar_url if target else None,
        role=membership.role,
        joined_at=membership.joined_at,
    )


@router.post("/{org_id}/members/invite", response_model=OrgMemberRead, status_code=201)
async def invite_member(
    org_id: str,
    payload: InviteMemberPayload,
    user: User = Depends(get_org_admin_user),
):
    """Invite a user to the organization by email. Creates membership if user exists."""
    target = await User.find_one(User.email == payload.email)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user with email '{payload.email}' found. They must sign up first.",
        )
    membership = await org_service.add_member(org_id, str(target.id), payload.role)
    return OrgMemberRead(
        id=str(membership.id),
        user_id=str(target.id),
        user_name=target.name or "",
        user_email=target.email or "",
        avatar_url=target.avatar_url,
        role=membership.role,
        joined_at=membership.joined_at,
    )


@router.patch("/{org_id}/members/{member_user_id}/role", response_model=OrgMemberRead)
async def update_member_role(
    org_id: str,
    member_user_id: str,
    payload: UpdateRolePayload,
    user: User = Depends(get_org_admin_user),
):
    """Change a member's role. Org admin only."""
    membership = await OrgMembership.find_one(
        OrgMembership.org_id == org_id,
        OrgMembership.user_id == member_user_id,
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )
    membership.role = payload.role
    await membership.save()
    target = await User.get(PydanticObjectId(member_user_id))
    return OrgMemberRead(
        id=str(membership.id),
        user_id=membership.user_id,
        user_name=target.name if target else "",
        user_email=target.email if target else "",
        avatar_url=target.avatar_url if target else None,
        role=membership.role,
        joined_at=membership.joined_at,
    )


@router.delete("/{org_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    org_id: str,
    member_user_id: str,
    user: User = Depends(get_org_admin_user),
):
    """Remove a member from the organization. Org admin only."""
    await org_service.remove_member(org_id, member_user_id)


# ---------------------------------------------------------------------------
# SSO configuration (org admin)
# ---------------------------------------------------------------------------


@router.get("/{org_id}/sso", response_model=OrgSSOConfigRead | None)
async def get_sso_config(org_id: str, user: User = Depends(get_org_admin_user)):
    """Get the SSO configuration for an organization. Secrets are redacted."""
    cfg = await OrgSSOConfig.find_one(OrgSSOConfig.org_id == org_id)
    if cfg is None:
        return None
    return OrgSSOConfigRead.from_doc(cfg)


@router.put("/{org_id}/sso", response_model=OrgSSOConfigRead)
async def update_sso_config(
    org_id: str,
    payload: OrgSSOConfigUpdate,
    user: User = Depends(get_org_admin_user),
):
    """Create or update SSO configuration for an organization. Org admin only."""
    await org_service.get_org(org_id)

    cfg = await OrgSSOConfig.find_one(OrgSSOConfig.org_id == org_id)
    if cfg is None:
        cfg = OrgSSOConfig(org_id=org_id)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(cfg, key, value)

    cfg.touch()
    if cfg.id is None:
        await cfg.insert()
    else:
        await cfg.save()

    return OrgSSOConfigRead.from_doc(cfg)
