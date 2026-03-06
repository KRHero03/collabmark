"""Version history routes: create snapshots, list versions, retrieve version."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.models.document_version import (
    DocumentVersionListItem,
    DocumentVersionRead,
)
from app.models.user import User
from app.services import document_service, version_service

router = APIRouter(prefix="/api/documents", tags=["versions"])


class SnapshotCreate(BaseModel):
    """Payload for manually creating a version snapshot."""

    content: str
    summary: str = ""


@router.post(
    "/{doc_id}/versions",
    response_model=DocumentVersionRead,
    status_code=201,
)
async def create_version(
    doc_id: str,
    payload: SnapshotCreate,
    user: User = Depends(get_current_user),
):
    """Create a version snapshot for a document. Requires EDIT access.

    Returns 204 (no content) if the content is identical to the latest version
    (deduplication). Otherwise returns 201 with the new version.
    """
    await document_service.get_document(doc_id, user)
    version = await version_service.save_snapshot(
        doc_id, user, payload.content, payload.summary
    )
    if version is None:
        return JSONResponse(status_code=204, content=None)
    return DocumentVersionRead.from_doc(version)


@router.get(
    "/{doc_id}/versions",
    response_model=list[DocumentVersionListItem],
)
async def list_versions(
    doc_id: str,
    user: User = Depends(get_current_user),
):
    """List all versions for a document, newest first. Requires VIEW access."""
    await document_service.get_document(doc_id, user)
    versions = await version_service.list_versions(doc_id)
    return [DocumentVersionListItem.from_doc(v) for v in versions]


@router.get(
    "/{doc_id}/versions/{version_number}",
    response_model=DocumentVersionRead,
)
async def get_version(
    doc_id: str,
    version_number: int,
    user: User = Depends(get_current_user),
):
    """Get a specific version with full content. Requires VIEW access."""
    await document_service.get_document(doc_id, user)
    version = await version_service.get_version(doc_id, version_number)
    return DocumentVersionRead.from_doc(version)
