"""Tests for collabmark.lib.crdt_sync — WebSocket-based CRDT content sync."""

from __future__ import annotations

import pytest

from collabmark.lib.crdt_sync import (
    MSG_SYNC,
    SYNC_STEP1,
    SYNC_STEP2,
    SYNC_UPDATE,
    _build_ws_url,
    _encode_sync_step1,
    _encode_sync_step2,
    _encode_sync_update,
    _read_var_bytes,
    _read_var_uint,
    _write_var_uint,
)


class TestVarUint:
    def test_small_value(self) -> None:
        encoded = _write_var_uint(5)
        val, offset = _read_var_uint(encoded)
        assert val == 5
        assert offset == 1

    def test_zero(self) -> None:
        encoded = _write_var_uint(0)
        val, _offset = _read_var_uint(encoded)
        assert val == 0

    def test_large_value(self) -> None:
        encoded = _write_var_uint(300)
        val, offset = _read_var_uint(encoded)
        assert val == 300
        assert offset == 2

    def test_very_large_value(self) -> None:
        encoded = _write_var_uint(100000)
        val, _offset = _read_var_uint(encoded)
        assert val == 100000

    def test_round_trip_various(self) -> None:
        for n in [0, 1, 127, 128, 255, 256, 16383, 16384, 65535, 1000000]:
            encoded = _write_var_uint(n)
            val, _ = _read_var_uint(encoded)
            assert val == n


class TestVarBytes:
    def test_round_trip(self) -> None:
        from collabmark.lib.crdt_sync import _encode_var_bytes

        data = b"hello world"
        encoded = _encode_var_bytes(data)
        decoded, offset = _read_var_bytes(encoded)
        assert decoded == data
        assert offset == len(encoded)

    def test_empty_bytes(self) -> None:
        from collabmark.lib.crdt_sync import _encode_var_bytes

        encoded = _encode_var_bytes(b"")
        decoded, _ = _read_var_bytes(encoded)
        assert decoded == b""


class TestMessageEncoding:
    def test_sync_step1_format(self) -> None:
        sv = b"\x01\x02\x03"
        msg = _encode_sync_step1(sv)
        assert msg[0] == MSG_SYNC
        assert msg[1] == SYNC_STEP1
        payload, _ = _read_var_bytes(msg, 2)
        assert payload == sv

    def test_sync_step2_format(self) -> None:
        update = b"\x04\x05\x06"
        msg = _encode_sync_step2(update)
        assert msg[0] == MSG_SYNC
        assert msg[1] == SYNC_STEP2
        payload, _ = _read_var_bytes(msg, 2)
        assert payload == update

    def test_sync_update_format(self) -> None:
        update = b"\x07\x08\x09"
        msg = _encode_sync_update(update)
        assert msg[0] == MSG_SYNC
        assert msg[1] == SYNC_UPDATE
        payload, _ = _read_var_bytes(msg, 2)
        assert payload == update


class TestBuildWsUrl:
    def test_http_to_ws(self) -> None:
        url = _build_ws_url("doc123", "key1", api_url="http://localhost:8000")
        assert url == "ws://localhost:8000/ws/doc/doc123?api_key=key1"

    def test_https_to_wss(self) -> None:
        url = _build_ws_url("doc123", "key1", api_url="https://app.example.com")
        assert url == "wss://app.example.com/ws/doc/doc123?api_key=key1"

    def test_strips_trailing_slash(self) -> None:
        url = _build_ws_url("d1", "k1", api_url="http://localhost:8000/")
        assert "//" not in url.split("://", 1)[1]


class TestYDocRoundTrip:
    def test_content_round_trip_via_protocol(self) -> None:
        """Simulate the full sync protocol between a client and server doc."""
        from pycrdt import Doc, Text

        client_doc = Doc()
        client_text = client_doc.get("content", type=Text)
        client_text += "# Hello World\n\nThis is a test."

        server_doc = Doc()

        server_sv = server_doc.get_state()

        client_update = client_doc.get_update(server_sv)
        server_doc.apply_update(client_update)

        server_text = server_doc.get("content", type=Text)
        assert str(server_text) == "# Hello World\n\nThis is a test."

    def test_empty_content(self) -> None:
        from pycrdt import Doc, Text

        client_doc = Doc()
        client_doc.get("content", type=Text)

        server_doc = Doc()
        server_sv = server_doc.get_state()
        update = client_doc.get_update(server_sv)
        server_doc.apply_update(update)

        server_text = server_doc.get("content", type=Text)
        assert str(server_text) == ""

    def test_unicode_content(self) -> None:
        from pycrdt import Doc, Text

        client_doc = Doc()
        client_text = client_doc.get("content", type=Text)
        client_text += "日本語テスト 🎉"

        server_doc = Doc()
        server_sv = server_doc.get_state()
        update = client_doc.get_update(server_sv)
        server_doc.apply_update(update)

        server_text = server_doc.get("content", type=Text)
        assert str(server_text) == "日本語テスト 🎉"


class TestWriteContentViaWs:
    @pytest.mark.asyncio
    async def test_handles_connection_failure_gracefully(self) -> None:
        """Should not raise when the server is unreachable."""
        from collabmark.lib.crdt_sync import write_content_via_ws

        await write_content_via_ws(
            doc_id="nonexistent",
            content="test",
            api_key="cm_fake_key",
            api_url="http://localhost:1",
        )


class TestReadContentViaWs:
    @pytest.mark.asyncio
    async def test_handles_connection_failure_gracefully(self) -> None:
        """Should return empty string when the server is unreachable."""
        from collabmark.lib.crdt_sync import read_content_via_ws

        result = await read_content_via_ws(
            doc_id="nonexistent",
            api_key="cm_fake_key",
            api_url="http://localhost:1",
        )
        assert result == ""


class TestReadContentsBatch:
    @pytest.mark.asyncio
    async def test_handles_connection_failures_gracefully(self) -> None:
        """Should return empty dict when all connections fail."""
        from collabmark.lib.crdt_sync import read_contents_batch

        result = await read_contents_batch(
            doc_ids=["d1", "d2"],
            api_key="cm_fake_key",
            api_url="http://localhost:1",
        )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty_dict(self) -> None:
        from collabmark.lib.crdt_sync import read_contents_batch

        result = await read_contents_batch([], "cm_fake_key")
        assert result == {}


class TestBackwardCompat:
    def test_sync_content_alias(self) -> None:
        from collabmark.lib.crdt_sync import sync_content_via_ws, write_content_via_ws

        assert sync_content_via_ws is write_content_via_ws
