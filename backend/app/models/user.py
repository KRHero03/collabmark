"""User model and related Pydantic schemas for API responses and updates."""

from datetime import UTC, datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field, field_validator


class User(Document):
    """Beanie document for a user. Key fields: google_id, email, name, avatar_url, org_id, auth_provider."""

    google_id: Optional[str] = None
    email: Indexed(str, unique=True)
    name: str
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    avatar_url: Optional[str] = None
    photos: list[str] = Field(default_factory=list)
    org_id: Optional[str] = None
    auth_provider: str = "google"
    external_id: Optional[str] = None
    scim_emails: Optional[list] = None
    scim_photos: Optional[list] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "users"

    def touch(self) -> None:
        """Update updated_at to the current UTC timestamp."""
        self.updated_at = datetime.now(UTC)


class UserRead(BaseModel):
    """Public-facing user representation."""

    id: str
    email: str
    name: str
    avatar_url: Optional[str] = None
    org_id: Optional[str] = None
    auth_provider: str = "google"
    created_at: datetime
    org_role: Optional[str] = None
    org_name: Optional[str] = None
    org_logo_url: Optional[str] = None
    is_super_admin: bool = False

    @classmethod
    def from_doc(cls, user: User) -> "UserRead":
        """Build UserRead from a User document."""
        return cls(
            id=str(user.id),
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            org_id=user.org_id,
            auth_provider=user.auth_provider,
            created_at=user.created_at,
        )


def _validate_avatar_url(url: str | None) -> str | None:
    if url is None or url == "":
        return url
    if not url.startswith(("https://", "http://localhost")):
        raise ValueError("avatar_url must use https:// scheme")
    return url


class UserUpdate(BaseModel):
    """Fields a user can update on their profile. All fields optional."""

    name: Optional[str] = None
    avatar_url: Optional[str] = None

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v: str | None) -> str | None:
        return _validate_avatar_url(v)
