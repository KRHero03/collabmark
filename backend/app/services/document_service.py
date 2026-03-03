"""Document CRUD business logic: create, get, list, update, soft-delete, restore, hard-delete."""

import logging

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.models.comment import Comment
from app.models.document import Document_, DocumentCreate, DocumentUpdate, GeneralAccess
from app.models.document_version import DocumentVersion
from app.models.document_view import DocumentView
from app.models.share_link import DocumentAccess, Permission
from app.models.user import User

logger = logging.getLogger(__name__)

MAX_DOCUMENTS_PER_USER = 10_000


async def create_document(owner: User, payload: DocumentCreate) -> Document_:
    """Create a new document for the owner. Enforces per-user document limit.

    Args:
        owner: The user who will own the document.
        payload: Title and content (optional with defaults).

    Returns:
        The created Document_ instance.

    Raises:
        HTTPException: 403 if owner has reached MAX_DOCUMENTS_PER_USER.
    """
    count = await Document_.find(
        Document_.owner_id == str(owner.id),
        Document_.is_deleted == False,  # noqa: E712
    ).count()
    if count >= MAX_DOCUMENTS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Document limit reached ({MAX_DOCUMENTS_PER_USER})",
        )

    doc = Document_(
        title=payload.title,
        content=payload.content,
        owner_id=str(owner.id),
    )
    await doc.insert()
    return doc


async def get_document(doc_id: str, user: User) -> Document_:
    """Fetch a document by ID. Allowed for owner or users with VIEW/EDIT access.

    Args:
        doc_id: Document ID.
        user: User requesting access.

    Returns:
        The Document_ instance.

    Raises:
        HTTPException: 404 if not found, 403 if no access.
    """
    doc = await _find_doc(doc_id)
    await _assert_access(doc, user, Permission.VIEW)
    return doc


async def list_documents(user: User, include_deleted: bool = False) -> list[Document_]:
    """List documents owned by the user, sorted by updated_at descending.

    Args:
        user: Owner whose documents to list.
        include_deleted: If True, include soft-deleted documents.

    Returns:
        List of Document_ instances.
    """
    query = Document_.find(Document_.owner_id == str(user.id))
    if not include_deleted:
        query = query.find(Document_.is_deleted == False)  # noqa: E712
    return await query.sort("-updated_at").to_list()


async def update_document(
    doc_id: str, user: User, payload: DocumentUpdate
) -> Document_:
    """Update a document's title and/or content. Owner or users with EDIT access.

    Args:
        doc_id: Document ID.
        user: User requesting update.
        payload: Fields to update. All optional.

    Returns:
        The updated Document_ instance.

    Raises:
        HTTPException: 404 if not found, 403 if no edit access.
    """
    doc = await _find_doc(doc_id)
    await _assert_access(doc, user, Permission.EDIT)

    content_changed = payload.content is not None and payload.content != doc.content

    if payload.title is not None:
        doc.title = payload.title
    if payload.content is not None:
        doc.content = payload.content
    doc.touch()
    await doc.save()

    if content_changed:
        from app.services.version_service import save_snapshot
        await save_snapshot(doc_id, user, doc.content)

    return doc


async def soft_delete_document(doc_id: str, user: User) -> Document_:
    """Soft-delete a document. Owner only.

    Args:
        doc_id: Document ID.
        user: User requesting delete (must be owner).

    Returns:
        The soft-deleted Document_ instance.

    Raises:
        HTTPException: 404 if not found, 403 if not owner.
    """
    doc = await _find_doc(doc_id)
    _assert_owner(doc, user)
    doc.soft_delete()
    await doc.save()
    return doc


async def restore_document(doc_id: str, user: User) -> Document_:
    """Restore a soft-deleted document. Owner only.

    Args:
        doc_id: Document ID.
        user: User requesting restore (must be owner).

    Returns:
        The restored Document_ instance.

    Raises:
        HTTPException: 404 if not found, 403 if not owner.
    """
    doc = await _find_doc(doc_id)
    _assert_owner(doc, user)
    doc.restore()
    await doc.save()
    return doc


async def list_trash(user: User) -> list[Document_]:
    """List soft-deleted documents owned by the user, sorted by deleted_at descending.

    Args:
        user: Owner whose trashed documents to list.

    Returns:
        List of soft-deleted Document_ instances.
    """
    return await Document_.find(
        Document_.owner_id == str(user.id),
        Document_.is_deleted == True,  # noqa: E712
    ).sort("-deleted_at").to_list()


async def hard_delete_document(doc_id: str, user: User) -> None:
    """Permanently delete a document and all related data. Owner only.

    Removes the document record plus associated CRDT updates, comments,
    versions, collaborator access records, and view records.

    Args:
        doc_id: Document ID.
        user: User requesting delete (must be owner).

    Raises:
        HTTPException: 404 if not found, 403 if not owner.
    """
    doc = await _find_doc(doc_id)
    _assert_owner(doc, user)

    str_id = str(doc.id)

    await Comment.find(Comment.document_id == str_id).delete()
    await DocumentVersion.find(DocumentVersion.document_id == str_id).delete()
    await DocumentAccess.find(DocumentAccess.document_id == str_id).delete()
    await DocumentView.find(DocumentView.document_id == str_id).delete()

    from app.services.crdt_store import MongoYStore
    if MongoYStore._db is not None:
        await MongoYStore._db["crdt_updates"].delete_many({"room": str_id})

    await doc.delete()
    logger.info("Hard-deleted document %s and related data", str_id)


async def _find_doc(doc_id: str) -> Document_:
    """Fetch a document by ID or raise 404.

    Only catches InvalidId/ValueError from malformed ObjectId strings.
    Other exceptions (e.g. database errors) propagate immediately.
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


def _assert_owner(doc: Document_, user: User) -> None:
    if doc.owner_id != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this document",
        )


async def _assert_access(
    doc: Document_, user: User, min_permission: Permission
) -> None:
    """Check that user is owner, has explicit DocumentAccess, or is covered
    by the document's general_access setting.

    Priority: owner > explicit DocumentAccess > general_access > deny.

    Args:
        doc: The document to check access for.
        user: The user requesting access.
        min_permission: Minimum required permission level.

    Raises:
        HTTPException: 403 if access is insufficient.
    """
    if doc.owner_id == str(user.id):
        return

    access = await DocumentAccess.find_one(
        DocumentAccess.document_id == str(doc.id),
        DocumentAccess.user_id == str(user.id),
    )

    if access is not None:
        if min_permission == Permission.EDIT and access.permission == Permission.VIEW:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You only have view access to this document",
            )
        access.touch_access()
        await access.save()
        return

    ga = doc.general_access
    if ga == GeneralAccess.ANYONE_EDIT:
        return
    if ga == GeneralAccess.ANYONE_VIEW and min_permission == Permission.VIEW:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access this document",
    )
