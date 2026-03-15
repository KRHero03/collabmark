"""Sharing business logic: share links, document access, permission checks, recently viewed."""

import logging
from datetime import UTC, datetime

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.models.document import Document_, GeneralAccess
from app.models.document_view import DocumentView
from app.models.notification import NotificationEvent
from app.models.share_link import DocumentAccess, Permission, ShareLink
from app.models.user import User
from app.services.acl_service import get_base_permission
from app.services.notification_dispatcher import get_dispatcher

logger = logging.getLogger(__name__)


async def create_share_link(
    doc_id: str,
    user: User,
    permission: Permission = Permission.VIEW,
    expires_at: datetime | None = None,
) -> ShareLink:
    """Create a share link for a document. Only the owner may create links.

    Args:
        doc_id: The document ID to share.
        user: The requesting user (must be owner).
        permission: VIEW or EDIT access level.
        expires_at: Optional expiration timestamp (UTC).

    Returns:
        The created ShareLink.

    Raises:
        HTTPException: 404 if document not found, 403 if not owner.
    """
    doc = await _find_doc_or_404(doc_id)
    _assert_owner(doc, user)

    link = ShareLink(
        document_id=doc_id,
        token=ShareLink.generate_token(),
        permission=permission,
        created_by=str(user.id),
        expires_at=expires_at,
    )
    await link.insert()
    return link


async def list_share_links(doc_id: str, user: User) -> list[ShareLink]:
    """List all active share links for a document. Owner only.

    Args:
        doc_id: The document ID.
        user: The requesting user (must be owner).

    Returns:
        List of ShareLink documents.

    Raises:
        HTTPException: 404 if document not found, 403 if not owner.
    """
    doc = await _find_doc_or_404(doc_id)
    _assert_owner(doc, user)
    return await ShareLink.find(ShareLink.document_id == doc_id).to_list()


async def revoke_share_link(link_id: str, user: User) -> None:
    """Delete a share link. Owner of the parent document only.

    Args:
        link_id: The ShareLink document ID.
        user: The requesting user (must be document owner).

    Raises:
        HTTPException: 404 if link not found, 403 if not owner.
    """
    try:
        link = await ShareLink.get(PydanticObjectId(link_id))
    except (InvalidId, ValueError):
        link = None
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found",
        )

    doc = await _find_doc_or_404(link.document_id)
    _assert_owner(doc, user)
    await link.delete()


async def resolve_share_link(token: str) -> tuple[ShareLink, Document_]:
    """Look up a share link by token, validate expiry, return link and document.

    Args:
        token: The share link token.

    Returns:
        Tuple of (ShareLink, Document_).

    Raises:
        HTTPException: 404 if token invalid/expired, or document not found.
    """
    link = await ShareLink.find_one(ShareLink.token == token)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found or expired",
        )

    if link.expires_at:
        now = datetime.now(UTC)
        expires_at = link.expires_at if link.expires_at.tzinfo else link.expires_at.replace(tzinfo=UTC)
        if expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Share link has expired",
            )

    doc = await _find_doc_or_404(link.document_id)
    if doc.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document has been deleted",
        )

    return link, doc


async def accept_share_link(token: str, user: User) -> tuple[Document_, Permission]:
    """Accept a share link: create/update DocumentAccess for the user.

    Args:
        token: The share link token.
        user: The user accepting the share.

    Returns:
        Tuple of (Document_, Permission granted).

    Raises:
        HTTPException: 404 if token invalid/expired.
    """
    link, doc = await resolve_share_link(token)

    existing = await DocumentAccess.find_one(
        DocumentAccess.document_id == link.document_id,
        DocumentAccess.user_id == str(user.id),
    )

    if existing:
        if link.permission == Permission.EDIT and existing.permission == Permission.VIEW:
            existing.permission = Permission.EDIT
        existing.touch_access()
        await existing.save()
    else:
        access = DocumentAccess(
            document_id=link.document_id,
            user_id=str(user.id),
            permission=link.permission,
            granted_by=link.created_by,
        )
        await access.insert()

    return doc, link.permission


async def list_shared_documents(user: User) -> list[dict]:
    """List documents shared with the user, sorted by last_accessed_at desc.

    Args:
        user: The user whose shared documents to list.

    Returns:
        List of dicts with document data and permission level.
    """
    accesses = (
        await DocumentAccess.find(
            DocumentAccess.user_id == str(user.id),
        )
        .sort("-last_accessed_at")
        .to_list()
    )

    results = []
    for access in accesses:
        try:
            doc = await Document_.get(PydanticObjectId(access.document_id))
        except (InvalidId, ValueError):
            continue
        if doc is None or doc.is_deleted:
            continue
        results.append(
            {
                "document": doc,
                "permission": access.permission,
                "last_accessed_at": access.last_accessed_at,
            }
        )
    return results


async def get_user_permission(doc_id: str, user: User) -> Permission | None:
    """Check if a user has access to a document.

    Priority: owner (EDIT) > explicit DocumentAccess > folder chain inheritance > general_access > None.
    Org boundary is enforced on general_access checks.

    Args:
        doc_id: The document ID.
        user: The user to check.

    Returns:
        Permission level, or None if no access.
    """
    return await get_base_permission("document", doc_id, str(user.id), user.org_id)


async def update_general_access(doc_id: str, user: User, general_access: str) -> Document_:
    """Update the document's general_access setting. Owner only.

    Args:
        doc_id: The document ID.
        user: The requesting user (must be owner).
        general_access: One of "restricted", "anyone_view", "anyone_edit".

    Returns:
        The updated Document_.

    Raises:
        HTTPException: 404 if document not found, 403 if not owner, 400 if invalid value.
    """
    doc = await _find_doc_or_404(doc_id)
    _assert_owner(doc, user)

    try:
        doc.general_access = GeneralAccess(general_access)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid general_access value: {general_access}. "
            f"Must be one of: restricted, anyone_view, anyone_edit",
        ) from exc

    doc.touch()
    await doc.save()
    return doc


async def add_collaborator(doc_id: str, owner: User, email: str, permission: Permission) -> DocumentAccess:
    """Add a collaborator by email. Creates or updates a DocumentAccess record.

    Args:
        doc_id: The document ID.
        owner: The requesting user (must be owner).
        email: The collaborator's email address.
        permission: VIEW or EDIT.

    Returns:
        The created/updated DocumentAccess record.

    Raises:
        HTTPException: 404 if document/user not found, 403 if not owner,
                       400 if trying to add self.
    """
    doc = await _find_doc_or_404(doc_id)
    _assert_owner(doc, owner)

    target_user = await User.find_one(User.email == email)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user found with email: {email}",
        )

    if str(target_user.id) == str(owner.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add yourself as a collaborator",
        )

    if doc.org_id is not None and target_user.org_id != doc.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot share with users outside your organization",
        )

    existing = await DocumentAccess.find_one(
        DocumentAccess.document_id == doc_id,
        DocumentAccess.user_id == str(target_user.id),
    )

    if existing:
        existing.permission = permission
        existing.touch_access()
        await existing.save()
        return existing

    access = DocumentAccess(
        document_id=doc_id,
        user_id=str(target_user.id),
        permission=permission,
        granted_by=str(owner.id),
    )
    await access.insert()

    await _schedule_share_notification(access, doc, owner, target_user)

    return access


async def list_collaborators(doc_id: str, user: User) -> list[dict]:
    """List all explicit collaborators on a document. Owner only.

    Args:
        doc_id: The document ID.
        user: The requesting user (must be owner).

    Returns:
        List of dicts with user info and permission.
    """
    doc = await _find_doc_or_404(doc_id)
    _assert_owner(doc, user)

    accesses = (
        await DocumentAccess.find(
            DocumentAccess.document_id == doc_id,
        )
        .sort("-granted_at")
        .to_list()
    )

    results = []
    for access in accesses:
        try:
            collab_user = await User.get(PydanticObjectId(access.user_id))
        except (InvalidId, ValueError):
            continue
        if collab_user is None:
            continue
        results.append(
            {
                "id": str(access.id),
                "user_id": str(collab_user.id),
                "email": collab_user.email,
                "name": collab_user.name,
                "avatar_url": collab_user.avatar_url,
                "permission": access.permission,
                "granted_at": access.granted_at,
            }
        )
    return results


async def remove_collaborator(doc_id: str, owner: User, user_id: str) -> None:
    """Remove a collaborator's access to a document. Owner only.

    Args:
        doc_id: The document ID.
        owner: The requesting user (must be owner).
        user_id: The user ID of the collaborator to remove.

    Raises:
        HTTPException: 404 if document/access not found, 403 if not owner.
    """
    doc = await _find_doc_or_404(doc_id)
    _assert_owner(doc, owner)

    access = await DocumentAccess.find_one(
        DocumentAccess.document_id == doc_id,
        DocumentAccess.user_id == user_id,
    )
    if access is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collaborator access record not found",
        )

    await access.delete()


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


async def record_document_view(doc_id: str, user: User) -> None:
    """Record that a user viewed a document (including their own).

    Creates or updates a DocumentView record.

    Args:
        doc_id: The document ID.
        user: The user viewing the document.
    """
    try:
        doc = await Document_.get(PydanticObjectId(doc_id))
    except (InvalidId, ValueError):
        return
    if doc is None:
        return

    existing = await DocumentView.find_one(
        DocumentView.user_id == str(user.id),
        DocumentView.document_id == doc_id,
    )
    if existing:
        existing.viewed_at = datetime.now(UTC)
        await existing.save()
    else:
        view = DocumentView(
            user_id=str(user.id),
            document_id=doc_id,
        )
        await view.insert()


async def list_recently_viewed(user: User) -> list[dict]:
    """List all documents recently viewed by the user (including their own).

    Returns documents sorted by most recently viewed first.

    Args:
        user: The user whose recently viewed documents to list.

    Returns:
        List of dicts with document data, permission, and view time.
    """
    views = (
        await DocumentView.find(
            DocumentView.user_id == str(user.id),
        )
        .sort("-viewed_at")
        .to_list()
    )

    results = []
    for view in views:
        try:
            doc = await Document_.get(PydanticObjectId(view.document_id))
        except (InvalidId, ValueError):
            continue
        if doc is None or doc.is_deleted:
            continue

        perm = await get_user_permission(str(doc.id), user)
        if perm is None:
            continue

        try:
            owner = await User.get(PydanticObjectId(doc.owner_id))
        except (InvalidId, ValueError):
            owner = None

        results.append(
            {
                "document": doc,
                "permission": perm.value,
                "viewed_at": view.viewed_at,
                "owner_name": owner.name if owner else "Unknown",
                "owner_email": owner.email if owner else "",
            }
        )
    return results


async def _schedule_share_notification(access: DocumentAccess, doc: Document_, owner: User, target_user: User) -> None:
    """Schedule a delayed document_shared notification for the target user."""
    try:
        dispatcher = get_dispatcher()
    except RuntimeError:
        return
    try:
        await dispatcher.schedule(
            event_type=NotificationEvent.DOCUMENT_SHARED,
            recipients=[
                {
                    "user_id": str(target_user.id),
                    "email": target_user.email,
                    "name": target_user.name,
                }
            ],
            action_ref_id=str(access.id),
            document_id=str(doc.id),
            payload={
                "recipient_name": target_user.name,
                "shared_by": owner.name,
                "document_title": doc.title,
                "document_id": str(doc.id),
                "permission": access.permission.value,
            },
        )
    except Exception:
        logger.exception("Failed to schedule share notification")


def _assert_owner(doc: Document_, user: User) -> None:
    """Raise 403 if user is not the document owner."""
    if doc.owner_id != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the document owner can perform this action",
        )
