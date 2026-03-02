"""User model and related Pydantic schemas for API responses and updates."""

from datetime import datetime, timezone
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, EmailStr, Field


class User(Document):
    """Beanie document for a user. Key fields: google_id, email, name, avatar_url."""

    google_id: Indexed(str, unique=True)
    email: Indexed(EmailStr, unique=True)
    name: str
    avatar_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "users"

    def touch(self) -> None:
        """Update updated_at to the current UTC timestamp."""
        self.updated_at = datetime.now(timezone.utc)


class UserRead(BaseModel):
    """Public-facing user representation."""

    id: str
    email: str
    name: str
    avatar_url: Optional[str] = None
    created_at: datetime

    @classmethod
    def from_doc(cls, user: User) -> "UserRead":
        """Build UserRead from a User document."""
        return cls(
            id=str(user.id),
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            created_at=user.created_at,
        )


class UserUpdate(BaseModel):
    """Fields a user can update on their profile. All fields optional."""

    name: Optional[str] = None
    avatar_url: Optional[str] = None
