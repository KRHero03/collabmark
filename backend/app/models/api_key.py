"""API key model and related Pydantic schemas for key management."""

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Optional

from beanie import Document, Indexed
from pydantic import BaseModel, Field

API_KEY_PREFIX = "cm_"
API_KEY_BYTES = 32


class ApiKey(Document):
    """Beanie document for an API key. Key fields: user_id, key_hash, name, is_active."""

    user_id: Indexed(str)
    key_hash: Indexed(str, unique=True)
    name: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used_at: Optional[datetime] = None

    class Settings:
        name = "api_keys"

    def record_usage(self) -> None:
        """Update last_used_at to the current UTC timestamp."""
        self.last_used_at = datetime.now(UTC)

    @staticmethod
    def generate_key() -> str:
        """Generate a new raw API key with prefix. Returned only at creation time."""
        return API_KEY_PREFIX + secrets.token_hex(API_KEY_BYTES)

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Return SHA-256 hex digest of the raw key for storage/lookup."""
        return hashlib.sha256(raw_key.encode()).hexdigest()


class ApiKeyRead(BaseModel):
    """Public-facing API key representation (excludes raw key and hash)."""

    id: str
    name: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]

    @classmethod
    def from_doc(cls, doc: ApiKey) -> "ApiKeyRead":
        """Build ApiKeyRead from an ApiKey document."""
        return cls(
            id=str(doc.id),
            name=doc.name,
            is_active=doc.is_active,
            created_at=doc.created_at,
            last_used_at=doc.last_used_at,
        )


class ApiKeyCreate(BaseModel):
    """Payload for creating a new API key. Requires a display name."""

    name: str


class ApiKeyCreated(BaseModel):
    """Returned once at creation time -- includes the raw key."""

    id: str
    name: str
    raw_key: str
    created_at: datetime
