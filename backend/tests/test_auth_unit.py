"""Direct unit tests for auth modules: jwt, api_key, dependencies."""

from datetime import UTC

import pytest
from app.auth.api_key import get_user_from_api_key
from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token, decode_access_token
from app.config import settings
from app.models.api_key import ApiKey
from app.models.user import User
from jose import jwt


class TestCreateAccessToken:
    def test_returns_string(self, test_user: User):
        token = create_access_token(str(test_user.id))
        assert isinstance(token, str)
        assert len(token) > 0

    def test_contains_correct_sub_claim(self, test_user: User):
        token = create_access_token(str(test_user.id))
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["sub"] == str(test_user.id)


class TestDecodeAccessToken:
    def test_valid_token_returns_user_id(self, test_user: User):
        token = create_access_token(str(test_user.id))
        user_id = decode_access_token(token)
        assert user_id == str(test_user.id)

    def test_expired_token_returns_none(self, test_user: User):
        from datetime import datetime, timedelta

        expire = datetime.now(UTC) - timedelta(minutes=1)
        payload = {"sub": str(test_user.id), "exp": expire}
        token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        assert decode_access_token(token) is None

    def test_tampered_token_returns_none(self, test_user: User):
        token = create_access_token(str(test_user.id))
        tampered = token[:-5] + "xxxxx"
        assert decode_access_token(tampered) is None

    def test_empty_string_returns_none(self):
        assert decode_access_token("") is None

    def test_completely_invalid_string_returns_none(self):
        assert decode_access_token("not-a-jwt-at-all") is None


class TestGetUserFromApiKey:
    @pytest.mark.asyncio
    async def test_no_key_returns_none(self):
        result = await get_user_from_api_key(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_key_returns_user_and_records_usage(self, test_user: User):
        raw_key = ApiKey.generate_key()
        key_hash = ApiKey.hash_key(raw_key)
        api_key_record = ApiKey(
            user_id=str(test_user.id),
            key_hash=key_hash,
            name="Test Key",
            is_active=True,
        )
        await api_key_record.insert()

        user = await get_user_from_api_key(raw_key)
        assert user is not None
        assert user.id == test_user.id

        updated = await ApiKey.get(api_key_record.id)
        assert updated.last_used_at is not None

    @pytest.mark.asyncio
    async def test_invalid_key_raises_401(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_user_from_api_key("cm_invalid_key_that_does_not_exist")
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid API key"

    @pytest.mark.asyncio
    async def test_key_with_missing_owner_raises_401(self):
        raw_key = ApiKey.generate_key()
        key_hash = ApiKey.hash_key(raw_key)
        api_key_record = ApiKey(
            user_id="000000000000000000000001",
            key_hash=key_hash,
            name="Orphan Key",
            is_active=True,
        )
        await api_key_record.insert()

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_user_from_api_key(raw_key)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "API key owner not found"


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_api_key_user_takes_precedence_over_jwt(self, test_user: User):
        other_user = User(
            google_id="other",
            email="other@example.com",
            name="Other",
        )
        await other_user.insert()
        jwt_token = create_access_token(str(other_user.id))

        raw_key = ApiKey.generate_key()
        key_hash = ApiKey.hash_key(raw_key)
        await ApiKey(
            user_id=str(test_user.id),
            key_hash=key_hash,
            name="Key",
            is_active=True,
        ).insert()

        user_from_key = await get_user_from_api_key(raw_key)
        user_from_jwt = await get_current_user(
            access_token=jwt_token,
            api_key_user=user_from_key,
        )
        assert user_from_jwt.id == test_user.id

    @pytest.mark.asyncio
    async def test_valid_jwt_returns_user(self, test_user: User):
        token = create_access_token(str(test_user.id))
        user = await get_current_user(access_token=token, api_key_user=None)
        assert user.id == test_user.id

    @pytest.mark.asyncio
    async def test_no_token_and_no_api_key_raises_401(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(access_token=None, api_key_user=None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Not authenticated"

    @pytest.mark.asyncio
    async def test_invalid_jwt_raises_401(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(access_token="invalid-token", api_key_user=None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid or expired token"

    @pytest.mark.asyncio
    async def test_valid_jwt_but_user_deleted_raises_401(self, test_user: User):
        token = create_access_token(str(test_user.id))
        await test_user.delete()
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(access_token=token, api_key_user=None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "User not found"

    @pytest.mark.asyncio
    async def test_malformed_user_id_in_jwt_raises_401(self):
        from datetime import datetime, timedelta

        expire = datetime.now(UTC) + timedelta(minutes=60)
        payload = {"sub": "not-a-valid-objectid", "exp": expire}
        token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(access_token=token, api_key_user=None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "User not found"
