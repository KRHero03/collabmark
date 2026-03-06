"""Resolve user IDs to owner display info."""

from beanie import PydanticObjectId
from bson.errors import InvalidId

from app.models.user import User


async def resolve_owner(owner_id: str) -> tuple[str, str, str | None]:
    """Resolve a user ID to (name, email, avatar_url).

    Returns ("Unknown", "", None) if the user is not found.
    """
    try:
        owner = await User.get(PydanticObjectId(owner_id))
    except (InvalidId, ValueError):
        owner = None
    if owner is None:
        return ("Unknown", "", None)
    return (owner.name or "Unknown", owner.email or "", owner.avatar_url)
