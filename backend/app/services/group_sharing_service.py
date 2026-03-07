"""Group collaborator CRUD for documents and folders.

Handles adding, listing, and removing group-based access to documents and folders.
Delegates to DocumentGroupAccess for documents and FolderGroupAccess for folders.
"""

from typing import Literal

from beanie import PydanticObjectId
from fastapi import HTTPException

from app.models.group import (
    DocumentGroupAccess,
    FolderGroupAccess,
    Group,
    GroupCollaboratorRead,
)
from app.models.share_link import Permission
from app.models.user import User


async def add_group_collaborator(
    entity_type: Literal["document", "folder"],
    entity_id: str,
    entity_owner_id: str,
    user: User,
    group_id: str,
    permission: Permission,
) -> GroupCollaboratorRead:
    """Add or update a group's access to a document or folder. Owner only."""
    if entity_owner_id != str(user.id):
        raise HTTPException(status_code=403, detail="Only the owner can share")

    group = await Group.get(PydanticObjectId(group_id))
    if group is None or group.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Group not found")

    if entity_type == "document":
        existing = await DocumentGroupAccess.find_one(
            DocumentGroupAccess.document_id == entity_id,
            DocumentGroupAccess.group_id == group_id,
        )
        if existing:
            existing.permission = permission
            await existing.save()
            access = existing
        else:
            access = DocumentGroupAccess(
                document_id=entity_id,
                group_id=group_id,
                permission=permission,
                granted_by=str(user.id),
            )
            await access.insert()
    else:
        existing = await FolderGroupAccess.find_one(
            FolderGroupAccess.folder_id == entity_id,
            FolderGroupAccess.group_id == group_id,
        )
        if existing:
            existing.permission = permission
            await existing.save()
            access = existing
        else:
            access = FolderGroupAccess(
                folder_id=entity_id,
                group_id=group_id,
                permission=permission,
                granted_by=str(user.id),
            )
            await access.insert()

    return GroupCollaboratorRead(
        id=str(access.id),
        group_id=group_id,
        group_name=group.name,
        permission=access.permission,
        granted_at=access.granted_at,
    )


async def list_group_collaborators(
    entity_type: Literal["document", "folder"],
    entity_id: str,
) -> list[GroupCollaboratorRead]:
    """List all groups with access to a document or folder."""
    if entity_type == "document":
        accesses = await DocumentGroupAccess.find(DocumentGroupAccess.document_id == entity_id).to_list()
    else:
        accesses = await FolderGroupAccess.find(FolderGroupAccess.folder_id == entity_id).to_list()

    result = []
    for a in accesses:
        group = await Group.get(PydanticObjectId(a.group_id))
        if group:
            result.append(
                GroupCollaboratorRead(
                    id=str(a.id),
                    group_id=a.group_id,
                    group_name=group.name,
                    permission=a.permission,
                    granted_at=a.granted_at,
                )
            )
    return result


async def remove_group_collaborator(
    entity_type: Literal["document", "folder"],
    entity_id: str,
    entity_owner_id: str,
    user_id: str,
    group_id: str,
) -> None:
    """Remove a group's access. Owner only."""
    if entity_owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only the owner can manage sharing")

    if entity_type == "document":
        access = await DocumentGroupAccess.find_one(
            DocumentGroupAccess.document_id == entity_id,
            DocumentGroupAccess.group_id == group_id,
        )
    else:
        access = await FolderGroupAccess.find_one(
            FolderGroupAccess.folder_id == entity_id,
            FolderGroupAccess.group_id == group_id,
        )

    if access:
        await access.delete()
