"""Document model and related Pydantic schemas for CRUD and API responses."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class GeneralAccess(str, Enum):
    """Controls who can access a document via its URL (Google Docs-style)."""

    RESTRICTED = "restricted"
    ANYONE_VIEW = "anyone_view"
    ANYONE_EDIT = "anyone_edit"


class Document_(Document):
    """A Markdown document owned by a user."""

    title: str = "Untitled"
    content: str = ""
    owner_id: Indexed(str)
    general_access: GeneralAccess = GeneralAccess.RESTRICTED
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "documents"

    def touch(self) -> None:
        """Update updated_at to the current UTC timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def soft_delete(self) -> None:
        """Mark document as deleted. Sets is_deleted and deleted_at."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.touch()

    def restore(self) -> None:
        """Restore a soft-deleted document."""
        self.is_deleted = False
        self.deleted_at = None
        self.touch()


class DocumentRead(BaseModel):
    """Public-facing document representation for API responses."""

    id: str
    title: str
    content: str
    owner_id: str
    owner_name: str = ""
    owner_email: str = ""
    general_access: GeneralAccess
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_doc(
        cls,
        doc: "Document_",
        *,
        owner_name: str = "",
        owner_email: str = "",
    ) -> "DocumentRead":
        """Build DocumentRead from a Document_ document.

        Args:
            doc: The Document_ instance.
            owner_name: The owner's display name (resolved externally).
            owner_email: The owner's email address (resolved externally).
        """
        return cls(
            id=str(doc.id),
            title=doc.title,
            content=doc.content,
            owner_id=doc.owner_id,
            owner_name=owner_name,
            owner_email=owner_email,
            general_access=doc.general_access,
            is_deleted=doc.is_deleted,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )


class DocumentCreate(BaseModel):
    """Payload for creating a new document. Title and content optional with defaults."""

    title: str = "Untitled"
    content: str = ""


class DocumentUpdate(BaseModel):
    """Payload for updating a document. All fields optional."""

    title: Optional[str] = None
    content: Optional[str] = None
