"""Tests for the persistent WebSocket sync module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from collabmark.lib.persistent_sync import PersistentDocSync


class TestPersistentDocSyncInit:
    def test_initializes_with_empty_content(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        assert psync.content == ""
        assert not psync.is_connected

    def test_stores_doc_id_and_api_key(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        assert psync._doc_id == "d1"
        assert psync._api_key == "key"


class TestPersistentDocSyncPush:
    async def test_push_returns_false_when_disconnected(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        result = await psync.push_content("hello")
        assert result is False

    async def test_push_returns_false_for_empty_content(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        psync._connected.set()
        psync._ws = MagicMock()
        result = await psync.push_content("")
        assert result is False

    async def test_push_returns_false_when_content_unchanged(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        psync._connected.set()
        psync._ws = AsyncMock()
        result = await psync.push_content("")
        assert result is False

    async def test_push_sends_update_on_change(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        psync._connected.set()
        mock_ws = AsyncMock()
        psync._ws = mock_ws

        result = await psync.push_content("new text")
        assert result is True
        mock_ws.send.assert_called_once()
        assert psync.content == "new text"

    async def test_push_returns_false_on_connection_error(self):
        from websockets.exceptions import ConnectionClosed

        psync = PersistentDocSync(doc_id="d1", api_key="key")
        psync._connected.set()
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = ConnectionClosed(None, None)
        psync._ws = mock_ws

        result = await psync.push_content("new text")
        assert result is False
        assert not psync.is_connected


class TestPersistentDocSyncLifecycle:
    async def test_stop_clears_connected_state(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        psync._connected.set()
        await psync.stop()
        assert not psync.is_connected
        assert psync._stopped is True

    async def test_wait_connected_returns_false_on_timeout(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        result = await psync.wait_connected(timeout=0.1)
        assert result is False

    async def test_wait_connected_returns_true_when_connected(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        psync._connected.set()
        result = await psync.wait_connected(timeout=1.0)
        assert result is True


class TestPersistentDocSyncContentProperty:
    def test_content_reflects_ydoc_state(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        psync._ytext += "hello world"
        assert psync.content == "hello world"

    def test_content_starts_empty(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        assert psync.content == ""


class TestPersistentDocSyncMultiplePushes:
    async def test_sequential_pushes_update_content(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        psync._connected.set()
        psync._ws = AsyncMock()

        await psync.push_content("first version")
        assert psync.content == "first version"

        await psync.push_content("second version")
        assert psync.content == "second version"

    async def test_push_same_content_twice_is_noop(self):
        psync = PersistentDocSync(doc_id="d1", api_key="key")
        psync._connected.set()
        mock_ws = AsyncMock()
        psync._ws = mock_ws

        await psync.push_content("same")
        call_count_after_first = mock_ws.send.call_count

        result = await psync.push_content("same")
        assert result is False
        assert mock_ws.send.call_count == call_count_after_first
