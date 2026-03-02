"""Version history business logic: save snapshots, list/retrieve versions."""

import logging

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.models.document import Document_
from app.models.document_version import DocumentVersion
from app.models.user import User

logger = logging.getLogger(__name__)


async def save_snapshot(
    doc_id: str, user: User, content: str, summary: str = ""
) -> DocumentVersion:
    """Save a new version snapshot for a document.

    Args:
        doc_id: The document ID.
        user: The user creating the snapshot (author).
        content: The full Markdown content at this point.
        summary: Optional human-readable summary of changes.

    Returns:
        The created DocumentVersion.

    Raises:
        HTTPException: 404 if document not found.
    """
    doc = await _find_doc_or_404(doc_id)

    latest = (
        await DocumentVersion.find(DocumentVersion.document_id == doc_id)
        .sort("-version_number")
        .first_or_none()
    )
    next_version = (latest.version_number + 1) if latest else 1

    if not summary:
        summary = f"Version {next_version} by {user.name}"

    version = DocumentVersion(
        document_id=doc_id,
        version_number=next_version,
        content=content,
        author_id=str(user.id),
        author_name=user.name,
        summary=summary,
    )
    await version.insert()
    return version


async def list_versions(doc_id: str) -> list[DocumentVersion]:
    """List all versions for a document, newest first.

    Args:
        doc_id: The document ID.

    Returns:
        List of DocumentVersion documents sorted by version_number descending.
    """
    return await (
        DocumentVersion.find(DocumentVersion.document_id == doc_id)
        .sort("-version_number")
        .to_list()
    )


async def get_version(doc_id: str, version_number: int) -> DocumentVersion:
    """Get a specific version of a document.

    Args:
        doc_id: The document ID.
        version_number: The version number to retrieve.

    Returns:
        The DocumentVersion.

    Raises:
        HTTPException: 404 if version not found.
    """
    version = await DocumentVersion.find_one(
        DocumentVersion.document_id == doc_id,
        DocumentVersion.version_number == version_number,
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} not found",
        )
    return version


async def _find_doc_or_404(doc_id: str) -> Document_:
    """Fetch a document by ID or raise 404.

    Only catches InvalidId/ValueError from malformed ObjectId strings.
    """
    try:
        doc = await Document_.get(PydanticObjectId(doc_id))
    except (InvalidId, ValueError):
        doc = None
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return doc
