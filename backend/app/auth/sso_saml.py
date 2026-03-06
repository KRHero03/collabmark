"""SAML 2.0 Service Provider helpers for SSO authentication.

Uses python3-saml (OneLogin) to build AuthnRequests and validate
SAML Responses from the Identity Provider.
"""

from typing import Any

from app.auth.sso_common import SSOCallbackResult
from app.models.org_sso_config import OrgSSOConfig

try:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
except ImportError:  # pragma: no cover
    OneLogin_Saml2_Auth = None  # type: ignore[assignment,misc]


def build_saml_settings(config: OrgSSOConfig, request_url: str) -> dict[str, Any]:
    """Construct python3-saml settings dict from OrgSSOConfig.

    Args:
        config: The organization's SSO configuration document.
        request_url: The base URL of the incoming request (used for SP URLs).

    Returns:
        Settings dict consumable by OneLoginSaml2Auth.
    """
    return {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": config.sp_entity_id or f"{request_url}/api/auth/sso/saml/metadata",
            "assertionConsumerService": {
                "url": config.sp_acs_url or f"{request_url}/api/auth/sso/saml/callback",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
        },
        "idp": {
            "entityId": config.idp_entity_id or "",
            "singleSignOnService": {
                "url": config.idp_sso_url or "",
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": config.idp_certificate or "",
        },
    }


def prepare_saml_request(request_data: dict) -> dict:
    """Prepare the request dict expected by python3-saml from a FastAPI Request.

    Args:
        request_data: Dict with keys: http_host, script_name, server_port,
                      get_data, post_data, https.

    Returns:
        Dict formatted for OneLoginSaml2Auth initialization.
    """
    return {
        "http_host": request_data.get("http_host", ""),
        "script_name": request_data.get("script_name", ""),
        "server_port": request_data.get("server_port", 443),
        "get_data": request_data.get("get_data", {}),
        "post_data": request_data.get("post_data", {}),
        "https": request_data.get("https", "on"),
    }


async def create_saml_auth_request(config: OrgSSOConfig, request_url: str, relay_state: str = "") -> str:
    """Generate a SAML AuthnRequest redirect URL.

    Args:
        config: The organization's SSO config.
        request_url: Base URL of the request.
        relay_state: Optional relay state to pass through.

    Returns:
        The IdP redirect URL with the encoded AuthnRequest.
    """
    saml_settings = build_saml_settings(config, request_url)
    req = prepare_saml_request(
        {
            "http_host": request_url.split("://")[-1].split("/")[0],
            "script_name": "",
            "server_port": 443 if request_url.startswith("https") else 80,
            "get_data": {},
            "post_data": {},
            "https": "on" if request_url.startswith("https") else "off",
        }
    )
    auth = OneLogin_Saml2_Auth(req, saml_settings)
    return auth.login(relay_state)


async def process_saml_response(
    config: OrgSSOConfig,
    request_url: str,
    post_data: dict,
) -> SSOCallbackResult:
    """Validate a SAML Response and extract user attributes.

    Args:
        config: The organization's SSO config.
        request_url: Base URL of the request.
        post_data: POST form data containing SAMLResponse.

    Returns:
        SSOCallbackResult with the user's email, name, and avatar_url.

    Raises:
        ValueError: If the SAML response is invalid or has errors.
    """
    saml_settings = build_saml_settings(config, request_url)
    req = prepare_saml_request(
        {
            "http_host": request_url.split("://")[-1].split("/")[0],
            "script_name": "",
            "server_port": 443 if request_url.startswith("https") else 80,
            "get_data": {},
            "post_data": post_data,
            "https": "on" if request_url.startswith("https") else "off",
        }
    )
    auth = OneLogin_Saml2_Auth(req, saml_settings)
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        raise ValueError(f"SAML validation failed: {', '.join(errors)}")

    attrs = auth.get_attributes()
    name_id = auth.get_nameid()

    email = (
        attrs.get("email", [None])[0]
        or attrs.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress", [None])[0]
        or name_id
    )
    name = (
        attrs.get("displayName", [None])[0]
        or attrs.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name", [None])[0]
        or email
    )
    avatar = attrs.get("picture", [None])[0]

    if not email:
        raise ValueError("SAML response missing email")

    return SSOCallbackResult(email=email, name=name, avatar_url=avatar)
