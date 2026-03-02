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
