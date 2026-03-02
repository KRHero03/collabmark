"""API key management routes: create, list, revoke."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.models.api_key import ApiKey, ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.models.user import User

router = APIRouter(prefix="/api/keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(
    payload: ApiKeyCreate,
    user: User = Depends(get_current_user),
):
    """Create a new API key. Raw key returned only in this response.

    Args:
        payload: Display name for the key.
        user: Injected by get_current_user dependency.

    Returns:
        ApiKeyCreated with id, name, raw_key (store securely), created_at.
    """
    raw_key = ApiKey.generate_key()
    key_hash = ApiKey.hash_key(raw_key)

    api_key = ApiKey(
        user_id=str(user.id),
        key_hash=key_hash,
        name=payload.name,
    )
    await api_key.insert()

    return ApiKeyCreated(
        id=str(api_key.id),
        name=api_key.name,
        raw_key=raw_key,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[ApiKeyRead])
async def list_api_keys(user: User = Depends(get_current_user)):
    """List all active API keys for the current user.

    Args:
        user: Injected by get_current_user dependency.

    Returns:
        List of ApiKeyRead (excludes raw key and hash).
    """
    keys = await ApiKey.find(
        ApiKey.user_id == str(user.id),
        ApiKey.is_active == True,  # noqa: E712
    ).to_list()
    return [ApiKeyRead.from_doc(k) for k in keys]


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    user: User = Depends(get_current_user),
):
    """Revoke an API key by setting is_active to False. Owner only.

    Args:
        key_id: API key document ID.
        user: Injected by get_current_user dependency.

    Raises:
        HTTPException: 404 if key not found or not owned by user.
    """
    from beanie import PydanticObjectId
    from bson.errors import InvalidId

    try:
        api_key = await ApiKey.get(PydanticObjectId(key_id))
    except (InvalidId, ValueError):
        api_key = None

    if api_key is None or api_key.user_id != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    api_key.is_active = False
    await api_key.save()
