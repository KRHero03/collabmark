import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.models.user import User


def _auth_cookies(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"access_token": token}


class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_create_document(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        response = await async_client.post(
            "/api/documents",
            json={"title": "My First Doc", "content": "# Hello"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My First Doc"
        assert data["content"] == "# Hello"
        assert data["owner_id"] == str(test_user.id)

    @pytest.mark.asyncio
    async def test_create_document_defaults(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        response = await async_client.post("/api/documents", json={})
        assert response.status_code == 201
        assert response.json()["title"] == "Untitled"

    @pytest.mark.asyncio
    async def test_create_without_auth(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/documents", json={"title": "Sneaky"}
        )
        assert response.status_code == 401


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_list_own_documents(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        await async_client.post("/api/documents", json={"title": "Doc A"})
        await async_client.post("/api/documents", json={"title": "Doc B"})

        response = await async_client.get("/api/documents")
        assert response.status_code == 200
        docs = response.json()
        assert len(docs) == 2
        titles = {d["title"] for d in docs}
        assert "Doc A" in titles
        assert "Doc B" in titles


class TestGetDocument:
    @pytest.mark.asyncio
    async def test_get_existing_document(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        create_resp = await async_client.post(
            "/api/documents", json={"title": "Get Me"}
        )
        doc_id = create_resp.json()["id"]

        response = await async_client.get(f"/api/documents/{doc_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Get Me"

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        response = await async_client.get(
            "/api/documents/000000000000000000000000"
        )
        assert response.status_code == 404


class TestUpdateDocument:
    @pytest.mark.asyncio
    async def test_update_title_and_content(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        create_resp = await async_client.post(
            "/api/documents", json={"title": "Original"}
        )
        doc_id = create_resp.json()["id"]

        response = await async_client.put(
            f"/api/documents/{doc_id}",
            json={"title": "Updated", "content": "New content"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"
        assert data["content"] == "New content"


class TestSoftDelete:
    @pytest.mark.asyncio
    async def test_delete_and_restore(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        create_resp = await async_client.post(
            "/api/documents", json={"title": "Deletable"}
        )
        doc_id = create_resp.json()["id"]

        del_resp = await async_client.delete(f"/api/documents/{doc_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["is_deleted"] is True

        list_resp = await async_client.get("/api/documents")
        ids = [d["id"] for d in list_resp.json()]
        assert doc_id not in ids

        restore_resp = await async_client.post(
            f"/api/documents/{doc_id}/restore"
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["is_deleted"] is False
