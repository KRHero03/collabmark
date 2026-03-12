"""CollabMark FastAPI application: lifespan, CORS, routes, static frontend."""

import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from beanie import init_beanie
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.sessions import SessionMiddleware

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
from app.models.org_sso_config import OrgSSOConfig
from app.models.organization import Organization, OrgMembership
from app.models.share_link import DocumentAccess, ShareLink
from app.models.user import User
from app.routes import auth, comments, documents, folders, keys, orgs, scim, sharing, users, versions, ws
from app.services.crdt_store import MongoYStore
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
]

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: DB connection, CRDT server startup/shutdown."""
    client = AsyncIOMotorClient(
        settings.mongodb_url,
        serverSelectionTimeoutMS=10_000,
        connectTimeoutMS=10_000,
    )
    db = client[settings.mongodb_db_name]
    await init_beanie(database=db, document_models=DOCUMENT_MODELS, skip_indexes=True)

    # Drop stale unique index on google_id that blocks SCIM users (google_id=null)
    with contextlib.suppress(Exception):
        await db["users"].drop_index("google_id_1")

    MongoYStore.set_database(db)
    await start_websocket_server()
    yield
    await stop_websocket_server()
    client.close()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_api(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(sharing.router)
app.include_router(versions.router)
app.include_router(documents.router)
app.include_router(folders.router)
app.include_router(keys.router)
app.include_router(comments.router)
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
async def serve_media(file_path: str):
    """Proxy media files from S3-compatible blob storage.

    Streams the object and sets appropriate Content-Type and cache headers.
    Returns 404 if the object does not exist.
    """
    from botocore.exceptions import ClientError

    from app.services.blob_storage import MIME_TYPES, _get_s3_client

    client = _get_s3_client()
    try:
        obj = client.get_object(Bucket=settings.s3_bucket, Key=file_path)
    except ClientError:
        return Response(status_code=404)

    ext = Path(file_path).suffix.lower()
    content_type = MIME_TYPES.get(ext, obj.get("ContentType", "application/octet-stream"))
    body = obj["Body"].read()
    return Response(
        content=body,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
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
