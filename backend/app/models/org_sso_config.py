"""SSO configuration model for organizations.

Stores per-organization SAML 2.0 or OIDC identity provider settings.
Only one SSO config per organization (org_id is unique-indexed).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class SSOProtocol(str, Enum):
    """Supported SSO protocol types."""

    SAML = "saml"
    OIDC = "oidc"


class OrgSSOConfig(Document):
    """Per-organization SSO configuration.

    Stores either SAML or OIDC provider details depending on the chosen
    protocol.  Only enabled configs are used during login detection.
    """

    org_id: Indexed(str, unique=True)
    protocol: SSOProtocol = SSOProtocol.OIDC
    enabled: bool = False

    # SAML fields
    idp_entity_id: Optional[str] = None
    idp_sso_url: Optional[str] = None
    idp_certificate: Optional[str] = None
    sp_entity_id: Optional[str] = None
    sp_acs_url: Optional[str] = None

    # OIDC fields
    oidc_discovery_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None

    # SCIM (Phase 5 — fields defined now, unused until then)
    scim_enabled: bool = False
    scim_bearer_token: Optional[str] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "org_sso_configs"

    def touch(self) -> None:
        """Update updated_at to the current UTC timestamp."""
        self.updated_at = datetime.now(timezone.utc)


class OrgSSOConfigRead(BaseModel):
    """Public-facing SSO config (secrets redacted)."""

    id: str
    org_id: str
    protocol: SSOProtocol
    enabled: bool
    idp_entity_id: Optional[str] = None
    idp_sso_url: Optional[str] = None
    sp_entity_id: Optional[str] = None
    sp_acs_url: Optional[str] = None
    oidc_discovery_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    scim_enabled: bool = False
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, cfg: OrgSSOConfig) -> "OrgSSOConfigRead":
        return cls(
            id=str(cfg.id),
            org_id=cfg.org_id,
            protocol=cfg.protocol,
            enabled=cfg.enabled,
            idp_entity_id=cfg.idp_entity_id,
            idp_sso_url=cfg.idp_sso_url,
            sp_entity_id=cfg.sp_entity_id,
            sp_acs_url=cfg.sp_acs_url,
            oidc_discovery_url=cfg.oidc_discovery_url,
            oidc_client_id=cfg.oidc_client_id,
            scim_enabled=cfg.scim_enabled,
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )


class OrgSSOConfigUpdate(BaseModel):
    """Payload for updating SSO configuration. All fields optional."""

    protocol: Optional[SSOProtocol] = None
    enabled: Optional[bool] = None
    idp_entity_id: Optional[str] = None
    idp_sso_url: Optional[str] = None
    idp_certificate: Optional[str] = None
    sp_entity_id: Optional[str] = None
    sp_acs_url: Optional[str] = None
    oidc_discovery_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
