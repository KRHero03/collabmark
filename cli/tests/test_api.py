"""Tests for collabmark.lib.api — REST API client."""

from __future__ import annotations

import httpx
import pytest
import respx

from collabmark.lib.api import (
    APIError,
    AuthenticationError,
    CollabMarkClient,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from collabmark.types import DocumentInfo, FolderContents, FolderInfo, SharedFolder

BASE = "http://test-api:8000"
API_KEY = "cm_test_key_abc123"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> CollabMarkClient:
    return CollabMarkClient(api_key=API_KEY, base_url=BASE, max_retries=1)


@pytest.fixture()
def retrying_client() -> CollabMarkClient:
    """Client with 3 retries for testing retry logic."""
    return CollabMarkClient(api_key=API_KEY, base_url=BASE, max_retries=3)


# ---------------------------------------------------------------------------
# Helpers — sample JSON payloads
# ---------------------------------------------------------------------------

SAMPLE_USER = {
    "id": "u1",
    "email": "pm@acme.com",
    "name": "Priya",
    "avatar_url": None,
}

SAMPLE_FOLDER = {
    "id": "f1",
    "name": "Engineering Context",
    "owner_id": "u1",
    "parent_id": None,
    "general_access": "restricted",
    "is_deleted": False,
    "created_at": "2025-01-15T10:00:00",
    "updated_at": "2025-06-20T14:30:00",
}

SAMPLE_SHARED_FOLDER = {
    **SAMPLE_FOLDER,
    "owner_name": "Priya",
    "owner_email": "pm@acme.com",
    "permission": "edit",
    "last_accessed_at": "2025-06-20T14:30:00",
}

SAMPLE_DOCUMENT = {
    "id": "d1",
    "title": "Architecture Overview",
    "content": "# Architecture\n\nThis doc...",
    "owner_id": "u1",
    "folder_id": "f1",
    "general_access": "restricted",
    "is_deleted": False,
    "content_length": 30,
    "created_at": "2025-02-01T09:00:00",
    "updated_at": "2025-06-21T11:00:00",
}


# ===================================================================
# Client lifecycle
# ===================================================================


class TestClientLifecycle:
    @respx.mock
    @pytest.mark.asyncio
    async def test_context_manager_opens_and_closes(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/users/me").mock(return_value=httpx.Response(200, json=SAMPLE_USER))
        async with client as c:
            await c.get_current_user()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_request_without_context_manager_raises(self, client: CollabMarkClient) -> None:
        with pytest.raises(RuntimeError, match="Client not open"):
            await client.get_current_user()

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_header_sent_on_every_request(self, client: CollabMarkClient) -> None:
        route = respx.get(f"{BASE}/api/users/me").mock(return_value=httpx.Response(200, json=SAMPLE_USER))
        async with client as c:
            await c.get_current_user()
        assert route.calls[0].request.headers["X-API-Key"] == API_KEY

    @respx.mock
    @pytest.mark.asyncio
    async def test_user_agent_header_sent(self, client: CollabMarkClient) -> None:
        route = respx.get(f"{BASE}/api/users/me").mock(return_value=httpx.Response(200, json=SAMPLE_USER))
        async with client as c:
            await c.get_current_user()
        ua = route.calls[0].request.headers["User-Agent"]
        assert ua.startswith("collabmark-cli/")

    @respx.mock
    @pytest.mark.asyncio
    async def test_accept_json_header_sent(self, client: CollabMarkClient) -> None:
        route = respx.get(f"{BASE}/api/users/me").mock(return_value=httpx.Response(200, json=SAMPLE_USER))
        async with client as c:
            await c.get_current_user()
        assert route.calls[0].request.headers["Accept"] == "application/json"


# ===================================================================
# Error mapping
# ===================================================================


class TestErrorMapping:
    @respx.mock
    @pytest.mark.asyncio
    async def test_401_raises_authentication_error(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/users/me").mock(return_value=httpx.Response(401, json={"detail": "Invalid key"}))
        async with client as c:
            with pytest.raises(AuthenticationError, match="Invalid key") as exc_info:
                await c.get_current_user()
        assert exc_info.value.status_code == 401

    @respx.mock
    @pytest.mark.asyncio
    async def test_403_raises_forbidden_error(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/documents/d1").mock(return_value=httpx.Response(403, json={"detail": "Not owner"}))
        async with client as c:
            with pytest.raises(ForbiddenError, match="Not owner"):
                await c.get_document("d1")

    @respx.mock
    @pytest.mark.asyncio
    async def test_404_raises_not_found_error(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/documents/missing").mock(
            return_value=httpx.Response(404, json={"detail": "Document not found"})
        )
        async with client as c:
            with pytest.raises(NotFoundError, match="Document not found"):
                await c.get_document("missing")

    @respx.mock
    @pytest.mark.asyncio
    async def test_500_raises_server_error(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/users/me").mock(return_value=httpx.Response(500, json={"detail": "Internal error"}))
        async with client as c:
            with pytest.raises(ServerError) as exc_info:
                await c.get_current_user()
        assert exc_info.value.status_code == 500

    @respx.mock
    @pytest.mark.asyncio
    async def test_422_raises_generic_api_error(self, client: CollabMarkClient) -> None:
        respx.post(f"{BASE}/api/documents").mock(return_value=httpx.Response(422, json={"detail": "Validation failed"}))
        async with client as c:
            with pytest.raises(APIError) as exc_info:
                await c.create_document(title="x")
        assert exc_info.value.status_code == 422

    @respx.mock
    @pytest.mark.asyncio
    async def test_error_with_non_json_body(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/users/me").mock(return_value=httpx.Response(502, text="<html>Bad Gateway</html>"))
        async with client as c:
            with pytest.raises(ServerError) as exc_info:
                await c.get_current_user()
        assert "<html>" in exc_info.value.response_body

    @respx.mock
    @pytest.mark.asyncio
    async def test_non_json_success_response_raises(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/users/me").mock(
            return_value=httpx.Response(200, text="not json", headers={"content-type": "text/html"})
        )
        async with client as c:
            with pytest.raises(APIError, match="Expected JSON"):
                await c.get_current_user()


# ===================================================================
# Retry logic
# ===================================================================


class TestRetryLogic:
    @respx.mock
    @pytest.mark.asyncio
    async def test_retries_on_503_then_succeeds(self, retrying_client: CollabMarkClient) -> None:
        route = respx.get(f"{BASE}/api/users/me").mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json=SAMPLE_USER),
            ]
        )
        async with retrying_client as c:
            result = await c.get_current_user()
        assert result["id"] == "u1"
        assert route.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_retries_on_429_then_succeeds(self, retrying_client: CollabMarkClient) -> None:
        route = respx.get(f"{BASE}/api/users/me").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(200, json=SAMPLE_USER),
            ]
        )
        async with retrying_client as c:
            result = await c.get_current_user()
        assert result["id"] == "u1"
        assert route.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_429_exhausted_raises_rate_limit_error(self) -> None:
        respx.get(f"{BASE}/api/users/me").mock(return_value=httpx.Response(429, json={"detail": "Too many requests"}))
        c = CollabMarkClient(api_key=API_KEY, base_url=BASE, max_retries=2)
        async with c:
            with pytest.raises(RateLimitError, match="Too many requests"):
                await c.get_current_user()

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_retry_on_404(self, retrying_client: CollabMarkClient) -> None:
        route = respx.get(f"{BASE}/api/documents/bad").mock(
            return_value=httpx.Response(404, json={"detail": "Not found"})
        )
        async with retrying_client as c:
            with pytest.raises(NotFoundError):
                await c.get_document("bad")
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_retry_on_400(self, retrying_client: CollabMarkClient) -> None:
        route = respx.post(f"{BASE}/api/documents").mock(
            return_value=httpx.Response(400, json={"detail": "Bad request"})
        )
        async with retrying_client as c:
            with pytest.raises(APIError):
                await c.create_document(title="x")
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_gives_up_after_max_retries(self) -> None:
        respx.get(f"{BASE}/api/users/me").mock(return_value=httpx.Response(503))
        c = CollabMarkClient(api_key=API_KEY, base_url=BASE, max_retries=2)
        async with c:
            with pytest.raises(ServerError):
                await c.get_current_user()

    @respx.mock
    @pytest.mark.asyncio
    async def test_retries_on_connect_error(self, retrying_client: CollabMarkClient) -> None:
        route = respx.get(f"{BASE}/api/users/me").mock(
            side_effect=[
                httpx.ConnectError("Connection refused"),
                httpx.Response(200, json=SAMPLE_USER),
            ]
        )
        async with retrying_client as c:
            result = await c.get_current_user()
        assert result["id"] == "u1"
        assert route.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_retries_on_timeout(self, retrying_client: CollabMarkClient) -> None:
        route = respx.get(f"{BASE}/api/users/me").mock(
            side_effect=[
                httpx.ReadTimeout("timed out"),
                httpx.Response(200, json=SAMPLE_USER),
            ]
        )
        async with retrying_client as c:
            result = await c.get_current_user()
        assert result["id"] == "u1"
        assert route.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_network_error_exhausts_retries(self) -> None:
        respx.get(f"{BASE}/api/users/me").mock(side_effect=httpx.ConnectError("down"))
        c = CollabMarkClient(api_key=API_KEY, base_url=BASE, max_retries=2)
        async with c:
            with pytest.raises(APIError, match="failed after 2 attempts"):
                await c.get_current_user()


# ===================================================================
# User endpoint
# ===================================================================


class TestGetCurrentUser:
    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_user_dict(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/users/me").mock(return_value=httpx.Response(200, json=SAMPLE_USER))
        async with client as c:
            user = await c.get_current_user()
        assert user["email"] == "pm@acme.com"
        assert user["name"] == "Priya"


# ===================================================================
# Folder endpoints
# ===================================================================


class TestGetFolder:
    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_folder_info(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/folders/f1").mock(return_value=httpx.Response(200, json=SAMPLE_FOLDER))
        async with client as c:
            folder = await c.get_folder("f1")
        assert isinstance(folder, FolderInfo)
        assert folder.id == "f1"
        assert folder.name == "Engineering Context"
        assert folder.owner_id == "u1"


class TestListFolderContents:
    @respx.mock
    @pytest.mark.asyncio
    async def test_with_folder_id(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/folders/contents").mock(
            return_value=httpx.Response(
                200,
                json={
                    "folders": [SAMPLE_FOLDER],
                    "documents": [SAMPLE_DOCUMENT],
                    "permission": "edit",
                },
            )
        )
        async with client as c:
            contents = await c.list_folder_contents("f1")
        assert isinstance(contents, FolderContents)
        assert len(contents.folders) == 1
        assert len(contents.documents) == 1
        assert contents.permission == "edit"

    @respx.mock
    @pytest.mark.asyncio
    async def test_root_level_no_folder_id(self, client: CollabMarkClient) -> None:
        route = respx.get(f"{BASE}/api/folders/contents").mock(
            return_value=httpx.Response(
                200,
                json={
                    "folders": [],
                    "documents": [],
                    "permission": "edit",
                },
            )
        )
        async with client as c:
            contents = await c.list_folder_contents()
        assert contents.folders == []
        assert contents.documents == []
        url = str(route.calls[0].request.url)
        assert "folder_id" not in url

    @respx.mock
    @pytest.mark.asyncio
    async def test_folder_id_sent_as_query_param(self, client: CollabMarkClient) -> None:
        route = respx.get(f"{BASE}/api/folders/contents").mock(
            return_value=httpx.Response(
                200,
                json={
                    "folders": [],
                    "documents": [],
                    "permission": "view",
                },
            )
        )
        async with client as c:
            await c.list_folder_contents("abc123")
        url = str(route.calls[0].request.url)
        assert "folder_id=abc123" in url


class TestListSharedFolders:
    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_shared_folders(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/folders/shared").mock(return_value=httpx.Response(200, json=[SAMPLE_SHARED_FOLDER]))
        async with client as c:
            folders = await c.list_shared_folders()
        assert len(folders) == 1
        assert isinstance(folders[0], SharedFolder)
        assert folders[0].permission == "edit"
        assert folders[0].owner_name == "Priya"

    @respx.mock
    @pytest.mark.asyncio
    async def test_empty_list(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/folders/shared").mock(return_value=httpx.Response(200, json=[]))
        async with client as c:
            folders = await c.list_shared_folders()
        assert folders == []


class TestCreateFolder:
    @respx.mock
    @pytest.mark.asyncio
    async def test_creates_folder_at_root(self, client: CollabMarkClient) -> None:
        route = respx.post(f"{BASE}/api/folders").mock(return_value=httpx.Response(201, json=SAMPLE_FOLDER))
        async with client as c:
            folder = await c.create_folder("Engineering Context")
        assert isinstance(folder, FolderInfo)
        assert folder.name == "Engineering Context"
        body = route.calls[0].request.content
        assert b'"name"' in body
        assert b'"parent_id"' not in body

    @respx.mock
    @pytest.mark.asyncio
    async def test_creates_nested_folder(self, client: CollabMarkClient) -> None:
        route = respx.post(f"{BASE}/api/folders").mock(
            return_value=httpx.Response(201, json={**SAMPLE_FOLDER, "parent_id": "p1"})
        )
        async with client as c:
            folder = await c.create_folder("Sub", parent_id="p1")
        assert folder.parent_id == "p1"
        body = route.calls[0].request.content
        assert b'"parent_id"' in body


# ===================================================================
# Document endpoints
# ===================================================================


class TestGetDocument:
    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_document_info(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/documents/d1").mock(return_value=httpx.Response(200, json=SAMPLE_DOCUMENT))
        async with client as c:
            doc = await c.get_document("d1")
        assert isinstance(doc, DocumentInfo)
        assert doc.id == "d1"
        assert doc.title == "Architecture Overview"
        assert "# Architecture" in doc.content
        assert doc.folder_id == "f1"
        assert doc.content_length == 30


class TestCreateDocument:
    @respx.mock
    @pytest.mark.asyncio
    async def test_creates_document(self, client: CollabMarkClient) -> None:
        route = respx.post(f"{BASE}/api/documents").mock(return_value=httpx.Response(201, json=SAMPLE_DOCUMENT))
        async with client as c:
            doc = await c.create_document("Architecture Overview", "# Arch", folder_id="f1")
        assert isinstance(doc, DocumentInfo)
        body = route.calls[0].request.content
        assert b'"title"' in body
        assert b'"content"' in body
        assert b'"folder_id"' in body

    @respx.mock
    @pytest.mark.asyncio
    async def test_creates_document_without_folder(self, client: CollabMarkClient) -> None:
        route = respx.post(f"{BASE}/api/documents").mock(
            return_value=httpx.Response(201, json={**SAMPLE_DOCUMENT, "folder_id": None})
        )
        async with client as c:
            await c.create_document("Untitled")
        body = route.calls[0].request.content
        assert b'"folder_id"' not in body


class TestUpdateDocument:
    @respx.mock
    @pytest.mark.asyncio
    async def test_update_title_only(self, client: CollabMarkClient) -> None:
        route = respx.put(f"{BASE}/api/documents/d1").mock(
            return_value=httpx.Response(200, json={**SAMPLE_DOCUMENT, "title": "New"})
        )
        async with client as c:
            doc = await c.update_document("d1", title="New")
        assert doc.title == "New"
        body = route.calls[0].request.content
        assert b'"title"' in body
        assert b'"content"' not in body

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_content_only(self, client: CollabMarkClient) -> None:
        route = respx.put(f"{BASE}/api/documents/d1").mock(return_value=httpx.Response(200, json=SAMPLE_DOCUMENT))
        async with client as c:
            await c.update_document("d1", content="updated")
        body = route.calls[0].request.content
        assert b'"content"' in body
        assert b'"title"' not in body

    @respx.mock
    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, client: CollabMarkClient) -> None:
        respx.put(f"{BASE}/api/documents/d1").mock(return_value=httpx.Response(200, json=SAMPLE_DOCUMENT))
        async with client as c:
            doc = await c.update_document("d1", title="T", content="C", folder_id="f2")
        assert isinstance(doc, DocumentInfo)


class TestDeleteDocument:
    @respx.mock
    @pytest.mark.asyncio
    async def test_soft_deletes_document(self, client: CollabMarkClient) -> None:
        respx.delete(f"{BASE}/api/documents/d1").mock(
            return_value=httpx.Response(200, json={**SAMPLE_DOCUMENT, "is_deleted": True})
        )
        async with client as c:
            doc = await c.delete_document("d1")
        assert isinstance(doc, DocumentInfo)
        assert doc.id == "d1"


class TestListDocuments:
    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_document_list(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/documents").mock(return_value=httpx.Response(200, json=[SAMPLE_DOCUMENT]))
        async with client as c:
            docs = await c.list_documents()
        assert len(docs) == 1
        assert isinstance(docs[0], DocumentInfo)

    @respx.mock
    @pytest.mark.asyncio
    async def test_empty_list(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/documents").mock(return_value=httpx.Response(200, json=[]))
        async with client as c:
            docs = await c.list_documents()
        assert docs == []


# ===================================================================
# Datetime parsing
# ===================================================================


class TestDatetimeParsing:
    @respx.mock
    @pytest.mark.asyncio
    async def test_parses_iso_datetime(self, client: CollabMarkClient) -> None:
        respx.get(f"{BASE}/api/documents/d1").mock(return_value=httpx.Response(200, json=SAMPLE_DOCUMENT))
        async with client as c:
            doc = await c.get_document("d1")
        assert doc.created_at is not None
        assert doc.created_at.year == 2025

    @respx.mock
    @pytest.mark.asyncio
    async def test_handles_missing_datetime(self, client: CollabMarkClient) -> None:
        payload = {**SAMPLE_DOCUMENT, "created_at": None, "updated_at": None}
        respx.get(f"{BASE}/api/documents/d1").mock(return_value=httpx.Response(200, json=payload))
        async with client as c:
            doc = await c.get_document("d1")
        assert doc.created_at is None
        assert doc.updated_at is None
