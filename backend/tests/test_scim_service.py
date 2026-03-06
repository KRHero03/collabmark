"""Tests for SCIM user provisioning service."""

import pytest
from app.models.organization import Organization, OrgMembership, OrgRole
from app.models.user import User
from app.services import scim_service
from fastapi import HTTPException


@pytest.fixture
async def scim_org() -> Organization:
    org = Organization(name="SCIM Test Org", slug="scim-test-org")
    await org.insert()
    return org


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
        with pytest.raises(HTTPException) as exc_info:
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
    async def test_duplicate_email_in_same_org_returns_409(self, scim_org):
        resource = {"userName": "dup@acme.com", "displayName": "Dup User"}
        await scim_service.create_scim_user(str(scim_org.id), resource)

        with pytest.raises(HTTPException) as exc_info:
            await scim_service.create_scim_user(str(scim_org.id), resource)
        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_duplicate_email_in_different_org_returns_409(self, scim_org):
        other_org = Organization(name="Other Org", slug="scim-other-org")
        await other_org.insert()

        resource = {"userName": "cross@acme.com", "displayName": "Cross User"}
        await scim_service.create_scim_user(str(scim_org.id), resource)

        with pytest.raises(HTTPException) as exc_info:
            await scim_service.create_scim_user(str(other_org.id), resource)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_missing_email_returns_400(self, scim_org):
        resource = {"displayName": "No Email User"}
        with pytest.raises(HTTPException) as exc_info:
            await scim_service.create_scim_user(str(scim_org.id), resource)
        assert exc_info.value.status_code == 400


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
        with pytest.raises(HTTPException) as exc_info:
            await scim_service.get_scim_user(str(scim_org.id), "000000000000000000000000")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_id_returns_404(self, scim_org):
        with pytest.raises(HTTPException) as exc_info:
            await scim_service.get_scim_user(str(scim_org.id), "bad-id")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_user_in_different_org_returns_404(self, scim_org):
        other_org = Organization(name="Other Get Org", slug="scim-other-get-org")
        await other_org.insert()
        created = await scim_service.create_scim_user(
            str(other_org.id), {"userName": "wrong-org@acme.com", "displayName": "Wrong Org"}
        )
        with pytest.raises(HTTPException) as exc_info:
            await scim_service.get_scim_user(str(scim_org.id), str(created.id))
        assert exc_info.value.status_code == 404


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
        with pytest.raises(HTTPException) as exc_info:
            await scim_service.update_scim_user(
                str(scim_org.id),
                "000000000000000000000000",
                {"displayName": "Ghost"},
            )
        assert exc_info.value.status_code == 404


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
        with pytest.raises(HTTPException) as exc_info:
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


class TestParseScimFilter:
    def test_parses_username_eq_filter(self):
        result = scim_service._parse_scim_filter('userName eq "alice@acme.com"')
        assert result == ("userName", "alice@acme.com")

    def test_parses_case_insensitive_eq(self):
        result = scim_service._parse_scim_filter('userName EQ "bob@acme.com"')
        assert result == ("userName", "bob@acme.com")

    def test_returns_none_for_unsupported_operator(self):
        result = scim_service._parse_scim_filter('userName co "acme"')
        assert result is None

    def test_returns_none_for_malformed_filter(self):
        result = scim_service._parse_scim_filter("garbage input")
        assert result is None

    def test_returns_none_for_empty_string(self):
        result = scim_service._parse_scim_filter("")
        assert result is None


class TestScimError:
    def test_builds_error_dict(self):
        err = scim_service.scim_error(409, "User already exists")
        assert err["schemas"] == [scim_service.SCIM_ERROR_SCHEMA]
        assert err["status"] == "409"
        assert err["detail"] == "User already exists"
