import pytest
from app.auth.jwt import create_access_token
from app.models.user import User
from httpx import AsyncClient


def _auth_cookies(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"access_token": token}


class TestGetMe:
    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, async_client: AsyncClient):
        response = await async_client.get("/api/users/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, async_client: AsyncClient, test_user: User):
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

    @pytest.mark.asyncio
    async def test_update_avatar_url_only(self, async_client: AsyncClient, test_user: User):
        cookies = _auth_cookies(test_user)
        async_client.cookies.update(cookies)
        response = await async_client.put(
            "/api/users/me",
            json={"avatar_url": "https://example.com/new-avatar.png"},
        )
        assert response.status_code == 200
        assert response.json()["avatar_url"] == "https://example.com/new-avatar.png"
        assert response.json()["name"] == "Test User"

    @pytest.mark.asyncio
    async def test_update_partial_data_name_and_avatar(self, async_client: AsyncClient, test_user: User):
        cookies = _auth_cookies(test_user)
        async_client.cookies.update(cookies)
        response = await async_client.put(
            "/api/users/me",
            json={"name": "New Name", "avatar_url": "https://example.com/avatar.png"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"
        assert response.json()["avatar_url"] == "https://example.com/avatar.png"

    @pytest.mark.asyncio
    async def test_update_empty_payload_preserves_data(self, async_client: AsyncClient, test_user: User):
        cookies = _auth_cookies(test_user)
        async_client.cookies.update(cookies)
        response = await async_client.put("/api/users/me", json={})
        assert response.status_code == 200
        assert response.json()["name"] == "Test User"
        assert response.json()["email"] == "test@example.com"
