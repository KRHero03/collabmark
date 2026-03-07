"""Comprehensive unit tests for document_service."""

from unittest.mock import patch

import pytest
from app.models.comment import Comment
from app.models.document import Document_, DocumentCreate, DocumentUpdate, GeneralAccess
from app.models.document_version import DocumentVersion
from app.models.document_view import DocumentView
from app.models.folder import Folder, FolderAccess
from app.models.share_link import DocumentAccess, Permission
from app.models.user import User
from app.services.document_service import (
    _find_doc,
    create_document,
    get_document,
    hard_delete_document,
    list_documents,
    list_trash,
    restore_document,
    soft_delete_document,
    update_document,
)
from beanie import PydanticObjectId
from fastapi import HTTPException


class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_create_without_folder_id(self, test_user: User):
        payload = DocumentCreate(title="My Doc", content="# Hello")
        doc = await create_document(test_user, payload)
        assert doc.title == "My Doc"
        assert doc.content == "# Hello"
        assert doc.owner_id == str(test_user.id)
        assert doc.folder_id is None
        assert doc.root_folder_id is None
        assert doc.is_deleted is False

    @pytest.mark.asyncio
    async def test_create_with_folder_id(self, test_user: User):
        folder = Folder(
            name="Test Folder",
            owner_id=str(test_user.id),
            root_folder_id=None,
        )
        await folder.insert()
        folder.root_folder_id = str(folder.id)
        await folder.save()

        payload = DocumentCreate(title="In Folder", content="", folder_id=str(folder.id))
        doc = await create_document(test_user, payload)
        assert doc.folder_id == str(folder.id)
        assert doc.root_folder_id == str(folder.id)

    @pytest.mark.asyncio
    async def test_create_exceeds_max_documents(self, test_user: User):
        with patch("app.services.document_service.MAX_DOCUMENTS_PER_USER", 2):
            await create_document(test_user, DocumentCreate(title="Doc 1"))
            await create_document(test_user, DocumentCreate(title="Doc 2"))
            with pytest.raises(HTTPException) as exc_info:
                await create_document(test_user, DocumentCreate(title="Doc 3"))
            assert exc_info.value.status_code == 403
            assert "Document limit reached" in exc_info.value.detail
            assert "2" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_folder_access_denied(self, test_user: User):
        other_user = User(
            google_id="google-other",
            email="other@example.com",
            name="Other User",
        )
        await other_user.insert()

        folder = Folder(
            name="Other Folder",
            owner_id=str(other_user.id),
            root_folder_id=str(other_user.id),
        )
        await folder.insert()

        payload = DocumentCreate(
            title="Sneaky",
            folder_id=str(folder.id),
        )
        with pytest.raises(HTTPException) as exc_info:
            await create_document(test_user, payload)
        assert exc_info.value.status_code == 403
        assert "Not authorized" in exc_info.value.detail or "view access" in exc_info.value.detail


class TestGetDocument:
    @pytest.mark.asyncio
    async def test_owner_can_get(self, test_user: User):
        doc = Document_(
            title="Owner Doc",
            content="",
            owner_id=str(test_user.id),
        )
        await doc.insert()
        result = await get_document(str(doc.id), test_user)
        assert result.id == doc.id
        assert result.title == "Owner Doc"

    @pytest.mark.asyncio
    async def test_non_owner_with_access_can_get(self, test_user: User):
        owner = User(
            google_id="google-owner",
            email="owner@example.com",
            name="Owner",
        )
        await owner.insert()
        doc = Document_(
            title="Shared",
            content="",
            owner_id=str(owner.id),
        )
        await doc.insert()
        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(test_user.id),
            permission=Permission.VIEW,
            granted_by=str(owner.id),
        )
        await access.insert()

        result = await get_document(str(doc.id), test_user)
        assert result.id == doc.id

    @pytest.mark.asyncio
    async def test_non_owner_without_access_403(self, test_user: User):
        owner = User(
            google_id="google-owner",
            email="owner@example.com",
            name="Owner",
        )
        await owner.insert()
        doc = Document_(
            title="Private",
            content="",
            owner_id=str(owner.id),
            general_access=GeneralAccess.RESTRICTED,
        )
        await doc.insert()

        with pytest.raises(HTTPException) as exc_info:
            await get_document(str(doc.id), test_user)
        assert exc_info.value.status_code == 403
        assert "Not authorized" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_nonexistent_doc_404(self, test_user: User):
        fake_id = "000000000000000000000001"
        with pytest.raises(HTTPException) as exc_info:
            await get_document(fake_id, test_user)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Document not found"

    @pytest.mark.asyncio
    async def test_malformed_id_404(self, test_user: User):
        with pytest.raises(HTTPException) as exc_info:
            await get_document("not-a-valid-id", test_user)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Document not found"


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_list_excludes_deleted_by_default(self, test_user: User):
        doc1 = Document_(title="Active", content="", owner_id=str(test_user.id))
        doc2 = Document_(title="Deleted", content="", owner_id=str(test_user.id))
        await doc1.insert()
        await doc2.insert()
        doc2.soft_delete()
        await doc2.save()

        docs = await list_documents(test_user, include_deleted=False)
        assert len(docs) == 1
        assert docs[0].title == "Active"

    @pytest.mark.asyncio
    async def test_list_includes_deleted_when_requested(self, test_user: User):
        doc1 = Document_(title="Active", content="", owner_id=str(test_user.id))
        doc2 = Document_(title="Deleted", content="", owner_id=str(test_user.id))
        await doc1.insert()
        await doc2.insert()
        doc2.soft_delete()
        await doc2.save()

        docs = await list_documents(test_user, include_deleted=True)
        assert len(docs) == 2
        titles = {d.title for d in docs}
        assert "Active" in titles
        assert "Deleted" in titles


class TestUpdateDocument:
    @pytest.mark.asyncio
    async def test_update_title_only(self, test_user: User):
        doc = Document_(
            title="Original",
            content="Content",
            owner_id=str(test_user.id),
        )
        await doc.insert()
        result = await update_document(
            str(doc.id),
            test_user,
            DocumentUpdate(title="New Title"),
        )
        assert result.title == "New Title"
        assert result.content == "Content"

    @pytest.mark.asyncio
    async def test_update_content_only(self, test_user: User):
        doc = Document_(
            title="Doc",
            content="Old",
            owner_id=str(test_user.id),
        )
        await doc.insert()
        result = await update_document(
            str(doc.id),
            test_user,
            DocumentUpdate(content="New content"),
        )
        assert result.content == "New content"

    @pytest.mark.asyncio
    async def test_update_both_title_and_content(self, test_user: User):
        doc = Document_(
            title="A",
            content="X",
            owner_id=str(test_user.id),
        )
        await doc.insert()
        result = await update_document(
            str(doc.id),
            test_user,
            DocumentUpdate(title="B", content="Y"),
        )
        assert result.title == "B"
        assert result.content == "Y"

    @pytest.mark.asyncio
    async def test_update_folder_id(self, test_user: User):
        folder = Folder(
            name="Target",
            owner_id=str(test_user.id),
            root_folder_id=None,
        )
        await folder.insert()
        folder.root_folder_id = str(folder.id)
        await folder.save()

        doc = Document_(title="Doc", content="", owner_id=str(test_user.id))
        await doc.insert()
        result = await update_document(
            str(doc.id),
            test_user,
            DocumentUpdate(folder_id=str(folder.id)),
        )
        assert result.folder_id == str(folder.id)

    @pytest.mark.asyncio
    async def test_update_no_edit_access_403(self, test_user: User):
        owner = User(
            google_id="google-owner",
            email="owner@example.com",
            name="Owner",
        )
        await owner.insert()
        doc = Document_(
            title="Doc",
            content="",
            owner_id=str(owner.id),
        )
        await doc.insert()
        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(test_user.id),
            permission=Permission.VIEW,
            granted_by=str(owner.id),
        )
        await access.insert()

        with pytest.raises(HTTPException) as exc_info:
            await update_document(
                str(doc.id),
                test_user,
                DocumentUpdate(title="Hacked"),
            )
        assert exc_info.value.status_code == 403
        assert "view access" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_content_triggers_version_snapshot(self, test_user: User):
        doc = Document_(
            title="Versioned",
            content="v1",
            owner_id=str(test_user.id),
        )
        await doc.insert()
        await update_document(
            str(doc.id),
            test_user,
            DocumentUpdate(content="v2"),
        )
        versions = await DocumentVersion.find(DocumentVersion.document_id == str(doc.id)).to_list()
        assert len(versions) == 1
        assert versions[0].content == "v2"
        assert versions[0].version_number == 1


class TestSoftDeleteDocument:
    @pytest.mark.asyncio
    async def test_owner_can_soft_delete(self, test_user: User):
        doc = Document_(title="Delete Me", content="", owner_id=str(test_user.id))
        await doc.insert()
        result = await soft_delete_document(str(doc.id), test_user)
        assert result.is_deleted is True
        assert result.deleted_at is not None

    @pytest.mark.asyncio
    async def test_editor_cannot_delete_403(self, test_user: User):
        owner = User(
            google_id="google-owner",
            email="owner@example.com",
            name="Owner",
        )
        await owner.insert()
        doc = Document_(title="Doc", content="", owner_id=str(owner.id))
        await doc.insert()
        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(test_user.id),
            permission=Permission.EDIT,
            granted_by=str(owner.id),
        )
        await access.insert()

        with pytest.raises(HTTPException) as exc_info:
            await soft_delete_document(str(doc.id), test_user)
        assert exc_info.value.status_code == 403
        assert "permission to delete" in exc_info.value.detail


class TestRestoreDocument:
    @pytest.mark.asyncio
    async def test_owner_can_restore(self, test_user: User):
        doc = Document_(title="Restore Me", content="", owner_id=str(test_user.id))
        await doc.insert()
        doc.soft_delete()
        await doc.save()
        result = await restore_document(str(doc.id), test_user)
        assert result.is_deleted is False
        assert result.deleted_at is None

    @pytest.mark.asyncio
    async def test_non_owner_cannot_restore_403(self, test_user: User):
        owner = User(
            google_id="google-owner",
            email="owner@example.com",
            name="Owner",
        )
        await owner.insert()
        doc = Document_(title="Doc", content="", owner_id=str(owner.id))
        await doc.insert()
        doc.soft_delete()
        await doc.save()

        with pytest.raises(HTTPException) as exc_info:
            await restore_document(str(doc.id), test_user)
        assert exc_info.value.status_code == 403


class TestHardDeleteDocument:
    @pytest.mark.asyncio
    async def test_cascading_cleanup(self, test_user: User):
        doc = Document_(title="Hard Delete", content="", owner_id=str(test_user.id))
        await doc.insert()
        doc_id = str(doc.id)

        comment = Comment(
            document_id=doc_id,
            author_id=str(test_user.id),
            author_name="Test",
            content="A comment",
        )
        await comment.insert()
        version = DocumentVersion(
            document_id=doc_id,
            version_number=1,
            content="",
            author_id=str(test_user.id),
            author_name="Test",
            summary="v1",
        )
        await version.insert()
        access = DocumentAccess(
            document_id=doc_id,
            user_id=str(test_user.id),
            permission=Permission.EDIT,
            granted_by=str(test_user.id),
        )
        await access.insert()
        view = DocumentView(user_id=str(test_user.id), document_id=doc_id)
        await view.insert()

        await hard_delete_document(doc_id, test_user)

        assert await Document_.get(PydanticObjectId(doc_id)) is None
        assert await Comment.find(Comment.document_id == doc_id).first_or_none() is None
        assert await DocumentVersion.find(DocumentVersion.document_id == doc_id).first_or_none() is None
        assert await DocumentAccess.find(DocumentAccess.document_id == doc_id).first_or_none() is None
        assert await DocumentView.find(DocumentView.document_id == doc_id).first_or_none() is None


class TestAssertAccess:
    """Test _assert_access via get_document and update_document."""

    @pytest.mark.asyncio
    async def test_owner_bypass(self, test_user: User):
        doc = Document_(title="Mine", content="", owner_id=str(test_user.id))
        await doc.insert()
        result = await get_document(str(doc.id), test_user)
        assert result.id == doc.id

    @pytest.mark.asyncio
    async def test_explicit_document_access_view(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(title="D", content="", owner_id=str(owner.id))
        await doc.insert()
        await DocumentAccess(
            document_id=str(doc.id),
            user_id=str(test_user.id),
            permission=Permission.VIEW,
            granted_by=str(owner.id),
        ).insert()
        result = await get_document(str(doc.id), test_user)
        assert result.id == doc.id

    @pytest.mark.asyncio
    async def test_explicit_document_access_edit_required_view_only_403(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(title="D", content="", owner_id=str(owner.id))
        await doc.insert()
        await DocumentAccess(
            document_id=str(doc.id),
            user_id=str(test_user.id),
            permission=Permission.VIEW,
            granted_by=str(owner.id),
        ).insert()
        with pytest.raises(HTTPException) as exc_info:
            await update_document(str(doc.id), test_user, DocumentUpdate(title="X"))
        assert exc_info.value.status_code == 403
        assert "view access" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_general_access_anyone_view(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(
            title="D",
            content="",
            owner_id=str(owner.id),
            general_access=GeneralAccess.ANYONE_VIEW,
        )
        await doc.insert()
        result = await get_document(str(doc.id), test_user)
        assert result.id == doc.id

    @pytest.mark.asyncio
    async def test_general_access_anyone_edit(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(
            title="D",
            content="",
            owner_id=str(owner.id),
            general_access=GeneralAccess.ANYONE_EDIT,
        )
        await doc.insert()
        result = await update_document(str(doc.id), test_user, DocumentUpdate(title="X"))
        assert result.title == "X"

    @pytest.mark.asyncio
    async def test_general_access_restricted_no_access_403(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(
            title="D",
            content="",
            owner_id=str(owner.id),
            general_access=GeneralAccess.RESTRICTED,
        )
        await doc.insert()
        with pytest.raises(HTTPException) as exc_info:
            await get_document(str(doc.id), test_user)
        assert exc_info.value.status_code == 403
        assert "Not authorized" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_folder_chain_inheritance(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        folder = Folder(name="Parent", owner_id=str(owner.id))
        await folder.insert()
        folder.root_folder_id = str(folder.id)
        await folder.save()
        subfolder = Folder(
            name="Child",
            owner_id=str(owner.id),
            parent_id=str(folder.id),
            root_folder_id=str(folder.id),
        )
        await subfolder.insert()
        doc = Document_(
            title="D",
            content="",
            owner_id=str(owner.id),
            folder_id=str(subfolder.id),
            root_folder_id=str(folder.id),
        )
        await doc.insert()
        await FolderAccess(
            folder_id=str(folder.id),
            user_id=str(test_user.id),
            permission=Permission.VIEW,
            granted_by=str(owner.id),
        ).insert()
        result = await get_document(str(doc.id), test_user)
        assert result.id == doc.id


class TestAssertCanDelete:
    """Test _assert_can_delete via soft_delete and restore."""

    @pytest.mark.asyncio
    async def test_root_owner_can_delete(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        await soft_delete_document(str(doc.id), test_user)
        fetched = await Document_.get(doc.id)
        assert fetched.is_deleted is True

    @pytest.mark.asyncio
    async def test_entity_owner_can_delete(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        await soft_delete_document(str(doc.id), test_user)
        assert (await Document_.get(doc.id)).is_deleted is True

    @pytest.mark.asyncio
    async def test_editor_cannot_delete(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(title="D", content="", owner_id=str(owner.id))
        await doc.insert()
        await DocumentAccess(
            document_id=str(doc.id),
            user_id=str(test_user.id),
            permission=Permission.EDIT,
            granted_by=str(owner.id),
        ).insert()
        with pytest.raises(HTTPException) as exc_info:
            await soft_delete_document(str(doc.id), test_user)
        assert exc_info.value.status_code == 403
        assert "permission to delete" in exc_info.value.detail


class TestFindDoc:
    @pytest.mark.asyncio
    async def test_valid_id_returns_doc(self, test_user: User):
        doc = Document_(title="X", content="", owner_id=str(test_user.id))
        await doc.insert()
        result = await _find_doc(str(doc.id))
        assert result.id == doc.id

    @pytest.mark.asyncio
    async def test_invalid_id_format_404(self):
        with pytest.raises(HTTPException) as exc_info:
            await _find_doc("invalid")
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Document not found"

    @pytest.mark.asyncio
    async def test_nonexistent_id_404(self):
        with pytest.raises(HTTPException) as exc_info:
            await _find_doc("000000000000000000000001")
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Document not found"


class TestListTrash:
    @pytest.mark.asyncio
    async def test_list_trash_returns_deleted_only(self, test_user: User):
        doc1 = Document_(title="Active", content="", owner_id=str(test_user.id))
        doc2 = Document_(title="Trashed", content="", owner_id=str(test_user.id))
        await doc1.insert()
        await doc2.insert()
        doc2.soft_delete()
        await doc2.save()

        trash = await list_trash(test_user)
        assert len(trash) == 1
        assert trash[0].title == "Trashed"


class TestHardDeleteDocumentCrdtSkip:
    """Test hard_delete_document skips CRDT cleanup when MongoYStore._db is None."""

    @pytest.mark.asyncio
    async def test_hard_delete_skips_crdt_when_db_none(self, test_user: User):
        from app.services.crdt_store import MongoYStore

        doc = Document_(title="CRDT Doc", content="", owner_id=str(test_user.id))
        await doc.insert()
        doc_id = str(doc.id)

        original_db = MongoYStore._db
        try:
            MongoYStore._db = None
            await hard_delete_document(doc_id, test_user)
            assert await Document_.get(doc.id) is None
        finally:
            MongoYStore._db = original_db
