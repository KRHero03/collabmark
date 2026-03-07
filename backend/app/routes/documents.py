"""Document CRUD routes: create, list, get, update, delete, restore, trash, hard-delete, ACL."""

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.models.document import DocumentCreate, DocumentRead, DocumentUpdate
from app.models.user import User
from app.services import document_service
from app.services.acl_service import get_acl_summary
from app.utils.owner_resolver import resolve_owner

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", response_model=DocumentRead, status_code=201)
async def create_document(
    payload: DocumentCreate,
    user: User = Depends(get_current_user),
):
    """Create a new document owned by the current user.

    Args:
        payload: Title and content (optional with defaults).
        user: Injected by get_current_user dependency.

    Returns:
        DocumentRead of the created document.
    """
    doc = await document_service.create_document(user, payload)
    return DocumentRead.from_doc(
        doc, owner_name=user.name or "", owner_email=user.email or "", owner_avatar_url=user.avatar_url
    )


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    include_deleted: bool = Query(False),
    user: User = Depends(get_current_user),
):
    """List documents owned by the current user, sorted by updated_at desc.

    Args:
        include_deleted: If True, include soft-deleted documents.
        user: Injected by get_current_user dependency.

    Returns:
        List of DocumentRead for the user's documents.
    """
    docs = await document_service.list_documents(user, include_deleted)
    return [
        DocumentRead.from_doc(
            d, owner_name=user.name or "", owner_email=user.email or "", owner_avatar_url=user.avatar_url
        )
        for d in docs
    ]


@router.get("/trash", response_model=list[DocumentRead])
async def list_trash(
    user: User = Depends(get_current_user),
):
    """List soft-deleted documents owned by the current user.

    Returns documents sorted by deleted_at descending (most recently
    trashed first).

    Args:
        user: Injected by get_current_user dependency.

    Returns:
        List of DocumentRead for the user's trashed documents.
    """
    docs = await document_service.list_trash(user)
    return [
        DocumentRead.from_doc(
            d, owner_name=user.name or "", owner_email=user.email or "", owner_avatar_url=user.avatar_url
        )
        for d in docs
    ]


@router.get("/{doc_id}", response_model=DocumentRead)
async def get_document(
    doc_id: str,
    user: User = Depends(get_current_user),
):
    """Get a single document by ID. Owner only.

    Args:
        doc_id: Document ID.
        user: Injected by get_current_user dependency.

    Returns:
        DocumentRead of the document.

    Raises:
        HTTPException: 404 if not found, 403 if not owner.
    """
    doc = await document_service.get_document(doc_id, user)
    name, email, avatar = await resolve_owner(doc.owner_id)
    return DocumentRead.from_doc(doc, owner_name=name, owner_email=email, owner_avatar_url=avatar)


@router.put("/{doc_id}", response_model=DocumentRead)
async def update_document(
    doc_id: str,
    payload: DocumentUpdate,
    user: User = Depends(get_current_user),
):
    """Update a document's title and/or content. Owner only.

    Args:
        doc_id: Document ID.
        payload: Fields to update. All optional.
        user: Injected by get_current_user dependency.

    Returns:
        DocumentRead of the updated document.

    Raises:
        HTTPException: 404 if not found, 403 if not owner.
    """
    doc = await document_service.update_document(doc_id, user, payload)
    name, email, avatar = await resolve_owner(doc.owner_id)
    return DocumentRead.from_doc(doc, owner_name=name, owner_email=email, owner_avatar_url=avatar)


@router.delete("/{doc_id}", response_model=DocumentRead)
async def delete_document(
    doc_id: str,
    user: User = Depends(get_current_user),
):
    """Soft-delete a document. Owner only.

    Args:
        doc_id: Document ID.
        user: Injected by get_current_user dependency.

    Returns:
        DocumentRead of the soft-deleted document.

    Raises:
        HTTPException: 404 if not found, 403 if not owner.
    """
    doc = await document_service.soft_delete_document(doc_id, user)
    return DocumentRead.from_doc(
        doc, owner_name=user.name or "", owner_email=user.email or "", owner_avatar_url=user.avatar_url
    )


@router.post("/{doc_id}/restore", response_model=DocumentRead)
async def restore_document(
    doc_id: str,
    user: User = Depends(get_current_user),
):
    """Restore a soft-deleted document. Owner only.

    Args:
        doc_id: Document ID.
        user: Injected by get_current_user dependency.

    Returns:
        DocumentRead of the restored document.

    Raises:
        HTTPException: 404 if not found, 403 if not owner.
    """
    doc = await document_service.restore_document(doc_id, user)
    return DocumentRead.from_doc(
        doc, owner_name=user.name or "", owner_email=user.email or "", owner_avatar_url=user.avatar_url
    )


@router.delete("/{doc_id}/permanent", status_code=204)
async def hard_delete_document(
    doc_id: str,
    user: User = Depends(get_current_user),
):
    """Permanently delete a document and all related data. Owner only.

    Removes the document, its CRDT updates, comments, versions,
    collaborator access records, and view tracking records.

    Args:
        doc_id: Document ID.
        user: Injected by get_current_user dependency.

    Raises:
        HTTPException: 404 if not found, 403 if not owner.
    """
    await document_service.hard_delete_document(doc_id, user)


@router.get("/{doc_id}/acl")
async def get_document_acl(
    doc_id: str,
    user: User = Depends(get_current_user),
):
    """Get consolidated ACL for a document showing all users with effective permissions."""
    await document_service.get_document(doc_id, user)
    entries = await get_acl_summary("document", doc_id)
    return [
        {
            "user_id": e.user_id,
            "user_name": e.user_name,
            "user_email": e.user_email,
            "avatar_url": e.avatar_url,
            "can_view": e.can_view,
            "can_edit": e.can_edit,
            "can_delete": e.can_delete,
            "can_share": e.can_share,
            "role": e.role,
            "inherited_from_id": e.inherited_from_id,
            "inherited_from_name": e.inherited_from_name,
        }
        for e in entries
    ]
