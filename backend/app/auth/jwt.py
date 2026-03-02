"""JWT creation and decoding for session authentication."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

_ALGORITHM = settings.jwt_algorithm
_SECRET = settings.jwt_secret_key
_EXPIRE_MINUTES = settings.jwt_expire_minutes


def create_access_token(user_id: str) -> str:
    """Create a signed JWT for the given user with expiration.

    Args:
        user_id: The user's ID to embed in the token as sub.

    Returns:
        Encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Decode and validate a JWT, returning the user ID if valid.

    Args:
        token: The encoded JWT string.

    Returns:
        The user ID (sub claim) if valid, else None.
    """
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
