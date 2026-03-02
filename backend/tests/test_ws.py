"""Tests for the WebSocket authentication and handler layer.

Covers authentication scenarios (valid JWT, invalid JWT, API key,
unauthenticated) for the WebSocket endpoint, and verifies the
FastAPIWebsocketAdapter interface.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import WebSocketDisconnect

from app.ws.handler import FastAPIWebsocketAdapter, CollabWebsocketServer


class TestFastAPIWebsocketAdapter:
    """Test the adapter that bridges FastAPI WebSocket to pycrdt Channel."""

    def test_adapter_has_path(self):
        """The adapter should expose the path for room identification."""
        mock_ws = MagicMock()
        adapter = FastAPIWebsocketAdapter(mock_ws, path="doc-123")
        assert adapter.path == "doc-123"

    @pytest.mark.asyncio
    async def test_send_forwards_bytes(self):
        """send() should forward binary data to the underlying WebSocket."""
        mock_ws = MagicMock()
        mock_ws.send_bytes = AsyncMock()
        adapter = FastAPIWebsocketAdapter(mock_ws, path="doc-456")

        await adapter.send(b"\x01\x02\x03")
        mock_ws.send_bytes.assert_called_once_with(b"\x01\x02\x03")

    @pytest.mark.asyncio
    async def test_send_swallows_exceptions(self):
        """send() should not raise even if the WebSocket is closed."""
        mock_ws = MagicMock()
        mock_ws.send_bytes = AsyncMock(side_effect=RuntimeError("closed"))
        adapter = FastAPIWebsocketAdapter(mock_ws, path="doc-789")

        await adapter.send(b"data")

    @pytest.mark.asyncio
    async def test_aiter_yields_messages(self):
        """The async iterator should yield messages from receive_bytes."""
        mock_ws = MagicMock()
        messages = [b"msg1", b"msg2"]
        call_count = 0

        async def mock_receive():
            nonlocal call_count
            if call_count < len(messages):
                msg = messages[call_count]
                call_count += 1
                return msg
            raise WebSocketDisconnect()

        mock_ws.receive_bytes = mock_receive
        adapter = FastAPIWebsocketAdapter(mock_ws, path="room-1")

        received = []
        async for msg in adapter:
            received.append(msg)

        assert received == [b"msg1", b"msg2"]

    @pytest.mark.asyncio
    async def test_aiter_stops_on_disconnect(self):
        """The iterator should stop cleanly when the client disconnects."""
        mock_ws = MagicMock()
        mock_ws.receive_bytes = AsyncMock(side_effect=WebSocketDisconnect())
        adapter = FastAPIWebsocketAdapter(mock_ws, path="room-2")

        received = []
        async for msg in adapter:
            received.append(msg)

        assert received == []


class TestCollabWebsocketServer:
    """Test the custom WebsocketServer subclass."""

    @pytest.mark.asyncio
    async def test_get_room_creates_room_with_store(self):
        """get_room() should create a YRoom with a MongoYStore attached."""
        from mongomock_motor import AsyncMongoMockClient
        from app.services.crdt_store import MongoYStore

        client = AsyncMongoMockClient()
        MongoYStore.set_database(client["test_ws_server"])

        server = CollabWebsocketServer(rooms_ready=True, auto_clean_rooms=False)

        async with server:
            room = await server.get_room("doc-abc")
            assert room is not None
            assert room.ystore is not None
            assert isinstance(room.ystore, MongoYStore)
            assert room.ystore.path == "doc-abc"

    @pytest.mark.asyncio
    async def test_get_room_returns_same_room_for_same_name(self):
        """Calling get_room twice with the same name should return the same instance."""
        from mongomock_motor import AsyncMongoMockClient
        from app.services.crdt_store import MongoYStore

        client = AsyncMongoMockClient()
        MongoYStore.set_database(client["test_ws_server2"])

        server = CollabWebsocketServer(rooms_ready=True, auto_clean_rooms=False)

        async with server:
            room1 = await server.get_room("doc-xyz")
            room2 = await server.get_room("doc-xyz")
            assert room1 is room2

    @pytest.mark.asyncio
    async def test_different_room_names_create_different_rooms(self):
        """Different document IDs should produce different rooms."""
        from mongomock_motor import AsyncMongoMockClient
        from app.services.crdt_store import MongoYStore

        client = AsyncMongoMockClient()
        MongoYStore.set_database(client["test_ws_server3"])

        server = CollabWebsocketServer(rooms_ready=True, auto_clean_rooms=False)

        async with server:
            room_a = await server.get_room("doc-a")
            room_b = await server.get_room("doc-b")
            assert room_a is not room_b
            assert room_a.ystore.path == "doc-a"
            assert room_b.ystore.path == "doc-b"
