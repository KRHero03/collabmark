"""Notification and preference models for the channel-agnostic notification system.

Supports delayed dispatch with action validation. Each Notification tracks its
lifecycle from scheduled -> sent/skipped/failed, with retry support.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field


class NotificationEvent(str, Enum):
    """Types of events that trigger notifications."""

    DOCUMENT_SHARED = "document_shared"
    COMMENT_ADDED = "comment_added"


class NotificationChannel(str, Enum):
    """Delivery channels for notifications."""

    EMAIL = "email"
    IN_APP = "in_app"
    PUSH = "push"


class NotificationStatus(str, Enum):
    """Lifecycle states of a notification."""

    SCHEDULED = "scheduled"
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class Notification(Document):
    """A notification queued for delivery. Tracks scheduling, validation, and send status."""

    recipient_id: Indexed(str)
    recipient_email: str = ""
    recipient_name: str = ""

    event_type: NotificationEvent
    channel: NotificationChannel = NotificationChannel.EMAIL
    status: NotificationStatus = NotificationStatus.SCHEDULED

    payload: dict = Field(default_factory=dict)

    document_id: Optional[str] = None
    action_ref_id: Optional[str] = None

    scheduled_for: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sent_at: Optional[datetime] = None

    error: Optional[str] = None
    retry_count: int = 0

    class Settings:
        name = "notifications"


class NotificationPreference(Document):
    """Per-user notification preferences. Controls which event/channel combos are enabled."""

    user_id: Indexed(str, unique=True)
    preferences: dict = Field(
        default_factory=lambda: {
            "document_shared": {"email": True},
            "comment_added": {"email": True},
        }
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "notification_preferences"

    def is_enabled(self, event_type: str, channel: str) -> bool:
        """Check if a specific event/channel combo is enabled for this user."""
        event_prefs = self.preferences.get(event_type, {})
        return event_prefs.get(channel, True)


class NotificationRead(BaseModel):
    """Public-facing notification representation for API responses."""

    id: str
    event_type: NotificationEvent
    channel: NotificationChannel
    status: NotificationStatus
    payload: dict
    document_id: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None

    @classmethod
    def from_doc(cls, notif: "Notification") -> "NotificationRead":
        return cls(
            id=str(notif.id),
            event_type=notif.event_type,
            channel=notif.channel,
            status=notif.status,
            payload=notif.payload,
            document_id=notif.document_id,
            created_at=notif.created_at,
            sent_at=notif.sent_at,
        )


class PreferenceUpdate(BaseModel):
    """Payload for updating notification preferences."""

    preferences: dict
