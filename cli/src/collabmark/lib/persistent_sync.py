"""Persistent WebSocket connections for real-time bidirectional CRDT sync.

Replaces the ephemeral connect-sync-disconnect pattern with long-lived
connections that receive server-pushed updates instantly.
"""

from __future__ import annotations

import asyncio
import logging

from pycrdt import Doc, Text
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

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
    apply_incremental_diff,
)

logger = logging.getLogger(__name__)

_RECONNECT_BASE_DELAY = 1.0
_RECONNECT_MAX_DELAY = 30.0
_HANDSHAKE_TIMEOUT = 10.0


class PersistentDocSync:
    """Maintains a persistent WebSocket connection for one document.

    Handles the Yjs sync handshake, listens for remote updates, and
    can push local changes without reconnecting each time.
    """

    def __init__(
        self,
        doc_id: str,
        api_key: str,
        on_remote_update: asyncio.coroutines | None = None,
        api_url: str | None = None,
    ):
        self._doc_id = doc_id
        self._api_key = api_key
        self._api_url = api_url
        self._on_remote_update = on_remote_update

        self._ydoc = Doc()
        self._ytext = self._ydoc.get("content", type=Text)

        self._ws = None
        self._connected = asyncio.Event()
        self._stopped = False
        self._listen_task: asyncio.Task | None = None
        self._reconnect_delay = _RECONNECT_BASE_DELAY

    @property
    def content(self) -> str:
        return str(self._ytext)

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    async def start(self) -> None:
        """Connect and begin listening for remote updates in background."""
        self._stopped = False
        self._listen_task = asyncio.create_task(self._connection_loop())

    async def stop(self) -> None:
        """Gracefully shut down the connection."""
        self._stopped = True
        self._connected.clear()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except (asyncio.CancelledError, Exception):
                pass

    async def push_content(self, new_content: str) -> bool:
        """Push local content to the server via the persistent connection.

        Returns True if the update was sent, False if not connected.
        """
        if not self._connected.is_set() or not self._ws:
            logger.warning("Cannot push: not connected to %s", self._doc_id)
            return False

        if not new_content:
            return False

        current = str(self._ytext)
        if current == new_content:
            return False

        state_before = self._ydoc.get_state()

        with self._ydoc.transaction():
            apply_incremental_diff(self._ytext, current, new_content)

        diff = self._ydoc.get_update(state_before)
        try:
            await self._ws.send(_encode_sync_update(diff))
            return True
        except (ConnectionClosed, Exception) as exc:
            logger.warning("Push failed for %s: %s", self._doc_id, exc)
            self._connected.clear()
            return False

    async def wait_connected(self, timeout: float = 15.0) -> bool:
        """Wait until the WebSocket is connected and synced."""
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def _connection_loop(self) -> None:
        """Reconnect loop: connect, handshake, listen, reconnect on failure."""
        while not self._stopped:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Connection error for %s: %s", self._doc_id, exc)

            if self._stopped:
                break

            self._connected.clear()
            logger.info(
                "Reconnecting to %s in %.1fs...",
                self._doc_id,
                self._reconnect_delay,
            )
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(
                self._reconnect_delay * 2,
                _RECONNECT_MAX_DELAY,
            )

    async def _connect_and_listen(self) -> None:
        """Single connection lifecycle: connect, handshake, listen forever."""
        ws_url = _build_ws_url(self._doc_id, self._api_key, self._api_url)

        async with connect(ws_url, close_timeout=5, ping_interval=20) as ws:
            self._ws = ws
            await self._handshake(ws)
            self._connected.set()
            self._reconnect_delay = _RECONNECT_BASE_DELAY
            logger.info("Connected to document %s", self._doc_id)

            async for raw in ws:
                msg = bytes(raw) if isinstance(raw, (bytes, bytearray, memoryview)) else raw.encode()
                await self._handle_message(msg, ws)

    async def _handshake(self, ws) -> None:
        """Yjs sync protocol handshake."""
        await ws.send(_encode_sync_step1(self._ydoc.get_state()))

        got_step1 = False
        got_step2 = False

        async with asyncio.timeout(_HANDSHAKE_TIMEOUT):
            async for raw in ws:
                msg = bytes(raw) if isinstance(raw, (bytes, bytearray, memoryview)) else raw.encode()

                if len(msg) < 2 or msg[0] != MSG_SYNC:
                    continue

                sync_type = msg[1]

                if sync_type == SYNC_STEP1:
                    remote_sv, _ = _read_var_bytes(msg, 2)
                    update = self._ydoc.get_update(remote_sv)
                    await ws.send(_encode_sync_step2(update))
                    got_step1 = True
                elif sync_type == SYNC_STEP2:
                    update_bytes, _ = _read_var_bytes(msg, 2)
                    self._ydoc.apply_update(update_bytes)
                    got_step2 = True
                elif sync_type == SYNC_UPDATE:
                    update_bytes, _ = _read_var_bytes(msg, 2)
                    self._ydoc.apply_update(update_bytes)

                if got_step1 and got_step2:
                    break

    async def _handle_message(self, msg: bytes, ws) -> None:
        """Process a message received after handshake."""
        if len(msg) < 2 or msg[0] != MSG_SYNC:
            return

        sync_type = msg[1]

        if sync_type == SYNC_STEP1:
            remote_sv, _ = _read_var_bytes(msg, 2)
            update = self._ydoc.get_update(remote_sv)
            await ws.send(_encode_sync_step2(update))
        elif sync_type in (SYNC_STEP2, SYNC_UPDATE):
            update_bytes, _ = _read_var_bytes(msg, 2)
            self._ydoc.apply_update(update_bytes)
            if self._on_remote_update:
                try:
                    await self._on_remote_update(self._doc_id, str(self._ytext))
                except Exception as exc:
                    logger.warning("Remote update callback error: %s", exc)
