"""Sharing routes: collaborator management, general access, shared/recent docs list."""

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.models.document import Document_, DocumentRead
from app.models.document_view import RecentlyViewedRead
from app.models.group import AddGroupCollaboratorPayload, GroupCollaboratorRead
from app.models.share_link import (
    CollaboratorAdd,
    CollaboratorRead,
    GeneralAccessUpdate,
    SharedDocumentRead,
)
from app.models.user import User
from app.services import group_sharing_service, share_service

router = APIRouter(tags=["sharing"])


@router.put("/api/documents/{doc_id}/access", response_model=DocumentRead)
async def update_general_access(
    doc_id: str,
    payload: GeneralAccessUpdate,
    user: User = Depends(get_current_user),
):
    """Update the document's general access setting. Owner only.

    Args:
        doc_id: Document ID.
        payload: New general_access value.
        user: Injected by get_current_user dependency.

    Returns:
        Updated DocumentRead.
    """
    doc = await share_service.update_general_access(doc_id, user, payload.general_access)
    return DocumentRead.from_doc(
        doc, owner_name=user.name or "", owner_email=user.email or "", owner_avatar_url=user.avatar_url
    )


@router.post(
    "/api/documents/{doc_id}/collaborators",
    response_model=CollaboratorRead,
    status_code=201,
)
async def add_collaborator(
    doc_id: str,
    payload: CollaboratorAdd,
    user: User = Depends(get_current_user),
):
    """Add a collaborator by email with specified permission. Owner only.

    Args:
        doc_id: Document ID.
        payload: Email and permission level.
        user: Injected by get_current_user dependency.

    Returns:
        CollaboratorRead with user info and permission.
    """
    access = await share_service.add_collaborator(doc_id, user, payload.email, payload.permission)
    collab_user = await User.get(PydanticObjectId(access.user_id))
    return CollaboratorRead(
        id=str(access.id),
        user_id=str(collab_user.id),
        email=collab_user.email,
        name=collab_user.name,
        avatar_url=collab_user.avatar_url,
        permission=access.permission,
        granted_at=access.granted_at,
    )


@router.get(
    "/api/documents/{doc_id}/collaborators",
    response_model=list[CollaboratorRead],
)
async def list_collaborators(
    doc_id: str,
    user: User = Depends(get_current_user),
):
    """List all collaborators for a document. Owner only.

    Args:
        doc_id: Document ID.
        user: Injected by get_current_user dependency.

    Returns:
        List of CollaboratorRead.
    """
    items = await share_service.list_collaborators(doc_id, user)
    return [CollaboratorRead(**item) for item in items]


@router.delete(
    "/api/documents/{doc_id}/collaborators/{user_id}",
    status_code=204,
)
async def remove_collaborator(
    doc_id: str,
    user_id: str,
    user: User = Depends(get_current_user),
):
    """Remove a collaborator's access. Owner only.

    Args:
        doc_id: Document ID.
        user_id: The collaborator's user ID.
        user: Injected by get_current_user dependency.
    """
    await share_service.remove_collaborator(doc_id, user, user_id)


@router.get("/api/documents/{doc_id}/permission")
async def get_my_permission(
    doc_id: str,
    user: User = Depends(get_current_user),
):
    """Return the current user's permission level on a document.

    Args:
        doc_id: Document ID.
        user: Injected by get_current_user dependency.

    Returns:
        Dict with ``permission`` key ("edit" or "view"), or 403 if no access.
    """
    perm = await share_service.get_user_permission(doc_id, user)
    if perm is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this document",
        )
    return {"permission": perm.value}


@router.get(
    "/api/documents/shared",
    response_model=list[SharedDocumentRead],
)
async def list_shared_documents(
    user: User = Depends(get_current_user),
):
    """List documents shared with the current user, sorted by recency.

    Args:
        user: Injected by get_current_user dependency.

    Returns:
        List of SharedDocumentRead.
    """
    items = await share_service.list_shared_documents(user)
    return [
        SharedDocumentRead(
            id=str(item["document"].id),
            title=item["document"].title,
            content=item["document"].content,
            owner_id=item["document"].owner_id,
            permission=item["permission"],
            last_accessed_at=item["last_accessed_at"],
            created_at=item["document"].created_at,
            updated_at=item["document"].updated_at,
        )
        for item in items
    ]


@router.post("/api/documents/{doc_id}/view", status_code=204)
async def record_view(
    doc_id: str,
    user: User = Depends(get_current_user),
):
    """Record that the current user viewed a document. Requires VIEW access."""
    perm = await share_service.get_user_permission(doc_id, user)
    if perm is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this document",
        )
    await share_service.record_document_view(doc_id, user)


@router.get(
    "/api/documents/recent",
    response_model=list[RecentlyViewedRead],
)
async def list_recently_viewed(
    user: User = Depends(get_current_user),
):
    """List all documents recently viewed by the current user (including owned).

    Args:
        user: Injected by get_current_user dependency.

    Returns:
        List of RecentlyViewedRead sorted by most recently viewed.
    """
    items = await share_service.list_recently_viewed(user)
    return [
        RecentlyViewedRead(
            id=str(item["document"].id),
            title=item["document"].title,
            owner_id=item["document"].owner_id,
            owner_name=item["owner_name"],
            owner_email=item["owner_email"],
            permission=item["permission"],
            viewed_at=item["viewed_at"],
            created_at=item["document"].created_at,
            updated_at=item["document"].updated_at,
        )
        for item in items
    ]


# ---------------------------------------------------------------------------
# Group collaborators (documents)
# ---------------------------------------------------------------------------


@router.post(
    "/api/documents/{doc_id}/group-collaborators",
    response_model=GroupCollaboratorRead,
    status_code=201,
)
async def add_document_group_collaborator(
    doc_id: str,
    payload: AddGroupCollaboratorPayload,
    user: User = Depends(get_current_user),
):
    """Add a group as a collaborator on a document. Owner only."""
    doc = await Document_.get(PydanticObjectId(doc_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return await group_sharing_service.add_group_collaborator(
        "document", doc_id, doc.owner_id, user, payload.group_id, payload.permission
    )


@router.get(
    "/api/documents/{doc_id}/group-collaborators",
    response_model=list[GroupCollaboratorRead],
)
async def list_document_group_collaborators(
    doc_id: str,
    user: User = Depends(get_current_user),
):
    """List groups that have access to a document. Requires VIEW access."""
    doc = await Document_.get(PydanticObjectId(doc_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    perm = await share_service.get_user_permission(doc_id, user)
    if perm is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this document",
        )
    return await group_sharing_service.list_group_collaborators("document", doc_id)


@router.delete(
    "/api/documents/{doc_id}/group-collaborators/{group_id}",
    status_code=204,
)
async def remove_document_group_collaborator(
    doc_id: str,
    group_id: str,
    user: User = Depends(get_current_user),
):
    """Remove a group's access to a document. Owner only."""
    doc = await Document_.get(PydanticObjectId(doc_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await group_sharing_service.remove_group_collaborator("document", doc_id, doc.owner_id, str(user.id), group_id)
