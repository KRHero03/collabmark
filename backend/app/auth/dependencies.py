"""FastAPI dependencies for authentication (JWT, API key)."""

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import Cookie, Depends, HTTPException, Security, status

from app.auth.api_key import get_user_from_api_key
from app.auth.jwt import decode_access_token
from app.models.user import User


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    api_key_user: User | None = Security(get_user_from_api_key),
) -> User:
    """Authenticate via JWT cookie or API key header. API key takes precedence.

    Args:
        access_token: JWT from cookie (optional).
        api_key_user: User resolved from X-API-Key header (optional).

    Returns:
        The authenticated User.

    Raises:
        HTTPException: 401 if not authenticated or token invalid.
    """
    if api_key_user is not None:
        return api_key_user

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user_id = decode_access_token(access_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    try:
        user = await User.get(PydanticObjectId(user_id))
    except (InvalidId, ValueError):
        user = None

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def get_super_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    """Require the authenticated user to be a super admin.

    Super admins are identified by email in the SUPER_ADMIN_EMAILS config.

    Args:
        user: The authenticated user from get_current_user.

    Returns:
        The authenticated super admin User.

    Raises:
        HTTPException: 403 if the user is not a super admin.
    """
    from app.config import settings

    if user.email not in settings.super_admin_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return user


async def get_org_admin_user(
    org_id: str,
    user: User = Depends(get_current_user),
) -> User:
    """Require the authenticated user to be an admin of the target organization.

    Args:
        org_id: Organization ID from the route path.
        user: The authenticated user from get_current_user.

    Returns:
        The authenticated org admin User.

    Raises:
        HTTPException: 403 if the user is not an admin of the target org.
    """
    from app.services.org_service import is_org_admin

    if not await is_org_admin(str(user.id), org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin access required",
        )
    return user
