"""SCIM 2.0 bearer token authentication dependency.

Enterprise IdPs authenticate SCIM requests with a per-organization bearer
token.  The token is hashed (SHA-256) before storage so that the plaintext
is never persisted.  On each request the incoming token is hashed and matched
against ``OrgSSOConfig.scim_bearer_token``.
"""

import hashlib

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, Request, status

from app.models.org_sso_config import OrgSSOConfig
from app.models.organization import Organization


def hash_scim_token(token: str) -> str:
    """Return the SHA-256 hex digest of a SCIM bearer token.

    Args:
        token: The plaintext bearer token.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    return hashlib.sha256(token.encode()).hexdigest()


async def get_scim_org(request: Request) -> tuple[Organization, OrgSSOConfig]:
    """FastAPI dependency that authenticates a SCIM request via bearer token.

    Extracts the ``Authorization: Bearer <token>`` header, hashes the token,
    and looks up the matching ``OrgSSOConfig`` with ``scim_enabled=True``.

    Args:
        request: The incoming HTTP request.

    Returns:
        A tuple of (Organization, OrgSSOConfig) for the authenticated org.

    Raises:
        HTTPException: 401 if the token is missing or invalid.
        HTTPException: 403 if SCIM is disabled for the matched org.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )

    token = auth_header[len("Bearer ") :]
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is empty",
        )

    token_hash = hash_scim_token(token)

    cfg = await OrgSSOConfig.find_one(OrgSSOConfig.scim_bearer_token == token_hash)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid SCIM bearer token",
        )

    if not cfg.scim_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SCIM provisioning is disabled for this organization",
        )

    try:
        org = await Organization.get(PydanticObjectId(cfg.org_id))
    except (InvalidId, ValueError):
        org = None

    if org is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Organization not found for SCIM token",
        )

    return org, cfg
