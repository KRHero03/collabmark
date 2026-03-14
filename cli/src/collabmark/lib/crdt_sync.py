"""WebSocket-based CRDT content sync for the CollabMark CLI.

The CLI acts as a headless Yjs client: it builds a ``pycrdt.Doc``,
populates the ``"content"`` ``Text`` type, and exchanges Yjs sync
messages with the server over WebSocket.

Content always flows through the CRDT layer (never via the REST
``content`` field), keeping the CLI, browser, and server in sync.

Updates use incremental text diffing so that only the changed
characters are sent over the wire (not a full clear + re-insert).
"""

from __future__ import annotations

import asyncio
import logging
from difflib import SequenceMatcher

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
_BATCH_CONCURRENCY = 8


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


def _build_ws_url(doc_id: str, api_key: str, api_url: str | None = None) -> str:
    base = (api_url or get_api_url()).rstrip("/")
    ws_scheme = "wss" if base.startswith("https") else "ws"
    http_part = base.split("://", 1)[1] if "://" in base else base
    return f"{ws_scheme}://{http_part}/ws/doc/{doc_id}?api_key={api_key}"


async def _yjs_sync_handshake(ws, ydoc: Doc) -> None:
    """Perform the Yjs sync-protocol handshake over an open WebSocket.

    The protocol exchange is:
      1. CLI -> Server: sync step 1 (our state vector)
      2. Server -> CLI: sync step 1 (server's state vector)
      3. CLI -> Server: sync step 2 (update for server based on its SV)
      4. Server -> CLI: sync step 2 (update for us based on our SV)

    We must wait for *both* step 1 and step 2 from the server before
    considering the handshake complete.
    """
    await ws.send(_encode_sync_step1(ydoc.get_state()))

    got_step1 = False
    got_step2 = False
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
                    got_step1 = True

                elif sync_type == SYNC_STEP2:
                    update_bytes, _ = _read_var_bytes(msg, 2)
                    ydoc.apply_update(update_bytes)
                    got_step2 = True

                elif sync_type == SYNC_UPDATE:
                    update_bytes, _ = _read_var_bytes(msg, 2)
                    ydoc.apply_update(update_bytes)

                if got_step1 and got_step2:
                    break

    except TimeoutError:
        logger.warning("CRDT sync handshake timed out")


async def read_content_via_ws(
    doc_id: str,
    api_key: str,
    api_url: str | None = None,
) -> str:
    """Read document content from the CRDT store via WebSocket.

    Connects to the Yjs room, syncs state, and extracts the
    plaintext from the shared ``"content"`` Text type.
    """
    ws_url = _build_ws_url(doc_id, api_key, api_url)
    ydoc = Doc()
    ydoc.get("content", type=Text)

    try:
        async with connect(ws_url, close_timeout=5) as ws:
            await _yjs_sync_handshake(ws, ydoc)
    except ConnectionClosed as exc:
        logger.debug("WebSocket closed during CRDT read for doc %s: %s", doc_id, exc)
    except Exception as exc:
        logger.warning("CRDT read failed for doc %s: %s", doc_id, exc)

    return str(ydoc.get("content", type=Text))


async def read_contents_batch(
    doc_ids: list[str],
    api_key: str,
    api_url: str | None = None,
) -> dict[str, str]:
    """Read content for multiple documents concurrently.

    Returns ``{doc_id: content_string}`` for each document.
    Concurrency is bounded to avoid overwhelming the server.
    """
    sem = asyncio.Semaphore(_BATCH_CONCURRENCY)

    async def _read_one(doc_id: str) -> tuple[str, str]:
        async with sem:
            content = await read_content_via_ws(doc_id, api_key, api_url)
            return doc_id, content

    tasks = [_read_one(did) for did in doc_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    out: dict[str, str] = {}
    for r in results:
        if isinstance(r, tuple):
            out[r[0]] = r[1]
        else:
            logger.warning("Batch CRDT read error: %s", r)
    return out


async def write_content_via_ws(
    doc_id: str,
    content: str,
    api_key: str,
    api_url: str | None = None,
) -> None:
    """Push document content to the server CRDT store via WebSocket.

    Creates a local Y.Doc with the given content, connects to the
    Yjs room, and syncs so the server persists the CRDT state.
    Skips the write if content is empty to avoid overwriting with nothing.
    """
    if not content:
        logger.debug("Skipping CRDT write for doc %s: empty content", doc_id)
        return

    ws_url = _build_ws_url(doc_id, api_key, api_url)

    ydoc = Doc()
    ytext = ydoc.get("content", type=Text)
    ytext += content

    try:
        async with connect(ws_url, close_timeout=5) as ws:
            await _yjs_sync_handshake(ws, ydoc)
    except ConnectionClosed as exc:
        logger.debug("WebSocket closed during CRDT write for doc %s: %s", doc_id, exc)
    except Exception as exc:
        logger.warning("CRDT write failed for doc %s: %s", doc_id, exc)


def apply_incremental_diff(ytext: Text, old: str, new: str) -> bool:
    """Apply only the changed characters from *old* to *new* on a Y.Text.

    Uses ``SequenceMatcher`` to identify equal/insert/delete/replace
    regions and applies targeted operations in reverse index order so
    that earlier indices stay valid.

    Returns True if any mutations were applied, False if texts are equal.
    """
    if old == new:
        return False

    ops: list[tuple[str, int, int, int, int]] = SequenceMatcher(None, old, new, autojunk=False).get_opcodes()

    for tag, i1, i2, j1, j2 in reversed(ops):
        if tag == "equal":
            continue
        elif tag == "replace":
            ytext[i1:i2] = new[j1:j2]
        elif tag == "delete":
            del ytext[i1:i2]
        elif tag == "insert":
            ytext.insert(i1, new[j1:j2])

    return True


async def update_content_via_ws(
    doc_id: str,
    new_content: str,
    api_key: str,
    api_url: str | None = None,
) -> None:
    """Update document content in the CRDT store via WebSocket.

    Connects, syncs the existing state, then applies an incremental
    text diff so only the changed characters are sent over the wire.
    """
    if not new_content:
        logger.debug("Skipping CRDT update for doc %s: empty content", doc_id)
        return

    ws_url = _build_ws_url(doc_id, api_key, api_url)

    ydoc = Doc()
    ytext = ydoc.get("content", type=Text)

    try:
        async with connect(ws_url, close_timeout=5) as ws:
            await _yjs_sync_handshake(ws, ydoc)

            current = str(ytext)
            if current == new_content:
                return

            state_before = ydoc.get_state()

            with ydoc.transaction():
                apply_incremental_diff(ytext, current, new_content)

            diff = ydoc.get_update(state_before)
            await ws.send(_encode_sync_update(diff))

            await asyncio.sleep(0.1)

    except ConnectionClosed as exc:
        logger.debug("WebSocket closed during CRDT update for doc %s: %s", doc_id, exc)
    except Exception as exc:
        logger.warning("CRDT update failed for doc %s: %s", doc_id, exc)


# Keep old name as an alias for backward compatibility
sync_content_via_ws = write_content_via_ws
