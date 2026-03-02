"""WebSocket handler for real-time collaborative editing.

Bridges FastAPI WebSocket connections to pycrdt-websocket YRooms.
Each document gets its own room identified by document ID. The handler
authenticates users via JWT cookie or API key query param before allowing
connection.
"""

import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from pycrdt.websocket import WebsocketServer, YRoom

from app.services.crdt_store import MongoYStore

logger = logging.getLogger(__name__)


class CollabWebsocketServer(WebsocketServer):
    """Extended WebsocketServer that attaches a MongoYStore to each room.

    Overrides ``get_room`` so that every new room is backed by MongoDB
    persistence via MongoYStore.
    """

    async def get_room(self, name: str) -> YRoom:
        """Get or create a room with MongoDB-backed persistence.

        Args:
            name: The room name (typically a document ID).

        Returns:
            The YRoom instance for the given name.
        """
        if name not in self.rooms:
            store = MongoYStore(path=name, log=self.log)
            self.rooms[name] = YRoom(
                ready=self.rooms_ready,
                ystore=store,
                log=self.log,
            )
        room = self.rooms[name]
        await self.start_room(room)
        return room


YJS_MSG_SYNC = 0
YJS_SYNC_UPDATE = 2


class FastAPIWebsocketAdapter:
    """Adapts a FastAPI WebSocket to the Channel interface expected by YRoom.serve().

    The pycrdt-websocket library expects a Channel object with:
    - ``path``: str
    - ``send(message: bytes)``: async method
    - ``__aiter__``: yields incoming binary messages

    When ``read_only=True``, incoming Yjs sync-update messages (document edits)
    are silently dropped so VIEW users cannot push changes through the CRDT layer.
    """

    def __init__(self, websocket: WebSocket, path: str, *, read_only: bool = False) -> None:
        """Initialize the adapter.

        Args:
            websocket: The FastAPI WebSocket connection.
            path: The room path (document ID).
            read_only: If True, block incoming document update messages.
        """
        self.websocket = websocket
        self.path = path
        self.read_only = read_only

    async def send(self, message: bytes) -> None:
        """Send a binary message to the client.

        Args:
            message: The binary data to send.
        """
        try:
            await self.websocket.send_bytes(message)
        except Exception:
            pass

    def _is_write_message(self, data: bytes) -> bool:
        """Check if a message is a Yjs sync-update (document edit).

        Yjs wire format: first byte = message type, second byte = sub-type.
        Sync updates are type 0, sub-type 2.
        """
        return len(data) >= 2 and data[0] == YJS_MSG_SYNC and data[1] == YJS_SYNC_UPDATE

    def __aiter__(self):
        """Return the async iterator for incoming messages."""
        return self

    async def __anext__(self) -> bytes:
        """Receive the next binary message from the client.

        When ``read_only`` is set, Yjs sync-update messages are silently
        dropped (the loop continues to the next message).

        Returns:
            The binary message data.

        Raises:
            StopAsyncIteration: When the WebSocket disconnects.
        """
        while True:
            try:
                data = await self.websocket.receive_bytes()
            except WebSocketDisconnect:
                raise StopAsyncIteration()
            except Exception:
                raise StopAsyncIteration()

            if self.read_only and self._is_write_message(data):
                logger.debug("Dropped write message from read-only client on room %s", self.path)
                continue
            return data


_ws_server: CollabWebsocketServer | None = None


async def get_websocket_server() -> CollabWebsocketServer:
    """Return the singleton CollabWebsocketServer, starting it if needed.

    Returns:
        The running CollabWebsocketServer instance.
    """
    global _ws_server
    if _ws_server is None:
        _ws_server = CollabWebsocketServer(
            rooms_ready=True,
            auto_clean_rooms=True,
        )
    return _ws_server


async def start_websocket_server() -> None:
    """Start the global WebsocketServer (called during app lifespan startup)."""
    server = await get_websocket_server()
    if server._task_group is None:
        import asyncio
        asyncio.create_task(server.start())
        await server.started.wait()
        logger.info("CollabWebsocketServer started")


async def stop_websocket_server() -> None:
    """Stop the global WebsocketServer (called during app lifespan shutdown)."""
    global _ws_server
    if _ws_server is not None and _ws_server._task_group is not None:
        await _ws_server.stop()
        logger.info("CollabWebsocketServer stopped")
    _ws_server = None
