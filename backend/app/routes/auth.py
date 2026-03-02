"""Authentication routes: Google OAuth login, callback, logout."""

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from app.auth.google_oauth import get_google_oauth
from app.auth.jwt import create_access_token
from app.config import settings
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/google/login")
async def google_login(request: Request):
    """Redirect the user to Google's OAuth consent screen.

    Args:
        request: Starlette request for OAuth state.

    Returns:
        RedirectResponse to Google's authorization URL.
    """
    google = get_google_oauth()
    redirect_uri = settings.google_redirect_uri
    return await google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request):
    """Handle the OAuth callback from Google, create/update user, set JWT cookie.

    Args:
        request: Starlette request with OAuth code/state.

    Returns:
        RedirectResponse to frontend with access_token cookie set, or error query param.
    """
    google = get_google_oauth()
    token = await google.authorize_access_token(request)
    user_info = token.get("userinfo")

    if not user_info:
        return RedirectResponse(url=f"{settings.frontend_url}?error=oauth_failed")

    user = await User.find_one(User.google_id == user_info["sub"])

    if user is None:
        user = User(
            google_id=user_info["sub"],
            email=user_info["email"],
            name=user_info.get("name", user_info["email"]),
            avatar_url=user_info.get("picture"),
        )
        await user.insert()
    else:
        user.name = user_info.get("name", user.name)
        user.avatar_url = user_info.get("picture", user.avatar_url)
        user.touch()
        await user.save()

    access_token = create_access_token(str(user.id))

    response = RedirectResponse(url=settings.frontend_url)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )
    return response


@router.post("/logout")
async def logout(response: Response):
    """Clear the access_token session cookie.

    Args:
        response: Response object to delete the cookie on.

    Returns:
        Dict with message confirming logout.
    """
    response.delete_cookie("access_token")
    return {"message": "Logged out"}
