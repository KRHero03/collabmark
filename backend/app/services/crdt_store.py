"""Custom MongoDB-backed store for pycrdt-websocket CRDT document persistence.

This module implements the BaseYStore interface from pycrdt-websocket,
storing Y.Doc binary updates in a MongoDB collection. Each document's
updates are stored as individual records, enabling incremental persistence
and later compaction.
"""

import time
from logging import Logger, getLogger
from typing import AsyncIterator, Callable, Awaitable

from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
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

    Args:
        path: The room name (used as the grouping key in MongoDB).
        metadata_callback: Optional async/sync callable returning metadata bytes.
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
        metadata_callback: Callable[[], Awaitable[bytes] | bytes] | None = None,
        log: Logger | None = None,
    ) -> None:
        self.path = path
        self.metadata_callback = metadata_callback
        self.log = log or getLogger(__name__)

    @property
    def _collection(self) -> AsyncIOMotorCollection:
        """Return the MongoDB collection for CRDT updates.

        Raises:
            RuntimeError: If ``set_database`` has not been called.
        """
        if self._db is None:
            raise RuntimeError(
                "MongoYStore.set_database() must be called before using the store"
            )
        return self._db["crdt_updates"]

    async def write(self, data: bytes) -> None:
        """Persist a single Y.Doc update to MongoDB.

        Args:
            data: The binary CRDT update to store.
        """
        metadata = await self.get_metadata()
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
        """
        doc = Doc()
        async for update, _meta, _ts in self.read():
            doc.apply_update(update)

        full_update = doc.get_update()
        metadata = await self.get_metadata()

        async with await self._db.client.start_session() as session:
            async with session.start_transaction():
                await self._collection.delete_many(
                    {"room": self.path}, session=session
                )
                await self._collection.insert_one(
                    {
                        "room": self.path,
                        "update": full_update,
                        "metadata": metadata,
                        "timestamp": time.time(),
                        "version": self.version,
                    },
                    session=session,
                )

        self.log.info("Compacted CRDT updates for room %s", self.path)
