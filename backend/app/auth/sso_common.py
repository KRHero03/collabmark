"""Shared SSO authentication utilities.

Provides a common data structure for SSO callback results and a
find-or-create function that works identically for SAML and OIDC flows.
"""

from dataclasses import dataclass
from typing import Optional

from app.models.organization import Organization, OrgMembership, OrgRole
from app.models.org_sso_config import OrgSSOConfig, SSOProtocol
from app.models.user import User


@dataclass
class SSOCallbackResult:
    """Normalized result from an SSO callback (SAML or OIDC)."""

    email: str
    name: str
    avatar_url: Optional[str] = None


async def detect_org_by_email_domain(email: str) -> tuple[Organization | None, OrgSSOConfig | None]:
    """Look up an organization and its SSO config by the email domain.

    Args:
        email: User email address (e.g. "alice@acme.com").

    Returns:
        Tuple of (Organization, OrgSSOConfig) if a matching enabled SSO
        config is found, otherwise (None, None).
    """
    domain = email.rsplit("@", 1)[-1].lower()
    org = await Organization.find_one({"verified_domains": domain})
    if org is None:
        return None, None
    sso_config = await OrgSSOConfig.find_one(
        OrgSSOConfig.org_id == str(org.id),
        OrgSSOConfig.enabled == True,
    )
    if sso_config is None:
        return None, None
    return org, sso_config


async def find_or_create_sso_user(
    result: SSOCallbackResult,
    org: Organization,
    protocol: SSOProtocol,
) -> User:
    """Find an existing user by email or create a new one for SSO login.

    If the user already exists, update their name, avatar, org_id, and
    auth_provider. If new, create the user and add an OrgMembership.

    Args:
        result: Normalized SSO callback result with email, name, avatar.
        org: The organization the user belongs to.
        protocol: The SSO protocol used (saml or oidc).

    Returns:
        The found or newly created User document.
    """
    user = await User.find_one(User.email == result.email)
    if user is not None:
        user.name = result.name or user.name
        if result.avatar_url:
            user.avatar_url = result.avatar_url
        user.org_id = str(org.id)
        user.auth_provider = protocol.value
        user.touch()
        await user.save()
    else:
        user = User(
            email=result.email,
            name=result.name or result.email,
            avatar_url=result.avatar_url,
            org_id=str(org.id),
            auth_provider=protocol.value,
        )
        await user.insert()
        # Add membership if not already a member
        existing = await OrgMembership.find_one(
            OrgMembership.org_id == str(org.id),
            OrgMembership.user_id == str(user.id),
        )
        if existing is None:
            membership = OrgMembership(
                org_id=str(org.id),
                user_id=str(user.id),
                role=OrgRole.MEMBER,
            )
            await membership.insert()
    return user
