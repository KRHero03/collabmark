"""CollabMark FastAPI application: lifespan, CORS, routes, static frontend."""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from beanie import init_beanie
from fastapi import Cookie, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse as StarletteJSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.config import settings
from app.models.api_key import ApiKey
from app.models.comment import Comment
from app.models.document import Document_
from app.models.document_version import DocumentVersion
from app.models.document_view import DocumentView
from app.models.folder import Folder, FolderAccess, FolderView
from app.models.group import DocumentGroupAccess, FolderGroupAccess, Group, GroupMembership
from app.models.notification import Notification, NotificationPreference
from app.models.org_sso_config import OrgSSOConfig
from app.models.organization import Organization, OrgMembership
from app.models.share_link import DocumentAccess, ShareLink
from app.models.user import User
from app.rate_limit import limiter
from app.routes import auth, comments, documents, folders, keys, notifications, orgs, scim, sharing, users, versions, ws
from app.services.blob_storage import MIME_TYPES
from app.services.channels.email import EmailChannel
from app.services.crdt_store import MongoYStore
from app.services.notification_dispatcher import (
    NotificationChannel,
    NotificationDispatcher,
    set_dispatcher,
)
from app.services.notification_retry import retry_loop
from app.services.notification_scheduler import scheduler_loop
from app.ws.handler import start_websocket_server, stop_websocket_server

DOCUMENT_MODELS = [
    User,
    Document_,
    ApiKey,
    DocumentAccess,
    ShareLink,
    DocumentVersion,
    Comment,
    DocumentView,
    Folder,
    FolderAccess,
    FolderView,
    Organization,
    OrgMembership,
    OrgSSOConfig,
    Group,
    GroupMembership,
    DocumentGroupAccess,
    FolderGroupAccess,
    Notification,
    NotificationPreference,
]

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: DB, CRDT, Redis, notification workers."""
    client = AsyncIOMotorClient(
        settings.mongodb_url,
        serverSelectionTimeoutMS=10_000,
        connectTimeoutMS=10_000,
    )
    db = client[settings.mongodb_db_name]
    await init_beanie(database=db, document_models=DOCUMENT_MODELS, skip_indexes=True)

    with contextlib.suppress(Exception):
        await db["users"].drop_index("google_id_1")

    MongoYStore.set_database(db)
    await start_websocket_server()

    _bg_tasks: list[asyncio.Task] = []
    redis_client = None
    if settings.notifications_enabled:
        try:
            redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
            await redis_client.ping()

            dispatcher = NotificationDispatcher(redis_client=redis_client)
            dispatcher.register_channel(NotificationChannel.EMAIL, EmailChannel())
            set_dispatcher(dispatcher)

            _bg_tasks.append(asyncio.create_task(scheduler_loop(redis_client, dispatcher)))
            _bg_tasks.append(asyncio.create_task(retry_loop(redis_client, dispatcher)))

            logging.getLogger(__name__).info(
                "Notification system initialized (delay=%ds)", settings.notification_delay_seconds
            )
        except Exception:
            logging.getLogger(__name__).warning("Redis unavailable — notifications disabled", exc_info=True)

    yield

    for task in _bg_tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    if redis_client:
        await redis_client.aclose()

    await stop_websocket_server()
    client.close()


def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return StarletteJSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(sharing.router)
app.include_router(versions.router)
app.include_router(documents.router)
app.include_router(folders.router)
app.include_router(keys.router)
app.include_router(comments.router)
app.include_router(notifications.router)
app.include_router(orgs.router)
app.include_router(scim.router)
scim.register_scim_error_handler(app)
app.include_router(ws.router)


@app.get("/api/health")
async def health():
    """Health check endpoint for load balancers and monitoring.

    Returns:
        Dict with status, version, and service info.
    """
    return {
        "status": "ok",
        "service": "collabmark",
        "version": "1.0.0",
    }


@app.get("/media/{file_path:path}")
async def serve_media(
    file_path: str,
    access_token: str | None = Cookie(default=None, alias="access_token"),
):
    """Proxy media files from blob storage (S3 or local filesystem).

    Requires a valid JWT cookie. Non-image files are served as attachments
    to prevent browser execution of uploaded PDFs, Office docs, etc.
    """
    from app.auth.jwt import decode_access_token
    from app.services.blob_storage import get_object

    if not access_token or decode_access_token(access_token) is None:
        return Response(status_code=401)

    obj = get_object(file_path)
    if obj is None:
        return Response(status_code=404)

    ext = Path(file_path).suffix.lower()
    content_type = MIME_TYPES.get(ext, obj.get("ContentType", "application/octet-stream"))
    body = obj["Body"].read()
    headers: dict[str, str] = {"Cache-Control": "public, max-age=86400"}
    if content_type not in _IMAGE_CONTENT_TYPES:
        filename = Path(file_path).name
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(
        content=body,
        media_type=content_type,
        headers=headers,
    )


if STATIC_DIR.is_dir():
    _index_html = STATIC_DIR / "index.html"
    _assets_dir = STATIC_DIR / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="static-assets")

    _static_resolved = STATIC_DIR.resolve()

    @app.get("/{full_path:path}")
    async def spa_fallback(request: Request, full_path: str) -> FileResponse:
        """Serve static files if they exist, otherwise serve index.html for SPA routing.

        Path traversal is prevented by resolving the candidate and verifying
        it is within the static directory.
        """
        if full_path:
            candidate = (STATIC_DIR / full_path).resolve()
            if candidate.is_file() and (_static_resolved in candidate.parents or candidate == _static_resolved):
                return FileResponse(candidate)
        return FileResponse(_index_html)
