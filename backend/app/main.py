"""CollabMark FastAPI application: lifespan, CORS, routes, static frontend."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from beanie import init_beanie
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
from app.models.share_link import DocumentAccess, ShareLink
from app.models.user import User
from app.models.organization import Organization, OrgMembership
from app.models.org_sso_config import OrgSSOConfig
from app.routes import auth, comments, documents, folders, keys, orgs, sharing, users, versions, ws
from app.services.crdt_store import MongoYStore
from app.ws.handler import start_websocket_server, stop_websocket_server

DOCUMENT_MODELS = [User, Document_, ApiKey, DocumentAccess, ShareLink, DocumentVersion, Comment, DocumentView, Folder, FolderAccess, FolderView, Organization, OrgMembership, OrgSSOConfig]

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
    secret_key=settings.jwt_secret_key,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(sharing.router)
app.include_router(versions.router)
app.include_router(documents.router)
app.include_router(folders.router)
app.include_router(keys.router)
app.include_router(comments.router)
app.include_router(orgs.router)
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


if STATIC_DIR.is_dir():
    _index_html = STATIC_DIR / "index.html"
    _assets_dir = STATIC_DIR / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="static-assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(request: Request, full_path: str) -> FileResponse:
        """Serve static files if they exist, otherwise serve index.html for SPA routing."""
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_index_html)
