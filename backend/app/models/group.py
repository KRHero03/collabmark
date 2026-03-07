"""Group models for organization-scoped groups and group-based access control.

Groups are synced from an Identity Provider via SCIM and can be used
to share documents/folders with all members of a group.
"""

from datetime import UTC, datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field

from app.models.share_link import Permission


class Group(Document):
    """A group within an organization, typically synced from an IdP via SCIM."""

    name: str
    org_id: Indexed(str)
    external_id: Optional[str] = None
    scim_synced: bool = False
    scim_members: Optional[list] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "groups"

    def touch(self) -> None:
        """Update updated_at to the current UTC timestamp."""
        self.updated_at = datetime.now(UTC)


class GroupMembership(Document):
    """Links a user to a group. Compound uniqueness on (group_id, user_id) enforced at app level."""

    group_id: Indexed(str)
    user_id: Indexed(str)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "group_memberships"


class DocumentGroupAccess(Document):
    """Grants a group access to a document with a specific permission level.

    A group can only have ONE permission level per document.
    """

    document_id: Indexed(str)
    group_id: Indexed(str)
    permission: Permission = Permission.VIEW
    granted_by: str
    granted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "document_group_access"


class FolderGroupAccess(Document):
    """Grants a group access to a folder with a specific permission level.

    A group can only have ONE permission level per folder.
    """

    folder_id: Indexed(str)
    group_id: Indexed(str)
    permission: Permission = Permission.VIEW
    granted_by: str
    granted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "folder_group_access"


class GroupRead(BaseModel):
    """Public-facing group representation for API responses."""

    id: str
    name: str
    org_id: str
    member_count: int = 0
    scim_synced: bool = False
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(cls, group: "Group", *, member_count: int = 0) -> "GroupRead":
        """Build GroupRead from a Group document."""
        return cls(
            id=str(group.id),
            name=group.name,
            org_id=group.org_id,
            member_count=member_count,
            scim_synced=group.scim_synced,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )


class GroupCollaboratorRead(BaseModel):
    """A group collaborator entry for documents or folders."""

    id: str
    group_id: str
    group_name: str
    permission: Permission
    granted_at: datetime


class AddGroupCollaboratorPayload(BaseModel):
    """Payload for adding a group collaborator."""

    group_id: str
    permission: Permission = Permission.VIEW
