"""Tests for SCIM bearer token authentication dependency."""

from unittest.mock import MagicMock

import pytest
from app.auth.scim_auth import get_scim_org, hash_scim_token
from app.models.org_sso_config import OrgSSOConfig
from app.models.organization import Organization
from app.services.scim_service import SCIMError


def _mock_request(token: str | None = None) -> MagicMock:
    """Build a mock Request with an Authorization header."""
    req = MagicMock()
    if token is not None:
        req.headers = {"Authorization": f"Bearer {token}"}
    else:
        req.headers = {}
    return req


class TestHashScimToken:
    def test_returns_sha256_hex_digest(self):
        result = hash_scim_token("my-secret-token")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_same_input_produces_same_hash(self):
        assert hash_scim_token("abc") == hash_scim_token("abc")

    def test_different_input_produces_different_hash(self):
        assert hash_scim_token("abc") != hash_scim_token("xyz")

    def test_empty_string_is_hashable(self):
        result = hash_scim_token("")
        assert isinstance(result, str)
        assert len(result) == 64


class TestGetScimOrg:
    @pytest.mark.asyncio
    async def test_missing_auth_header_returns_401(self):
        req = _mock_request(token=None)
        with pytest.raises(SCIMError) as exc_info:
            await get_scim_org(req)
        assert exc_info.value.status_code == 401
        assert "authorization" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_malformed_auth_header_returns_401(self):
        req = MagicMock()
        req.headers = {"Authorization": "Basic dXNlcjpwYXNz"}
        with pytest.raises(SCIMError) as exc_info:
            await get_scim_org(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_bearer_token_returns_401(self):
        req = MagicMock()
        req.headers = {"Authorization": "Bearer "}
        with pytest.raises(SCIMError) as exc_info:
            await get_scim_org(req)
        assert exc_info.value.status_code == 401
        assert "empty" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        req = _mock_request("completely-invalid-token")
        with pytest.raises(SCIMError) as exc_info:
            await get_scim_org(req)
        assert exc_info.value.status_code == 401
        assert "invalid" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_valid_token_with_scim_disabled_returns_403(self):
        org = Organization(name="SCIM Disabled Org", slug="scim-disabled-org")
        await org.insert()
        token = "valid-disabled-token"
        cfg = OrgSSOConfig(
            org_id=str(org.id),
            scim_enabled=False,
            scim_bearer_token=hash_scim_token(token),
        )
        await cfg.insert()

        req = _mock_request(token)
        with pytest.raises(SCIMError) as exc_info:
            await get_scim_org(req)
        assert exc_info.value.status_code == 403
        assert "disabled" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_valid_token_returns_org_and_config(self):
        org = Organization(name="SCIM Valid Org", slug="scim-valid-org")
        await org.insert()
        token = "valid-scim-token-123"
        cfg = OrgSSOConfig(
            org_id=str(org.id),
            scim_enabled=True,
            scim_bearer_token=hash_scim_token(token),
        )
        await cfg.insert()

        req = _mock_request(token)
        result_org, result_cfg = await get_scim_org(req)
        assert str(result_org.id) == str(org.id)
        assert result_cfg.scim_enabled is True

    @pytest.mark.asyncio
    async def test_revoked_token_returns_401(self):
        """After revoking (clearing) the token, auth should fail."""
        org = Organization(name="Revoked Token Org", slug="revoked-token-org")
        await org.insert()
        token = "will-be-revoked"
        cfg = OrgSSOConfig(
            org_id=str(org.id),
            scim_enabled=True,
            scim_bearer_token=hash_scim_token(token),
        )
        await cfg.insert()

        cfg.scim_bearer_token = None
        cfg.scim_enabled = False
        await cfg.save()

        req = _mock_request(token)
        with pytest.raises(SCIMError) as exc_info:
            await get_scim_org(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_org_not_found_returns_401(self):
        """Config exists but referenced org has been deleted."""
        cfg = OrgSSOConfig(
            org_id="000000000000000000000000",
            scim_enabled=True,
            scim_bearer_token=hash_scim_token("orphan-token"),
        )
        await cfg.insert()

        req = _mock_request("orphan-token")
        with pytest.raises(SCIMError) as exc_info:
            await get_scim_org(req)
        assert exc_info.value.status_code == 401
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_wrong_token_for_org_returns_401(self):
        """Token exists for a different org; wrong token should fail."""
        org = Organization(name="Wrong Token Org", slug="wrong-token-org")
        await org.insert()
        cfg = OrgSSOConfig(
            org_id=str(org.id),
            scim_enabled=True,
            scim_bearer_token=hash_scim_token("correct-token"),
        )
        await cfg.insert()

        req = _mock_request("wrong-token")
        with pytest.raises(SCIMError) as exc_info:
            await get_scim_org(req)
        assert exc_info.value.status_code == 401
