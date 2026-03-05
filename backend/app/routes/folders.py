"""Folder CRUD routes: create, list, get, update, delete, restore, trash, hard-delete, sharing, ACL."""

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.models.document import DocumentRead
from app.models.folder import (
    Folder,
    FolderCreate,
    FolderRead,
    FolderUpdate,
    RecentlyViewedFolderRead,
    SharedFolderRead,
)
from app.models.share_link import CollaboratorAdd, CollaboratorRead, Permission
from app.models.user import User
from app.services import folder_service
from app.services.acl_service import get_acl_summary

router = APIRouter(prefix="/api/folders", tags=["folders"])


async def _resolve_owner(folder: Folder) -> tuple[str, str, str | None]:
    try:
        owner = await User.get(PydanticObjectId(folder.owner_id))
    except (InvalidId, ValueError):
        owner = None
    if owner is None:
        return ("Unknown", "", None)
    return (owner.name or "Unknown", owner.email or "", owner.avatar_url)


@router.post("", response_model=FolderRead, status_code=201)
async def create_folder(
    payload: FolderCreate,
    user: User = Depends(get_current_user),
):
    """Create a new folder. Optionally nest it under a parent folder."""
    folder = await folder_service.create_folder(user, payload)
    return FolderRead.from_folder(folder, owner_name=user.name or "", owner_email=user.email or "", owner_avatar_url=user.avatar_url)


@router.get("/trash", response_model=list[FolderRead])
async def list_trash_folders(
    user: User = Depends(get_current_user),
):
    """List all soft-deleted folders owned by the current user."""
    folders = await folder_service.list_trash_folders(user)
    return [FolderRead.from_folder(f, owner_name=user.name or "", owner_email=user.email or "", owner_avatar_url=user.avatar_url) for f in folders]


@router.get("/shared", response_model=list[SharedFolderRead])
async def list_shared_folders(
    user: User = Depends(get_current_user),
):
    """List all folders shared with the current user, with owner info and permission."""
    items = await folder_service.list_shared_folders(user)
    return [
        SharedFolderRead.from_folder(
            item["folder"],
            owner_name=item.get("owner_name", "Unknown"),
            owner_email=item.get("owner_email", ""),
            permission=item["permission"].value if hasattr(item["permission"], "value") else item["permission"],
            last_accessed_at=item["last_accessed_at"],
        )
        for item in items
    ]


@router.get("/contents")
async def list_folder_contents(
    folder_id: str | None = Query(None),
    user: User = Depends(get_current_user),
):
    """List folders and documents at a given level. Pass folder_id=null for root.

    When accessing a shared folder, returns ALL content inside it and includes
    a 'permission' field indicating the user's access level ('view' or 'edit').
    """
    data = await folder_service.list_folder_contents(user, folder_id)
    owner_cache: dict[str, tuple[str, str]] = {}

    async def resolve(owner_id: str) -> tuple[str, str, str | None]:
        if owner_id in owner_cache:
            return owner_cache[owner_id]
        try:
            o = await User.get(PydanticObjectId(owner_id))
        except (InvalidId, ValueError):
            o = None
        result = (o.name or "Unknown", o.email or "", o.avatar_url) if o else ("Unknown", "", None)
        owner_cache[owner_id] = result
        return result

    folders = []
    for f in data["folders"]:
        oname, oemail, oavatar = await resolve(f.owner_id)
        folders.append(FolderRead.from_folder(f, owner_name=oname, owner_email=oemail, owner_avatar_url=oavatar))

    documents = []
    for d in data["documents"]:
        oname, oemail, oavatar = await resolve(d.owner_id)
        documents.append(DocumentRead.from_doc(d, owner_name=oname, owner_email=oemail, owner_avatar_url=oavatar))

    return {"folders": folders, "documents": documents, "permission": data.get("permission", "edit")}


@router.get("/breadcrumbs")
async def get_breadcrumbs(
    folder_id: str = Query(...),
    user: User = Depends(get_current_user),
):
    """Return the breadcrumb trail from root to the given folder."""
    return await folder_service.get_breadcrumbs(folder_id)


@router.get("/recent", response_model=list[RecentlyViewedFolderRead])
async def list_recently_viewed_folders(
    user: User = Depends(get_current_user),
):
    """List all folders recently viewed by the current user, sorted by recency."""
    items = await folder_service.list_recently_viewed_folders(user)
    return [
        RecentlyViewedFolderRead(
            id=str(item["folder"].id),
            name=item["folder"].name,
            owner_id=item["folder"].owner_id,
            owner_name=item.get("owner_name", "Unknown"),
            owner_email=item.get("owner_email", ""),
            permission=item["permission"],
            viewed_at=item["viewed_at"],
            created_at=item["folder"].created_at,
            updated_at=item["folder"].updated_at,
        )
        for item in items
    ]


@router.post("/{folder_id}/view", status_code=204)
async def record_folder_view(
    folder_id: str,
    user: User = Depends(get_current_user),
):
    """Record that the current user viewed/opened a folder.

    Creates or updates the view timestamp for the 'Recently Viewed' tab.
    """
    await folder_service.record_folder_view(folder_id, user)


@router.get("/{folder_id}", response_model=FolderRead)
async def get_folder(
    folder_id: str,
    user: User = Depends(get_current_user),
):
    """Get a folder by ID. Returns 404 if not found or not accessible."""
    folder = await folder_service.get_folder(folder_id, user)
    name, email, avatar = await _resolve_owner(folder)
    return FolderRead.from_folder(folder, owner_name=name, owner_email=email, owner_avatar_url=avatar)


@router.put("/{folder_id}", response_model=FolderRead)
async def update_folder(
    folder_id: str,
    payload: FolderUpdate,
    user: User = Depends(get_current_user),
):
    """Update a folder's name or move it to a different parent."""
    folder = await folder_service.update_folder(folder_id, user, payload)
    name, email, avatar = await _resolve_owner(folder)
    return FolderRead.from_folder(folder, owner_name=name, owner_email=email, owner_avatar_url=avatar)


@router.delete("/{folder_id}", response_model=FolderRead)
async def delete_folder(
    folder_id: str,
    user: User = Depends(get_current_user),
):
    """Cascade soft-delete a folder and all its contents."""
    folder = await folder_service.soft_delete_folder(folder_id, user)
    return FolderRead.from_folder(folder, owner_name=user.name or "", owner_email=user.email or "", owner_avatar_url=user.avatar_url)


@router.post("/{folder_id}/restore", response_model=FolderRead)
async def restore_folder(
    folder_id: str,
    user: User = Depends(get_current_user),
):
    """Cascade restore a folder and all its contents."""
    folder = await folder_service.restore_folder(folder_id, user)
    return FolderRead.from_folder(folder, owner_name=user.name or "", owner_email=user.email or "", owner_avatar_url=user.avatar_url)


@router.delete("/{folder_id}/permanent", status_code=204)
async def hard_delete_folder(
    folder_id: str,
    user: User = Depends(get_current_user),
):
    """Permanently delete a folder and all nested content."""
    await folder_service.hard_delete_folder(folder_id, user)


@router.post(
    "/{folder_id}/collaborators",
    response_model=CollaboratorRead,
    status_code=201,
)
async def add_folder_collaborator(
    folder_id: str,
    payload: CollaboratorAdd,
    user: User = Depends(get_current_user),
):
    """Add a collaborator to a folder with the specified permission level."""
    access = await folder_service.add_folder_collaborator(
        folder_id, user, payload.email, payload.permission
    )
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
    "/{folder_id}/collaborators",
    response_model=list[CollaboratorRead],
)
async def list_folder_collaborators(
    folder_id: str,
    user: User = Depends(get_current_user),
):
    """List all collaborators for a given folder."""
    items = await folder_service.list_folder_collaborators(folder_id, user)
    return [CollaboratorRead(**item) for item in items]


@router.delete(
    "/{folder_id}/collaborators/{user_id}",
    status_code=204,
)
async def remove_folder_collaborator(
    folder_id: str,
    user_id: str,
    user: User = Depends(get_current_user),
):
    """Remove a collaborator's access from a folder."""
    await folder_service.remove_folder_collaborator(folder_id, user, user_id)


@router.get("/{folder_id}/acl")
async def get_folder_acl(
    folder_id: str,
    user: User = Depends(get_current_user),
):
    """Get consolidated ACL for a folder showing all users with effective permissions."""
    await folder_service.get_folder(folder_id, user)
    entries = await get_acl_summary("folder", folder_id)
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
