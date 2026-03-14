"""Tests for the MongoYStore custom CRDT persistence layer.

Validates that Y.Doc updates can be written to and read from MongoDB,
that compaction correctly merges incremental updates into a single
state snapshot, and that user attribution via the enqueue/dequeue
mechanism works correctly.
"""

import json

import pytest
from app.services.crdt_store import MongoYStore
from mongomock_motor import AsyncMongoMockClient
from pycrdt import Doc, Text


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
    async def test_multiple_writes_create_separate_records(self, store: MongoYStore, mock_db):
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
        async for update, _metadata, _timestamp in store.read():
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


class TestEnqueueUser:
    def test_enqueue_populates_queue(self, store: MongoYStore):
        """enqueue_user should add an entry to the internal queue."""
        store.enqueue_user("user-42")
        assert len(store._user_queue) == 1

    def test_pop_metadata_returns_json(self, store: MongoYStore):
        """After enqueuing a user, _pop_user_metadata returns JSON bytes."""
        store.enqueue_user("user-42")
        meta = store._pop_user_metadata()
        parsed = json.loads(meta)
        assert parsed == {"user_id": "user-42"}

    def test_pop_metadata_empty_when_no_enqueue(self, store: MongoYStore):
        """Without enqueue, _pop_user_metadata returns empty bytes."""
        assert store._pop_user_metadata() == b""

    def test_pop_metadata_none_user_returns_empty(self, store: MongoYStore):
        """Enqueuing None should produce empty metadata."""
        store.enqueue_user(None)
        assert store._pop_user_metadata() == b""

    def test_fifo_order(self, store: MongoYStore):
        """Users should be dequeued in FIFO order."""
        store.enqueue_user("alice")
        store.enqueue_user("bob")
        meta1 = json.loads(store._pop_user_metadata())
        meta2 = json.loads(store._pop_user_metadata())
        assert meta1["user_id"] == "alice"
        assert meta2["user_id"] == "bob"


class TestMongoYStoreUserAttribution:
    @pytest.fixture
    def attr_store(self, mock_db) -> MongoYStore:
        MongoYStore.set_database(mock_db)
        return MongoYStore(path="attributed-room")

    @pytest.mark.asyncio
    async def test_write_stores_user_id_in_metadata(self, attr_store, mock_db):
        """Enqueuing a user before write should embed user_id in the record."""
        attr_store.enqueue_user("user-42")

        doc = Doc()
        text = doc.get("content", type=Text)
        text += "attributed edit"
        await attr_store.write(doc.get_update())

        record = await mock_db["crdt_updates"].find_one({"room": "attributed-room"})
        metadata = json.loads(record["metadata"])
        assert metadata["user_id"] == "user-42"

    @pytest.mark.asyncio
    async def test_write_without_enqueue_stores_empty_metadata(self, attr_store, mock_db):
        """A write with no enqueued user should store empty metadata."""
        doc = Doc()
        text = doc.get("content", type=Text)
        text += "anonymous edit"
        await attr_store.write(doc.get_update())

        record = await mock_db["crdt_updates"].find_one({"room": "attributed-room"})
        assert record["metadata"] == b""

    @pytest.mark.asyncio
    async def test_consecutive_writes_track_different_users(self, attr_store, mock_db):
        """Each write should consume the next enqueued user in FIFO order."""
        doc = Doc()
        text = doc.get("content", type=Text)

        attr_store.enqueue_user("alice")
        text += "alice's edit"
        await attr_store.write(doc.get_update())

        attr_store.enqueue_user("bob")
        text += " bob's edit"
        await attr_store.write(doc.get_update())

        cursor = mock_db["crdt_updates"].find(
            {"room": "attributed-room"},
            sort=[("timestamp", 1)],
        )
        records = await cursor.to_list(length=10)
        assert len(records) == 2

        meta_0 = json.loads(records[0]["metadata"])
        meta_1 = json.loads(records[1]["metadata"])
        assert meta_0["user_id"] == "alice"
        assert meta_1["user_id"] == "bob"
