"""Document CRUD business logic: create, get, list, update, soft-delete, restore, hard-delete."""

import logging
import uuid
from pathlib import Path

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.models.comment import Comment
from app.models.document import Document_, DocumentCreate, DocumentUpdate, GeneralAccess
from app.models.document_version import DocumentVersion
from app.models.document_view import DocumentView
from app.models.share_link import DocumentAccess, Permission
from app.models.user import User
from app.services import blob_storage

logger = logging.getLogger(__name__)

MAX_DOCUMENTS_PER_USER = 10_000
IMAGE_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
IMAGE_MAX_SIZE = 5 * 1024 * 1024  # 5MB


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
        Document_.is_deleted == False,
    ).count()
    if count >= MAX_DOCUMENTS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Document limit reached ({MAX_DOCUMENTS_PER_USER})",
        )

    root_folder_id: str | None = None
    if payload.folder_id is not None:
        from app.services.folder_service import _assert_folder_access, _find_folder

        folder = await _find_folder(payload.folder_id)
        await _assert_folder_access(folder, owner, Permission.EDIT)
        if owner.org_id is not None and getattr(folder, "org_id", None) != owner.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create document in a folder from a different organization",
            )
        root_folder_id = folder.root_folder_id or str(folder.id)

    doc = Document_(
        title=payload.title,
        content=payload.content,
        owner_id=str(owner.id),
        folder_id=payload.folder_id,
        root_folder_id=root_folder_id,
        org_id=owner.org_id,
    )
    await doc.insert()
    return doc


async def upload_document_image(doc_id: str, user: User, filename: str, contents: bytes) -> dict[str, str]:
    """Upload an image for a document. Requires EDIT permission.

    Returns:
        Dict with "url" and "name" of the stored image.

    Raises:
        HTTPException: 400 for invalid file type/size, 403/404 for access.
    """
    ext = Path(filename).suffix.lower()
    if ext not in IMAGE_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type. Allowed: {', '.join(IMAGE_ALLOWED_EXTENSIONS)}",
        )
    if len(contents) > IMAGE_MAX_SIZE:
        raise HTTPException(status_code=400, detail="Image too large. Maximum size is 5MB.")

    doc = await _find_doc(doc_id)
    await _assert_access(doc, user, Permission.EDIT)

    image_name = f"{uuid.uuid4().hex}{ext}"
    key = f"documents/{doc_id}/{image_name}"
    content_type = blob_storage.MIME_TYPES.get(ext, "application/octet-stream")
    blob_storage.upload(key, contents, content_type)

    url = blob_storage.get_public_url(key)
    return {"url": url, "name": image_name}


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
        query = query.find(Document_.is_deleted == False)
    return await query.sort("-updated_at").to_list()


async def update_document(doc_id: str, user: User, payload: DocumentUpdate) -> Document_:
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
    if payload.folder_id is not None:
        from app.services.folder_service import _assert_folder_access, _find_folder

        target_folder = await _find_folder(payload.folder_id)
        await _assert_folder_access(target_folder, user, Permission.EDIT)
        if doc.org_id is not None and getattr(target_folder, "org_id", None) != doc.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot move document to a folder in a different organization",
            )
        doc.folder_id = payload.folder_id
        doc.root_folder_id = target_folder.root_folder_id or str(target_folder.id)
    doc.touch()
    await doc.save()

    if content_changed:
        from app.services.version_service import save_snapshot

        await save_snapshot(doc_id, user, doc.content)

    return doc


async def soft_delete_document(doc_id: str, user: User) -> Document_:
    """Soft-delete a document. Requires delete permission (ACL-aware)."""
    doc = await _find_doc(doc_id)
    await _assert_can_delete(doc, user)
    doc.soft_delete()
    await doc.save()
    return doc


async def restore_document(doc_id: str, user: User) -> Document_:
    """Restore a soft-deleted document. Requires delete permission (ACL-aware)."""
    doc = await _find_doc(doc_id)
    await _assert_can_delete(doc, user)
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
    return (
        await Document_.find(
            Document_.owner_id == str(user.id),
            Document_.is_deleted == True,
        )
        .sort(["-deleted_at", "-_id"])
        .to_list()
    )


async def hard_delete_document(doc_id: str, user: User) -> None:
    """Permanently delete a document and all related data. Requires delete permission (ACL-aware)."""
    doc = await _find_doc(doc_id)
    await _assert_can_delete(doc, user)

    str_id = str(doc.id)

    await Comment.find(Comment.document_id == str_id).delete()
    await DocumentVersion.find(DocumentVersion.document_id == str_id).delete()
    await DocumentAccess.find(DocumentAccess.document_id == str_id).delete()
    await DocumentView.find(DocumentView.document_id == str_id).delete()

    from app.services.crdt_store import MongoYStore

    if MongoYStore._db is not None:
        await MongoYStore._db["crdt_updates"].delete_many({"room": str_id})

    blob_storage.delete_prefix(f"documents/{str_id}/")

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


async def _assert_can_delete(doc: Document_, user: User) -> None:
    """ACL-aware delete check: root owner or entity owner (for docs, always deletable by owner)."""
    from app.services.acl_service import resolve_effective_permission

    perm = await resolve_effective_permission("document", str(doc.id), user)
    if not perm.can_delete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this document",
        )


async def _assert_access(doc: Document_, user: User, min_permission: Permission) -> None:
    """Check that user is owner, has explicit DocumentAccess, inherits access
    from a parent folder, or is covered by the document's general_access setting.

    Priority: owner > explicit DocumentAccess > folder chain inheritance > general_access > deny.

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

    if doc.folder_id is not None:
        from app.services.folder_service import get_folder_permission

        folder_perm = await get_folder_permission(doc.folder_id, user)
        if folder_perm is not None:
            if min_permission == Permission.EDIT and folder_perm == Permission.VIEW:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You only have view access via the parent folder",
                )
            return

    from app.services.acl_service import org_allows_general_access

    if org_allows_general_access(getattr(doc, "org_id", None), user.org_id):
        ga = doc.general_access
        if ga == GeneralAccess.ANYONE_EDIT:
            return
        if ga == GeneralAccess.ANYONE_VIEW and min_permission == Permission.VIEW:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access this document",
    )
