"""Organization management routes: CRUD, membership, SSO, and SCIM token management.

Super admin routes require the user's email to be in SUPER_ADMIN_EMAILS.
Org admin routes require the user to be an admin of the target organization.
Member routes only require the user to belong to the target organization.
"""

import re
import secrets

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, EmailStr

from app.auth.dependencies import get_current_user, get_org_admin_user, get_super_admin_user
from app.auth.scim_auth import hash_scim_token
from app.config import settings
from app.models.group import Group, GroupMembership, GroupRead
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
from app.rate_limit import limiter
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


@router.get("/{org_id}/groups", response_model=list[GroupRead])
async def search_groups(
    org_id: str,
    q: str = "",
    user: User = Depends(get_current_user),
):
    """Search groups by name within an organization. Any org member can search."""
    if user.org_id != org_id:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    if q:
        escaped = re.escape(q)
        groups = await Group.find(
            Group.org_id == org_id,
            {"name": {"$regex": escaped, "$options": "i"}},
        ).to_list()
    else:
        groups = await Group.find(Group.org_id == org_id).to_list()

    result = []
    for g in groups:
        count = await GroupMembership.find(GroupMembership.group_id == str(g.id)).count()
        result.append(GroupRead.from_doc(g, member_count=count))
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
                is_super_admin=u.email in settings.super_admin_emails,
                auth_provider=u.auth_provider,
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


# ---------------------------------------------------------------------------
# SCIM token management (org admin)
# ---------------------------------------------------------------------------


@router.post("/{org_id}/scim/token", status_code=201)
@limiter.limit("5/minute")
async def generate_scim_token(
    request: Request,
    org_id: str,
    user: User = Depends(get_org_admin_user),
):
    """Generate a new SCIM bearer token for the organization.

    The plaintext token is returned exactly once.  Only the SHA-256 hash
    is stored in the database.  Generating a new token invalidates any
    previous token.

    Returns:
        JSON with ``token`` (plaintext, one-time display) and ``scim_enabled``.
    """
    await org_service.get_org(org_id)

    cfg = await OrgSSOConfig.find_one(OrgSSOConfig.org_id == org_id)
    if cfg is None:
        cfg = OrgSSOConfig(org_id=org_id)

    plaintext = secrets.token_urlsafe(48)
    cfg.scim_bearer_token = hash_scim_token(plaintext)
    cfg.scim_enabled = True
    cfg.touch()

    if cfg.id is None:
        await cfg.insert()
    else:
        await cfg.save()

    return {"token": plaintext, "scim_enabled": True}


@router.delete("/{org_id}/scim/token", status_code=204)
async def revoke_scim_token(
    org_id: str,
    user: User = Depends(get_org_admin_user),
):
    """Revoke the SCIM bearer token and disable SCIM provisioning.

    Clears the stored token hash and sets ``scim_enabled=False``.
    """
    cfg = await OrgSSOConfig.find_one(OrgSSOConfig.org_id == org_id)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO configuration not found",
        )

    cfg.scim_bearer_token = None
    cfg.scim_enabled = False
    cfg.touch()
    await cfg.save()


# ---------------------------------------------------------------------------
# Logo upload/delete (org admin)
# ---------------------------------------------------------------------------


@router.post("/{org_id}/logo", response_model=OrganizationRead)
@limiter.limit("10/minute")
async def upload_logo(
    request: Request,
    org_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_org_admin_user),
):
    """Upload or replace the organization logo. Max 2MB. PNG/JPG/SVG/WebP."""
    contents = await file.read()
    org = await org_service.upload_org_logo(org_id, file.filename or "logo.png", contents)
    count = await org_service.get_org_member_count(org_id)
    return OrganizationRead.from_doc(org, member_count=count)


@router.delete("/{org_id}/logo", status_code=204)
async def delete_logo(
    org_id: str,
    user: User = Depends(get_org_admin_user),
):
    """Remove the organization logo."""
    await org_service.delete_org_logo(org_id)
