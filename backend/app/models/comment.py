"""Comment model for inline and document-level comments with reply threads.

Inline comments are anchored to text via three mechanisms:
- Yjs RelativePositions (anchor_from_relative/anchor_to_relative): CRDT-aware
  positions serialised as Base64 that survive concurrent edits.
- Absolute offsets (anchor_from/anchor_to): snapshot values periodically
  refreshed by the frontend; used as fallback for API-only consumers.
- Quoted text (quoted_text): immutable snapshot of the selected text at
  creation time; used for human-readable context and reconciliation.

When the anchored text is fully deleted the comment is marked orphaned
(is_orphaned=True) and remains visible in the global comments panel.
"""

from datetime import UTC, datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class Comment(Document):
    """A comment on a document. Can be inline (anchored to text) or doc-level.

    Inline comments carry anchor positions and quoted_text.
    Replies reference a parent_id (single-depth only).
    Orphaned comments have is_orphaned=True when their anchored text was deleted.
    """

    document_id: Indexed(str)
    author_id: str
    author_name: str
    author_avatar_url: Optional[str] = None
    content: str

    anchor_from: Optional[int] = None
    anchor_to: Optional[int] = None
    anchor_from_relative: Optional[str] = None
    anchor_to_relative: Optional[str] = None
    quoted_text: Optional[str] = None

    parent_id: Optional[str] = None

    is_resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

    is_orphaned: bool = False
    orphaned_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "comments"

    def resolve(self, user_id: str) -> None:
        """Mark the comment as resolved."""
        self.is_resolved = True
        self.resolved_by = user_id
        self.resolved_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def orphan(self) -> None:
        """Mark the comment as orphaned (anchored text was deleted)."""
        self.is_orphaned = True
        self.orphaned_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def reanchor(self, anchor_from: int, anchor_to: int) -> None:
        """Update absolute anchor offsets after the frontend re-resolves positions.

        Args:
            anchor_from: New start character offset.
            anchor_to: New end character offset.
        """
        self.anchor_from = anchor_from
        self.anchor_to = anchor_to
        self.updated_at = datetime.now(UTC)


class CommentCreate(BaseModel):
    """Payload for creating a new comment."""

    content: str = Field(..., max_length=50_000)
    anchor_from: Optional[int] = None
    anchor_to: Optional[int] = None
    anchor_from_relative: Optional[str] = None
    anchor_to_relative: Optional[str] = None
    quoted_text: Optional[str] = None


class CommentReanchor(BaseModel):
    """Payload for updating comment anchor positions after resolution."""

    anchor_from: int
    anchor_to: int


class ReplyCreate(BaseModel):
    """Payload for replying to a comment."""

    content: str = Field(..., max_length=50_000)


class CommentRead(BaseModel):
    """Public-facing comment representation with nested replies."""

    id: str
    document_id: str
    author_id: str
    author_name: str
    author_avatar_url: Optional[str] = None
    content: str
    anchor_from: Optional[int] = None
    anchor_to: Optional[int] = None
    anchor_from_relative: Optional[str] = None
    anchor_to_relative: Optional[str] = None
    quoted_text: Optional[str] = None
    parent_id: Optional[str] = None
    is_resolved: bool
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    is_orphaned: bool
    orphaned_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    replies: list["CommentRead"] = []

    @classmethod
    def from_doc(cls, comment: "Comment", replies: list["CommentRead"] | None = None) -> "CommentRead":
        """Build CommentRead from a Comment document.

        Args:
            comment: The Comment document.
            replies: Optional list of reply CommentRead items.
        """
        return cls(
            id=str(comment.id),
            document_id=comment.document_id,
            author_id=comment.author_id,
            author_name=comment.author_name,
            author_avatar_url=comment.author_avatar_url,
            content=comment.content,
            anchor_from=comment.anchor_from,
            anchor_to=comment.anchor_to,
            anchor_from_relative=comment.anchor_from_relative,
            anchor_to_relative=comment.anchor_to_relative,
            quoted_text=comment.quoted_text,
            parent_id=comment.parent_id,
            is_resolved=comment.is_resolved,
            resolved_by=comment.resolved_by,
            resolved_at=comment.resolved_at,
            is_orphaned=comment.is_orphaned,
            orphaned_at=comment.orphaned_at,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            replies=replies or [],
        )
