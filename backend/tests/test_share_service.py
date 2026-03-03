"""Comprehensive unit tests for share_service."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.document import Document_, GeneralAccess
from app.models.document_view import DocumentView
from app.models.folder import Folder, FolderAccess
from app.models.share_link import DocumentAccess, Permission, ShareLink
from app.models.user import User
from app.services.share_service import (
    accept_share_link,
    add_collaborator,
    get_user_permission,
    list_collaborators,
    list_recently_viewed,
    list_shared_documents,
    list_share_links,
    record_document_view,
    remove_collaborator,
    resolve_share_link,
    revoke_share_link,
    update_general_access,
    create_share_link,
)


class TestCreateShareLink:
    @pytest.mark.asyncio
    async def test_create_valid(self, test_user: User):
        doc = Document_(title="Share Me", content="", owner_id=str(test_user.id))
        await doc.insert()
        link = await create_share_link(str(doc.id), test_user)
        assert link.document_id == str(doc.id)
        assert link.permission == Permission.VIEW
        assert link.created_by == str(test_user.id)
        assert link.token
        assert link.expires_at is None

    @pytest.mark.asyncio
    async def test_create_non_owner_403(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(title="D", content="", owner_id=str(owner.id))
        await doc.insert()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await create_share_link(str(doc.id), test_user)
        assert exc_info.value.status_code == 403
        assert "owner" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_create_custom_permission(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        link = await create_share_link(
            str(doc.id), test_user, permission=Permission.EDIT
        )
        assert link.permission == Permission.EDIT

    @pytest.mark.asyncio
    async def test_create_custom_expiry(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        link = await create_share_link(
            str(doc.id), test_user, expires_at=expires
        )
        assert link.expires_at == expires


class TestListShareLinks:
    @pytest.mark.asyncio
    async def test_owner_gets_links(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        link1 = await create_share_link(str(doc.id), test_user)
        link2 = await create_share_link(str(doc.id), test_user, permission=Permission.EDIT)
        links = await list_share_links(str(doc.id), test_user)
        assert len(links) == 2
        tokens = {l.token for l in links}
        assert link1.token in tokens
        assert link2.token in tokens

    @pytest.mark.asyncio
    async def test_non_owner_403(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(title="D", content="", owner_id=str(owner.id))
        await doc.insert()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await list_share_links(str(doc.id), test_user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_list(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        links = await list_share_links(str(doc.id), test_user)
        assert links == []


class TestRevokeShareLink:
    @pytest.mark.asyncio
    async def test_valid_revoke(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        link = await create_share_link(str(doc.id), test_user)
        await revoke_share_link(str(link.id), test_user)
        fetched = await ShareLink.get(link.id)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_invalid_link_id_404(self, test_user: User):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await revoke_share_link("000000000000000000000001", test_user)
        assert exc_info.value.status_code == 404
        assert "Share link not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_non_owner_403(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(title="D", content="", owner_id=str(owner.id))
        await doc.insert()
        link = await create_share_link(str(doc.id), owner)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await revoke_share_link(str(link.id), test_user)
        assert exc_info.value.status_code == 403


class TestResolveShareLink:
    @pytest.mark.asyncio
    async def test_valid_token(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        link = await create_share_link(str(doc.id), test_user)
        resolved_link, resolved_doc = await resolve_share_link(link.token)
        assert resolved_link.id == link.id
        assert resolved_doc.id == doc.id

    @pytest.mark.asyncio
    async def test_invalid_token_404(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await resolve_share_link("nonexistent-token-xyz")
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower() or "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_expired_link_404(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        link = ShareLink(
            document_id=str(doc.id),
            token=ShareLink.generate_token(),
            permission=Permission.VIEW,
            created_by=str(test_user.id),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        await link.insert()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await resolve_share_link(link.token)
        assert exc_info.value.status_code == 404
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_deleted_document_404(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        link = await create_share_link(str(doc.id), test_user)
        doc.soft_delete()
        await doc.save()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await resolve_share_link(link.token)
        assert exc_info.value.status_code == 404
        assert "deleted" in exc_info.value.detail.lower()


class TestAcceptShareLink:
    @pytest.mark.asyncio
    async def test_new_access_created(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(title="D", content="", owner_id=str(owner.id))
        await doc.insert()
        link = await create_share_link(str(doc.id), owner, permission=Permission.EDIT)
        resolved_doc, perm = await accept_share_link(link.token, test_user)
        assert resolved_doc.id == doc.id
        assert perm == Permission.EDIT
        access = await DocumentAccess.find_one(
            DocumentAccess.document_id == str(doc.id),
            DocumentAccess.user_id == str(test_user.id),
        )
        assert access is not None
        assert access.permission == Permission.EDIT

    @pytest.mark.asyncio
    async def test_existing_access_upgraded_view_to_edit(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(title="D", content="", owner_id=str(owner.id))
        await doc.insert()
        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(test_user.id),
            permission=Permission.VIEW,
            granted_by=str(owner.id),
        )
        await access.insert()
        link = await create_share_link(str(doc.id), owner, permission=Permission.EDIT)
        await accept_share_link(link.token, test_user)
        updated = await DocumentAccess.find_one(
            DocumentAccess.document_id == str(doc.id),
            DocumentAccess.user_id == str(test_user.id),
        )
        assert updated.permission == Permission.EDIT

    @pytest.mark.asyncio
    async def test_existing_access_not_downgraded_edit_stays_edit(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(title="D", content="", owner_id=str(owner.id))
        await doc.insert()
        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(test_user.id),
            permission=Permission.EDIT,
            granted_by=str(owner.id),
        )
        await access.insert()
        link = await create_share_link(str(doc.id), owner, permission=Permission.VIEW)
        await accept_share_link(link.token, test_user)
        updated = await DocumentAccess.find_one(
            DocumentAccess.document_id == str(doc.id),
            DocumentAccess.user_id == str(test_user.id),
        )
        assert updated.permission == Permission.EDIT


class TestListSharedDocuments:
    @pytest.mark.asyncio
    async def test_returns_shared_docs_sorted(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc1 = Document_(title="A", content="", owner_id=str(owner.id))
        doc2 = Document_(title="B", content="", owner_id=str(owner.id))
        await doc1.insert()
        await doc2.insert()
        acc1 = DocumentAccess(
            document_id=str(doc1.id),
            user_id=str(test_user.id),
            permission=Permission.VIEW,
            granted_by=str(owner.id),
        )
        acc2 = DocumentAccess(
            document_id=str(doc2.id),
            user_id=str(test_user.id),
            permission=Permission.EDIT,
            granted_by=str(owner.id),
        )
        await acc1.insert()
        await acc2.insert()
        results = await list_shared_documents(test_user)
        assert len(results) == 2
        titles = {r["document"].title for r in results}
        assert "A" in titles
        assert "B" in titles

    @pytest.mark.asyncio
    async def test_skips_deleted_docs(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(title="Deleted", content="", owner_id=str(owner.id))
        await doc.insert()
        doc.soft_delete()
        await doc.save()
        await DocumentAccess(
            document_id=str(doc.id),
            user_id=str(test_user.id),
            permission=Permission.VIEW,
            granted_by=str(owner.id),
        ).insert()
        results = await list_shared_documents(test_user)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_skips_invalid_ids(self, test_user: User):
        access = DocumentAccess(
            document_id="000000000000000000000001",
            user_id=str(test_user.id),
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await access.insert()
        results = await list_shared_documents(test_user)
        assert len(results) == 0


class TestGetUserPermission:
    @pytest.mark.asyncio
    async def test_owner_gets_edit(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        perm = await get_user_permission(str(doc.id), test_user)
        assert perm == Permission.EDIT

    @pytest.mark.asyncio
    async def test_explicit_access_returns_correct_perm(self, test_user: User):
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
        perm = await get_user_permission(str(doc.id), test_user)
        assert perm == Permission.VIEW

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
        perm = await get_user_permission(str(doc.id), test_user)
        assert perm == Permission.VIEW

    @pytest.mark.asyncio
    async def test_no_access_returns_none(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(
            title="D",
            content="",
            owner_id=str(owner.id),
            general_access=GeneralAccess.RESTRICTED,
        )
        await doc.insert()
        perm = await get_user_permission(str(doc.id), test_user)
        assert perm is None

    @pytest.mark.asyncio
    async def test_folder_chain_inheritance(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        folder = Folder(
            name="Parent",
            owner_id=str(owner.id),
        )
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
        perm = await get_user_permission(str(doc.id), test_user)
        assert perm == Permission.VIEW


class TestUpdateGeneralAccess:
    @pytest.mark.asyncio
    async def test_valid_values(self, test_user: User):
        doc = Document_(
            title="D",
            content="",
            owner_id=str(test_user.id),
            general_access=GeneralAccess.RESTRICTED,
        )
        await doc.insert()
        result = await update_general_access(str(doc.id), test_user, "anyone_view")
        assert result.general_access == GeneralAccess.ANYONE_VIEW
        result2 = await update_general_access(str(doc.id), test_user, "anyone_edit")
        assert result2.general_access == GeneralAccess.ANYONE_EDIT

    @pytest.mark.asyncio
    async def test_invalid_value_400(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await update_general_access(str(doc.id), test_user, "invalid")
        assert exc_info.value.status_code == 400
        assert "Invalid general_access" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_non_owner_403(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(title="D", content="", owner_id=str(owner.id))
        await doc.insert()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await update_general_access(str(doc.id), test_user, "anyone_view")
        assert exc_info.value.status_code == 403


class TestAddCollaborator:
    @pytest.mark.asyncio
    async def test_valid_add(self, test_user: User):
        collab = User(
            google_id="c",
            email="collab@example.com",
            name="Collaborator",
        )
        await collab.insert()
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        access = await add_collaborator(
            str(doc.id), test_user, "collab@example.com", Permission.EDIT
        )
        assert access.user_id == str(collab.id)
        assert access.permission == Permission.EDIT

    @pytest.mark.asyncio
    async def test_non_owner_403(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(title="D", content="", owner_id=str(owner.id))
        await doc.insert()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await add_collaborator(str(doc.id), test_user, "x@x.com", Permission.EDIT)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_self_add_400(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await add_collaborator(
                str(doc.id), test_user, test_user.email, Permission.EDIT
            )
        assert exc_info.value.status_code == 400
        assert "yourself" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_nonexistent_email_404(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await add_collaborator(
                str(doc.id), test_user, "nonexistent@example.com", Permission.EDIT
            )
        assert exc_info.value.status_code == 404
        assert "No user found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_existing_permission(self, test_user: User):
        collab = User(google_id="c", email="c@x.com", name="C")
        await collab.insert()
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        await add_collaborator(str(doc.id), test_user, "c@x.com", Permission.VIEW)
        access = await add_collaborator(str(doc.id), test_user, "c@x.com", Permission.EDIT)
        assert access.permission == Permission.EDIT


class TestListCollaborators:
    @pytest.mark.asyncio
    async def test_owner_only(self, test_user: User):
        collab = User(google_id="c", email="c@x.com", name="C")
        await collab.insert()
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        await DocumentAccess(
            document_id=str(doc.id),
            user_id=str(collab.id),
            permission=Permission.EDIT,
            granted_by=str(test_user.id),
        ).insert()
        results = await list_collaborators(str(doc.id), test_user)
        assert len(results) == 1
        assert results[0]["email"] == "c@x.com"
        assert results[0]["permission"] == Permission.EDIT

    @pytest.mark.asyncio
    async def test_skips_invalid_user_ids(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        await DocumentAccess(
            document_id=str(doc.id),
            user_id="000000000000000000000001",
            permission=Permission.EDIT,
            granted_by=str(test_user.id),
        ).insert()
        results = await list_collaborators(str(doc.id), test_user)
        assert len(results) == 0


class TestRemoveCollaborator:
    @pytest.mark.asyncio
    async def test_valid_remove(self, test_user: User):
        collab = User(google_id="c", email="c@x.com", name="C")
        await collab.insert()
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        await DocumentAccess(
            document_id=str(doc.id),
            user_id=str(collab.id),
            permission=Permission.EDIT,
            granted_by=str(test_user.id),
        ).insert()
        await remove_collaborator(str(doc.id), test_user, str(collab.id))
        access = await DocumentAccess.find_one(
            DocumentAccess.document_id == str(doc.id),
            DocumentAccess.user_id == str(collab.id),
        )
        assert access is None

    @pytest.mark.asyncio
    async def test_non_owner_403(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        collab = User(google_id="c", email="c@x.com", name="C")
        await collab.insert()
        doc = Document_(title="D", content="", owner_id=str(owner.id))
        await doc.insert()
        await DocumentAccess(
            document_id=str(doc.id),
            user_id=str(collab.id),
            permission=Permission.EDIT,
            granted_by=str(owner.id),
        ).insert()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await remove_collaborator(str(doc.id), test_user, str(collab.id))
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_nonexistent_access_404(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        fake_user_id = "000000000000000000000001"
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await remove_collaborator(str(doc.id), test_user, fake_user_id)
        assert exc_info.value.status_code == 404
        assert "Collaborator access record not found" in exc_info.value.detail


class TestRecordDocumentView:
    @pytest.mark.asyncio
    async def test_new_view(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        await record_document_view(str(doc.id), test_user)
        view = await DocumentView.find_one(
            DocumentView.document_id == str(doc.id),
            DocumentView.user_id == str(test_user.id),
        )
        assert view is not None

    @pytest.mark.asyncio
    async def test_update_existing_view(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        view = DocumentView(
            user_id=str(test_user.id),
            document_id=str(doc.id),
        )
        await view.insert()
        await record_document_view(str(doc.id), test_user)
        views = await DocumentView.find(
            DocumentView.document_id == str(doc.id),
            DocumentView.user_id == str(test_user.id),
        ).to_list()
        assert len(views) == 1
        assert views[0].viewed_at is not None

    @pytest.mark.asyncio
    async def test_invalid_doc_id_does_not_crash(self, test_user: User):
        await record_document_view("invalid-id", test_user)
        await record_document_view("000000000000000000000001", test_user)


class TestListRecentlyViewed:
    @pytest.mark.asyncio
    async def test_returns_viewed_docs(self, test_user: User):
        doc = Document_(title="Viewed", content="", owner_id=str(test_user.id))
        await doc.insert()
        await record_document_view(str(doc.id), test_user)
        results = await list_recently_viewed(test_user)
        assert len(results) == 1
        assert results[0]["document"].title == "Viewed"
        assert results[0]["owner_name"] == test_user.name
        assert results[0]["owner_email"] == test_user.email

    @pytest.mark.asyncio
    async def test_skips_deleted(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        await record_document_view(str(doc.id), test_user)
        doc.soft_delete()
        await doc.save()
        results = await list_recently_viewed(test_user)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_skips_no_access(self, test_user: User):
        owner = User(google_id="o", email="o@x.com", name="O")
        await owner.insert()
        doc = Document_(
            title="D",
            content="",
            owner_id=str(owner.id),
            general_access=GeneralAccess.RESTRICTED,
        )
        await doc.insert()
        view = DocumentView(
            user_id=str(test_user.id),
            document_id=str(doc.id),
        )
        await view.insert()
        results = await list_recently_viewed(test_user)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_resolves_owner_info(self, test_user: User):
        owner = User(google_id="o", email="owner@x.com", name="Doc Owner")
        await owner.insert()
        doc = Document_(title="Shared", content="", owner_id=str(owner.id))
        await doc.insert()
        await DocumentAccess(
            document_id=str(doc.id),
            user_id=str(test_user.id),
            permission=Permission.VIEW,
            granted_by=str(owner.id),
        ).insert()
        await record_document_view(str(doc.id), test_user)
        results = await list_recently_viewed(test_user)
        assert len(results) == 1
        assert results[0]["owner_name"] == "Doc Owner"
        assert results[0]["owner_email"] == "owner@x.com"

    @pytest.mark.asyncio
    async def test_skips_invalid_document_ids_in_views(self, test_user: User):
        from app.models.document_view import DocumentView

        view = DocumentView(
            user_id=str(test_user.id),
            document_id="invalid-doc-id",
        )
        await view.insert()
        results = await list_recently_viewed(test_user)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_owner_not_found_uses_unknown(self, test_user: User):
        doc = Document_(
            title="D",
            content="",
            owner_id="000000000000000000000001",
        )
        await doc.insert()
        await DocumentAccess(
            document_id=str(doc.id),
            user_id=str(test_user.id),
            permission=Permission.VIEW,
            granted_by="000000000000000000000001",
        ).insert()
        await record_document_view(str(doc.id), test_user)
        results = await list_recently_viewed(test_user)
        assert len(results) == 1
        assert results[0]["owner_name"] == "Unknown"
        assert results[0]["owner_email"] == ""


# =====================================================================
# Coverage: revoke_share_link InvalidId, list_shared_documents invalid doc_id,
# list_collaborators invalid user_id, record_document_view InvalidId
# =====================================================================

class TestShareServiceEdgeCases:
    @pytest.mark.asyncio
    async def test_revoke_share_link_invalid_id_format(self, test_user: User):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await revoke_share_link("invalid-link-id", test_user)
        assert exc_info.value.status_code == 404
        assert "Share link not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_list_shared_documents_invalid_document_id_skipped(self, test_user: User):
        access = DocumentAccess(
            document_id="invalid-doc-id",
            user_id=str(test_user.id),
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await access.insert()
        results = await list_shared_documents(test_user)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_list_collaborators_invalid_user_id_skipped(self, test_user: User):
        doc = Document_(title="D", content="", owner_id=str(test_user.id))
        await doc.insert()
        await DocumentAccess(
            document_id=str(doc.id),
            user_id="invalid-user-id",
            permission=Permission.EDIT,
            granted_by=str(test_user.id),
        ).insert()
        results = await list_collaborators(str(doc.id), test_user)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_record_document_view_invalid_id_no_crash(self, test_user: User):
        await record_document_view("invalid", test_user)
        await record_document_view("not-an-object-id", test_user)
