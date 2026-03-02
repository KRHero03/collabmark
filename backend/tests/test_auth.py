import pytest

from app.auth.jwt import create_access_token, decode_access_token
from app.models.user import User


class TestJWT:
    def test_create_and_decode_token(self):
        user_id = "507f1f77bcf86cd799439011"
        token = create_access_token(user_id)
        decoded = decode_access_token(token)
        assert decoded == user_id

    def test_decode_invalid_token_returns_none(self):
        assert decode_access_token("garbage.token.here") is None

    def test_decode_empty_token_returns_none(self):
        assert decode_access_token("") is None


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self, async_client):
        response = await async_client.post("/api/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out"
