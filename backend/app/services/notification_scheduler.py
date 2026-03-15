"""Notification scheduler: polls Redis for due notifications, validates, and dispatches.

Runs as an asyncio background task. Every poll cycle it pops scheduled notifications
whose delivery time has arrived, validates that the triggering action still exists
(comment not deleted, access not revoked), and either dispatches or skips.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime

from beanie import PydanticObjectId
from bson.errors import InvalidId

from app.models.comment import Comment
from app.models.notification import (
    Notification,
    NotificationEvent,
    NotificationStatus,
)
from app.models.share_link import DocumentAccess
from app.services.notification_dispatcher import REDIS_SCHEDULE_KEY, NotificationDispatcher

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 10


async def _validate_action_exists(notification: Notification) -> bool:
    """Check that the action which triggered this notification still exists."""
    ref_id = notification.action_ref_id
    if not ref_id:
        return True

    try:
        oid = PydanticObjectId(ref_id)
    except (InvalidId, ValueError):
        logger.warning("Invalid action_ref_id %s", ref_id)
        return False

    if notification.event_type == NotificationEvent.COMMENT_ADDED:
        comment = await Comment.get(oid)
        return comment is not None

    if notification.event_type == NotificationEvent.DOCUMENT_SHARED:
        access = await DocumentAccess.get(oid)
        return access is not None

    return True


async def scheduler_loop(redis_client, dispatcher: NotificationDispatcher) -> None:
    """Long-running loop that processes due scheduled notifications."""
    logger.info("Notification scheduler started (poll every %ds)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await _process_due_notifications(redis_client, dispatcher)
        except asyncio.CancelledError:
            logger.info("Notification scheduler cancelled")
            break
        except Exception:
            logger.exception("Scheduler loop error")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _process_due_notifications(redis_client, dispatcher: NotificationDispatcher) -> None:
    """Pop all due items from the Redis ZSET and process them."""
    now = datetime.now(UTC).timestamp()
    items = await redis_client.zrangebyscore(REDIS_SCHEDULE_KEY, "-inf", now)
    if not items:
        return

    await redis_client.zremrangebyscore(REDIS_SCHEDULE_KEY, "-inf", now)

    for raw in items:
        try:
            data = json.loads(raw)
            notif_id = data["notification_id"]
        except (json.JSONDecodeError, KeyError):
            logger.error("Malformed scheduled notification entry: %s", raw)
            continue

        try:
            oid = PydanticObjectId(notif_id)
        except (InvalidId, ValueError):
            logger.error("Invalid notification_id in schedule: %s", notif_id)
            continue

        notification = await Notification.get(oid)
        if notification is None:
            logger.warning("Notification %s not found, skipping", notif_id)
            continue

        if notification.status != NotificationStatus.SCHEDULED:
            continue

        action_valid = await _validate_action_exists(notification)
        if not action_valid:
            notification.status = NotificationStatus.SKIPPED
            notification.error = "Action was reverted before delivery"
            await notification.save()
            logger.info(
                "Skipped notification %s — %s action %s no longer exists",
                notif_id,
                notification.event_type.value,
                notification.action_ref_id,
            )
            continue

        notification.status = NotificationStatus.PENDING
        await notification.save()
        await dispatcher.send(notification)
