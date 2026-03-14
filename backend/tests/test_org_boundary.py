"""Tests for Phase 3: Org-scoped ACLs and cross-org sharing restrictions.

Covers:
  - org_allows_general_access utility
  - acl_service org boundary enforcement on general_access
  - Cross-org sharing blocked in share_service and folder_service
  - Personal users unaffected (backward compatibility)
  - Folder inheritance respects org boundary
"""

import pytest
from app.models.document import Document_
from app.models.folder import Folder
from app.models.organization import Organization
from app.models.share_link import DocumentAccess, Permission
from app.models.user import User
from app.services import acl_service, folder_service, share_service
from app.services.acl_service import org_allows_general_access
from app.services.document_service import get_document
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Unit tests for org_allows_general_access
# ---------------------------------------------------------------------------


class TestOrgAllowsGeneralAccess:
    def test_both_none_returns_true(self):
        assert org_allows_general_access(None, None) is True

    def test_entity_none_user_has_org_returns_true(self):
        assert org_allows_general_access(None, "org-1") is True

    def test_same_org_returns_true(self):
        assert org_allows_general_access("org-1", "org-1") is True

    def test_different_org_returns_false(self):
        assert org_allows_general_access("org-1", "org-2") is False

    def test_entity_has_org_user_none_returns_false(self):
        assert org_allows_general_access("org-1", None) is False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_org(slug: str) -> Organization:
    org = Organization(name=f"Org {slug}", slug=slug, verified_domains=[f"{slug}.com"])
    await org.insert()
    return org


async def _create_user(email: str, org_id: str | None = None) -> User:
    user = User(
        email=email,
        name=email.split("@")[0],
        avatar_url=None,
        org_id=org_id,
        auth_provider="saml" if org_id else "google",
    )
    await user.insert()
    return user


async def _create_doc(owner: User, ga: str = "restricted", org_id: str | None = None) -> Document_:
    doc = Document_(
        title="Test Doc",
        content="hello",
        owner_id=str(owner.id),
        owner_name=owner.name,
        owner_email=owner.email,
        general_access=ga,
        org_id=org_id,
    )
    await doc.insert()
    return doc


async def _create_folder(
    owner: User, ga: str = "restricted", org_id: str | None = None, parent_id: str | None = None
) -> Folder:
    folder = Folder(
        name="Test Folder",
        owner_id=str(owner.id),
        owner_name=owner.name,
        owner_email=owner.email,
        general_access=ga,
        org_id=org_id,
        parent_id=parent_id,
    )
    await folder.insert()
    return folder


# ---------------------------------------------------------------------------
# ACL service: general_access scoped to same org
# ---------------------------------------------------------------------------


class TestAclServiceOrgBoundary:
    @pytest.mark.asyncio
    async def test_personal_doc_anyone_view_accessible_by_any_user(self):
        owner = await _create_user("owner@personal.com")
        viewer = await _create_user("viewer@other.com")
        doc = await _create_doc(owner, ga="anyone_view", org_id=None)

        perm = await acl_service.get_base_permission("document", str(doc.id), str(viewer.id), viewer.org_id)
        assert perm == Permission.VIEW

    @pytest.mark.asyncio
    async def test_org_doc_anyone_view_same_org_can_view(self):
        org = await _create_org("acme")
        owner = await _create_user("owner@acme.com", org_id=str(org.id))
        colleague = await _create_user("peer@acme.com", org_id=str(org.id))
        doc = await _create_doc(owner, ga="anyone_view", org_id=str(org.id))

        perm = await acl_service.get_base_permission("document", str(doc.id), str(colleague.id), colleague.org_id)
        assert perm == Permission.VIEW

    @pytest.mark.asyncio
    async def test_org_doc_anyone_view_different_org_denied(self):
        org_a = await _create_org("acme-a")
        org_b = await _create_org("acme-b")
        owner = await _create_user("owner@a.com", org_id=str(org_a.id))
        outsider = await _create_user("spy@b.com", org_id=str(org_b.id))
        doc = await _create_doc(owner, ga="anyone_view", org_id=str(org_a.id))

        perm = await acl_service.get_base_permission("document", str(doc.id), str(outsider.id), outsider.org_id)
        assert perm is None

    @pytest.mark.asyncio
    async def test_org_doc_anyone_view_personal_user_denied(self):
        org = await _create_org("acme-c")
        owner = await _create_user("owner@acme-c.com", org_id=str(org.id))
        personal = await _create_user("free@gmail.com", org_id=None)
        doc = await _create_doc(owner, ga="anyone_view", org_id=str(org.id))

        perm = await acl_service.get_base_permission("document", str(doc.id), str(personal.id), personal.org_id)
        assert perm is None

    @pytest.mark.asyncio
    async def test_org_doc_anyone_edit_same_org_can_edit(self):
        org = await _create_org("acme-d")
        owner = await _create_user("owner@d.com", org_id=str(org.id))
        colleague = await _create_user("peer@d.com", org_id=str(org.id))
        doc = await _create_doc(owner, ga="anyone_edit", org_id=str(org.id))

        perm = await acl_service.get_base_permission("document", str(doc.id), str(colleague.id), colleague.org_id)
        assert perm == Permission.EDIT

    @pytest.mark.asyncio
    async def test_org_doc_anyone_edit_outsider_denied(self):
        org_a = await _create_org("acme-e")
        org_b = await _create_org("acme-f")
        owner = await _create_user("owner@e.com", org_id=str(org_a.id))
        outsider = await _create_user("spy@f.com", org_id=str(org_b.id))
        doc = await _create_doc(owner, ga="anyone_edit", org_id=str(org_a.id))

        perm = await acl_service.get_base_permission("document", str(doc.id), str(outsider.id), outsider.org_id)
        assert perm is None

    @pytest.mark.asyncio
    async def test_org_doc_explicit_access_still_works_cross_org(self):
        """Explicit DocumentAccess overrides org boundary (edge: should not happen in practice)."""
        org_a = await _create_org("acme-g")
        org_b = await _create_org("acme-h")
        owner = await _create_user("owner@g.com", org_id=str(org_a.id))
        outsider = await _create_user("granted@h.com", org_id=str(org_b.id))
        doc = await _create_doc(owner, ga="restricted", org_id=str(org_a.id))

        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(outsider.id),
            permission=Permission.VIEW,
            granted_by=str(owner.id),
        )
        await access.insert()

        perm = await acl_service.get_base_permission("document", str(doc.id), str(outsider.id), outsider.org_id)
        assert perm == Permission.VIEW

    @pytest.mark.asyncio
    async def test_org_doc_owner_always_has_edit(self):
        org = await _create_org("acme-i")
        owner = await _create_user("owner@i.com", org_id=str(org.id))
        doc = await _create_doc(owner, ga="restricted", org_id=str(org.id))

        perm = await acl_service.get_base_permission("document", str(doc.id), str(owner.id), owner.org_id)
        assert perm == Permission.EDIT


# ---------------------------------------------------------------------------
# ACL service: folders with org boundary
# ---------------------------------------------------------------------------


class TestAclServiceFolderOrgBoundary:
    @pytest.mark.asyncio
    async def test_org_folder_anyone_view_same_org(self):
        org = await _create_org("folder-org-a")
        owner = await _create_user("o@fa.com", org_id=str(org.id))
        peer = await _create_user("p@fa.com", org_id=str(org.id))
        folder = await _create_folder(owner, ga="anyone_view", org_id=str(org.id))

        perm = await acl_service.get_base_permission("folder", str(folder.id), str(peer.id), peer.org_id)
        assert perm == Permission.VIEW

    @pytest.mark.asyncio
    async def test_org_folder_anyone_view_cross_org_denied(self):
        org_a = await _create_org("folder-org-b")
        org_b = await _create_org("folder-org-c")
        owner = await _create_user("o@fb.com", org_id=str(org_a.id))
        outsider = await _create_user("o@fc.com", org_id=str(org_b.id))
        folder = await _create_folder(owner, ga="anyone_view", org_id=str(org_a.id))

        perm = await acl_service.get_base_permission("folder", str(folder.id), str(outsider.id), outsider.org_id)
        assert perm is None

    @pytest.mark.asyncio
    async def test_org_folder_inheritance_cross_org_denied(self):
        """Folder chain: parent has anyone_edit, child inherits. Outsider should NOT inherit."""
        org_a = await _create_org("inherit-org-a")
        org_b = await _create_org("inherit-org-b")
        owner = await _create_user("o@ia.com", org_id=str(org_a.id))
        outsider = await _create_user("o@ib.com", org_id=str(org_b.id))

        parent = await _create_folder(owner, ga="anyone_edit", org_id=str(org_a.id))
        child = await _create_folder(owner, ga="restricted", org_id=str(org_a.id), parent_id=str(parent.id))
        doc = await _create_doc(owner, ga="restricted", org_id=str(org_a.id))
        doc.folder_id = str(child.id)
        await doc.save()

        perm = await acl_service.get_base_permission("document", str(doc.id), str(outsider.id), outsider.org_id)
        assert perm is None

    @pytest.mark.asyncio
    async def test_org_folder_inheritance_same_org_allowed(self):
        """Same org user should inherit through folder chain."""
        org = await _create_org("inherit-org-c")
        owner = await _create_user("o@ic.com", org_id=str(org.id))
        peer = await _create_user("p@ic.com", org_id=str(org.id))

        parent = await _create_folder(owner, ga="anyone_edit", org_id=str(org.id))
        child = await _create_folder(owner, ga="restricted", org_id=str(org.id), parent_id=str(parent.id))
        doc = await _create_doc(owner, ga="restricted", org_id=str(org.id))
        doc.folder_id = str(child.id)
        await doc.save()

        perm = await acl_service.get_base_permission("document", str(doc.id), str(peer.id), peer.org_id)
        assert perm == Permission.EDIT


# ---------------------------------------------------------------------------
# Cross-org sharing blocked
# ---------------------------------------------------------------------------


class TestCrossOrgSharingBlocked:
    @pytest.mark.asyncio
    async def test_add_doc_collaborator_cross_org_raises_403(self):
        org_a = await _create_org("share-org-a")
        org_b = await _create_org("share-org-b")
        owner = await _create_user("own@sa.com", org_id=str(org_a.id))
        outsider = await _create_user("out@sb.com", org_id=str(org_b.id))
        doc = await _create_doc(owner, ga="restricted", org_id=str(org_a.id))

        with pytest.raises(HTTPException) as exc_info:
            await share_service.add_collaborator(str(doc.id), owner, outsider.email, Permission.VIEW)
        assert exc_info.value.status_code == 403
        assert "outside your organization" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_add_doc_collaborator_personal_to_org_allowed(self):
        """Personal user's doc can be shared with anyone (no org restriction)."""
        owner = await _create_user("personal@gmail.com", org_id=None)
        org = await _create_org("share-org-c")
        recipient = await _create_user("r@sc.com", org_id=str(org.id))
        doc = await _create_doc(owner, ga="restricted", org_id=None)

        access = await share_service.add_collaborator(str(doc.id), owner, recipient.email, Permission.VIEW)
        assert access.permission == Permission.VIEW

    @pytest.mark.asyncio
    async def test_add_doc_collaborator_same_org_allowed(self):
        org = await _create_org("share-org-d")
        owner = await _create_user("own@sd.com", org_id=str(org.id))
        peer = await _create_user("peer@sd.com", org_id=str(org.id))
        doc = await _create_doc(owner, ga="restricted", org_id=str(org.id))

        access = await share_service.add_collaborator(str(doc.id), owner, peer.email, Permission.EDIT)
        assert access.permission == Permission.EDIT

    @pytest.mark.asyncio
    async def test_add_folder_collaborator_cross_org_raises_403(self):
        org_a = await _create_org("fshare-a")
        org_b = await _create_org("fshare-b")
        owner = await _create_user("own@fsa.com", org_id=str(org_a.id))
        outsider = await _create_user("out@fsb.com", org_id=str(org_b.id))
        folder = await _create_folder(owner, ga="restricted", org_id=str(org_a.id))

        with pytest.raises(HTTPException) as exc_info:
            await folder_service.add_folder_collaborator(str(folder.id), owner, outsider.email, Permission.VIEW)
        assert exc_info.value.status_code == 403
        assert "outside your organization" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_add_folder_collaborator_same_org_allowed(self):
        org = await _create_org("fshare-c")
        owner = await _create_user("own@fsc.com", org_id=str(org.id))
        peer = await _create_user("peer@fsc.com", org_id=str(org.id))
        folder = await _create_folder(owner, ga="restricted", org_id=str(org.id))

        access = await folder_service.add_folder_collaborator(str(folder.id), owner, peer.email, Permission.VIEW)
        assert access.permission == Permission.VIEW

    @pytest.mark.asyncio
    async def test_add_folder_collaborator_personal_folder_to_org_user_allowed(self):
        owner = await _create_user("personal-f@gmail.com", org_id=None)
        org = await _create_org("fshare-d")
        recipient = await _create_user("r@fsd.com", org_id=str(org.id))
        folder = await _create_folder(owner, ga="restricted", org_id=None)

        access = await folder_service.add_folder_collaborator(str(folder.id), owner, recipient.email, Permission.EDIT)
        assert access.permission == Permission.EDIT


# ---------------------------------------------------------------------------
# resolve_effective_permission with org boundary
# ---------------------------------------------------------------------------


class TestResolveEffectivePermissionOrgBoundary:
    @pytest.mark.asyncio
    async def test_org_doc_anyone_edit_outsider_gets_no_access(self):
        org_a = await _create_org("resolve-a")
        org_b = await _create_org("resolve-b")
        owner = await _create_user("own@ra.com", org_id=str(org_a.id))
        outsider = await _create_user("out@rb.com", org_id=str(org_b.id))
        doc = await _create_doc(owner, ga="anyone_edit", org_id=str(org_a.id))

        eff = await acl_service.resolve_effective_permission("document", str(doc.id), outsider)
        assert eff.can_view is False
        assert eff.can_edit is False
        assert eff.role == "none"

    @pytest.mark.asyncio
    async def test_org_doc_anyone_edit_same_org_gets_editor(self):
        org = await _create_org("resolve-c")
        owner = await _create_user("own@rc.com", org_id=str(org.id))
        peer = await _create_user("peer@rc.com", org_id=str(org.id))
        doc = await _create_doc(owner, ga="anyone_edit", org_id=str(org.id))

        eff = await acl_service.resolve_effective_permission("document", str(doc.id), peer)
        assert eff.can_view is True
        assert eff.can_edit is True
        assert eff.role == "editor"

    @pytest.mark.asyncio
    async def test_personal_doc_anyone_edit_any_user_gets_editor(self):
        owner = await _create_user("personal-r@gmail.com", org_id=None)
        viewer = await _create_user("other-r@gmail.com", org_id=None)
        doc = await _create_doc(owner, ga="anyone_edit", org_id=None)

        eff = await acl_service.resolve_effective_permission("document", str(doc.id), viewer)
        assert eff.can_view is True
        assert eff.can_edit is True

    @pytest.mark.asyncio
    async def test_org_doc_restricted_outsider_no_access(self):
        org = await _create_org("resolve-d")
        owner = await _create_user("own@rd.com", org_id=str(org.id))
        outsider = await _create_user("out@gmail.com", org_id=None)
        doc = await _create_doc(owner, ga="restricted", org_id=str(org.id))

        eff = await acl_service.resolve_effective_permission("document", str(doc.id), outsider)
        assert eff.can_view is False
        assert eff.role == "none"


# ---------------------------------------------------------------------------
# document_service._assert_access with org boundary
# ---------------------------------------------------------------------------


class TestDocumentServiceOrgBoundary:
    @pytest.mark.asyncio
    async def test_org_doc_anyone_view_outsider_denied(self):
        org_a = await _create_org("docsvc-a")
        org_b = await _create_org("docsvc-b")
        owner = await _create_user("own@da.com", org_id=str(org_a.id))
        outsider = await _create_user("out@db.com", org_id=str(org_b.id))
        doc = await _create_doc(owner, ga="anyone_view", org_id=str(org_a.id))

        with pytest.raises(HTTPException) as exc_info:
            await get_document(str(doc.id), outsider)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_org_doc_anyone_view_same_org_allowed(self):
        org = await _create_org("docsvc-c")
        owner = await _create_user("own@dc.com", org_id=str(org.id))
        peer = await _create_user("peer@dc.com", org_id=str(org.id))
        doc = await _create_doc(owner, ga="anyone_view", org_id=str(org.id))

        result = await get_document(str(doc.id), peer)
        assert result.title == "Test Doc"

    @pytest.mark.asyncio
    async def test_personal_doc_anyone_view_always_allowed(self):
        owner = await _create_user("personal-ds@gmail.com", org_id=None)
        org = await _create_org("docsvc-d")
        viewer = await _create_user("v@dd.com", org_id=str(org.id))
        doc = await _create_doc(owner, ga="anyone_view", org_id=None)

        result = await get_document(str(doc.id), viewer)
        assert result.title == "Test Doc"
