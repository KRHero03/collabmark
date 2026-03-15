"""NotificationDispatcher: schedules delayed notifications and delivers via channels.

Scheduling pushes a notification ID into a Redis sorted set keyed by delivery time.
The scheduler loop (notification_scheduler.py) pops due items, validates, and calls send().
"""

import json
import logging
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationEvent,
    NotificationPreference,
    NotificationStatus,
)
from app.services.channels.base import BaseChannel

logger = logging.getLogger(__name__)

REDIS_SCHEDULE_KEY = "collabmark:notifications:scheduled"

_dispatcher: "NotificationDispatcher | None" = None


def get_dispatcher() -> "NotificationDispatcher":
    """Return the global dispatcher instance. Must be initialized at startup."""
    if _dispatcher is None:
        raise RuntimeError("NotificationDispatcher not initialized")
    return _dispatcher


def set_dispatcher(d: "NotificationDispatcher") -> None:
    """Set the global dispatcher singleton (called during app lifespan)."""
    global _dispatcher
    _dispatcher = d


class NotificationDispatcher:
    """Schedules and delivers notifications through registered channels."""

    def __init__(self, redis_client=None):
        self._channels: dict[NotificationChannel, BaseChannel] = {}
        self._redis = redis_client

    def register_channel(self, channel: NotificationChannel, handler: BaseChannel) -> None:
        self._channels[channel] = handler

    async def schedule(
        self,
        *,
        event_type: NotificationEvent,
        recipients: list[dict],
        action_ref_id: str,
        payload: dict,
        document_id: str | None = None,
    ) -> list[Notification]:
        """Create Notification docs and schedule them for delayed delivery.

        Args:
            event_type: The notification event type.
            recipients: List of dicts with keys: user_id, email, name.
            action_ref_id: ID of the triggering action (comment_id or access_id)
                           used for pre-send validation.
            payload: Template rendering data (shared_by, document_title, etc.).
            document_id: The related document ID.

        Returns:
            List of created Notification documents.
        """
        if not settings.notifications_enabled:
            return []

        deliver_at = datetime.now(UTC) + timedelta(seconds=settings.notification_delay_seconds)
        created: list[Notification] = []

        for recipient in recipients:
            pref = await NotificationPreference.find_one(NotificationPreference.user_id == recipient["user_id"])
            if pref and not pref.is_enabled(event_type.value, NotificationChannel.EMAIL.value):
                continue

            notif = Notification(
                recipient_id=recipient["user_id"],
                recipient_email=recipient["email"],
                recipient_name=recipient["name"],
                event_type=event_type,
                channel=NotificationChannel.EMAIL,
                status=NotificationStatus.SCHEDULED,
                payload=payload,
                document_id=document_id,
                action_ref_id=action_ref_id,
                scheduled_for=deliver_at,
            )
            await notif.insert()
            created.append(notif)

            if self._redis:
                score = deliver_at.timestamp()
                value = json.dumps({"notification_id": str(notif.id)})
                await self._redis.zadd(REDIS_SCHEDULE_KEY, {value: score})
                logger.info(
                    "Scheduled %s notification %s for %s (deliver at %s)",
                    event_type.value,
                    notif.id,
                    recipient["email"],
                    deliver_at.isoformat(),
                )

        return created

    async def send(self, notification: Notification) -> bool:
        """Deliver a notification through its registered channel.

        Updates the notification status to sent/failed and records errors.
        Returns True on success.
        """
        handler = self._channels.get(notification.channel)
        if handler is None:
            logger.error("No handler for channel %s", notification.channel)
            notification.status = NotificationStatus.FAILED
            notification.error = f"No handler for channel {notification.channel.value}"
            await notification.save()
            return False

        ok = await handler.send(notification)
        now = datetime.now(UTC)

        if ok:
            notification.status = NotificationStatus.SENT
            notification.sent_at = now
            notification.error = None
        else:
            notification.status = NotificationStatus.FAILED
            notification.error = "Channel send returned False"
            notification.retry_count += 1

        await notification.save()
        return ok
