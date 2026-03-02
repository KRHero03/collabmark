"""Model for tracking document views, powering the 'Recently Viewed' tab."""

from datetime import datetime, timezone

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class DocumentView(Document):
    """Records when a user views a document they don't own.

    One record per (user_id, document_id) pair. The viewed_at timestamp
    is updated on each subsequent view to keep the list sorted by recency.
    """

    user_id: Indexed(str)
    document_id: Indexed(str)
    viewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "document_views"


class RecentlyViewedRead(BaseModel):
    """A recently viewed document for API responses."""

    id: str
    title: str
    owner_id: str
    owner_name: str
    owner_email: str
    permission: str
    viewed_at: datetime
    created_at: datetime
    updated_at: datetime
