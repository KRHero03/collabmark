import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.models.user import User


def _auth_cookies(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"access_token": token}


class TestGetMe:
    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, async_client: AsyncClient):
        response = await async_client.get("/api/users/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_authenticated(
        self, async_client: AsyncClient, test_user: User
    ):
        cookies = _auth_cookies(test_user)
        async_client.cookies.update(cookies)
        response = await async_client.get("/api/users/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"


class TestUpdateMe:
    @pytest.mark.asyncio
    async def test_update_name(self, async_client: AsyncClient, test_user: User):
        cookies = _auth_cookies(test_user)
        async_client.cookies.update(cookies)
        response = await async_client.put(
            "/api/users/me",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_without_auth(self, async_client: AsyncClient):
        response = await async_client.put(
            "/api/users/me",
            json={"name": "Hacker"},
        )
        assert response.status_code == 401
