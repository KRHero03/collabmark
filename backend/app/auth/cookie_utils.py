"""Shared utilities for setting and clearing auth cookies."""

from fastapi.responses import RedirectResponse, Response

from app.config import AUTH_COOKIE_NAME, settings


def set_auth_cookie(response: Response | RedirectResponse, access_token: str) -> None:
    """Set the JWT access token as an HTTP-only cookie on the response.

    Args:
        response: The FastAPI response to attach the cookie to.
        access_token: The encoded JWT.
    """
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )


def clear_auth_cookie(response: Response) -> None:
    """Delete the access_token cookie, matching original set params.

    Args:
        response: The response to delete the cookie from.
    """
    response.delete_cookie(AUTH_COOKIE_NAME, path="/", samesite="lax")
