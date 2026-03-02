"""API key authentication for programmatic access."""

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.models.api_key import ApiKey
from app.models.user import User

_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_user_from_api_key(
    api_key: str | None = Security(_header_scheme),
) -> User | None:
    """Resolve X-API-Key header to User. Records usage and updates last_used_at.

    Args:
        api_key: Raw API key from X-API-Key header (optional).

    Returns:
        The User if API key is valid and active, else None if no key provided.

    Raises:
        HTTPException: 401 if key is invalid or owner not found.
    """
    if not api_key:
        return None

    key_hash = ApiKey.hash_key(api_key)
    record = await ApiKey.find_one(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True,  # noqa: E712
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    from beanie import PydanticObjectId

    user = await User.get(PydanticObjectId(record.user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key owner not found",
        )

    record.record_usage()
    await record.save()
    return user
