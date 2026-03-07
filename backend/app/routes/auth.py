"""Authentication routes: Google OAuth login/callback, logout, and SSO (SAML/OIDC)."""

import logging
import secrets

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.auth.cookie_utils import clear_auth_cookie, set_auth_cookie
from app.auth.google_oauth import get_google_oauth
from app.auth.jwt import create_access_token
from app.auth.sso_common import detect_org_by_email_domain, find_or_create_sso_user
from app.config import settings
from app.models.org_sso_config import OrgSSOConfig, SSOProtocol
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _error_redirect(code: str) -> RedirectResponse:
    """Build a redirect to the frontend with a generic error query param."""
    return RedirectResponse(url=f"{settings.frontend_url}?error={code}", status_code=302)


async def _get_enabled_sso_config(org_id: str) -> OrgSSOConfig | None:
    """Find an enabled SSO config for the given org, or None."""
    return await OrgSSOConfig.find_one(
        OrgSSOConfig.org_id == org_id,
        OrgSSOConfig.enabled == True,
    )


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------


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
        return _error_redirect("oauth_failed")

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
    set_auth_cookie(response, access_token)
    return response


@router.post("/logout")
async def logout(response: Response):
    """Clear the access_token session cookie.

    Args:
        response: Response object to delete the cookie on.

    Returns:
        Dict with message confirming logout.
    """
    clear_auth_cookie(response)
    return {"message": "Logged out"}


# ---------------------------------------------------------------------------
# SSO detect
# ---------------------------------------------------------------------------


@router.post("/sso/detect")
async def detect_idp(request: Request):
    """Detect whether an email address belongs to an SSO-enabled organization.

    Args:
        request: Request with JSON body containing 'email'.

    Returns:
        Dict with sso (bool), and if true: org_id, org_name, protocol.
    """
    body = await request.json()
    email = body.get("email", "").strip().lower()
    if not email or "@" not in email:
        return {"sso": False}
    org, sso_config = await detect_org_by_email_domain(email)
    if org is None or sso_config is None:
        return {"sso": False}
    return {
        "sso": True,
        "org_id": str(org.id),
        "org_name": org.name,
        "protocol": sso_config.protocol.value,
    }


# ---------------------------------------------------------------------------
# SAML SSO
# ---------------------------------------------------------------------------


@router.get("/sso/saml/login/{org_id}")
async def saml_login(org_id: str, request: Request):
    """Redirect the user to the SAML Identity Provider for authentication.

    Args:
        org_id: The organization ID to authenticate against.
        request: The incoming request (for building SP URLs).

    Returns:
        RedirectResponse to the IdP's SSO URL.
    """
    from app.auth.sso_saml import create_saml_auth_request

    sso_config = await _get_enabled_sso_config(org_id)
    if sso_config is None:
        return _error_redirect("sso_not_configured")

    base_url = str(request.base_url).rstrip("/")
    redirect_url = await create_saml_auth_request(sso_config, base_url, relay_state=org_id)
    return RedirectResponse(url=redirect_url)


@router.post("/sso/saml/callback")
async def saml_callback(request: Request):
    """SAML Assertion Consumer Service (ACS) endpoint.

    Validates the SAML response, finds/creates the user, and sets a JWT cookie.

    Args:
        request: POST request with SAMLResponse form field.

    Returns:
        RedirectResponse to frontend with JWT cookie set.
    """
    from app.auth.sso_saml import process_saml_response

    form = await request.form()
    saml_response = form.get("SAMLResponse")
    relay_state = form.get("RelayState", "")
    if not saml_response:
        return _error_redirect("saml_missing_response")

    org_id = relay_state if relay_state else None
    if not org_id:
        return _error_redirect("saml_missing_org")

    sso_config = await _get_enabled_sso_config(org_id)
    if sso_config is None:
        return _error_redirect("sso_not_configured")

    try:
        base_url = str(request.base_url).rstrip("/")
        result = await process_saml_response(sso_config, base_url, {"SAMLResponse": saml_response})
    except ValueError:
        logger.warning("SAML validation failed for org %s", org_id, exc_info=True)
        return _error_redirect("saml_invalid")

    from app.models.organization import Organization

    org = await Organization.get(org_id)
    if org is None:
        return _error_redirect("org_not_found")

    user = await find_or_create_sso_user(result, org, SSOProtocol.SAML)
    access_token = create_access_token(str(user.id))

    response = RedirectResponse(url=settings.frontend_url, status_code=302)
    set_auth_cookie(response, access_token)
    return response


# ---------------------------------------------------------------------------
# OIDC SSO
# ---------------------------------------------------------------------------


@router.get("/sso/oidc/login/{org_id}")
async def oidc_login(org_id: str, request: Request):
    """Redirect the user to the OIDC Identity Provider for authentication.

    Args:
        org_id: The organization ID to authenticate against.
        request: The incoming request.

    Returns:
        RedirectResponse to the IdP's authorization URL.
    """
    from app.auth.sso_oidc import initiate_oidc_login

    sso_config = await _get_enabled_sso_config(org_id)
    if sso_config is None:
        return _error_redirect("sso_not_configured")

    base_url = str(request.base_url).rstrip("/")
    callback_url = f"{base_url}/api/auth/sso/oidc/callback"
    state = f"{org_id}:{secrets.token_urlsafe(16)}"
    request.session["oidc_state"] = state

    try:
        redirect_url = await initiate_oidc_login(sso_config, callback_url, state)
    except ValueError:
        logger.warning("OIDC login init failed for org %s", org_id, exc_info=True)
        return _error_redirect("oidc_config_error")

    return RedirectResponse(url=redirect_url)


@router.get("/sso/oidc/callback")
async def oidc_callback(request: Request, code: str = Query(default=""), state: str = Query(default="")):
    """OIDC callback endpoint. Exchanges code for tokens, creates/finds user.

    Args:
        request: Incoming request with code and state query params.
        code: Authorization code from the IdP.
        state: State parameter for CSRF validation.

    Returns:
        RedirectResponse to frontend with JWT cookie set.
    """
    from app.auth.sso_oidc import process_oidc_callback

    if not code:
        return _error_redirect("oidc_missing_code")

    saved_state = request.session.get("oidc_state", "")
    if not state or state != saved_state:
        return _error_redirect("oidc_state_mismatch")

    org_id = state.split(":")[0] if ":" in state else ""
    if not org_id:
        return _error_redirect("oidc_missing_org")

    sso_config = await _get_enabled_sso_config(org_id)
    if sso_config is None:
        return _error_redirect("sso_not_configured")

    base_url = str(request.base_url).rstrip("/")
    callback_url = f"{base_url}/api/auth/sso/oidc/callback"

    try:
        result = await process_oidc_callback(sso_config, callback_url, code)
    except ValueError:
        logger.warning("OIDC callback failed for org %s", org_id, exc_info=True)
        return _error_redirect("oidc_failed")

    from app.models.organization import Organization

    org = await Organization.get(org_id)
    if org is None:
        return _error_redirect("org_not_found")

    user = await find_or_create_sso_user(result, org, SSOProtocol.OIDC)
    access_token = create_access_token(str(user.id))

    response = RedirectResponse(url=settings.frontend_url, status_code=302)
    set_auth_cookie(response, access_token)
    return response
