"""WebSocket-based CRDT content sync for the CollabMark CLI.

After creating or updating a document via the REST API, this module
connects to the backend's Yjs WebSocket endpoint and pushes the document
content through the CRDT layer.  This ensures the content appears in
the browser editor, which loads exclusively from the CRDT store.

The CLI acts as a headless Yjs client: it builds a ``pycrdt.Doc``,
populates the ``"content"`` ``Text`` type, and exchanges Yjs sync
messages with the server over WebSocket.
"""

from __future__ import annotations

import asyncio
import logging

from pycrdt import Doc, Text
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from collabmark.lib.config import get_api_url

logger = logging.getLogger(__name__)

MSG_SYNC = 0
SYNC_STEP1 = 0
SYNC_STEP2 = 1
SYNC_UPDATE = 2

_SYNC_TIMEOUT = 10.0


def _write_var_uint(n: int) -> bytes:
    buf = bytearray()
    while n > 0x7F:
        buf.append(0x80 | (n & 0x7F))
        n >>= 7
    buf.append(n & 0x7F)
    return bytes(buf)


def _read_var_uint(data: bytes, offset: int = 0) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        byte = data[offset]
        result |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80):
            break
        shift += 7
    return result, offset


def _read_var_bytes(data: bytes, offset: int = 0) -> tuple[bytes, int]:
    length, offset = _read_var_uint(data, offset)
    return data[offset : offset + length], offset + length


def _encode_var_bytes(payload: bytes) -> bytes:
    return _write_var_uint(len(payload)) + payload


def _encode_sync_step1(state_vector: bytes) -> bytes:
    return bytes([MSG_SYNC, SYNC_STEP1]) + _encode_var_bytes(state_vector)


def _encode_sync_step2(update: bytes) -> bytes:
    return bytes([MSG_SYNC, SYNC_STEP2]) + _encode_var_bytes(update)


def _encode_sync_update(update: bytes) -> bytes:
    return bytes([MSG_SYNC, SYNC_UPDATE]) + _encode_var_bytes(update)


async def sync_content_via_ws(
    doc_id: str,
    content: str,
    api_key: str,
    api_url: str | None = None,
) -> None:
    """Push document content to the server CRDT store via WebSocket.

    Connects to ``/ws/doc/{doc_id}``, performs the Yjs sync handshake,
    and pushes the content so the editor can display it.
    """
    base = (api_url or get_api_url()).rstrip("/")
    ws_scheme = "wss" if base.startswith("https") else "ws"
    http_part = base.split("://", 1)[1] if "://" in base else base
    ws_url = f"{ws_scheme}://{http_part}/ws/doc/{doc_id}?api_key={api_key}"

    ydoc = Doc()
    ytext = ydoc.get("content", type=Text)
    ytext += content

    try:
        async with connect(ws_url, close_timeout=5) as ws:
            ws.send(_encode_sync_step1(ydoc.get_state()))

            synced = False
            try:
                async with asyncio.timeout(_SYNC_TIMEOUT):
                    async for raw in ws:
                        msg = bytes(raw) if isinstance(raw, (bytes, bytearray, memoryview)) else raw.encode()

                        if len(msg) < 2 or msg[0] != MSG_SYNC:
                            continue

                        sync_type = msg[1]

                        if sync_type == SYNC_STEP1:
                            remote_sv, _ = _read_var_bytes(msg, 2)
                            update = ydoc.get_update(remote_sv)
                            await ws.send(_encode_sync_step2(update))
                            synced = True

                        elif sync_type == SYNC_STEP2:
                            update_bytes, _ = _read_var_bytes(msg, 2)
                            ydoc.apply_update(update_bytes)

                        if synced:
                            break

            except TimeoutError:
                logger.warning("CRDT sync timed out for doc %s", doc_id)

    except ConnectionClosed as exc:
        logger.debug("WebSocket closed during CRDT sync for doc %s: %s", doc_id, exc)
    except Exception as exc:
        logger.warning("CRDT sync failed for doc %s: %s", doc_id, exc)
