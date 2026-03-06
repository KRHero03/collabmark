"""Tests for SCIM user provisioning service."""

import pytest
from app.models.organization import Organization, OrgMembership, OrgRole
from app.models.user import User
from app.services import scim_service
from app.services.scim_service import SCIMError


@pytest.fixture
async def scim_org() -> Organization:
    org = Organization(name="SCIM Test Org", slug="scim-test-org")
    await org.insert()
    return org


# ---------------------------------------------------------------------------
# scim_to_user_fields
# ---------------------------------------------------------------------------


class TestScimToUserFields:
    def test_extracts_username_and_display_name(self):
        resource = {"userName": "alice@acme.com", "displayName": "Alice Smith"}
        fields = scim_service.scim_to_user_fields(resource)
        assert fields["email"] == "alice@acme.com"
        assert fields["name"] == "Alice Smith"

    def test_extracts_name_from_name_object(self):
        resource = {
            "userName": "bob@acme.com",
            "name": {"givenName": "Bob", "familyName": "Jones"},
        }
        fields = scim_service.scim_to_user_fields(resource)
        assert fields["name"] == "Bob Jones"

    def test_extracts_name_formatted(self):
        resource = {
            "userName": "carol@acme.com",
            "name": {"formatted": "Carol D."},
        }
        fields = scim_service.scim_to_user_fields(resource)
        assert fields["name"] == "Carol D."

    def test_falls_back_to_email_prefix_for_name(self):
        resource = {"userName": "noname@acme.com"}
        fields = scim_service.scim_to_user_fields(resource)
        assert fields["name"] == "noname"

    def test_extracts_primary_email_from_emails_array(self):
        resource = {
            "emails": [
                {"value": "secondary@acme.com", "primary": False},
                {"value": "primary@acme.com", "primary": True},
            ],
            "displayName": "Primary User",
        }
        fields = scim_service.scim_to_user_fields(resource)
        assert fields["email"] == "primary@acme.com"

    def test_extracts_first_email_when_no_primary(self):
        resource = {
            "emails": [{"value": "first@acme.com"}],
            "displayName": "First User",
        }
        fields = scim_service.scim_to_user_fields(resource)
        assert fields["email"] == "first@acme.com"

    def test_extracts_avatar_from_photos(self):
        resource = {
            "userName": "photo@acme.com",
            "displayName": "Photo User",
            "photos": [{"value": "https://example.com/avatar.png", "type": "photo"}],
        }
        fields = scim_service.scim_to_user_fields(resource)
        assert fields["avatar_url"] == "https://example.com/avatar.png"

    def test_missing_email_raises_400(self):
        resource = {"displayName": "No Email"}
        with pytest.raises(SCIMError) as exc_info:
            scim_service.scim_to_user_fields(resource)
        assert exc_info.value.status_code == 400

    def test_empty_username_falls_back_to_emails(self):
        resource = {
            "userName": "",
            "emails": [{"value": "fallback@acme.com", "primary": True}],
            "displayName": "Fallback",
        }
        fields = scim_service.scim_to_user_fields(resource)
        assert fields["email"] == "fallback@acme.com"

    def test_extracts_external_id(self):
        resource = {"userName": "ext@acme.com", "displayName": "Ext", "externalId": "ext-123"}
        fields = scim_service.scim_to_user_fields(resource)
        assert fields["external_id"] == "ext-123"

    def test_no_external_id_when_absent(self):
        resource = {"userName": "noext@acme.com", "displayName": "NoExt"}
        fields = scim_service.scim_to_user_fields(resource)
        assert "external_id" not in fields


# ---------------------------------------------------------------------------
# user_to_scim
# ---------------------------------------------------------------------------


class TestUserToScim:
    @pytest.mark.asyncio
    async def test_converts_active_user(self, scim_org):
        user = User(
            email="scim-user@acme.com",
            name="SCIM User",
            org_id=str(scim_org.id),
            auth_provider="scim",
        )
        await user.insert()

        resource = scim_service.user_to_scim(user, str(scim_org.id))
        assert resource["userName"] == "scim-user@acme.com"
        assert resource["displayName"] == "SCIM User"
        assert resource["active"] is True
        assert resource["id"] == str(user.id)
        assert resource["schemas"] == [scim_service.SCIM_USER_SCHEMA]
        assert resource["emails"][0]["value"] == "scim-user@acme.com"
        assert resource["meta"]["resourceType"] == "User"

    @pytest.mark.asyncio
    async def test_inactive_user_has_active_false(self, scim_org):
        user = User(
            email="inactive@acme.com",
            name="Inactive User",
            org_id=None,
            auth_provider="scim",
        )
        await user.insert()

        resource = scim_service.user_to_scim(user, str(scim_org.id))
        assert resource["active"] is False

    @pytest.mark.asyncio
    async def test_external_id_in_response(self, scim_org):
        user = User(
            email="extid@acme.com",
            name="ExtId User",
            org_id=str(scim_org.id),
            auth_provider="scim",
            external_id="ext-456",
        )
        await user.insert()
        resource = scim_service.user_to_scim(user, str(scim_org.id))
        assert resource["externalId"] == "ext-456"

    @pytest.mark.asyncio
    async def test_no_external_id_when_none(self, scim_org):
        user = User(
            email="noextid@acme.com",
            name="NoExtId",
            org_id=str(scim_org.id),
            auth_provider="scim",
        )
        await user.insert()
        resource = scim_service.user_to_scim(user, str(scim_org.id))
        assert "externalId" not in resource


# ---------------------------------------------------------------------------
# filter_scim_attributes
# ---------------------------------------------------------------------------


class TestFilterScimAttributes:
    def test_returns_all_when_no_params(self):
        resource = {"schemas": ["x"], "id": "1", "userName": "a@b.com", "displayName": "A"}
        assert scim_service.filter_scim_attributes(resource) == resource

    def test_attributes_includes_requested_plus_always(self):
        resource = {"schemas": ["x"], "id": "1", "userName": "a@b.com", "displayName": "A", "active": True}
        result = scim_service.filter_scim_attributes(resource, attributes="userName")
        assert "schemas" in result
        assert "id" in result
        assert "userName" in result
        assert "displayName" not in result
        assert "active" not in result

    def test_excluded_attributes_removes_requested(self):
        resource = {"schemas": ["x"], "id": "1", "userName": "a@b.com", "displayName": "A"}
        result = scim_service.filter_scim_attributes(resource, excluded_attributes="displayName")
        assert "schemas" in result
        assert "id" in result
        assert "userName" in result
        assert "displayName" not in result

    def test_excluded_cannot_remove_always_returned(self):
        resource = {"schemas": ["x"], "id": "1", "userName": "a@b.com"}
        result = scim_service.filter_scim_attributes(resource, excluded_attributes="schemas,id")
        assert "schemas" in result
        assert "id" in result

    def test_attributes_overrides_excluded(self):
        resource = {"schemas": ["x"], "id": "1", "userName": "a@b.com", "displayName": "A"}
        result = scim_service.filter_scim_attributes(resource, attributes="userName", excluded_attributes="userName")
        assert "userName" in result


# ---------------------------------------------------------------------------
# create_scim_user
# ---------------------------------------------------------------------------


class TestCreateScimUser:
    @pytest.mark.asyncio
    async def test_creates_user_and_membership(self, scim_org):
        resource = {"userName": "new@acme.com", "displayName": "New User"}
        user = await scim_service.create_scim_user(str(scim_org.id), resource)

        assert user.email == "new@acme.com"
        assert user.name == "New User"
        assert user.org_id == str(scim_org.id)
        assert user.auth_provider == "scim"

        membership = await OrgMembership.find_one(
            OrgMembership.org_id == str(scim_org.id),
            OrgMembership.user_id == str(user.id),
        )
        assert membership is not None
        assert membership.role == OrgRole.MEMBER

    @pytest.mark.asyncio
    async def test_creates_user_with_external_id(self, scim_org):
        resource = {"userName": "ext-new@acme.com", "displayName": "Ext New", "externalId": "idp-789"}
        user = await scim_service.create_scim_user(str(scim_org.id), resource)
        assert user.external_id == "idp-789"

    @pytest.mark.asyncio
    async def test_duplicate_email_in_same_org_returns_409(self, scim_org):
        resource = {"userName": "dup@acme.com", "displayName": "Dup User"}
        await scim_service.create_scim_user(str(scim_org.id), resource)

        with pytest.raises(SCIMError) as exc_info:
            await scim_service.create_scim_user(str(scim_org.id), resource)
        assert exc_info.value.status_code == 409
        assert exc_info.value.scim_type == "uniqueness"
        assert "already exists" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_duplicate_email_in_different_org_returns_409(self, scim_org):
        other_org = Organization(name="Other Org", slug="scim-other-org")
        await other_org.insert()

        resource = {"userName": "cross@acme.com", "displayName": "Cross User"}
        await scim_service.create_scim_user(str(scim_org.id), resource)

        with pytest.raises(SCIMError) as exc_info:
            await scim_service.create_scim_user(str(other_org.id), resource)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_missing_email_returns_400(self, scim_org):
        resource = {"displayName": "No Email User"}
        with pytest.raises(SCIMError) as exc_info:
            await scim_service.create_scim_user(str(scim_org.id), resource)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# list_scim_users
# ---------------------------------------------------------------------------


class TestListScimUsers:
    @pytest.mark.asyncio
    async def test_returns_empty_list_for_no_users(self, scim_org):
        result = await scim_service.list_scim_users(str(scim_org.id))
        assert result["totalResults"] == 0
        assert result["Resources"] == []
        assert result["schemas"] == [scim_service.SCIM_LIST_SCHEMA]

    @pytest.mark.asyncio
    async def test_returns_provisioned_users(self, scim_org):
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "list1@acme.com", "displayName": "User 1"})
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "list2@acme.com", "displayName": "User 2"})

        result = await scim_service.list_scim_users(str(scim_org.id))
        assert result["totalResults"] == 2
        assert len(result["Resources"]) == 2
        emails = {r["userName"] for r in result["Resources"]}
        assert "list1@acme.com" in emails
        assert "list2@acme.com" in emails

    @pytest.mark.asyncio
    async def test_filter_by_username(self, scim_org):
        await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "find-me@acme.com", "displayName": "Find Me"}
        )
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "not-me@acme.com", "displayName": "Not Me"})

        result = await scim_service.list_scim_users(str(scim_org.id), filter_str='userName eq "find-me@acme.com"')
        assert result["totalResults"] == 1
        assert result["Resources"][0]["userName"] == "find-me@acme.com"

    @pytest.mark.asyncio
    async def test_pagination(self, scim_org):
        for i in range(5):
            await scim_service.create_scim_user(
                str(scim_org.id), {"userName": f"page{i}@acme.com", "displayName": f"Page {i}"}
            )

        result = await scim_service.list_scim_users(str(scim_org.id), start_index=1, count=2)
        assert result["totalResults"] == 5
        assert result["itemsPerPage"] == 2
        assert result["startIndex"] == 1

    @pytest.mark.asyncio
    async def test_start_index_offset(self, scim_org):
        for i in range(3):
            await scim_service.create_scim_user(
                str(scim_org.id), {"userName": f"off{i}@acme.com", "displayName": f"Off {i}"}
            )

        result = await scim_service.list_scim_users(str(scim_org.id), start_index=2, count=10)
        assert result["startIndex"] == 2
        assert result["itemsPerPage"] == 2

    @pytest.mark.asyncio
    async def test_does_not_return_users_from_other_orgs(self, scim_org):
        other_org = Organization(name="Other List Org", slug="scim-other-list-org")
        await other_org.insert()
        await scim_service.create_scim_user(
            str(other_org.id), {"userName": "other-org-user@acme.com", "displayName": "Other"}
        )
        await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "my-org-user@acme.com", "displayName": "Mine"}
        )

        result = await scim_service.list_scim_users(str(scim_org.id))
        assert result["totalResults"] == 1
        assert result["Resources"][0]["userName"] == "my-org-user@acme.com"

    @pytest.mark.asyncio
    async def test_list_with_attributes_filter(self, scim_org):
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "attr@acme.com", "displayName": "Attr"})
        result = await scim_service.list_scim_users(str(scim_org.id), attributes="userName")
        r = result["Resources"][0]
        assert "userName" in r
        assert "schemas" in r
        assert "id" in r
        assert "displayName" not in r

    @pytest.mark.asyncio
    async def test_list_with_excluded_attributes(self, scim_org):
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "excl@acme.com", "displayName": "Excl"})
        result = await scim_service.list_scim_users(str(scim_org.id), excluded_attributes="displayName,photos")
        r = result["Resources"][0]
        assert "userName" in r
        assert "displayName" not in r
        assert "photos" not in r


# ---------------------------------------------------------------------------
# Filter operators (ne, co, sw, ew, pr)
# ---------------------------------------------------------------------------


class TestFilterOperators:
    @pytest.mark.asyncio
    async def test_ne_filter(self, scim_org):
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "ne1@acme.com", "displayName": "NE1"})
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "ne2@acme.com", "displayName": "NE2"})
        result = await scim_service.list_scim_users(str(scim_org.id), filter_str='userName ne "ne1@acme.com"')
        assert result["totalResults"] == 1
        assert result["Resources"][0]["userName"] == "ne2@acme.com"

    @pytest.mark.asyncio
    async def test_co_filter(self, scim_org):
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "alice-co@acme.com", "displayName": "Alice"})
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "bob-co@acme.com", "displayName": "Bob"})
        result = await scim_service.list_scim_users(str(scim_org.id), filter_str='userName co "alice"')
        assert result["totalResults"] == 1
        assert result["Resources"][0]["userName"] == "alice-co@acme.com"

    @pytest.mark.asyncio
    async def test_sw_filter(self, scim_org):
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "sw-test@acme.com", "displayName": "SW"})
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "other-sw@acme.com", "displayName": "Other"})
        result = await scim_service.list_scim_users(str(scim_org.id), filter_str='userName sw "sw-"')
        assert result["totalResults"] == 1

    @pytest.mark.asyncio
    async def test_ew_filter(self, scim_org):
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "test@ends.com", "displayName": "Ends"})
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "test@other.com", "displayName": "Other"})
        result = await scim_service.list_scim_users(str(scim_org.id), filter_str='userName ew "ends.com"')
        assert result["totalResults"] == 1
        assert result["Resources"][0]["userName"] == "test@ends.com"

    @pytest.mark.asyncio
    async def test_pr_filter(self, scim_org):
        await scim_service.create_scim_user(
            str(scim_org.id),
            {"userName": "has-ext@acme.com", "displayName": "HasExt", "externalId": "ext-pr"},
        )
        await scim_service.create_scim_user(str(scim_org.id), {"userName": "no-ext@acme.com", "displayName": "NoExt"})
        result = await scim_service.list_scim_users(str(scim_org.id), filter_str="externalId pr")
        assert result["totalResults"] == 1
        assert result["Resources"][0]["userName"] == "has-ext@acme.com"

    @pytest.mark.asyncio
    async def test_unsupported_operator_raises_invalid_filter(self, scim_org):
        with pytest.raises(SCIMError) as exc_info:
            await scim_service.list_scim_users(str(scim_org.id), filter_str='userName gt "abc"')
        assert exc_info.value.status_code == 400
        assert exc_info.value.scim_type == "invalidFilter"

    @pytest.mark.asyncio
    async def test_malformed_filter_raises_invalid_filter(self, scim_org):
        with pytest.raises(SCIMError) as exc_info:
            await scim_service.list_scim_users(str(scim_org.id), filter_str="garbage input")
        assert exc_info.value.status_code == 400
        assert exc_info.value.scim_type == "invalidFilter"


# ---------------------------------------------------------------------------
# get_scim_user
# ---------------------------------------------------------------------------


class TestGetScimUser:
    @pytest.mark.asyncio
    async def test_returns_user_in_org(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "get-me@acme.com", "displayName": "Get Me"}
        )
        user = await scim_service.get_scim_user(str(scim_org.id), str(created.id))
        assert user.email == "get-me@acme.com"

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, scim_org):
        with pytest.raises(SCIMError) as exc_info:
            await scim_service.get_scim_user(str(scim_org.id), "000000000000000000000000")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_id_returns_404(self, scim_org):
        with pytest.raises(SCIMError) as exc_info:
            await scim_service.get_scim_user(str(scim_org.id), "bad-id")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_user_in_different_org_returns_404(self, scim_org):
        other_org = Organization(name="Other Get Org", slug="scim-other-get-org")
        await other_org.insert()
        created = await scim_service.create_scim_user(
            str(other_org.id), {"userName": "wrong-org@acme.com", "displayName": "Wrong Org"}
        )
        with pytest.raises(SCIMError) as exc_info:
            await scim_service.get_scim_user(str(scim_org.id), str(created.id))
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# replace_scim_user (PUT)
# ---------------------------------------------------------------------------


class TestReplaceScimUser:
    @pytest.mark.asyncio
    async def test_replaces_all_fields(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id),
            {"userName": "put-original@acme.com", "displayName": "Original", "externalId": "ext-orig"},
        )
        replaced = await scim_service.replace_scim_user(
            str(scim_org.id),
            str(created.id),
            {"userName": "put-replaced@acme.com", "displayName": "Replaced", "externalId": "ext-new"},
        )
        assert replaced.email == "put-replaced@acme.com"
        assert replaced.name == "Replaced"
        assert replaced.external_id == "ext-new"

    @pytest.mark.asyncio
    async def test_omitted_readwrite_attrs_are_cleared(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id),
            {"userName": "put-clear@acme.com", "displayName": "Clear", "externalId": "ext-clear"},
        )
        replaced = await scim_service.replace_scim_user(
            str(scim_org.id),
            str(created.id),
            {"userName": "put-clear@acme.com", "displayName": "Still"},
        )
        assert replaced.external_id is None

    @pytest.mark.asyncio
    async def test_put_nonexistent_returns_404(self, scim_org):
        with pytest.raises(SCIMError) as exc_info:
            await scim_service.replace_scim_user(
                str(scim_org.id),
                "000000000000000000000000",
                {"userName": "ghost@acme.com", "displayName": "Ghost"},
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_put_preserves_org_id(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "put-org@acme.com", "displayName": "Org"}
        )
        replaced = await scim_service.replace_scim_user(
            str(scim_org.id),
            str(created.id),
            {"userName": "put-org-new@acme.com", "displayName": "OrgNew"},
        )
        assert replaced.org_id == str(scim_org.id)


# ---------------------------------------------------------------------------
# update_scim_user (PATCH)
# ---------------------------------------------------------------------------


class TestUpdateScimUser:
    @pytest.mark.asyncio
    async def test_patch_replace_display_name(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "update-name@acme.com", "displayName": "Old Name"}
        )
        updated = await scim_service.update_scim_user(
            str(scim_org.id),
            str(created.id),
            {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [{"op": "replace", "path": "displayName", "value": "New Name"}],
            },
        )
        assert updated.name == "New Name"

    @pytest.mark.asyncio
    async def test_patch_replace_username(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "old-email@acme.com", "displayName": "Email User"}
        )
        updated = await scim_service.update_scim_user(
            str(scim_org.id),
            str(created.id),
            {
                "Operations": [{"op": "replace", "path": "userName", "value": "new-email@acme.com"}],
            },
        )
        assert updated.email == "new-email@acme.com"

    @pytest.mark.asyncio
    async def test_patch_replace_name_object(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "name-obj@acme.com", "displayName": "Before"}
        )
        updated = await scim_service.update_scim_user(
            str(scim_org.id),
            str(created.id),
            {
                "Operations": [{"op": "replace", "path": "name", "value": {"givenName": "Jane", "familyName": "Doe"}}],
            },
        )
        assert updated.name == "Jane Doe"

    @pytest.mark.asyncio
    async def test_direct_attribute_replacement(self, scim_org):
        """Azure AD-style direct attribute replacement (no Operations array)."""
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "direct@acme.com", "displayName": "Direct User"}
        )
        updated = await scim_service.update_scim_user(
            str(scim_org.id),
            str(created.id),
            {"displayName": "Updated Direct", "userName": "direct-new@acme.com"},
        )
        assert updated.name == "Updated Direct"
        assert updated.email == "direct-new@acme.com"

    @pytest.mark.asyncio
    async def test_update_nonexistent_user_returns_404(self, scim_org):
        with pytest.raises(SCIMError) as exc_info:
            await scim_service.update_scim_user(
                str(scim_org.id),
                "000000000000000000000000",
                {"displayName": "Ghost"},
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_replace_external_id(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "patch-ext@acme.com", "displayName": "PatchExt"}
        )
        updated = await scim_service.update_scim_user(
            str(scim_org.id),
            str(created.id),
            {"Operations": [{"op": "replace", "path": "externalId", "value": "ext-patched"}]},
        )
        assert updated.external_id == "ext-patched"


# ---------------------------------------------------------------------------
# PATCH add and remove operations
# ---------------------------------------------------------------------------


class TestPatchAddRemove:
    @pytest.mark.asyncio
    async def test_add_sets_single_valued_attribute(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "add-test@acme.com", "displayName": "AddTest"}
        )
        updated = await scim_service.update_scim_user(
            str(scim_org.id),
            str(created.id),
            {"Operations": [{"op": "add", "path": "externalId", "value": "add-ext"}]},
        )
        assert updated.external_id == "add-ext"

    @pytest.mark.asyncio
    async def test_add_without_path_applies_value_dict(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "add-nopath@acme.com", "displayName": "AddNoPath"}
        )
        updated = await scim_service.update_scim_user(
            str(scim_org.id),
            str(created.id),
            {"Operations": [{"op": "add", "value": {"displayName": "NewName", "externalId": "new-ext"}}]},
        )
        assert updated.name == "NewName"
        assert updated.external_id == "new-ext"

    @pytest.mark.asyncio
    async def test_remove_clears_optional_attribute(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id),
            {"userName": "rm-test@acme.com", "displayName": "RmTest", "externalId": "rm-ext"},
        )
        updated = await scim_service.update_scim_user(
            str(scim_org.id),
            str(created.id),
            {"Operations": [{"op": "remove", "path": "externalId"}]},
        )
        assert updated.external_id is None

    @pytest.mark.asyncio
    async def test_remove_required_attribute_raises_mutability(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "rm-req@acme.com", "displayName": "RmReq"}
        )
        with pytest.raises(SCIMError) as exc_info:
            await scim_service.update_scim_user(
                str(scim_org.id),
                str(created.id),
                {"Operations": [{"op": "remove", "path": "userName"}]},
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.scim_type == "mutability"

    @pytest.mark.asyncio
    async def test_remove_without_path_raises_no_target(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "rm-nopath@acme.com", "displayName": "RmNoPath"}
        )
        with pytest.raises(SCIMError) as exc_info:
            await scim_service.update_scim_user(
                str(scim_org.id),
                str(created.id),
                {"Operations": [{"op": "remove"}]},
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.scim_type == "noTarget"

    @pytest.mark.asyncio
    async def test_remove_display_name_clears_to_empty(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "rm-dn@acme.com", "displayName": "ToRemove"}
        )
        updated = await scim_service.update_scim_user(
            str(scim_org.id),
            str(created.id),
            {"Operations": [{"op": "remove", "path": "displayName"}]},
        )
        assert updated.name == ""


# ---------------------------------------------------------------------------
# delete_scim_user
# ---------------------------------------------------------------------------


class TestDeleteScimUser:
    @pytest.mark.asyncio
    async def test_deactivates_user_and_removes_membership(self, scim_org):
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "delete-me@acme.com", "displayName": "Delete Me"}
        )
        await scim_service.delete_scim_user(str(scim_org.id), str(created.id))

        refreshed = await User.get(created.id)
        assert refreshed.org_id is None

        membership = await OrgMembership.find_one(
            OrgMembership.org_id == str(scim_org.id),
            OrgMembership.user_id == str(created.id),
        )
        assert membership is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_user_returns_404(self, scim_org):
        with pytest.raises(SCIMError) as exc_info:
            await scim_service.delete_scim_user(str(scim_org.id), "000000000000000000000000")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_user_document_preserved_after_delete(self, scim_org):
        """User document still exists after SCIM deletion (for document ownership)."""
        created = await scim_service.create_scim_user(
            str(scim_org.id), {"userName": "preserved@acme.com", "displayName": "Preserved"}
        )
        await scim_service.delete_scim_user(str(scim_org.id), str(created.id))

        user = await User.get(created.id)
        assert user is not None
        assert user.email == "preserved@acme.com"


# ---------------------------------------------------------------------------
# SCIMError
# ---------------------------------------------------------------------------


class TestSCIMError:
    def test_builds_error_dict_without_scim_type(self):
        err = SCIMError(404, "Not found")
        d = err.to_dict()
        assert d["schemas"] == [scim_service.SCIM_ERROR_SCHEMA]
        assert d["status"] == "404"
        assert d["detail"] == "Not found"
        assert "scimType" not in d

    def test_builds_error_dict_with_scim_type(self):
        err = SCIMError(409, "User already exists", scim_type="uniqueness")
        d = err.to_dict()
        assert d["scimType"] == "uniqueness"
        assert d["status"] == "409"

    def test_is_exception(self):
        err = SCIMError(400, "bad")
        assert isinstance(err, Exception)
        assert str(err) == "bad"
