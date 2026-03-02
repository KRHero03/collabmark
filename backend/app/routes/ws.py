"""WebSocket route for real-time collaborative document editing.

Handles authentication (JWT cookie or API key query param), validates
document access, and bridges the connection to the pycrdt-websocket
room for the requested document.

Both VIEW and EDIT users can connect. The CRDT protocol syncs document
state to all connected clients; write permissions are enforced by the
editor UI (read-only mode for VIEW users).
"""

import logging

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.auth.jwt import decode_access_token
from app.models.api_key import ApiKey
from app.models.share_link import Permission
from app.models.user import User
from app.services.share_service import get_user_permission
from app.ws.handler import FastAPIWebsocketAdapter, get_websocket_server

router = APIRouter()
logger = logging.getLogger(__name__)


async def _authenticate_ws(websocket: WebSocket) -> User | None:
    """Authenticate a WebSocket connection via cookie or query param.

    Checks in order:
    1. ``access_token`` cookie (JWT)
    2. ``api_key`` query parameter

    Args:
        websocket: The incoming WebSocket connection.

    Returns:
        The authenticated User, or None if authentication fails.
    """
    token = websocket.cookies.get("access_token")
    if token:
        user_id = decode_access_token(token)
        if user_id:
            try:
                user = await User.get(PydanticObjectId(user_id))
                if user:
                    return user
            except (InvalidId, ValueError):
                logger.warning("Invalid user ID in JWT: %s", user_id)

    api_key_raw = websocket.query_params.get("api_key")
    if api_key_raw:
        key_hash = ApiKey.hash_key(api_key_raw)
        record = await ApiKey.find_one(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active == True,  # noqa: E712
        )
        if record:
            try:
                user = await User.get(PydanticObjectId(record.user_id))
                if user:
                    record.record_usage()
                    await record.save()
                    return user
            except (InvalidId, ValueError):
                logger.warning("Invalid user ID in API key record: %s", record.user_id)

    return None


@router.websocket("/ws/doc/{document_id}")
async def websocket_endpoint(websocket: WebSocket, document_id: str):
    """WebSocket endpoint for collaborative document editing.

    Authenticates the user, checks for at least VIEW permission
    (via explicit access or general_access), accepts the connection,
    then delegates to the pycrdt-websocket room for CRDT sync.

    Args:
        websocket: The incoming WebSocket connection.
        document_id: The ID of the document to collaborate on.
    """
    user = await _authenticate_ws(websocket)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    permission = await get_user_permission(document_id, user)
    if permission is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    read_only = permission == Permission.VIEW

    await websocket.accept()

    server = await get_websocket_server()
    room = await server.get_room(document_id)

    adapter = FastAPIWebsocketAdapter(websocket, path=document_id, read_only=read_only)

    try:
        await room.serve(adapter)
    except WebSocketDisconnect:
        pass
