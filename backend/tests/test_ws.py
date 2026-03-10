"""Tests for the WebSocket authentication and handler layer.

Covers authentication scenarios (valid JWT, invalid JWT, API key,
unauthenticated) for the WebSocket endpoint, and verifies the
FastAPIWebsocketAdapter interface.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.ws.handler import CollabWebsocketServer, FastAPIWebsocketAdapter
from fastapi import WebSocketDisconnect


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


class TestPermissionRecheck:
    """Test dynamic permission re-checking on the adapter."""

    @pytest.mark.asyncio
    async def test_recheck_upgrades_read_only_to_writable(self):
        """When DB permission changes to EDIT, read_only should become False."""
        from unittest.mock import patch

        mock_ws = MagicMock()
        mock_user = MagicMock()
        adapter = FastAPIWebsocketAdapter(mock_ws, path="doc-perm", read_only=True, user=mock_user)
        adapter._last_perm_check = 0

        with patch("app.services.share_service.get_user_permission", new_callable=AsyncMock) as mock_perm:
            mock_perm.return_value = "edit"
            await adapter._recheck_permission()

        assert adapter.read_only is False

    @pytest.mark.asyncio
    async def test_recheck_downgrades_writable_to_read_only(self):
        """When DB permission changes to VIEW, read_only should become True."""
        from unittest.mock import patch

        mock_ws = MagicMock()
        mock_user = MagicMock()
        adapter = FastAPIWebsocketAdapter(mock_ws, path="doc-perm", read_only=False, user=mock_user)
        adapter._last_perm_check = 0

        with patch("app.services.share_service.get_user_permission", new_callable=AsyncMock) as mock_perm:
            mock_perm.return_value = "view"
            await adapter._recheck_permission()

        assert adapter.read_only is True

    @pytest.mark.asyncio
    async def test_recheck_revoked_access_sets_read_only(self):
        """When DB permission is None (revoked), read_only should be True."""
        from unittest.mock import patch

        mock_ws = MagicMock()
        mock_user = MagicMock()
        adapter = FastAPIWebsocketAdapter(mock_ws, path="doc-perm", read_only=False, user=mock_user)
        adapter._last_perm_check = 0

        with patch("app.services.share_service.get_user_permission", new_callable=AsyncMock) as mock_perm:
            mock_perm.return_value = None
            await adapter._recheck_permission()

        assert adapter.read_only is True

    @pytest.mark.asyncio
    async def test_recheck_skipped_within_interval(self):
        """Re-check should be skipped if interval has not elapsed."""
        from unittest.mock import patch

        mock_ws = MagicMock()
        mock_user = MagicMock()
        adapter = FastAPIWebsocketAdapter(mock_ws, path="doc-perm", read_only=True, user=mock_user)

        with patch("app.services.share_service.get_user_permission", new_callable=AsyncMock) as mock_perm:
            mock_perm.return_value = "edit"
            await adapter._recheck_permission()

        assert adapter.read_only is True
        assert mock_perm.call_count == 0

    @pytest.mark.asyncio
    async def test_recheck_skipped_when_no_user(self):
        """Re-check should be a no-op when user is None."""
        from unittest.mock import patch

        mock_ws = MagicMock()
        adapter = FastAPIWebsocketAdapter(mock_ws, path="doc-perm", read_only=True, user=None)
        adapter._last_perm_check = 0

        with patch("app.services.share_service.get_user_permission", new_callable=AsyncMock) as mock_perm:
            await adapter._recheck_permission()

        assert adapter.read_only is True
        mock_perm.assert_not_called()

    @pytest.mark.asyncio
    async def test_write_message_allowed_after_upgrade(self):
        """After permission upgrade, sync-update messages should pass through."""
        from unittest.mock import patch

        mock_ws = MagicMock()
        mock_user = MagicMock()
        sync_update_msg = bytes([0, 2]) + b"\x01\x02\x03"
        mock_ws.receive_bytes = AsyncMock(return_value=sync_update_msg)

        adapter = FastAPIWebsocketAdapter(mock_ws, path="doc-perm", read_only=True, user=mock_user)
        adapter._last_perm_check = 0

        with patch("app.services.share_service.get_user_permission", new_callable=AsyncMock) as mock_perm:
            mock_perm.return_value = "edit"
            result = await adapter.__anext__()

        assert result == sync_update_msg

    @pytest.mark.asyncio
    async def test_write_message_dropped_when_read_only(self):
        """Sync-update messages should be dropped when read_only, non-write passes through."""
        mock_ws = MagicMock()
        mock_user = MagicMock()
        sync_update_msg = bytes([0, 2]) + b"\x01\x02\x03"
        normal_msg = bytes([0, 0]) + b"\x04\x05"
        mock_ws.receive_bytes = AsyncMock(side_effect=[sync_update_msg, normal_msg])

        adapter = FastAPIWebsocketAdapter(mock_ws, path="doc-perm", read_only=True, user=mock_user)

        result = await adapter.__anext__()
        assert result == normal_msg


class TestCollabWebsocketServer:
    """Test the custom WebsocketServer subclass."""

    @pytest.mark.asyncio
    async def test_get_room_creates_room_with_store(self):
        """get_room() should create a YRoom with a MongoYStore attached."""
        from app.services.crdt_store import MongoYStore
        from mongomock_motor import AsyncMongoMockClient

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
        from app.services.crdt_store import MongoYStore
        from mongomock_motor import AsyncMongoMockClient

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
        from app.services.crdt_store import MongoYStore
        from mongomock_motor import AsyncMongoMockClient

        client = AsyncMongoMockClient()
        MongoYStore.set_database(client["test_ws_server3"])

        server = CollabWebsocketServer(rooms_ready=True, auto_clean_rooms=False)

        async with server:
            room_a = await server.get_room("doc-a")
            room_b = await server.get_room("doc-b")
            assert room_a is not room_b
            assert room_a.ystore.path == "doc-a"
            assert room_b.ystore.path == "doc-b"
