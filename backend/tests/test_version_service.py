"""Comprehensive unit tests for version_service (service level)."""

import pytest

from app.models.document import Document_
from app.models.document_version import DocumentVersion
from app.models.user import User
from app.services.version_service import (
    _find_doc_or_404,
    get_version,
    list_versions,
    save_snapshot,
)


class TestSaveSnapshot:
    @pytest.mark.asyncio
    async def test_creates_first_version_number_one(self, test_user: User):
        doc = Document_(title="D", content="Initial", owner_id=str(test_user.id))
        await doc.insert()
        version = await save_snapshot(str(doc.id), test_user, "Initial")
        assert version is not None
        assert version.version_number == 1
        assert version.content == "Initial"
        assert version.author_id == str(test_user.id)
        assert version.author_name == test_user.name

    @pytest.mark.asyncio
    async def test_increments_version_numbers(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        v1 = await save_snapshot(str(doc.id), test_user, "v1")
        v2 = await save_snapshot(str(doc.id), test_user, "v2")
        v3 = await save_snapshot(str(doc.id), test_user, "v3")
        assert v1.version_number == 1
        assert v2.version_number == 2
        assert v3.version_number == 3

    @pytest.mark.asyncio
    async def test_deduplication_same_content_returns_none(self, test_user: User):
        doc = Document_(title="D", content="Same", owner_id=str(test_user.id))
        await doc.insert()
        v1 = await save_snapshot(str(doc.id), test_user, "Same")
        assert v1 is not None
        v2 = await save_snapshot(str(doc.id), test_user, "Same")
        assert v2 is None
        versions = await list_versions(str(doc.id))
        assert len(versions) == 1

    @pytest.mark.asyncio
    async def test_summary_auto_generated(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        version = await save_snapshot(str(doc.id), test_user, "Content")
        assert version.summary
        assert "Version 1" in version.summary
        assert test_user.name in version.summary

    @pytest.mark.asyncio
    async def test_custom_summary_used(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        version = await save_snapshot(
            str(doc.id),
            test_user,
            "Content",
            summary="Fixed typo in intro",
        )
        assert version.summary == "Fixed typo in intro"


class TestListVersions:
    @pytest.mark.asyncio
    async def test_returns_sorted_by_version_number_desc(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        await save_snapshot(str(doc.id), test_user, "v1")
        await save_snapshot(str(doc.id), test_user, "v2")
        await save_snapshot(str(doc.id), test_user, "v3")
        versions = await list_versions(str(doc.id))
        assert len(versions) == 3
        assert versions[0].version_number == 3
        assert versions[1].version_number == 2
        assert versions[2].version_number == 1

    @pytest.mark.asyncio
    async def test_empty_list_for_no_versions(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        versions = await list_versions(str(doc.id))
        assert versions == []


class TestGetVersion:
    @pytest.mark.asyncio
    async def test_valid_version_returned(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        await save_snapshot(str(doc.id), test_user, "Content")
        version = await get_version(str(doc.id), 1)
        assert version.version_number == 1
        assert version.content == "Content"

    @pytest.mark.asyncio
    async def test_nonexistent_version_raises_404(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_version(str(doc.id), 99)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Version 99 not found"


class TestFindDocOr404:
    @pytest.mark.asyncio
    async def test_valid_doc_returned(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        result = await _find_doc_or_404(str(doc.id))
        assert result.id == doc.id

    @pytest.mark.asyncio
    async def test_invalid_id_format_raises_404(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await _find_doc_or_404("invalid")
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Document not found"

    @pytest.mark.asyncio
    async def test_nonexistent_doc_raises_404(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await _find_doc_or_404("000000000000000000000001")
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Document not found"
