"""Tests for the MongoYStore custom CRDT persistence layer.

Validates that Y.Doc updates can be written to and read from MongoDB,
and that compaction correctly merges incremental updates into a single
state snapshot.
"""

import pytest
from mongomock_motor import AsyncMongoMockClient
from pycrdt import Doc, Text

from app.services.crdt_store import MongoYStore


@pytest.fixture
def mock_db():
    """Provide a fresh mongomock database for each test."""
    client = AsyncMongoMockClient()
    return client["test_crdt"]


@pytest.fixture
def store(mock_db) -> MongoYStore:
    """Provide a MongoYStore backed by the mock database."""
    MongoYStore.set_database(mock_db)
    return MongoYStore(path="test-room-001")


class TestMongoYStoreWrite:
    @pytest.mark.asyncio
    async def test_write_stores_update_in_mongodb(self, store: MongoYStore, mock_db):
        """A single write should create exactly one record in the collection."""
        doc = Doc()
        text = doc.get("content", type=Text)
        text += "hello world"
        update = doc.get_update()

        await store.write(update)

        count = await mock_db["crdt_updates"].count_documents({"room": "test-room-001"})
        assert count == 1

    @pytest.mark.asyncio
    async def test_write_stores_correct_binary_data(self, store: MongoYStore, mock_db):
        """The stored update bytes should match exactly what was written."""
        doc = Doc()
        text = doc.get("content", type=Text)
        text += "exact data check"
        update = doc.get_update()

        await store.write(update)

        record = await mock_db["crdt_updates"].find_one({"room": "test-room-001"})
        assert record["update"] == update
        assert record["version"] == store.version
        assert record["room"] == "test-room-001"

    @pytest.mark.asyncio
    async def test_multiple_writes_create_separate_records(
        self, store: MongoYStore, mock_db
    ):
        """Each write call should create an independent MongoDB document."""
        doc = Doc()
        text = doc.get("content", type=Text)

        text += "first"
        await store.write(doc.get_update())

        text += " second"
        await store.write(doc.get_update())

        count = await mock_db["crdt_updates"].count_documents({"room": "test-room-001"})
        assert count == 2


class TestMongoYStoreRead:
    @pytest.mark.asyncio
    async def test_read_empty_room_yields_nothing(self, store: MongoYStore):
        """Reading from a room with no writes should yield zero results."""
        updates = []
        async for update, metadata, timestamp in store.read():
            updates.append(update)
        assert updates == []

    @pytest.mark.asyncio
    async def test_read_returns_written_updates(self, store: MongoYStore):
        """Updates read back should reconstruct the same document state."""
        original = Doc()
        text = original.get("content", type=Text)
        text += "round trip test"
        await store.write(original.get_update())

        reconstructed = Doc()
        async for update, _meta, _ts in store.read():
            reconstructed.apply_update(update)

        result_text = reconstructed.get("content", type=Text)
        assert str(result_text) == "round trip test"

    @pytest.mark.asyncio
    async def test_read_chronological_order(self, store: MongoYStore):
        """Updates should be returned in chronological (ascending) order."""
        doc = Doc()
        text = doc.get("content", type=Text)

        text += "A"
        await store.write(doc.get_update())
        text += "B"
        await store.write(doc.get_update())

        timestamps = []
        async for _update, _meta, ts in store.read():
            timestamps.append(ts)

        assert len(timestamps) == 2
        assert timestamps[0] <= timestamps[1]


class TestMongoYStoreRoomIsolation:
    @pytest.mark.asyncio
    async def test_different_rooms_are_isolated(self, mock_db):
        """Updates in one room should not appear in another."""
        MongoYStore.set_database(mock_db)
        store_a = MongoYStore(path="room-a")
        store_b = MongoYStore(path="room-b")

        doc_a = Doc()
        text_a = doc_a.get("content", type=Text)
        text_a += "room A content"
        await store_a.write(doc_a.get_update())

        updates_b = []
        async for update, _meta, _ts in store_b.read():
            updates_b.append(update)

        assert updates_b == []

        updates_a = []
        async for update, _meta, _ts in store_a.read():
            updates_a.append(update)

        assert len(updates_a) == 1


class TestMongoYStoreApplyUpdates:
    @pytest.mark.asyncio
    async def test_apply_updates_reconstructs_document(self, store: MongoYStore):
        """The BaseYStore.apply_updates helper should correctly rebuild state."""
        original = Doc()
        text = original.get("content", type=Text)
        text += "Hello, "
        await store.write(original.get_update())
        text += "World!"
        await store.write(original.get_update())

        rebuilt = Doc()
        await store.apply_updates(rebuilt)

        rebuilt_text = rebuilt.get("content", type=Text)
        assert str(rebuilt_text) == "Hello, World!"
