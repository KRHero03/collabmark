"""Tests for ACL group-based permissions: DocumentGroupAccess, FolderGroupAccess,
and resolution via get_base_permission and resolve_effective_permission.
"""

import pytest
import pytest_asyncio
from app.models.document import Document_
from app.models.folder import Folder
from app.models.group import DocumentGroupAccess, FolderGroupAccess, Group, GroupMembership
from app.models.organization import Organization, OrgMembership, OrgRole
from app.models.share_link import Permission
from app.models.user import User
from app.services.acl_service import get_base_permission, resolve_effective_permission

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def org_with_users():
    """Create org and users for group-based ACL tests."""
    org = Organization(name="ACL Group Org", slug="acl-group-org")
    await org.insert()

    owner = User(
        google_id="acl-owner",
        email="owner@aclgroup.com",
        name="Doc Owner",
        org_id=str(org.id),
    )
    await owner.insert()
    await OrgMembership(org_id=str(org.id), user_id=str(owner.id), role=OrgRole.MEMBER).insert()

    member_view = User(
        google_id="acl-member-view",
        email="memberview@aclgroup.com",
        name="Group Viewer",
        org_id=str(org.id),
    )
    await member_view.insert()
    await OrgMembership(org_id=str(org.id), user_id=str(member_view.id), role=OrgRole.MEMBER).insert()

    member_edit = User(
        google_id="acl-member-edit",
        email="memberedit@aclgroup.com",
        name="Group Editor",
        org_id=str(org.id),
    )
    await member_edit.insert()
    await OrgMembership(org_id=str(org.id), user_id=str(member_edit.id), role=OrgRole.MEMBER).insert()

    non_member = User(
        google_id="acl-non-member",
        email="nonmember@aclgroup.com",
        name="Not In Group",
        org_id=str(org.id),
    )
    await non_member.insert()
    await OrgMembership(org_id=str(org.id), user_id=str(non_member.id), role=OrgRole.MEMBER).insert()

    return {
        "org": org,
        "owner": owner,
        "member_view": member_view,
        "member_edit": member_edit,
        "non_member": non_member,
    }


@pytest_asyncio.fixture
async def doc_with_group_access(org_with_users):
    """Document with group VIEW access for one group and EDIT for another."""
    org = org_with_users["org"]
    owner = org_with_users["owner"]
    member_view = org_with_users["member_view"]
    member_edit = org_with_users["member_edit"]
    non_member = org_with_users["non_member"]

    group_view = Group(name="Viewers", org_id=str(org.id))
    await group_view.insert()
    await GroupMembership(group_id=str(group_view.id), user_id=str(member_view.id)).insert()

    group_edit = Group(name="Editors", org_id=str(org.id))
    await group_edit.insert()
    await GroupMembership(group_id=str(group_edit.id), user_id=str(member_edit.id)).insert()

    doc = Document_(
        title="Group Doc",
        content="",
        owner_id=str(owner.id),
        org_id=str(org.id),
    )
    await doc.insert()

    await DocumentGroupAccess(
        document_id=str(doc.id),
        group_id=str(group_view.id),
        permission=Permission.VIEW,
        granted_by=str(owner.id),
    ).insert()

    await DocumentGroupAccess(
        document_id=str(doc.id),
        group_id=str(group_edit.id),
        permission=Permission.EDIT,
        granted_by=str(owner.id),
    ).insert()

    return {
        "doc": doc,
        "group_view": group_view,
        "group_edit": group_edit,
        "owner": owner,
        "member_view": member_view,
        "member_edit": member_edit,
        "non_member": non_member,
    }


@pytest_asyncio.fixture
async def doc_group_view_only(org_with_users):
    """Document with only group VIEW access (no EDIT group)."""
    org = org_with_users["org"]
    owner = org_with_users["owner"]
    member_view = org_with_users["member_view"]
    non_member = org_with_users["non_member"]

    group = Group(name="ViewOnlyGroup", org_id=str(org.id))
    await group.insert()
    await GroupMembership(group_id=str(group.id), user_id=str(member_view.id)).insert()

    doc = Document_(
        title="View Only Doc",
        content="",
        owner_id=str(owner.id),
        org_id=str(org.id),
    )
    await doc.insert()

    await DocumentGroupAccess(
        document_id=str(doc.id),
        group_id=str(group.id),
        permission=Permission.VIEW,
        granted_by=str(owner.id),
    ).insert()

    return {
        "doc": doc,
        "owner": owner,
        "member_view": member_view,
        "non_member": non_member,
    }


@pytest_asyncio.fixture
async def folder_with_group_access(org_with_users):
    """Folder with group VIEW access."""
    org = org_with_users["org"]
    owner = org_with_users["owner"]
    member_view = org_with_users["member_view"]

    group = Group(name="FolderViewers", org_id=str(org.id))
    await group.insert()
    await GroupMembership(group_id=str(group.id), user_id=str(member_view.id)).insert()

    folder = Folder(
        name="Group Folder",
        owner_id=str(owner.id),
        org_id=str(org.id),
    )
    await folder.insert()

    await FolderGroupAccess(
        folder_id=str(folder.id),
        group_id=str(group.id),
        permission=Permission.VIEW,
        granted_by=str(owner.id),
    ).insert()

    return {
        "folder": folder,
        "owner": owner,
        "member_view": member_view,
    }


@pytest_asyncio.fixture
async def folder_hierarchy_with_inherited_group_access(org_with_users):
    """Parent folder has group VIEW; child folder inherits."""
    org = org_with_users["org"]
    owner = org_with_users["owner"]
    member_view = org_with_users["member_view"]

    group = Group(name="InheritedViewers", org_id=str(org.id))
    await group.insert()
    await GroupMembership(group_id=str(group.id), user_id=str(member_view.id)).insert()

    parent = Folder(
        name="Parent",
        owner_id=str(owner.id),
        org_id=str(org.id),
    )
    await parent.insert()
    parent.root_folder_id = str(parent.id)
    await parent.save()

    await FolderGroupAccess(
        folder_id=str(parent.id),
        group_id=str(group.id),
        permission=Permission.VIEW,
        granted_by=str(owner.id),
    ).insert()

    child = Folder(
        name="Child",
        owner_id=str(owner.id),
        parent_id=str(parent.id),
        root_folder_id=str(parent.id),
        org_id=str(org.id),
    )
    await child.insert()

    return {
        "parent": parent,
        "child": child,
        "owner": owner,
        "member_view": member_view,
    }


# ---------------------------------------------------------------------------
# Document group access
# ---------------------------------------------------------------------------


class TestDocumentGroupAccess:
    @pytest.mark.asyncio
    async def test_user_in_group_with_view_gets_view_permission(self, doc_group_view_only):
        """User in group with VIEW on document gets view permission."""
        perm = await get_base_permission(
            "document",
            str(doc_group_view_only["doc"].id),
            str(doc_group_view_only["member_view"].id),
            doc_group_view_only["member_view"].org_id,
        )
        assert perm == Permission.VIEW

    @pytest.mark.asyncio
    async def test_user_in_group_with_edit_gets_edit_permission(self, doc_with_group_access):
        """User in group with EDIT on document gets edit permission."""
        perm = await get_base_permission(
            "document",
            str(doc_with_group_access["doc"].id),
            str(doc_with_group_access["member_edit"].id),
            doc_with_group_access["member_edit"].org_id,
        )
        assert perm == Permission.EDIT

    @pytest.mark.asyncio
    async def test_user_not_in_group_gets_no_access(self, doc_group_view_only):
        """User NOT in group gets no access (None from get_base_permission)."""
        perm = await get_base_permission(
            "document",
            str(doc_group_view_only["doc"].id),
            str(doc_group_view_only["non_member"].id),
            doc_group_view_only["non_member"].org_id,
        )
        assert perm is None


# ---------------------------------------------------------------------------
# Folder group access
# ---------------------------------------------------------------------------


class TestFolderGroupAccess:
    @pytest.mark.asyncio
    async def test_user_in_group_with_view_on_folder_gets_view_permission(self, folder_with_group_access):
        """User in group with VIEW on folder gets view permission."""
        perm = await get_base_permission(
            "folder",
            str(folder_with_group_access["folder"].id),
            str(folder_with_group_access["member_view"].id),
            folder_with_group_access["member_view"].org_id,
        )
        assert perm == Permission.VIEW

    @pytest.mark.asyncio
    async def test_inherited_group_access_through_parent_folders(self, folder_hierarchy_with_inherited_group_access):
        """Inherited group access through parent folders works."""
        child = folder_hierarchy_with_inherited_group_access["child"]
        member_view = folder_hierarchy_with_inherited_group_access["member_view"]
        perm = await get_base_permission(
            "folder",
            str(child.id),
            str(member_view.id),
            member_view.org_id,
        )
        assert perm == Permission.VIEW


# ---------------------------------------------------------------------------
# resolve_effective_permission role resolution
# ---------------------------------------------------------------------------


class TestGroupRoleResolution:
    @pytest.mark.asyncio
    async def test_group_based_editor_gets_role_editor(self, doc_with_group_access):
        """Group-based editor gets role='editor' from resolve_effective_permission."""
        perm = await resolve_effective_permission(
            "document",
            str(doc_with_group_access["doc"].id),
            doc_with_group_access["member_edit"],
        )
        assert perm.role == "editor"
        assert perm.can_view is True
        assert perm.can_edit is True
        assert perm.can_delete is False
        assert perm.can_share is False

    @pytest.mark.asyncio
    async def test_owner_overrides_group(self, doc_with_group_access):
        """Document owner still gets full edit even without group membership."""
        perm = await resolve_effective_permission(
            "document",
            str(doc_with_group_access["doc"].id),
            doc_with_group_access["owner"],
        )
        assert perm.role == "owner"
        assert perm.can_view is True
        assert perm.can_edit is True
        assert perm.can_delete is True
        assert perm.can_share is True

    @pytest.mark.asyncio
    async def test_multiple_groups_edit_wins(self, doc_with_group_access):
        """If user is in two groups with different permissions, EDIT wins."""
        org = doc_with_group_access["owner"].org_id
        member_edit = doc_with_group_access["member_edit"]
        group_view = doc_with_group_access["group_view"]
        doc = doc_with_group_access["doc"]

        await GroupMembership(
            group_id=str(group_view.id),
            user_id=str(member_edit.id),
        ).insert()

        perm = await get_base_permission(
            "document",
            str(doc.id),
            str(member_edit.id),
            org,
        )
        assert perm == Permission.EDIT
