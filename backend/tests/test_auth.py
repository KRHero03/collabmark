import pytest
from app.auth.jwt import create_access_token, decode_access_token
from app.config import AUTH_COOKIE_NAME
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


class TestCLIComplete:
    @pytest.mark.asyncio
    async def test_redirects_to_localhost_with_valid_token(self, async_client, test_user: User):
        token = create_access_token(str(test_user.id))
        response = await async_client.get(
            "/api/auth/cli/complete",
            params={"port": 54321},
            cookies={AUTH_COOKIE_NAME: token},
            follow_redirects=False,
        )
        assert response.status_code == 200
        body = response.text
        assert "http://localhost:54321/callback?code=" in body

    @pytest.mark.asyncio
    async def test_rejects_unauthenticated_request(self, async_client):
        response = await async_client.get(
            "/api/auth/cli/complete",
            params={"port": 54321},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "error=cli_not_authenticated" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_rejects_invalid_token(self, async_client):
        response = await async_client.get(
            "/api/auth/cli/complete",
            params={"port": 54321},
            cookies={AUTH_COOKIE_NAME: "invalid-jwt-token"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "error=cli_not_authenticated" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_rejects_port_below_range(self, async_client, test_user: User):
        token = create_access_token(str(test_user.id))
        response = await async_client.get(
            "/api/auth/cli/complete",
            params={"port": 80},
            cookies={AUTH_COOKIE_NAME: token},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "error=cli_invalid_port" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_rejects_port_above_range(self, async_client, test_user: User):
        token = create_access_token(str(test_user.id))
        response = await async_client.get(
            "/api/auth/cli/complete",
            params={"port": 70000},
            cookies={AUTH_COOKIE_NAME: token},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "error=cli_invalid_port" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_requires_port_parameter(self, async_client, test_user: User):
        token = create_access_token(str(test_user.id))
        response = await async_client.get(
            "/api/auth/cli/complete",
            cookies={AUTH_COOKIE_NAME: token},
        )
        assert response.status_code == 422
