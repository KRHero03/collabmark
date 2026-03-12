"""Async REST API client for the CollabMark backend.

Wraps all endpoints needed for folder/document sync with automatic
auth-header injection, exponential-backoff retry for transient failures,
and structured error types.

Usage::

    async with CollabMarkClient(api_key="cm_...") as client:
        user = await client.get_current_user()
        contents = await client.list_folder_contents(folder_id)
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from typing import Any, Optional, Self

import httpx

from collabmark import __version__
from collabmark.lib.config import API_KEY_HEADER, get_api_url
from collabmark.types import DocumentInfo, FolderContents, FolderInfo, SharedFolder

logger = logging.getLogger(__name__)

_USER_AGENT = f"collabmark-cli/{__version__}"
_READ_TIMEOUT = 10.0
_WRITE_TIMEOUT = 15.0

_RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})
_MAX_RETRY_AFTER = 60
_DEFAULT_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0
_BACKOFF_MAX = 30.0
_JITTER_MAX = 0.5


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class APIError(Exception):
    """Base error for all CollabMark API failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class AuthenticationError(APIError):
    """401 — invalid or expired credentials."""


class ForbiddenError(APIError):
    """403 — insufficient permissions."""


class NotFoundError(APIError):
    """404 — resource does not exist."""


class RateLimitError(APIError):
    """429 — too many requests."""


class ServerError(APIError):
    """5xx — server-side failure."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUS_TO_ERROR: dict[int, type[APIError]] = {
    401: AuthenticationError,
    403: ForbiddenError,
    404: NotFoundError,
    429: RateLimitError,
}


def _parse_error_detail(response: httpx.Response) -> str:
    """Extract a human-readable message from an error response."""
    try:
        body = response.json()
        if isinstance(body, dict) and "detail" in body:
            detail = body["detail"]
            if isinstance(detail, str):
                return detail
            return str(detail)
    except (ValueError, KeyError):
        pass
    return response.text[:200] if response.text else f"HTTP {response.status_code}"


def _raise_for_status(response: httpx.Response) -> None:
    """Raise the appropriate ``APIError`` subclass for non-2xx responses."""
    if response.is_success:
        return

    detail = _parse_error_detail(response)
    status = response.status_code
    body = response.text

    error_cls = _STATUS_TO_ERROR.get(status)
    if error_cls:
        raise error_cls(detail, status_code=status, response_body=body)
    if 500 <= status < 600:
        raise ServerError(detail, status_code=status, response_body=body)
    raise APIError(detail, status_code=status, response_body=body)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _parse_folder(data: dict[str, Any]) -> FolderInfo:
    return FolderInfo(
        id=data["id"],
        name=data["name"],
        owner_id=data["owner_id"],
        parent_id=data.get("parent_id"),
        created_at=_parse_datetime(data.get("created_at")),
        updated_at=_parse_datetime(data.get("updated_at")),
    )


def _parse_shared_folder(data: dict[str, Any]) -> SharedFolder:
    return SharedFolder(
        id=data["id"],
        name=data["name"],
        owner_id=data["owner_id"],
        owner_name=data.get("owner_name", ""),
        owner_email=data.get("owner_email", ""),
        permission=data.get("permission", "view"),
        parent_id=data.get("parent_id"),
        created_at=_parse_datetime(data.get("created_at")),
        updated_at=_parse_datetime(data.get("updated_at")),
    )


def _parse_document(data: dict[str, Any]) -> DocumentInfo:
    return DocumentInfo(
        id=data["id"],
        title=data["title"],
        content=data.get("content", ""),
        owner_id=data.get("owner_id", ""),
        folder_id=data.get("folder_id"),
        content_length=data.get("content_length", 0),
        created_at=_parse_datetime(data.get("created_at")),
        updated_at=_parse_datetime(data.get("updated_at")),
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class CollabMarkClient:
    """Async HTTP client for the CollabMark REST API.

    Use as an async context manager to ensure the underlying connection
    pool is properly closed::

        async with CollabMarkClient(api_key) as client:
            ...
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        *,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        read_timeout: float = _READ_TIMEOUT,
        write_timeout: float = _WRITE_TIMEOUT,
    ) -> None:
        self._api_key = api_key
        self._base_url = (base_url or get_api_url()).rstrip("/")
        self._max_retries = max_retries
        self._read_timeout = read_timeout
        self._write_timeout = write_timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                API_KEY_HEADER: self._api_key,
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
            },
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # -- internal request with retry -----------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        if not self._client:
            raise RuntimeError("Client not open. Use 'async with CollabMarkClient(...) as c:'")

        is_read = method.upper() == "GET"
        timeout = self._read_timeout if is_read else self._write_timeout

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = await self._client.request(
                    method,
                    path,
                    json=json,
                    params=params,
                    timeout=timeout,
                )
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                await self._backoff(attempt, None)
                continue

            if response.status_code not in _RETRYABLE_STATUS_CODES:
                _raise_for_status(response)
                return response

            last_exc = None
            await self._backoff(attempt, response)

        if last_exc:
            raise APIError(
                f"Request failed after {self._max_retries} attempts: {last_exc}",
                status_code=None,
            )
        _raise_for_status(response)  # type: ignore[possibly-undefined]
        return response  # type: ignore[possibly-undefined]

    async def _backoff(self, attempt: int, response: httpx.Response | None) -> None:
        delay = min(_BACKOFF_BASE * (2**attempt), _BACKOFF_MAX)

        if response is not None and response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = min(float(retry_after), _MAX_RETRY_AFTER)
                except ValueError:
                    pass

        delay += random.uniform(0, _JITTER_MAX)
        logger.debug("Retry attempt %d, sleeping %.2fs", attempt + 1, delay)
        await asyncio.sleep(delay)

    def _ensure_json(self, response: httpx.Response) -> Any:
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            raise APIError(
                f"Expected JSON response but got Content-Type: {content_type}",
                status_code=response.status_code,
                response_body=response.text[:500],
            )
        return response.json()

    # -- User ----------------------------------------------------------------

    async def get_current_user(self) -> dict[str, Any]:
        """``GET /api/users/me`` — returns the raw user profile dict.

        Callers can construct ``UserInfo`` from the result if needed.
        """
        resp = await self._request("GET", "/api/users/me")
        return self._ensure_json(resp)

    # -- Folders -------------------------------------------------------------

    async def get_folder(self, folder_id: str) -> FolderInfo:
        """``GET /api/folders/{folder_id}``"""
        resp = await self._request("GET", f"/api/folders/{folder_id}")
        return _parse_folder(self._ensure_json(resp))

    async def list_folder_contents(
        self,
        folder_id: Optional[str] = None,
    ) -> FolderContents:
        """``GET /api/folders/contents?folder_id={id}``

        Pass ``folder_id=None`` for root-level contents.
        """
        params: dict[str, Any] = {}
        if folder_id is not None:
            params["folder_id"] = folder_id

        resp = await self._request("GET", "/api/folders/contents", params=params)
        data = self._ensure_json(resp)
        return FolderContents(
            folders=[_parse_folder(f) for f in data.get("folders", [])],
            documents=[_parse_document(d) for d in data.get("documents", [])],
            permission=data.get("permission", "edit"),
        )

    async def get_folder_tree(self, folder_id: str) -> dict[str, Any]:
        """``GET /api/folders/{folder_id}/tree``

        Returns the full recursive tree of sub-folders and documents
        under a folder in a single request.
        """
        resp = await self._request("GET", f"/api/folders/{folder_id}/tree")
        return self._ensure_json(resp)

    async def list_shared_folders(self) -> list[SharedFolder]:
        """``GET /api/folders/shared``"""
        resp = await self._request("GET", "/api/folders/shared")
        return [_parse_shared_folder(item) for item in self._ensure_json(resp)]

    async def create_folder(
        self,
        name: str,
        parent_id: Optional[str] = None,
    ) -> FolderInfo:
        """``POST /api/folders``"""
        body: dict[str, Any] = {"name": name}
        if parent_id is not None:
            body["parent_id"] = parent_id
        resp = await self._request("POST", "/api/folders", json=body)
        return _parse_folder(self._ensure_json(resp))

    # -- Documents -----------------------------------------------------------

    async def get_document(self, doc_id: str) -> DocumentInfo:
        """``GET /api/documents/{doc_id}``"""
        resp = await self._request("GET", f"/api/documents/{doc_id}")
        return _parse_document(self._ensure_json(resp))

    async def create_document(
        self,
        title: str,
        content: str = "",
        folder_id: Optional[str] = None,
    ) -> DocumentInfo:
        """``POST /api/documents``"""
        body: dict[str, Any] = {"title": title, "content": content}
        if folder_id is not None:
            body["folder_id"] = folder_id
        resp = await self._request("POST", "/api/documents", json=body)
        return _parse_document(self._ensure_json(resp))

    async def update_document(
        self,
        doc_id: str,
        *,
        title: Optional[str] = None,
        content: Optional[str] = None,
        folder_id: Optional[str] = None,
    ) -> DocumentInfo:
        """``PUT /api/documents/{doc_id}``"""
        body: dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if content is not None:
            body["content"] = content
        if folder_id is not None:
            body["folder_id"] = folder_id
        resp = await self._request("PUT", f"/api/documents/{doc_id}", json=body)
        return _parse_document(self._ensure_json(resp))

    async def delete_document(self, doc_id: str) -> DocumentInfo:
        """``DELETE /api/documents/{doc_id}`` — soft-delete."""
        resp = await self._request("DELETE", f"/api/documents/{doc_id}")
        return _parse_document(self._ensure_json(resp))

    async def list_documents(self) -> list[DocumentInfo]:
        """``GET /api/documents``"""
        resp = await self._request("GET", "/api/documents")
        return [_parse_document(d) for d in self._ensure_json(resp)]
