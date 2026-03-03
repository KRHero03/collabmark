"""Version history business logic: save snapshots, list/retrieve versions."""

import logging

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.models.document import Document_
from app.models.document_version import DocumentVersion
from app.models.user import User

logger = logging.getLogger(__name__)

MAX_DEDUP_RETRIES = 2


async def save_snapshot(
    doc_id: str, user: User, content: str, summary: str = ""
) -> DocumentVersion | None:
    """Save a new version snapshot for a document.

    Deduplicates: if the content is identical to the latest snapshot,
    no new version is created and None is returned. Uses a unique
    compound index on (document_id, version_number) to handle
    concurrent inserts safely via retry.

    Args:
        doc_id: The document ID.
        user: The user creating the snapshot (author).
        content: The full Markdown content at this point.
        summary: Optional human-readable summary of changes.

    Returns:
        The created DocumentVersion, or None if content is unchanged.

    Raises:
        HTTPException: 404 if document not found.
    """
    doc = await _find_doc_or_404(doc_id)

    for _attempt in range(MAX_DEDUP_RETRIES + 1):
        latest = (
            await DocumentVersion.find(DocumentVersion.document_id == doc_id)
            .sort("-version_number")
            .first_or_none()
        )

        if latest is not None and latest.content == content:
            return None

        next_version = (latest.version_number + 1) if latest else 1
        resolved_summary = summary or f"Version {next_version} by {user.name}"

        version = DocumentVersion(
            document_id=doc_id,
            version_number=next_version,
            content=content,
            author_id=str(user.id),
            author_name=user.name,
            summary=resolved_summary,
        )
        try:
            await version.insert()
            return version
        except DuplicateKeyError:
            logger.info(
                "Version %d for doc %s already exists, retrying",
                next_version,
                doc_id,
            )
            continue

    logger.warning("Failed to insert version for doc %s after retries", doc_id)
    return None


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
