"""Organization and membership models for multi-tenant support.

Organizations group users under a single tenant. Each org has verified email
domains used for SSO routing and membership rules.  OrgMembership links users
to their organization with a role (admin or member).
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class OrgRole(str, Enum):
    """Role a user can hold within an organization."""

    ADMIN = "admin"
    MEMBER = "member"


class Organization(Document):
    """A tenant organization.  Owns verified domains and groups users."""

    name: str
    slug: Indexed(str, unique=True)
    verified_domains: list[str] = Field(default_factory=list)
    plan: str = "free"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "organizations"

    def touch(self) -> None:
        """Update updated_at to the current UTC timestamp."""
        self.updated_at = datetime.now(UTC)


class OrgMembership(Document):
    """Links a user to an organization with a specific role.

    Compound uniqueness on (org_id, user_id) enforced at application level.
    """

    org_id: Indexed(str)
    user_id: Indexed(str)
    role: OrgRole = OrgRole.MEMBER
    joined_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "org_memberships"


class OrganizationRead(BaseModel):
    """Public-facing organization representation for API responses."""

    id: str
    name: str
    slug: str
    verified_domains: list[str]
    plan: str
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, org: Organization, *, member_count: int = 0) -> "OrganizationRead":
        """Build OrganizationRead from an Organization document with optional member count."""
        return cls(
            id=str(org.id),
            name=org.name,
            slug=org.slug,
            verified_domains=org.verified_domains,
            plan=org.plan,
            member_count=member_count,
            created_at=org.created_at,
            updated_at=org.updated_at,
        )


class OrgMemberRead(BaseModel):
    """A member entry in an organization."""

    id: str
    user_id: str
    user_name: str
    user_email: str
    avatar_url: Optional[str] = None
    role: OrgRole
    joined_at: datetime


class OrganizationCreate(BaseModel):
    """Payload for creating a new organization."""

    name: str
    slug: str
    verified_domains: list[str] = Field(default_factory=list)
    plan: str = "free"


class OrganizationUpdate(BaseModel):
    """Payload for updating an organization. All fields optional."""

    name: Optional[str] = None
    slug: Optional[str] = None
    verified_domains: Optional[list[str]] = None
    plan: Optional[str] = None


class AddMemberPayload(BaseModel):
    """Payload for adding a member to an organization."""

    user_id: str
    role: OrgRole = OrgRole.MEMBER
