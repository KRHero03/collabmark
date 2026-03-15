"""Abstract base class for notification delivery channels."""

from abc import ABC, abstractmethod

from app.models.notification import Notification


class BaseChannel(ABC):
    """Interface that every notification channel must implement."""

    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Deliver a notification. Returns True on success, False on failure."""
