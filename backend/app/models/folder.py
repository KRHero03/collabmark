"""Folder (Space) model and related schemas for organizing documents."""

from datetime import datetime, timezone
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field

from app.models.document import GeneralAccess
from app.models.share_link import Permission


class Folder(Document):
    """A folder/space that can contain documents and other folders."""

    name: str = "Untitled Folder"
    owner_id: Indexed(str)
    parent_id: Optional[str] = None
    root_folder_id: Optional[str] = None
    general_access: GeneralAccess = GeneralAccess.RESTRICTED
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "folders"

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.touch()

    def restore(self) -> None:
        self.is_deleted = False
        self.deleted_at = None
        self.touch()


class FolderAccess(Document):
    """Tracks which users have access to which folders (powers shared folders)."""

    folder_id: Indexed(str)
    user_id: Indexed(str)
    permission: Permission = Permission.VIEW
    granted_by: str
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "folder_access"

    def touch_access(self) -> None:
        self.last_accessed_at = datetime.now(timezone.utc)


class FolderRead(BaseModel):
    """Public-facing folder representation for API responses."""

    id: str
    name: str
    owner_id: str
    owner_name: str = ""
    owner_email: str = ""
    parent_id: Optional[str] = None
    general_access: GeneralAccess
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_folder(
        cls,
        folder: "Folder",
        *,
        owner_name: str = "",
        owner_email: str = "",
    ) -> "FolderRead":
        return cls(
            id=str(folder.id),
            name=folder.name,
            owner_id=folder.owner_id,
            owner_name=owner_name,
            owner_email=owner_email,
            parent_id=folder.parent_id,
            general_access=folder.general_access,
            is_deleted=folder.is_deleted,
            deleted_at=folder.deleted_at,
            created_at=folder.created_at,
            updated_at=folder.updated_at,
        )


class FolderView(Document):
    """Records when a user views/opens a folder, powering the 'Recently Viewed' tab."""

    user_id: Indexed(str)
    folder_id: Indexed(str)
    viewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "folder_views"


class RecentlyViewedFolderRead(BaseModel):
    """A recently viewed folder for API responses."""

    id: str
    name: str
    owner_id: str
    owner_name: str
    owner_email: str
    permission: str
    viewed_at: datetime
    created_at: datetime
    updated_at: datetime


class SharedFolderRead(BaseModel):
    """A shared folder for API responses (Shared with me tab)."""

    id: str
    name: str
    owner_id: str
    owner_name: str
    owner_email: str
    permission: str
    last_accessed_at: datetime
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_folder(
        cls,
        folder: "Folder",
        *,
        owner_name: str = "",
        owner_email: str = "",
        permission: str = "view",
        last_accessed_at: datetime | None = None,
    ) -> "SharedFolderRead":
        return cls(
            id=str(folder.id),
            name=folder.name,
            owner_id=folder.owner_id,
            owner_name=owner_name,
            owner_email=owner_email,
            permission=permission,
            last_accessed_at=last_accessed_at or folder.updated_at,
            created_at=folder.created_at,
            updated_at=folder.updated_at,
        )


class FolderCreate(BaseModel):
    """Payload for creating a new folder."""

    name: str = "Untitled Folder"
    parent_id: Optional[str] = None


class FolderUpdate(BaseModel):
    """Payload for updating a folder (rename, move, or change access)."""

    name: Optional[str] = None
    parent_id: Optional[str] = None
    general_access: Optional[GeneralAccess] = None
