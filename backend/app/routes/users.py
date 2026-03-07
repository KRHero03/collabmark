"""User profile routes: get and update current user."""

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.models.user import User, UserRead, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile.

    Args:
        user: Injected by get_current_user dependency.

    Returns:
        UserRead representation of the current user.
    """
    return UserRead.from_doc(user)


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
