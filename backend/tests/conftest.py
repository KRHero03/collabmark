import asyncio
from unittest.mock import patch

import pytest
import pytest_asyncio
from app.main import DOCUMENT_MODELS, app
from app.models.user import User
from beanie import init_beanie
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def init_db():
    client = AsyncMongoMockClient()
    await init_beanie(
        database=client["test_collabmark"],
        document_models=DOCUMENT_MODELS,
    )
    yield
    await client.drop_database("test_collabmark")


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def _mock_blob_storage():
    """Prevent all tests from hitting real S3/MinIO.

    `get_public_url` is left unpatched since it's pure string formatting.
    """
    with (
        patch("app.services.blob_storage.upload", side_effect=lambda key, *a, **kw: key),
        patch("app.services.blob_storage.delete_prefix"),
        patch("app.services.blob_storage._ensure_bucket"),
    ):
        yield


@pytest_asyncio.fixture
async def test_user() -> User:
    user = User(
        google_id="google-test-123",
        email="test@example.com",
        name="Test User",
        avatar_url="https://example.com/avatar.png",
    )
    await user.insert()
    return user
