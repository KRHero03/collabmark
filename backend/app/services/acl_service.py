"""Centralized ACL resolver for hierarchical permission enforcement.

ACL Rules:
  - Root Folder Owner: supreme authority over the entire hierarchy.
  - Entity Owner: full control of their entity; can delete only if all
    nested content is also owned by them.
  - Editor: can view, edit, and create inside folders; cannot delete or share.
  - Viewer: read-only access.
  - Inheritance: permissions flow down parent->child via FolderAccess chains.

Performance: Folder and Document models carry a denormalized root_folder_id
field, eliminating recursive parent-chain walks for root-owner resolution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Optional

from beanie import PydanticObjectId
from bson.errors import InvalidId

from app.models.document import Document_, GeneralAccess
from app.models.folder import Folder, FolderAccess
from app.models.share_link import DocumentAccess, Permission
from app.models.user import User

logger = logging.getLogger(__name__)

MAX_DEPTH = 50


@dataclass
class EffectivePermission:
    can_view: bool
    can_edit: bool
    can_delete: bool
    can_share: bool
    role: str  # "root_owner" | "owner" | "editor" | "viewer" | "none"


@dataclass
class AclEntry:
    user_id: str
    user_name: str
    user_email: str
    avatar_url: Optional[str]
    can_view: bool
    can_edit: bool
    can_delete: bool
    can_share: bool
    role: str
    inherited_from_id: Optional[str] = None
    inherited_from_name: Optional[str] = None


NO_ACCESS = EffectivePermission(
    can_view=False, can_edit=False, can_delete=False, can_share=False, role="none"
)


# ---------------------------------------------------------------------------
# Hierarchy helpers (O(1) via denormalized root_folder_id)
# ---------------------------------------------------------------------------

async def _get_folder(fid: str) -> Folder | None:
    try:
        return await Folder.get(PydanticObjectId(fid))
    except (InvalidId, ValueError):
        return None


async def find_root_folder_from_id(root_folder_id: str | None) -> Folder | None:
    """O(1) root lookup via the denormalized root_folder_id."""
    if root_folder_id is None:
        return None
    return await _get_folder(root_folder_id)


async def find_root_folder_by_walk(folder_id: str) -> Folder | None:
    """Fallback: walk parent_id chain for legacy data without root_folder_id."""
    visited: set[str] = set()
    current_id: str | None = folder_id
    last: Folder | None = None
    while current_id and current_id not in visited and len(visited) < MAX_DEPTH:
        visited.add(current_id)
        f = await _get_folder(current_id)
        if f is None:
            break
        last = f
        current_id = f.parent_id
    return last


async def get_root_owner_id(entity: Document_ | Folder, entity_type: Literal["document", "folder"]) -> str | None:
    """Return the owner_id of the root folder for an entity, using the fast path."""
    rfid = entity.root_folder_id
    if rfid:
        root = await find_root_folder_from_id(rfid)
        return root.owner_id if root else None

    parent_id = entity.folder_id if entity_type == "document" else entity.parent_id
    if parent_id is None:
        if entity_type == "folder":
            return entity.owner_id
        return None

    root = await find_root_folder_by_walk(parent_id)
    return root.owner_id if root else None


async def all_children_owned_by(folder_id: str, user_id: str) -> bool:
    """Recursively check that every sub-folder and document is owned by user_id."""
    child_folders = await Folder.find(
        {"parent_id": folder_id, "is_deleted": False}
    ).to_list()
    for cf in child_folders:
        if cf.owner_id != user_id:
            return False
        if not await all_children_owned_by(str(cf.id), user_id):
            return False

    child_docs = await Document_.find(
        {"folder_id": folder_id, "is_deleted": False}
    ).to_list()
    for doc in child_docs:
        if doc.owner_id != user_id:
            return False

    return True


# ---------------------------------------------------------------------------
# Low-level access resolution (view/edit only, no delete logic)
# ---------------------------------------------------------------------------

async def _get_inherited_permission(folder_id: str, user_id: str) -> Permission | None:
    """Walk up the folder chain looking for an explicit FolderAccess or general_access."""
    visited: set[str] = set()
    current_id: str | None = folder_id

    while current_id and current_id not in visited and len(visited) < MAX_DEPTH:
        visited.add(current_id)
        folder = await _get_folder(current_id)
        if folder is None:
            break

        if folder.owner_id == user_id:
            return Permission.EDIT

        access = await FolderAccess.find_one(
            FolderAccess.folder_id == current_id,
            FolderAccess.user_id == user_id,
        )
        if access is not None:
            return access.permission

        if folder.general_access == GeneralAccess.ANYONE_EDIT:
            return Permission.EDIT
        if folder.general_access == GeneralAccess.ANYONE_VIEW:
            return Permission.VIEW

        current_id = folder.parent_id

    return None


async def get_base_permission(
    entity_type: Literal["document", "folder"],
    entity_id: str,
    user_id: str,
) -> Permission | None:
    """Resolve the base view/edit permission (ignoring delete/share logic)."""
    if entity_type == "document":
        try:
            doc = await Document_.get(PydanticObjectId(entity_id))
        except (InvalidId, ValueError):
            return None
        if doc is None:
            return None

        if doc.owner_id == user_id:
            return Permission.EDIT

        da = await DocumentAccess.find_one(
            DocumentAccess.document_id == entity_id,
            DocumentAccess.user_id == user_id,
        )
        if da is not None:
            return da.permission

        if doc.folder_id is not None:
            perm = await _get_inherited_permission(doc.folder_id, user_id)
            if perm is not None:
                return perm

        if doc.general_access == GeneralAccess.ANYONE_EDIT:
            return Permission.EDIT
        if doc.general_access == GeneralAccess.ANYONE_VIEW:
            return Permission.VIEW

        return None

    # folder
    try:
        folder = await Folder.get(PydanticObjectId(entity_id))
    except (InvalidId, ValueError):
        return None
    if folder is None:
        return None

    if folder.owner_id == user_id:
        return Permission.EDIT

    fa = await FolderAccess.find_one(
        FolderAccess.folder_id == entity_id,
        FolderAccess.user_id == user_id,
    )
    if fa is not None:
        return fa.permission

    if folder.parent_id is not None:
        return await _get_inherited_permission(folder.parent_id, user_id)

    if folder.general_access == GeneralAccess.ANYONE_EDIT:
        return Permission.EDIT
    if folder.general_access == GeneralAccess.ANYONE_VIEW:
        return Permission.VIEW

    return None


# ---------------------------------------------------------------------------
# Core: resolve_effective_permission
# ---------------------------------------------------------------------------

async def resolve_effective_permission(
    entity_type: Literal["document", "folder"],
    entity_id: str,
    user: User,
) -> EffectivePermission:
    """Resolve the full effective permission for a user on an entity.

    Resolution order:
      1. Root folder owner -> full control (view, edit, delete, share)
      2. Entity owner at root level (no parent folder) -> full control
      3. Entity owner (non-root) -> view, edit, share; delete only if
         all children are owned by them
      4. Editor (direct or inherited) -> view, edit; no delete, no share
      5. Viewer (direct or inherited) -> view only
      6. No access
    """
    user_id = str(user.id)

    if entity_type == "document":
        try:
            entity = await Document_.get(PydanticObjectId(entity_id))
        except (InvalidId, ValueError):
            return NO_ACCESS
        if entity is None:
            return NO_ACCESS
    else:
        try:
            entity = await Folder.get(PydanticObjectId(entity_id))
        except (InvalidId, ValueError):
            return NO_ACCESS
        if entity is None:
            return NO_ACCESS

    entity_owner_id = entity.owner_id
    is_entity_owner = entity_owner_id == user_id

    root_owner_id = await get_root_owner_id(entity, entity_type)
    is_root_owner = root_owner_id is not None and root_owner_id == user_id

    # For a document, parent_folder_id = folder_id; for a folder, = parent_id
    parent_folder_id = entity.folder_id if entity_type == "document" else entity.parent_id

    # 1. Root folder owner (not the entity owner) -> full control
    if is_root_owner and not is_entity_owner:
        return EffectivePermission(
            can_view=True, can_edit=True, can_delete=True, can_share=True,
            role="root_owner",
        )

    # 2. Entity owner who IS also the root owner, or entity lives at root level
    if is_entity_owner and (is_root_owner or parent_folder_id is None):
        return EffectivePermission(
            can_view=True, can_edit=True, can_delete=True, can_share=True,
            role="owner",
        )

    # 3. Entity owner but NOT root owner (nested entity created via edit access)
    if is_entity_owner:
        can_delete = True
        if entity_type == "folder":
            can_delete = await all_children_owned_by(entity_id, user_id)
        return EffectivePermission(
            can_view=True, can_edit=True, can_delete=can_delete, can_share=True,
            role="owner",
        )

    # 4/5. Not owner — check inherited/explicit permission
    base_perm = await get_base_permission(entity_type, entity_id, user_id)

    if base_perm == Permission.EDIT:
        return EffectivePermission(
            can_view=True, can_edit=True, can_delete=False, can_share=False,
            role="editor",
        )

    if base_perm == Permission.VIEW:
        return EffectivePermission(
            can_view=True, can_edit=False, can_delete=False, can_share=False,
            role="viewer",
        )

    # 6. No access
    return NO_ACCESS


# ---------------------------------------------------------------------------
# ACL summary for the consolidated view
# ---------------------------------------------------------------------------

async def get_acl_summary(
    entity_type: Literal["document", "folder"],
    entity_id: str,
) -> list[AclEntry]:
    """Build a list of all users with their effective permissions on this entity."""
    seen_user_ids: set[str] = set()
    entries: list[AclEntry] = []

    if entity_type == "document":
        try:
            entity = await Document_.get(PydanticObjectId(entity_id))
        except (InvalidId, ValueError):
            return []
        if entity is None:
            return []
        entity_owner_id = entity.owner_id
        parent_folder_id = entity.folder_id
    else:
        try:
            entity = await Folder.get(PydanticObjectId(entity_id))
        except (InvalidId, ValueError):
            return []
        if entity is None:
            return []
        entity_owner_id = entity.owner_id
        parent_folder_id = entity.parent_id

    root_owner_id = await get_root_owner_id(entity, entity_type)

    async def _add_user(
        uid: str,
        inherited_id: str | None = None,
        inherited_name: str | None = None,
    ) -> None:
        if uid in seen_user_ids:
            return
        seen_user_ids.add(uid)
        try:
            u = await User.get(PydanticObjectId(uid))
        except (InvalidId, ValueError):
            return
        if u is None:
            return
        perm = await resolve_effective_permission(entity_type, entity_id, u)
        entries.append(AclEntry(
            user_id=uid,
            user_name=u.name or "Unknown",
            user_email=u.email or "",
            avatar_url=u.avatar_url,
            can_view=perm.can_view,
            can_edit=perm.can_edit,
            can_delete=perm.can_delete,
            can_share=perm.can_share,
            role=perm.role,
            inherited_from_id=inherited_id,
            inherited_from_name=inherited_name,
        ))

    await _add_user(entity_owner_id)

    if root_owner_id and root_owner_id != entity_owner_id:
        await _add_user(root_owner_id)

    if entity_type == "document":
        accesses = await DocumentAccess.find(
            DocumentAccess.document_id == entity_id
        ).to_list()
        for a in accesses:
            await _add_user(a.user_id)
    else:
        accesses = await FolderAccess.find(
            FolderAccess.folder_id == entity_id
        ).to_list()
        for a in accesses:
            await _add_user(a.user_id)

    if parent_folder_id:
        await _collect_folder_chain_users(
            parent_folder_id, seen_user_ids, entity_type, entity_id, entries
        )

    return entries


async def _collect_folder_chain_users(
    folder_id: str,
    seen: set[str],
    entity_type: Literal["document", "folder"],
    entity_id: str,
    entries: list[AclEntry],
) -> None:
    """Walk up the folder chain collecting users with explicit FolderAccess."""
    visited: set[str] = set()
    current_id: str | None = folder_id

    while current_id and current_id not in visited and len(visited) < MAX_DEPTH:
        visited.add(current_id)
        folder = await _get_folder(current_id)
        if folder is None:
            break

        folder_str_id = str(folder.id)

        if folder.owner_id not in seen:
            seen.add(folder.owner_id)
            try:
                u = await User.get(PydanticObjectId(folder.owner_id))
            except (InvalidId, ValueError):
                u = None
            if u:
                perm = await resolve_effective_permission(entity_type, entity_id, u)
                entries.append(AclEntry(
                    user_id=folder.owner_id,
                    user_name=u.name or "Unknown",
                    user_email=u.email or "",
                    avatar_url=u.avatar_url,
                    can_view=perm.can_view,
                    can_edit=perm.can_edit,
                    can_delete=perm.can_delete,
                    can_share=perm.can_share,
                    role=perm.role,
                    inherited_from_id=folder_str_id,
                    inherited_from_name=folder.name,
                ))

        chain_accesses = await FolderAccess.find(
            FolderAccess.folder_id == current_id
        ).to_list()
        for a in chain_accesses:
            if a.user_id not in seen:
                seen.add(a.user_id)
                try:
                    u = await User.get(PydanticObjectId(a.user_id))
                except (InvalidId, ValueError):
                    continue
                if u is None:
                    continue
                perm = await resolve_effective_permission(entity_type, entity_id, u)
                entries.append(AclEntry(
                    user_id=a.user_id,
                    user_name=u.name or "Unknown",
                    user_email=u.email or "",
                    avatar_url=u.avatar_url,
                    can_view=perm.can_view,
                    can_edit=perm.can_edit,
                    can_delete=perm.can_delete,
                    can_share=perm.can_share,
                    role=perm.role,
                    inherited_from_id=folder_str_id,
                    inherited_from_name=folder.name,
                ))

        current_id = folder.parent_id
