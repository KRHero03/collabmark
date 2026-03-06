"""Folder (Space) CRUD business logic with cascade soft-delete/restore/hard-delete and access control."""

import logging

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from datetime import datetime, timezone

from app.models.document import Document_, GeneralAccess
from app.models.folder import Folder, FolderAccess, FolderCreate, FolderUpdate, FolderView
from app.models.share_link import Permission
from app.models.user import User

logger = logging.getLogger(__name__)

MAX_FOLDERS_PER_USER = 5_000
MAX_FOLDER_DEPTH = 20


async def create_folder(owner: User, payload: FolderCreate) -> Folder:
    count = await Folder.find(
        Folder.owner_id == str(owner.id),
        Folder.is_deleted == False,  # noqa: E712
    ).count()
    if count >= MAX_FOLDERS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Folder limit reached ({MAX_FOLDERS_PER_USER})",
        )

    root_folder_id: str | None = None
    if payload.parent_id is not None:
        parent = await _find_folder(payload.parent_id)
        await _assert_folder_access(parent, owner, Permission.EDIT)
        await _check_depth(payload.parent_id, 1)
        root_folder_id = parent.root_folder_id or str(parent.id)

    folder = Folder(
        name=payload.name,
        owner_id=str(owner.id),
        parent_id=payload.parent_id,
        root_folder_id=root_folder_id,
        org_id=owner.org_id,
    )
    await folder.insert()

    if root_folder_id is None:
        folder.root_folder_id = str(folder.id)
        await folder.save()

    return folder


async def get_folder(folder_id: str, user: User) -> Folder:
    folder = await _find_folder(folder_id)
    await _assert_folder_access(folder, user, Permission.VIEW)
    return folder


async def list_folders(
    user: User, parent_id: str | None = None
) -> list[Folder]:
    """List non-deleted folders owned by the user at a given level."""
    query = {
        "owner_id": str(user.id),
        "is_deleted": False,
        "parent_id": parent_id,
    }
    return await Folder.find(query).sort("-updated_at").to_list()


async def list_shared_folders(user: User) -> list[dict]:
    """List folders shared with the user via FolderAccess, with owner info."""
    accesses = await FolderAccess.find(
        FolderAccess.user_id == str(user.id),
    ).sort("-last_accessed_at").to_list()

    results = []
    for access in accesses:
        try:
            folder = await Folder.get(PydanticObjectId(access.folder_id))
        except (InvalidId, ValueError):
            continue
        if folder is None or folder.is_deleted:
            continue
        try:
            owner = await User.get(PydanticObjectId(folder.owner_id))
        except (InvalidId, ValueError):
            owner = None
        results.append({
            "folder": folder,
            "permission": access.permission,
            "last_accessed_at": access.last_accessed_at,
            "owner_name": owner.name if owner else "Unknown",
            "owner_email": owner.email if owner else "",
        })
    return results


async def update_folder(
    folder_id: str, user: User, payload: FolderUpdate
) -> Folder:
    folder = await _find_folder(folder_id)
    await _assert_folder_access(folder, user, Permission.EDIT)

    if payload.name is not None:
        folder.name = payload.name

    if payload.parent_id is not None:
        if payload.parent_id == folder_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A folder cannot be its own parent",
            )
        if await _is_descendant(payload.parent_id, folder_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot move a folder into one of its descendants",
            )
        await _check_depth(payload.parent_id, await _subtree_depth(folder_id))
        folder.parent_id = payload.parent_id

    if payload.general_access is not None:
        if folder.owner_id != str(user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the owner can change general access",
            )
        folder.general_access = payload.general_access

    folder.touch()
    await folder.save()
    return folder


async def soft_delete_folder(folder_id: str, user: User) -> Folder:
    """Cascade soft-delete: marks the folder and all nested folders/documents as deleted."""
    folder = await _find_folder(folder_id)
    await _assert_can_delete_folder(folder, user)

    await _cascade_soft_delete(folder)
    return folder


async def restore_folder(folder_id: str, user: User) -> Folder:
    """Cascade restore: restores the folder and all nested folders/documents."""
    folder = await _find_folder(folder_id)
    await _assert_can_delete_folder(folder, user)

    if folder.parent_id is not None:
        parent = await _find_folder_or_none(folder.parent_id)
        if parent is not None and parent.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot restore a folder whose parent is still deleted",
            )

    await _cascade_restore(folder)
    return folder


async def list_trash_folders(user: User) -> list[Folder]:
    """List top-level trashed folders (whose parent is NOT trashed or has no parent)."""
    trashed = await Folder.find(
        Folder.owner_id == str(user.id),
        Folder.is_deleted == True,  # noqa: E712
    ).sort("-deleted_at").to_list()

    result = []
    for f in trashed:
        if f.parent_id is None:
            result.append(f)
        else:
            parent = await _find_folder_or_none(f.parent_id)
            if parent is None or not parent.is_deleted:
                result.append(f)
    return result


async def hard_delete_folder(folder_id: str, user: User) -> None:
    """Permanently delete a folder and all nested folders, documents, and access records."""
    folder = await _find_folder(folder_id)
    await _assert_can_delete_folder(folder, user)
    await _cascade_hard_delete(folder)
    logger.info("Hard-deleted folder %s and all nested content", folder_id)


async def get_folder_permission(folder_id: str, user: User) -> Permission | None:
    """Get the effective permission a user has on a folder, or None.

    Uses acl_service._get_inherited_permission for consistent chain resolution.
    """
    from app.services.acl_service import get_base_permission
    return await get_base_permission("folder", folder_id, str(user.id))


async def list_folder_contents(
    user: User, folder_id: str | None = None
) -> dict:
    """List folders and documents at a given level.

    At root (folder_id=None): returns only content owned by the user.
    Inside a folder: checks access, then returns ALL non-deleted content
    in that folder (regardless of owner), plus the user's permission level.
    """
    if folder_id is not None:
        folder = await _find_folder(folder_id)
        await _assert_folder_access(folder, user, Permission.VIEW)
        permission = await get_folder_permission(folder_id, user)

        child_folders = await Folder.find(
            {"parent_id": folder_id, "is_deleted": False}
        ).sort("-updated_at").to_list()
        child_docs = await Document_.find(
            {"folder_id": folder_id, "is_deleted": False}
        ).sort("-updated_at").to_list()

        return {"folders": child_folders, "documents": child_docs, "permission": permission}

    own_folders = await list_folders(user, parent_id=None)
    own_docs = await Document_.find(
        {"owner_id": str(user.id), "is_deleted": False, "folder_id": None}
    ).sort("-updated_at").to_list()

    return {"folders": own_folders, "documents": own_docs, "permission": "edit"}


async def get_breadcrumbs(folder_id: str) -> list[dict]:
    """Build breadcrumb trail from root to the given folder."""
    crumbs: list[dict] = []
    current_id: str | None = folder_id
    visited: set[str] = set()
    while current_id is not None:
        if current_id in visited:
            break
        visited.add(current_id)
        folder = await _find_folder_or_none(current_id)
        if folder is None:
            break
        crumbs.append({"id": str(folder.id), "name": folder.name})
        current_id = folder.parent_id

    crumbs.reverse()
    return crumbs


# --- Sharing / Collaborators ---

async def _assert_can_share_folder(folder: Folder, user: User) -> None:
    """ACL-aware share check: only users with can_share may manage collaborators."""
    from app.services.acl_service import resolve_effective_permission
    perm = await resolve_effective_permission("folder", str(folder.id), user)
    if not perm.can_share:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to share this folder",
        )


async def add_folder_collaborator(
    folder_id: str, owner: User, email: str, permission: Permission
) -> FolderAccess:
    folder = await _find_folder(folder_id)
    await _assert_can_share_folder(folder, owner)

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

    existing = await FolderAccess.find_one(
        FolderAccess.folder_id == folder_id,
        FolderAccess.user_id == str(target_user.id),
    )

    if existing:
        existing.permission = permission
        existing.touch_access()
        await existing.save()
        return existing

    access = FolderAccess(
        folder_id=folder_id,
        user_id=str(target_user.id),
        permission=permission,
        granted_by=str(owner.id),
    )
    await access.insert()
    return access


async def list_folder_collaborators(folder_id: str, user: User) -> list[dict]:
    folder = await _find_folder(folder_id)
    await _assert_can_share_folder(folder, user)

    accesses = await FolderAccess.find(
        FolderAccess.folder_id == folder_id,
    ).sort("-granted_at").to_list()

    results = []
    for access in accesses:
        try:
            collab_user = await User.get(PydanticObjectId(access.user_id))
        except (InvalidId, ValueError):
            continue
        if collab_user is None:
            continue
        results.append({
            "id": str(access.id),
            "user_id": str(collab_user.id),
            "email": collab_user.email,
            "name": collab_user.name,
            "avatar_url": collab_user.avatar_url,
            "permission": access.permission,
            "granted_at": access.granted_at,
        })
    return results


async def remove_folder_collaborator(
    folder_id: str, owner: User, user_id: str
) -> None:
    folder = await _find_folder(folder_id)
    await _assert_can_share_folder(folder, owner)

    access = await FolderAccess.find_one(
        FolderAccess.folder_id == folder_id,
        FolderAccess.user_id == user_id,
    )
    if access is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collaborator access record not found",
        )
    await access.delete()


# --- Internal helpers ---

async def _find_folder(folder_id: str) -> Folder:
    try:
        folder = await Folder.get(PydanticObjectId(folder_id))
    except (InvalidId, ValueError):
        folder = None
    if folder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found",
        )
    return folder


async def _find_folder_or_none(folder_id: str) -> Folder | None:
    try:
        return await Folder.get(PydanticObjectId(folder_id))
    except (InvalidId, ValueError):
        return None


def _assert_owner(folder: Folder, user: User) -> None:
    if folder.owner_id != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this folder",
        )


async def _assert_can_delete_folder(folder: Folder, user: User) -> None:
    """ACL-aware delete check: root owner or entity owner with all children owned."""
    from app.services.acl_service import resolve_effective_permission
    perm = await resolve_effective_permission("folder", str(folder.id), user)
    if not perm.can_delete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this folder",
        )


async def _assert_folder_access(
    folder: Folder, user: User, min_permission: Permission
) -> None:
    """Check access: owner > explicit FolderAccess > parent chain inheritance > general_access > deny."""
    if folder.owner_id == str(user.id):
        return

    access = await FolderAccess.find_one(
        FolderAccess.folder_id == str(folder.id),
        FolderAccess.user_id == str(user.id),
    )
    if access is not None:
        if min_permission == Permission.EDIT and access.permission == Permission.VIEW:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You only have view access to this folder",
            )
        access.touch_access()
        await access.save()
        return

    if folder.parent_id is not None:
        parent = await _find_folder_or_none(folder.parent_id)
        if parent is not None:
            try:
                await _assert_folder_access(parent, user, min_permission)
                return
            except HTTPException:
                pass

    ga = folder.general_access
    from app.models.document import GeneralAccess
    if ga == GeneralAccess.ANYONE_EDIT:
        return
    if ga == GeneralAccess.ANYONE_VIEW and min_permission == Permission.VIEW:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access this folder",
    )




async def _check_depth(parent_id: str | None, extra_levels: int) -> None:
    """Ensure nesting won't exceed MAX_FOLDER_DEPTH."""
    depth = extra_levels
    current_id = parent_id
    visited: set[str] = set()
    while current_id is not None:
        if current_id in visited:
            break
        visited.add(current_id)
        depth += 1
        if depth > MAX_FOLDER_DEPTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Folder nesting depth cannot exceed {MAX_FOLDER_DEPTH}",
            )
        parent = await _find_folder_or_none(current_id)
        if parent is None:
            break
        current_id = parent.parent_id


async def _subtree_depth(folder_id: str) -> int:
    """Return the max depth of the subtree rooted at folder_id (inclusive)."""
    children = await Folder.find(Folder.parent_id == folder_id).to_list()
    if not children:
        return 1
    max_child = 0
    for child in children:
        max_child = max(max_child, await _subtree_depth(str(child.id)))
    return 1 + max_child


async def _is_descendant(candidate_id: str, ancestor_id: str) -> bool:
    """Check if candidate_id is a descendant of ancestor_id."""
    current_id: str | None = candidate_id
    visited: set[str] = set()
    while current_id is not None:
        if current_id == ancestor_id:
            return True
        if current_id in visited:
            break
        visited.add(current_id)
        folder = await _find_folder_or_none(current_id)
        if folder is None:
            break
        current_id = folder.parent_id
    return False


async def _cascade_soft_delete(folder: Folder) -> None:
    folder.soft_delete()
    await folder.save()

    child_folders = await Folder.find(
        Folder.parent_id == str(folder.id),
        Folder.is_deleted == False,  # noqa: E712
    ).to_list()
    for child in child_folders:
        await _cascade_soft_delete(child)

    child_docs = await Document_.find(
        Document_.folder_id == str(folder.id),
        Document_.is_deleted == False,  # noqa: E712
    ).to_list()
    for doc in child_docs:
        doc.soft_delete()
        await doc.save()


async def _cascade_restore(folder: Folder) -> None:
    folder.restore()
    await folder.save()

    child_folders = await Folder.find(
        Folder.parent_id == str(folder.id),
        Folder.is_deleted == True,  # noqa: E712
    ).to_list()
    for child in child_folders:
        await _cascade_restore(child)

    child_docs = await Document_.find(
        Document_.folder_id == str(folder.id),
        Document_.is_deleted == True,  # noqa: E712
    ).to_list()
    for doc in child_docs:
        doc.restore()
        await doc.save()


async def _cascade_hard_delete(folder: Folder) -> None:
    child_folders = await Folder.find(
        Folder.parent_id == str(folder.id),
    ).to_list()
    for child in child_folders:
        await _cascade_hard_delete(child)

    child_docs = await Document_.find(
        Document_.folder_id == str(folder.id),
    ).to_list()
    for doc in child_docs:
        from app.services.document_service import hard_delete_document as _hard_del
        from app.models.comment import Comment
        from app.models.document_version import DocumentVersion
        from app.models.document_view import DocumentView
        from app.models.share_link import DocumentAccess

        str_id = str(doc.id)
        await Comment.find(Comment.document_id == str_id).delete()
        await DocumentVersion.find(DocumentVersion.document_id == str_id).delete()
        await DocumentAccess.find(DocumentAccess.document_id == str_id).delete()
        from app.models.document_view import DocumentView as DV
        await DV.find(DV.document_id == str_id).delete()
        from app.services.crdt_store import MongoYStore
        if MongoYStore._db is not None:
            await MongoYStore._db["crdt_updates"].delete_many({"room": str_id})
        await doc.delete()

    await FolderAccess.find(FolderAccess.folder_id == str(folder.id)).delete()
    await FolderView.find(FolderView.folder_id == str(folder.id)).delete()
    await folder.delete()


async def record_folder_view(folder_id: str, user: User) -> None:
    """Record that a user viewed/opened a folder."""
    try:
        folder = await Folder.get(PydanticObjectId(folder_id))
    except (InvalidId, ValueError):
        return
    if folder is None:
        return

    existing = await FolderView.find_one(
        FolderView.user_id == str(user.id),
        FolderView.folder_id == folder_id,
    )
    if existing:
        existing.viewed_at = datetime.now(timezone.utc)
        await existing.save()
    else:
        view = FolderView(user_id=str(user.id), folder_id=folder_id)
        await view.insert()


async def list_recently_viewed_folders(user: User) -> list[dict]:
    """List folders recently viewed by the user, sorted by most recent first."""
    views = await FolderView.find(
        FolderView.user_id == str(user.id),
    ).sort("-viewed_at").to_list()

    results = []
    for view in views:
        try:
            folder = await Folder.get(PydanticObjectId(view.folder_id))
        except (InvalidId, ValueError):
            continue
        if folder is None or folder.is_deleted:
            continue

        perm = await get_folder_permission(view.folder_id, user)
        if perm is None:
            continue

        try:
            owner = await User.get(PydanticObjectId(folder.owner_id))
        except (InvalidId, ValueError):
            owner = None

        results.append({
            "folder": folder,
            "permission": perm,
            "viewed_at": view.viewed_at,
            "owner_name": owner.name if owner else "Unknown",
            "owner_email": owner.email if owner else "",
        })
    return results
