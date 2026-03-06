"""OpenID Connect Relying Party helpers for SSO authentication.

Uses authlib to handle OIDC discovery, authorization, and token exchange
with the organization's Identity Provider.
"""

from typing import Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.auth.sso_common import SSOCallbackResult
from app.models.org_sso_config import OrgSSOConfig


def create_oidc_client(config: OrgSSOConfig) -> AsyncOAuth2Client:
    """Build an authlib async OAuth2 client from OrgSSOConfig.

    Args:
        config: The organization's SSO configuration with OIDC fields.

    Returns:
        Configured AsyncOAuth2Client ready for authorization.
    """
    return AsyncOAuth2Client(
        client_id=config.oidc_client_id or "",
        client_secret=config.oidc_client_secret or "",
        scope="openid email profile",
    )


async def get_oidc_discovery(config: OrgSSOConfig) -> dict[str, Any]:
    """Fetch the OIDC discovery document (.well-known/openid-configuration).

    Args:
        config: The organization's SSO config with oidc_discovery_url.

    Returns:
        The parsed discovery JSON.

    Raises:
        ValueError: If discovery URL is not configured or fetch fails.
    """
    if not config.oidc_discovery_url:
        raise ValueError("OIDC discovery URL not configured")
    async with httpx.AsyncClient() as client:
        resp = await client.get(config.oidc_discovery_url)
        resp.raise_for_status()
        return resp.json()


async def initiate_oidc_login(config: OrgSSOConfig, callback_url: str, state: str) -> str:
    """Generate the OIDC authorization URL to redirect the user to the IdP.

    Args:
        config: The organization's SSO config.
        callback_url: The OIDC callback URL (our RP endpoint).
        state: An opaque state string for CSRF protection.

    Returns:
        The IdP authorization URL to redirect the user to.

    Raises:
        ValueError: If discovery fails or authorization endpoint missing.
    """
    discovery = await get_oidc_discovery(config)
    authorization_endpoint = discovery.get("authorization_endpoint")
    if not authorization_endpoint:
        raise ValueError("No authorization_endpoint in discovery")

    client = create_oidc_client(config)
    url, _ = client.create_authorization_url(
        authorization_endpoint,
        redirect_uri=callback_url,
        state=state,
    )
    return url


async def process_oidc_callback(
    config: OrgSSOConfig,
    callback_url: str,
    code: str,
) -> SSOCallbackResult:
    """Exchange the authorization code for tokens and extract user info.

    Args:
        config: The organization's SSO config.
        callback_url: The callback URL used in the authorization request.
        code: The authorization code from the IdP callback.

    Returns:
        SSOCallbackResult with the user's email, name, and avatar.

    Raises:
        ValueError: If token exchange or userinfo retrieval fails.
    """
    discovery = await get_oidc_discovery(config)
    token_endpoint = discovery.get("token_endpoint")
    userinfo_endpoint = discovery.get("userinfo_endpoint")
    if not token_endpoint:
        raise ValueError("No token_endpoint in discovery")

    client = create_oidc_client(config)
    token = await client.fetch_token(
        token_endpoint,
        code=code,
        redirect_uri=callback_url,
    )

    if not token or "access_token" not in token:
        raise ValueError("Failed to obtain access token")

    if userinfo_endpoint:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                userinfo_endpoint,
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
            resp.raise_for_status()
            userinfo = resp.json()
    else:
        userinfo = token.get("userinfo", {})

    email = userinfo.get("email")
    if not email:
        raise ValueError("OIDC response missing email claim")

    name = userinfo.get("name") or userinfo.get("preferred_username") or email
    avatar = userinfo.get("picture")

    return SSOCallbackResult(email=email, name=name, avatar_url=avatar)
