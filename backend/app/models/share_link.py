"""Share link and document access models for sharing and permissions."""

import secrets
from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class Permission(str, Enum):
    """Permission level for shared documents: view or edit."""

    VIEW = "view"
    EDIT = "edit"


class ShareLink(Document):
    """Beanie document for a shareable link. Key fields: document_id, token, permission."""

    document_id: Indexed(str)
    token: Indexed(str, unique=True)
    permission: Permission = Permission.VIEW
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: Optional[datetime] = None

    class Settings:
        name = "share_links"

    @staticmethod
    def generate_token() -> str:
        """Generate a URL-safe random token for the share link."""
        return secrets.token_urlsafe(24)


class DocumentAccess(Document):
    """Tracks which users have accessed which documents (powers 'Shared with me')."""

    document_id: Indexed(str)
    user_id: Indexed(str)
    permission: Permission = Permission.VIEW
    granted_by: str
    granted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "document_access"

    def touch_access(self) -> None:
        """Update last_accessed_at to the current UTC timestamp."""
        self.last_accessed_at = datetime.now(UTC)


class ShareLinkRead(BaseModel):
    """Public-facing share link representation (legacy)."""

    id: str
    document_id: str
    token: str
    permission: Permission
    created_by: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    url: str = ""

    @classmethod
    def from_doc(cls, link: "ShareLink", base_url: str = "") -> "ShareLinkRead":
        """Build ShareLinkRead from a ShareLink document."""
        return cls(
            id=str(link.id),
            document_id=link.document_id,
            token=link.token,
            permission=link.permission,
            created_by=link.created_by,
            created_at=link.created_at,
            expires_at=link.expires_at,
            url=f"{base_url}/share/{link.token}" if base_url else f"/share/{link.token}",
        )


class SharedDocumentRead(BaseModel):
    """A document shared with the user, including permission and access time."""

    id: str
    title: str
    content: str
    owner_id: str
    permission: Permission
    last_accessed_at: datetime
    created_at: datetime
    updated_at: datetime


class GeneralAccessUpdate(BaseModel):
    """Payload for updating a document's general access level."""

    general_access: str  # Validated as GeneralAccess enum at service layer


class CollaboratorAdd(BaseModel):
    """Payload for adding a collaborator by email."""

    email: str
    permission: Permission = Permission.VIEW


class CollaboratorRead(BaseModel):
    """A collaborator's access info, including user details.

    Returned when listing document or folder collaborators. Includes the
    collaborator's user info (id, user_id, email, name, avatar_url),
    permission level, and when access was granted.
    """

    id: str
    user_id: str
    email: str
    name: str
    avatar_url: Optional[str] = None
    permission: Permission
    granted_at: datetime
