"""Document version model for storing CRDT snapshots with author attribution."""

from datetime import UTC, datetime

from beanie import Document, Indexed
from pydantic import BaseModel, Field
from pymongo import ASCENDING, IndexModel


class DocumentVersion(Document):
    """Immutable snapshot of a document at a point in time.

    Stores the full Markdown content (reconstructed from CRDT state)
    along with author metadata for the version history timeline.
    """

    document_id: Indexed(str)
    version_number: int
    content: str
    author_id: str
    author_name: str
    summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "document_versions"
        indexes = [
            IndexModel(
                [("document_id", ASCENDING), ("version_number", ASCENDING)],
                unique=True,
            ),
        ]


class DocumentVersionRead(BaseModel):
    """Public-facing version representation for API responses."""

    id: str
    document_id: str
    version_number: int
    content: str
    author_id: str
    author_name: str
    summary: str
    created_at: datetime

    @classmethod
    def from_doc(cls, ver: DocumentVersion) -> "DocumentVersionRead":
        """Build DocumentVersionRead from a DocumentVersion document."""
        return cls(
            id=str(ver.id),
            document_id=ver.document_id,
            version_number=ver.version_number,
            content=ver.content,
            author_id=ver.author_id,
            author_name=ver.author_name,
            summary=ver.summary,
            created_at=ver.created_at,
        )


class DocumentVersionListItem(BaseModel):
    """Lightweight version item for the timeline list (excludes content)."""

    id: str
    version_number: int
    author_id: str
    author_name: str
    summary: str
    created_at: datetime

    @classmethod
    def from_doc(cls, ver: DocumentVersion) -> "DocumentVersionListItem":
        """Build DocumentVersionListItem from a DocumentVersion document."""
        return cls(
            id=str(ver.id),
            version_number=ver.version_number,
            author_id=ver.author_id,
            author_name=ver.author_name,
            summary=ver.summary,
            created_at=ver.created_at,
        )
