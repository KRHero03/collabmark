"""Redis-based retry queue for failed notification sends.

Failed notifications are pushed to a Redis list. A background poller pops items,
re-attempts delivery with exponential backoff, and gives up after max retries.
"""

import asyncio
import json
import logging

from beanie import PydanticObjectId
from bson.errors import InvalidId

from app.models.notification import Notification, NotificationStatus
from app.services.notification_dispatcher import NotificationDispatcher

logger = logging.getLogger(__name__)

REDIS_RETRY_KEY = "collabmark:notifications:retry"
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 30
POLL_INTERVAL_SECONDS = 15


async def push_to_retry(redis_client, notification_id: str) -> None:
    """Push a failed notification ID onto the retry queue."""
    await redis_client.rpush(REDIS_RETRY_KEY, json.dumps({"notification_id": notification_id}))
    logger.info("Pushed notification %s to retry queue", notification_id)


async def retry_loop(redis_client, dispatcher: NotificationDispatcher) -> None:
    """Long-running loop that processes the retry queue."""
    logger.info("Notification retry worker started (poll every %ds)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await _process_retry_queue(redis_client, dispatcher)
        except asyncio.CancelledError:
            logger.info("Notification retry worker cancelled")
            break
        except Exception:
            logger.exception("Retry loop error")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def _process_retry_queue(redis_client, dispatcher: NotificationDispatcher) -> None:
    """Pop one item at a time from the retry list and re-attempt."""
    raw = await redis_client.lpop(REDIS_RETRY_KEY)
    if raw is None:
        return

    try:
        data = json.loads(raw)
        notif_id = data["notification_id"]
    except (json.JSONDecodeError, KeyError):
        logger.error("Malformed retry queue entry: %s", raw)
        return

    try:
        oid = PydanticObjectId(notif_id)
    except (InvalidId, ValueError):
        logger.error("Invalid notification_id in retry: %s", notif_id)
        return

    notification = await Notification.get(oid)
    if notification is None:
        logger.warning("Notification %s not found for retry", notif_id)
        return

    if notification.retry_count >= MAX_RETRIES:
        notification.status = NotificationStatus.FAILED
        notification.error = f"Exhausted {MAX_RETRIES} retries"
        await notification.save()
        logger.warning("Notification %s exceeded max retries, giving up", notif_id)
        return

    backoff = BASE_BACKOFF_SECONDS * (2**notification.retry_count)
    logger.info("Retrying notification %s (attempt %d, backoff %ds)", notif_id, notification.retry_count + 1, backoff)
    await asyncio.sleep(backoff)

    ok = await dispatcher.send(notification)
    if not ok:
        await push_to_retry(redis_client, notif_id)
