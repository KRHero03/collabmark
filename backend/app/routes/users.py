"""User profile routes: get and update current user."""

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.config import settings
from app.models.organization import Organization, OrgMembership
from app.models.user import User, UserRead, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile with org context.

    Args:
        user: Injected by get_current_user dependency.

    Returns:
        UserRead representation of the current user.
    """
    result = UserRead.from_doc(user)
    is_super = user.email in settings.super_admin_emails
    result.is_super_admin = is_super

    if user.org_id and not is_super:
        membership = await OrgMembership.find_one(
            OrgMembership.org_id == user.org_id,
            OrgMembership.user_id == str(user.id),
        )
        if membership:
            result.org_role = membership.role.value

        try:
            org = await Organization.get(PydanticObjectId(user.org_id))
        except Exception:
            org = None
        if org:
            result.org_name = org.name
            result.org_logo_url = org.logo_url

    return result


@router.put("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
):
    """Update the current user's profile (name, avatar_url).

    Args:
        payload: Fields to update. All optional.
        user: Injected by get_current_user dependency.

    Returns:
        UserRead representation of the updated user.
    """
    if payload.name is not None:
        user.name = payload.name
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    user.touch()
    await user.save()
    return UserRead.from_doc(user)
