"""Custom MongoDB-backed store for pycrdt-websocket CRDT document persistence.

This module implements the BaseYStore interface from pycrdt-websocket,
storing Y.Doc binary updates in a MongoDB collection. Each document's
updates are stored as individual records, enabling incremental persistence
and later compaction.
"""

import json
import time
from collections import deque
from collections.abc import AsyncIterator
from logging import Logger, getLogger

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pycrdt import Doc
from pycrdt.store import BaseYStore


class MongoYStore(BaseYStore):
    """Persists Y.Doc updates to a MongoDB collection.

    Each update is stored as a document in the ``crdt_updates`` collection
    with the following schema::

        {
            "room":      str,      # room/document identifier
            "update":    bytes,    # binary CRDT update
            "metadata":  bytes,    # caller-supplied metadata (e.g. user info)
            "timestamp": float,    # epoch seconds when the update was written
            "version":   int       # store protocol version
        }

    User attribution works via a FIFO queue: the WebSocket adapter pushes
    the authenticated user's ID into ``_user_queue`` for every Y.Doc-modifying
    message it forwards. When ``write()`` is called (once per applied update),
    it pops the next user ID from the queue and embeds it in the metadata.

    Args:
        path: The room name (used as the grouping key in MongoDB).
        metadata_callback: Ignored (kept for BaseYStore compat); use
            ``enqueue_user`` instead.
        log: Optional logger instance.
    """

    _db: AsyncIOMotorDatabase | None = None

    @classmethod
    def set_database(cls, db: AsyncIOMotorDatabase) -> None:
        """Set the shared MongoDB database for all MongoYStore instances.

        Must be called once during application startup before any rooms are
        created.

        Args:
            db: The Motor async database instance.
        """
        cls._db = db

    def __init__(
        self,
        path: str,
        metadata_callback: None = None,
        log: Logger | None = None,
    ) -> None:
        self.path = path
        self.metadata_callback = None
        self.log = log or getLogger(__name__)
        self._user_queue: deque[str | None] = deque()

    def enqueue_user(self, user_id: str | None) -> None:
        """Record which user is responsible for the next Y.Doc write."""
        self._user_queue.append(user_id)

    @property
    def _collection(self) -> AsyncIOMotorCollection:
        """Return the MongoDB collection for CRDT updates.

        Raises:
            RuntimeError: If ``set_database`` has not been called.
        """
        if self._db is None:
            raise RuntimeError("MongoYStore.set_database() must be called before using the store")
        return self._db["crdt_updates"]

    def _pop_user_metadata(self) -> bytes:
        """Pop the next user ID from the queue and return JSON metadata bytes."""
        try:
            uid = self._user_queue.popleft()
        except IndexError:
            uid = None
        if uid:
            return json.dumps({"user_id": uid}).encode()
        return b""

    async def write(self, data: bytes) -> None:
        """Persist a single Y.Doc update to MongoDB.

        Args:
            data: The binary CRDT update to store.
        """
        metadata = self._pop_user_metadata()
        await self._collection.insert_one(
            {
                "room": self.path,
                "update": data,
                "metadata": metadata,
                "timestamp": time.time(),
                "version": self.version,
            }
        )
        self.log.debug("Stored CRDT update for room %s (%d bytes)", self.path, len(data))

    async def read(self) -> AsyncIterator[tuple[bytes, bytes, float]]:
        """Read all stored updates for this room in chronological order.

        Yields:
            Tuples of (update_bytes, metadata_bytes, timestamp).
        """
        cursor = self._collection.find(
            {"room": self.path},
            sort=[("timestamp", 1)],
        )
        async for record in cursor:
            yield record["update"], record["metadata"], record["timestamp"]

    async def compact(self) -> None:
        """Compact all incremental updates into a single state snapshot.

        This reduces storage size and speeds up room initialization by
        replacing N incremental updates with one full-state update.
        Compaction is a server-internal operation so metadata is empty.
        """
        doc = Doc()
        async for update, _meta, _ts in self.read():
            doc.apply_update(update)

        full_update = doc.get_update()

        async with await self._db.client.start_session() as session, session.start_transaction():
            await self._collection.delete_many({"room": self.path}, session=session)
            await self._collection.insert_one(
                {
                    "room": self.path,
                    "update": full_update,
                    "metadata": b"",
                    "timestamp": time.time(),
                    "version": self.version,
                },
                session=session,
            )

        self.log.info("Compacted CRDT updates for room %s", self.path)
