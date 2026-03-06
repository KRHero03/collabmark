import pytest
from app.auth.jwt import create_access_token
from app.models.user import User
from httpx import AsyncClient


def _auth_cookies(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"access_token": token}


class TestApiKeyLifecycle:
    @pytest.mark.asyncio
    async def test_create_and_list_api_key(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))

        create_resp = await async_client.post("/api/keys", json={"name": "CI key"})
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert data["name"] == "CI key"
        assert data["raw_key"].startswith("cm_")

        list_resp = await async_client.get("/api/keys")
        assert list_resp.status_code == 200
        keys = list_resp.json()
        assert len(keys) == 1
        assert keys[0]["name"] == "CI key"

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))

        create_resp = await async_client.post("/api/keys", json={"name": "Temp key"})
        key_id = create_resp.json()["id"]

        del_resp = await async_client.delete(f"/api/keys/{key_id}")
        assert del_resp.status_code == 204

        list_resp = await async_client.get("/api/keys")
        ids = [k["id"] for k in list_resp.json()]
        assert key_id not in ids

    @pytest.mark.asyncio
    async def test_use_api_key_for_auth(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))

        create_resp = await async_client.post("/api/keys", json={"name": "Auth test key"})
        raw_key = create_resp.json()["raw_key"]

        async_client.cookies.clear()
        response = await async_client.get(
            "/api/users/me",
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 200
        assert response.json()["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_invalid_api_key_rejected(self, async_client: AsyncClient):
        response = await async_client.get(
            "/api/users/me",
            headers={"X-API-Key": "cm_invalid_key_here"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_revoke_invalid_key_id_404(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.delete("/api/keys/invalid-id")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_revoke_key_not_owned_by_user_404(self, async_client: AsyncClient, test_user: User):
        from app.models.api_key import ApiKey

        other = User(
            google_id="other-keys",
            email="other-keys@example.com",
            name="Other",
        )
        await other.insert()

        key = ApiKey(
            user_id=str(other.id),
            key_hash=ApiKey.hash_key("cm_test123"),
            name="Other Key",
        )
        await key.insert()

        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.delete(f"/api/keys/{key.id}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
