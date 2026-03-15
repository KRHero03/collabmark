"""Comprehensive tests for SSO authentication: SAML, OIDC, detect, and shared logic."""

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from app.auth.jwt import create_access_token
from app.auth.sso_common import (
    SSOCallbackResult,
    detect_org_by_email_domain,
    find_or_create_sso_user,
)
from app.auth.sso_oidc import (
    create_oidc_client,
    get_oidc_discovery,
    initiate_oidc_login,
    process_oidc_callback,
)
from app.auth.sso_saml import (
    build_saml_settings,
    create_saml_auth_request,
    prepare_saml_request,
    process_saml_response,
)
from app.models.org_sso_config import OrgSSOConfig, SSOProtocol
from app.models.organization import Organization, OrgMembership, OrgRole
from app.models.user import User


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"Cookie": f"access_token={token}"}


# ---------------------------------------------------------------------------
# detect_org_by_email_domain (unit)
# ---------------------------------------------------------------------------


class TestDetectOrgByEmailDomain:
    @pytest.mark.asyncio
    async def test_email_with_matching_verified_domain_returns_org_and_config(self):
        org = Organization(
            name="Acme Corp",
            slug="acme",
            verified_domains=["acme.com"],
        )
        await org.insert()
        sso_config = OrgSSOConfig(
            org_id=str(org.id),
            protocol=SSOProtocol.SAML,
            enabled=True,
            idp_entity_id="https://idp.acme.com",
            idp_sso_url="https://idp.acme.com/sso",
            idp_certificate="-----BEGIN CERT-----",
        )
        await sso_config.insert()
        try:
            found_org, found_config = await detect_org_by_email_domain("alice@acme.com")
            assert found_org is not None
            assert found_config is not None
            assert found_org.id == org.id
            assert found_config.org_id == str(org.id)
            assert found_config.protocol == SSOProtocol.SAML
        finally:
            await org.delete()
            await sso_config.delete()

    @pytest.mark.asyncio
    async def test_email_with_non_matching_domain_returns_none(self):
        org = Organization(
            name="Acme Corp",
            slug="acme",
            verified_domains=["acme.com"],
        )
        await org.insert()
        sso_config = OrgSSOConfig(
            org_id=str(org.id),
            protocol=SSOProtocol.SAML,
            enabled=True,
        )
        await sso_config.insert()
        try:
            found_org, found_config = await detect_org_by_email_domain("bob@other.com")
            assert found_org is None
            assert found_config is None
        finally:
            await org.delete()
            await sso_config.delete()

    @pytest.mark.asyncio
    async def test_email_with_matching_domain_but_sso_disabled_returns_none(self):
        org = Organization(
            name="Acme Corp",
            slug="acme",
            verified_domains=["acme.com"],
        )
        await org.insert()
        sso_config = OrgSSOConfig(
            org_id=str(org.id),
            protocol=SSOProtocol.SAML,
            enabled=False,
        )
        await sso_config.insert()
        try:
            found_org, found_config = await detect_org_by_email_domain("alice@acme.com")
            assert found_org is None
            assert found_config is None
        finally:
            await org.delete()
            await sso_config.delete()

    @pytest.mark.asyncio
    async def test_invalid_email_format_returns_none(self):
        found_org, found_config = await detect_org_by_email_domain("not-an-email")
        assert found_org is None
        assert found_config is None


# ---------------------------------------------------------------------------
# find_or_create_sso_user (unit)
# ---------------------------------------------------------------------------


class TestFindOrCreateSsoUser:
    @pytest.mark.asyncio
    async def test_new_user_created_with_correct_org_id_and_auth_provider(self):
        org = Organization(name="Acme", slug="acme", verified_domains=["acme.com"])
        await org.insert()
        result = SSOCallbackResult(email="new@acme.com", name="New User", avatar_url=None)
        try:
            user = await find_or_create_sso_user(result, org, SSOProtocol.OIDC)
            assert user.email == "new@acme.com"
            assert user.name == "New User"
            assert user.org_id == str(org.id)
            assert user.auth_provider == "oidc"
        finally:
            u = await User.find_one(User.email == "new@acme.com")
            if u:
                await u.delete()
            await org.delete()

    @pytest.mark.asyncio
    async def test_existing_user_updated_with_org_id_and_auth_provider(self):
        org = Organization(name="Acme", slug="acme", verified_domains=["acme.com"])
        await org.insert()
        existing = User(
            email="existing@acme.com",
            name="Old Name",
            org_id=None,
            auth_provider="google",
        )
        await existing.insert()
        result = SSOCallbackResult(email="existing@acme.com", name="Updated Name", avatar_url="https://x.com/a.png")
        try:
            user = await find_or_create_sso_user(result, org, SSOProtocol.SAML)
            assert user.id == existing.id
            assert user.name == "Updated Name"
            assert user.avatar_url == "https://x.com/a.png"
            assert user.org_id == str(org.id)
            assert user.auth_provider == "saml"
        finally:
            await existing.delete()
            await org.delete()

    @pytest.mark.asyncio
    async def test_org_membership_created_for_new_user(self):
        org = Organization(name="Acme", slug="acme", verified_domains=["acme.com"])
        await org.insert()
        result = SSOCallbackResult(email="member@acme.com", name="Member")
        try:
            user = await find_or_create_sso_user(result, org, SSOProtocol.OIDC)
            membership = await OrgMembership.find_one(
                OrgMembership.org_id == str(org.id),
                OrgMembership.user_id == str(user.id),
            )
            assert membership is not None
            assert membership.role == OrgRole.MEMBER
        finally:
            u = await User.find_one(User.email == "member@acme.com")
            if u:
                m = await OrgMembership.find_one(
                    OrgMembership.org_id == str(org.id),
                    OrgMembership.user_id == str(u.id),
                )
                if m:
                    await m.delete()
                await u.delete()
            await org.delete()

    @pytest.mark.asyncio
    async def test_existing_membership_not_duplicated(self):
        org = Organization(name="Acme", slug="acme", verified_domains=["acme.com"])
        await org.insert()
        user = User(email="dup@acme.com", name="Dup", org_id=str(org.id), auth_provider="oidc")
        await user.insert()
        membership = OrgMembership(org_id=str(org.id), user_id=str(user.id), role=OrgRole.MEMBER)
        await membership.insert()
        result = SSOCallbackResult(email="dup@acme.com", name="Dup")
        try:
            found = await find_or_create_sso_user(result, org, SSOProtocol.OIDC)
            assert found.id == user.id
            count = await OrgMembership.find(OrgMembership.org_id == str(org.id)).count()
            assert count == 1
        finally:
            await user.delete()
            await membership.delete()
            await org.delete()


# ---------------------------------------------------------------------------
# build_saml_settings (unit)
# ---------------------------------------------------------------------------


class TestBuildSamlSettings:
    def test_correct_settings_dict_structure_from_config(self):
        config = OrgSSOConfig(
            org_id="org123",
            protocol=SSOProtocol.SAML,
            idp_entity_id="https://idp.example.com",
            idp_sso_url="https://idp.example.com/sso",
            idp_certificate="cert-data",
            sp_entity_id="https://sp.example.com",
            sp_acs_url="https://sp.example.com/acs",
        )
        settings = build_saml_settings(config, "https://app.example.com")
        assert settings["strict"] is True
        assert settings["sp"]["entityId"] == "https://sp.example.com"
        assert settings["sp"]["assertionConsumerService"]["url"] == "https://sp.example.com/acs"
        assert settings["idp"]["entityId"] == "https://idp.example.com"
        assert settings["idp"]["singleSignOnService"]["url"] == "https://idp.example.com/sso"
        assert settings["idp"]["x509cert"] == "cert-data"


# ---------------------------------------------------------------------------
# create_oidc_client (unit)
# ---------------------------------------------------------------------------


class TestCreateOidcClient:
    def test_client_has_correct_client_id_and_scope(self):
        config = OrgSSOConfig(
            org_id="org123",
            protocol=SSOProtocol.OIDC,
            oidc_client_id="client-123",
            oidc_client_secret="secret-456",
        )
        client = create_oidc_client(config)
        assert client.client_id == "client-123"
        assert client.client_secret == "secret-456"
        assert "openid" in client.scope
        assert "email" in client.scope
        assert "profile" in client.scope


# ---------------------------------------------------------------------------
# detect_idp route (HTTP)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def sso_org_and_config():
    org = Organization(name="SSO Org", slug="sso-org", verified_domains=["sso-org.com"])
    await org.insert()
    config = OrgSSOConfig(
        org_id=str(org.id),
        protocol=SSOProtocol.OIDC,
        enabled=True,
        oidc_discovery_url="https://idp.sso-org.com/.well-known/openid-configuration",
    )
    await config.insert()
    yield org, config
    await config.delete()
    await org.delete()


class TestDetectIdpRoute:
    @pytest.mark.asyncio
    async def test_post_with_sso_email_returns_sso_true(self, async_client, sso_org_and_config):
        org, _ = sso_org_and_config
        response = await async_client.post(
            "/api/auth/sso/detect",
            json={"email": "user@sso-org.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sso"] is True
        assert data["org_id"] == str(org.id)
        assert data["org_name"] == "SSO Org"
        assert data["protocol"] == "oidc"

    @pytest.mark.asyncio
    async def test_post_with_non_sso_email_returns_sso_false(self, async_client):
        response = await async_client.post(
            "/api/auth/sso/detect",
            json={"email": "user@unknown.com"},
        )
        assert response.status_code == 200
        assert response.json()["sso"] is False

    @pytest.mark.asyncio
    async def test_post_with_empty_email_returns_sso_false(self, async_client):
        response = await async_client.post(
            "/api/auth/sso/detect",
            json={"email": ""},
        )
        assert response.status_code == 200
        assert response.json()["sso"] is False


# ---------------------------------------------------------------------------
# saml_login route (HTTP, mock create_saml_auth_request)
# ---------------------------------------------------------------------------


class TestSamlLoginRoute:
    @pytest.mark.asyncio
    async def test_get_with_valid_org_id_redirects_to_idp(self, async_client, sso_org_and_config):
        org, config = sso_org_and_config
        config.protocol = SSOProtocol.SAML
        config.enabled = True
        config.idp_sso_url = "https://idp.example.com/sso"
        await config.save()

        with patch("app.routes.auth.create_saml_auth_request", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = "https://idp.example.com/sso?SAMLRequest=xxx"
            response = await async_client.get(
                f"/api/auth/sso/saml/login/{org.id}",
                follow_redirects=False,
            )
            assert response.status_code in (302, 307)
            assert "idp.example.com" in response.headers.get("location", "")
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_with_invalid_org_id_redirects_with_error(self, async_client):
        response = await async_client.get(
            "/api/auth/sso/saml/login/507f1f77bcf86cd799439011",
            follow_redirects=False,
        )
        assert response.status_code in (302, 307)
        assert "error=sso_not_configured" in response.headers.get("location", "")


# ---------------------------------------------------------------------------
# saml_callback route (HTTP, mock process_saml_response)
# ---------------------------------------------------------------------------


class TestSamlCallbackRoute:
    @pytest.mark.asyncio
    async def test_post_with_valid_saml_response_creates_user_and_sets_cookie(self, async_client, sso_org_and_config):
        org, config = sso_org_and_config
        config.protocol = SSOProtocol.SAML
        config.enabled = True
        await config.save()

        with patch("app.routes.auth.process_saml_response", new_callable=AsyncMock) as mock_process:
            mock_process.return_value = SSOCallbackResult(
                email="saml-user@sso-org.com",
                name="SAML User",
                avatar_url=None,
            )
            response = await async_client.post(
                "/api/auth/sso/saml/callback",
                data={"SAMLResponse": "fake-saml-response", "RelayState": str(org.id)},
                follow_redirects=False,
            )
            assert response.status_code in (302, 307)
            assert "access_token" in response.headers.get("set-cookie", "")
            user = await User.find_one(User.email == "saml-user@sso-org.com")
            assert user is not None
            assert user.org_id == str(org.id)
            assert user.auth_provider == "saml"
            await user.delete()

    @pytest.mark.asyncio
    async def test_post_with_invalid_response_redirects_with_error(self, async_client, sso_org_and_config):
        org, config = sso_org_and_config
        config.protocol = SSOProtocol.SAML
        config.enabled = True
        await config.save()

        with patch("app.routes.auth.process_saml_response", new_callable=AsyncMock) as mock_process:
            mock_process.side_effect = ValueError("SAML validation failed")
            response = await async_client.post(
                "/api/auth/sso/saml/callback",
                data={"SAMLResponse": "invalid", "RelayState": str(org.id)},
                follow_redirects=False,
            )
            assert response.status_code in (302, 307)
            assert "error=saml_invalid" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_post_without_saml_response_redirects_with_error(self, async_client):
        response = await async_client.post(
            "/api/auth/sso/saml/callback",
            data={"RelayState": "some-org-id"},
            follow_redirects=False,
        )
        assert response.status_code in (302, 307)
        assert "error=saml_missing_response" in response.headers.get("location", "")


# ---------------------------------------------------------------------------
# oidc_login route (HTTP, mock initiate_oidc_login)
# ---------------------------------------------------------------------------


class TestOidcLoginRoute:
    @pytest.mark.asyncio
    async def test_get_with_valid_org_id_redirects_to_idp(self, async_client, sso_org_and_config):
        org, _config = sso_org_and_config

        with patch("app.routes.auth.initiate_oidc_login", new_callable=AsyncMock) as mock_initiate:
            mock_initiate.return_value = "https://idp.example.com/authorize?state=xxx"
            response = await async_client.get(
                f"/api/auth/sso/oidc/login/{org.id}",
                follow_redirects=False,
            )
            assert response.status_code in (302, 307)
            assert "idp.example.com" in response.headers.get("location", "")
            mock_initiate.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_with_invalid_org_id_redirects_with_error(self, async_client):
        response = await async_client.get(
            "/api/auth/sso/oidc/login/507f1f77bcf86cd799439011",
            follow_redirects=False,
        )
        assert response.status_code in (302, 307)
        assert "error=sso_not_configured" in response.headers.get("location", "")


# ---------------------------------------------------------------------------
# oidc_callback route (HTTP, mock process_oidc_callback)
# ---------------------------------------------------------------------------


class TestOidcCallbackRoute:
    @pytest.mark.asyncio
    async def test_get_with_valid_code_and_state_creates_user_and_sets_cookie(self, async_client, sso_org_and_config):
        org, _config = sso_org_and_config
        fixed_token = "test-state-token"
        state = f"{org.id}:{fixed_token}"

        with patch("app.routes.auth.secrets.token_urlsafe", return_value=fixed_token):
            with patch("app.routes.auth.process_oidc_callback", new_callable=AsyncMock) as mock_process:
                mock_process.return_value = SSOCallbackResult(
                    email="oidc-user@sso-org.com",
                    name="OIDC User",
                    avatar_url=None,
                )
                with patch("app.routes.auth.initiate_oidc_login", new_callable=AsyncMock) as mock_init:
                    mock_init.return_value = f"https://idp.example.com/authorize?state={state}"
                    login_resp = await async_client.get(
                        f"/api/auth/sso/oidc/login/{org.id}",
                        follow_redirects=False,
                    )
                cookies = login_resp.cookies

                response = await async_client.get(
                    f"/api/auth/sso/oidc/callback?code=fake-code&state={state}",
                    cookies=dict(cookies),
                    follow_redirects=False,
                )
                assert response.status_code in (302, 307)
                assert "access_token" in response.headers.get("set-cookie", "")
                user = await User.find_one(User.email == "oidc-user@sso-org.com")
                assert user is not None
                assert user.org_id == str(org.id)
                assert user.auth_provider == "oidc"
                await user.delete()

    @pytest.mark.asyncio
    async def test_get_with_missing_code_redirects_with_error(self, async_client):
        response = await async_client.get(
            "/api/auth/sso/oidc/callback?state=org:token",
            follow_redirects=False,
        )
        assert response.status_code in (302, 307)
        assert "error=oidc_missing_code" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_get_with_state_mismatch_redirects_with_error(self, async_client, sso_org_and_config):
        org, _ = sso_org_and_config
        response = await async_client.get(
            f"/api/auth/sso/oidc/callback?code=fake&state={org.id}:wrong-state",
            follow_redirects=False,
        )
        assert response.status_code in (302, 307)
        assert "error=oidc_state_mismatch" in response.headers.get("location", "")


# ---------------------------------------------------------------------------
# Integration: detect -> initiate -> callback -> user exists
# ---------------------------------------------------------------------------


class TestSsoIntegration:
    @pytest.mark.asyncio
    async def test_detect_then_oidc_login_then_callback_user_exists(self, async_client, sso_org_and_config):
        org, _config = sso_org_and_config

        # 1. Detect
        detect_resp = await async_client.post(
            "/api/auth/sso/detect",
            json={"email": "integration@sso-org.com"},
        )
        assert detect_resp.json()["sso"] is True
        assert detect_resp.json()["org_id"] == str(org.id)

        # 2. Initiate login (mock) - use fixed token so state matches session
        fixed_token = "integration-test-token"
        state = f"{org.id}:{fixed_token}"
        with patch("app.routes.auth.secrets.token_urlsafe", return_value=fixed_token):
            with patch("app.routes.auth.initiate_oidc_login", new_callable=AsyncMock) as mock_init:
                mock_init.return_value = f"https://idp.example.com/auth?state={state}"
                login_resp = await async_client.get(
                    f"/api/auth/sso/oidc/login/{org.id}",
                    follow_redirects=False,
                )
            cookies = login_resp.cookies

            # 3. Callback (mock)
            with patch("app.routes.auth.process_oidc_callback", new_callable=AsyncMock) as mock_process:
                mock_process.return_value = SSOCallbackResult(
                    email="integration@sso-org.com",
                    name="Integration User",
                    avatar_url=None,
                )
                callback_resp = await async_client.get(
                    f"/api/auth/sso/oidc/callback?code=abc123&state={state}",
                    cookies=dict(cookies),
                    follow_redirects=False,
                )

            assert callback_resp.status_code in (302, 307)
            assert "access_token" in callback_resp.headers.get("set-cookie", "")

        # 4. User exists with correct org_id
        user = await User.find_one(User.email == "integration@sso-org.com")
        assert user is not None
        assert user.org_id == str(org.id)
        assert user.auth_provider == "oidc"
        await user.delete()


# ---------------------------------------------------------------------------
# prepare_saml_request (unit)
# ---------------------------------------------------------------------------


class TestPrepareSamlRequest:
    def test_returns_correct_keys(self):
        result = prepare_saml_request(
            {
                "http_host": "app.example.com",
                "script_name": "/saml",
                "server_port": 443,
                "get_data": {"key": "val"},
                "post_data": {"SAMLResponse": "base64data"},
                "https": "on",
            }
        )
        assert result["http_host"] == "app.example.com"
        assert result["script_name"] == "/saml"
        assert result["server_port"] == 443
        assert result["get_data"] == {"key": "val"}
        assert result["post_data"] == {"SAMLResponse": "base64data"}
        assert result["https"] == "on"

    def test_defaults_for_missing_keys(self):
        result = prepare_saml_request({})
        assert result["http_host"] == ""
        assert result["script_name"] == ""
        assert result["server_port"] == 443
        assert result["get_data"] == {}
        assert result["post_data"] == {}
        assert result["https"] == "on"


class TestBuildSamlSettingsDefaults:
    def test_uses_request_url_for_defaults_when_sp_fields_missing(self):
        config = OrgSSOConfig(
            org_id="org1",
            protocol=SSOProtocol.SAML,
            sp_entity_id=None,
            sp_acs_url=None,
            idp_entity_id=None,
            idp_sso_url=None,
            idp_certificate=None,
        )
        settings = build_saml_settings(config, "https://myapp.com")
        assert settings["sp"]["entityId"] == "https://myapp.com/api/auth/sso/saml/metadata"
        assert settings["sp"]["assertionConsumerService"]["url"] == "https://myapp.com/api/auth/sso/saml/callback"
        assert settings["idp"]["entityId"] == ""
        assert settings["idp"]["singleSignOnService"]["url"] == ""
        assert settings["idp"]["x509cert"] == ""


# ---------------------------------------------------------------------------
# create_saml_auth_request (unit, mock OneLogin_Saml2_Auth)
# ---------------------------------------------------------------------------


class TestCreateSamlAuthRequest:
    @pytest.mark.asyncio
    async def test_creates_auth_request_and_returns_redirect_url(self):
        config = OrgSSOConfig(
            org_id="org1",
            protocol=SSOProtocol.SAML,
            idp_entity_id="https://idp.test.com",
            idp_sso_url="https://idp.test.com/sso",
            idp_certificate="CERT",
            sp_entity_id="https://sp.test.com",
            sp_acs_url="https://sp.test.com/acs",
        )
        mock_auth_instance = MagicMock()
        mock_auth_instance.login.return_value = "https://idp.test.com/sso?SAMLRequest=encoded"

        with patch("app.auth.sso_saml.OneLogin_Saml2_Auth", return_value=mock_auth_instance) as mock_cls:
            result = await create_saml_auth_request(config, "https://myapp.com", relay_state="org1")
            assert result == "https://idp.test.com/sso?SAMLRequest=encoded"
            mock_cls.assert_called_once()
            mock_auth_instance.login.assert_called_once_with("org1")

    @pytest.mark.asyncio
    async def test_http_url_sets_port_80_and_https_off(self):
        config = OrgSSOConfig(
            org_id="org1",
            protocol=SSOProtocol.SAML,
            idp_sso_url="https://idp.test.com/sso",
        )
        mock_auth_instance = MagicMock()
        mock_auth_instance.login.return_value = "https://idp.test.com/sso?SAMLRequest=x"

        with patch("app.auth.sso_saml.OneLogin_Saml2_Auth", return_value=mock_auth_instance) as mock_cls:
            await create_saml_auth_request(config, "http://localhost:8000")
            call_args = mock_cls.call_args[0]
            req_data = call_args[0]
            assert req_data["server_port"] == 80
            assert req_data["https"] == "off"


# ---------------------------------------------------------------------------
# process_saml_response (unit, mock OneLogin_Saml2_Auth)
# ---------------------------------------------------------------------------


class TestProcessSamlResponse:
    @pytest.mark.asyncio
    async def test_valid_response_returns_callback_result(self):
        config = OrgSSOConfig(
            org_id="org1",
            protocol=SSOProtocol.SAML,
            idp_entity_id="https://idp.test.com",
            idp_sso_url="https://idp.test.com/sso",
            idp_certificate="CERT",
        )
        mock_auth = MagicMock()
        mock_auth.process_response.return_value = None
        mock_auth.get_errors.return_value = []
        mock_auth.get_attributes.return_value = {
            "email": ["alice@test.com"],
            "displayName": ["Alice Test"],
            "picture": ["https://pic.com/alice.jpg"],
        }
        mock_auth.get_nameid.return_value = "alice@test.com"

        with patch("app.auth.sso_saml.OneLogin_Saml2_Auth", return_value=mock_auth):
            result = await process_saml_response(config, "https://myapp.com", {"SAMLResponse": "base64"})
            assert result.email == "alice@test.com"
            assert result.name == "Alice Test"
            assert result.avatar_url == "https://pic.com/alice.jpg"

    @pytest.mark.asyncio
    async def test_response_with_errors_raises_value_error(self):
        config = OrgSSOConfig(org_id="org1", protocol=SSOProtocol.SAML)
        mock_auth = MagicMock()
        mock_auth.process_response.return_value = None
        mock_auth.get_errors.return_value = ["invalid_signature", "expired"]

        with patch("app.auth.sso_saml.OneLogin_Saml2_Auth", return_value=mock_auth):
            with pytest.raises(ValueError, match="SAML validation failed"):
                await process_saml_response(config, "https://myapp.com", {"SAMLResponse": "bad"})

    @pytest.mark.asyncio
    async def test_response_missing_email_raises_value_error(self):
        config = OrgSSOConfig(org_id="org1", protocol=SSOProtocol.SAML)
        mock_auth = MagicMock()
        mock_auth.process_response.return_value = None
        mock_auth.get_errors.return_value = []
        mock_auth.get_attributes.return_value = {}
        mock_auth.get_nameid.return_value = None

        with patch("app.auth.sso_saml.OneLogin_Saml2_Auth", return_value=mock_auth):
            with pytest.raises(ValueError, match="SAML response missing email"):
                await process_saml_response(config, "https://myapp.com", {"SAMLResponse": "noemail"})

    @pytest.mark.asyncio
    async def test_uses_claims_uri_fallback_for_email_and_name(self):
        config = OrgSSOConfig(org_id="org1", protocol=SSOProtocol.SAML)
        mock_auth = MagicMock()
        mock_auth.process_response.return_value = None
        mock_auth.get_errors.return_value = []
        mock_auth.get_attributes.return_value = {
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress": ["bob@test.com"],
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name": ["Bob Test"],
        }
        mock_auth.get_nameid.return_value = "bob@test.com"

        with patch("app.auth.sso_saml.OneLogin_Saml2_Auth", return_value=mock_auth):
            result = await process_saml_response(config, "https://myapp.com", {"SAMLResponse": "data"})
            assert result.email == "bob@test.com"
            assert result.name == "Bob Test"

    @pytest.mark.asyncio
    async def test_falls_back_to_nameid_for_email(self):
        config = OrgSSOConfig(org_id="org1", protocol=SSOProtocol.SAML)
        mock_auth = MagicMock()
        mock_auth.process_response.return_value = None
        mock_auth.get_errors.return_value = []
        mock_auth.get_attributes.return_value = {}
        mock_auth.get_nameid.return_value = "carol@test.com"

        with patch("app.auth.sso_saml.OneLogin_Saml2_Auth", return_value=mock_auth):
            result = await process_saml_response(config, "https://myapp.com", {"SAMLResponse": "data"})
            assert result.email == "carol@test.com"
            assert result.name == "carol@test.com"


# ---------------------------------------------------------------------------
# get_oidc_discovery (unit, mock httpx)
# ---------------------------------------------------------------------------


class TestGetOidcDiscovery:
    @pytest.mark.asyncio
    async def test_fetches_discovery_document(self):
        config = OrgSSOConfig(
            org_id="org1",
            protocol=SSOProtocol.OIDC,
            oidc_discovery_url="https://idp.test.com/.well-known/openid-configuration",
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "authorization_endpoint": "https://idp.test.com/auth",
            "token_endpoint": "https://idp.test.com/token",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        with (
            patch("app.auth.sso_oidc.socket.getaddrinfo", return_value=fake_addrinfo),
            patch("app.auth.sso_oidc.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await get_oidc_discovery(config)
            assert result["authorization_endpoint"] == "https://idp.test.com/auth"
            mock_client.get.assert_called_once_with("https://idp.test.com/.well-known/openid-configuration")

    @pytest.mark.asyncio
    async def test_raises_for_missing_discovery_url(self):
        config = OrgSSOConfig(org_id="org1", protocol=SSOProtocol.OIDC, oidc_discovery_url=None)
        with pytest.raises(ValueError, match="OIDC discovery URL not configured"):
            await get_oidc_discovery(config)


# ---------------------------------------------------------------------------
# initiate_oidc_login (unit, mock get_oidc_discovery)
# ---------------------------------------------------------------------------


class TestInitiateOidcLogin:
    @pytest.mark.asyncio
    async def test_returns_authorization_url(self):
        config = OrgSSOConfig(
            org_id="org1",
            protocol=SSOProtocol.OIDC,
            oidc_client_id="client-123",
            oidc_client_secret="secret-456",
            oidc_discovery_url="https://idp.test.com/.well-known/openid-configuration",
        )
        discovery = {
            "authorization_endpoint": "https://idp.test.com/authorize",
            "token_endpoint": "https://idp.test.com/token",
        }
        with patch("app.auth.sso_oidc.get_oidc_discovery", new_callable=AsyncMock, return_value=discovery):
            url = await initiate_oidc_login(config, "https://myapp.com/callback", "state123")
            assert "idp.test.com/authorize" in url
            assert "client_id=client-123" in url
            assert "state=state123" in url

    @pytest.mark.asyncio
    async def test_raises_for_missing_authorization_endpoint(self):
        config = OrgSSOConfig(
            org_id="org1",
            protocol=SSOProtocol.OIDC,
            oidc_client_id="c",
            oidc_client_secret="s",
        )
        discovery = {"token_endpoint": "https://idp.test.com/token"}
        with patch("app.auth.sso_oidc.get_oidc_discovery", new_callable=AsyncMock, return_value=discovery):
            with pytest.raises(ValueError, match="No authorization_endpoint"):
                await initiate_oidc_login(config, "https://myapp.com/callback", "state")


# ---------------------------------------------------------------------------
# process_oidc_callback (unit, mock get_oidc_discovery + httpx)
# ---------------------------------------------------------------------------


class TestProcessOidcCallback:
    @pytest.mark.asyncio
    async def test_exchanges_code_and_returns_callback_result(self):
        config = OrgSSOConfig(
            org_id="org1",
            protocol=SSOProtocol.OIDC,
            oidc_client_id="client-123",
            oidc_client_secret="secret-456",
        )
        discovery = {
            "token_endpoint": "https://idp.test.com/token",
            "userinfo_endpoint": "https://idp.test.com/userinfo",
        }
        mock_token = {"access_token": "at-123", "token_type": "Bearer"}

        mock_userinfo_resp = MagicMock()
        mock_userinfo_resp.json.return_value = {
            "email": "dave@test.com",
            "name": "Dave",
            "picture": "https://pic.com/dave.jpg",
        }
        mock_userinfo_resp.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.get.return_value = mock_userinfo_resp
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.auth.sso_oidc.get_oidc_discovery", new_callable=AsyncMock, return_value=discovery):
            with patch("app.auth.sso_oidc.create_oidc_client") as mock_create_client:
                mock_client = AsyncMock()
                mock_client.fetch_token = AsyncMock(return_value=mock_token)
                mock_create_client.return_value = mock_client

                with patch("app.auth.sso_oidc.httpx.AsyncClient", return_value=mock_http_client):
                    result = await process_oidc_callback(config, "https://myapp.com/callback", "code-abc")
                    assert result.email == "dave@test.com"
                    assert result.name == "Dave"
                    assert result.avatar_url == "https://pic.com/dave.jpg"

    @pytest.mark.asyncio
    async def test_raises_for_missing_token_endpoint(self):
        config = OrgSSOConfig(org_id="org1", protocol=SSOProtocol.OIDC)
        discovery = {"userinfo_endpoint": "https://idp.test.com/userinfo"}

        with patch("app.auth.sso_oidc.get_oidc_discovery", new_callable=AsyncMock, return_value=discovery):
            with pytest.raises(ValueError, match="No token_endpoint"):
                await process_oidc_callback(config, "https://myapp.com/callback", "code")

    @pytest.mark.asyncio
    async def test_raises_for_failed_token_exchange(self):
        config = OrgSSOConfig(
            org_id="org1",
            protocol=SSOProtocol.OIDC,
            oidc_client_id="c",
            oidc_client_secret="s",
        )
        discovery = {"token_endpoint": "https://idp.test.com/token"}

        with patch("app.auth.sso_oidc.get_oidc_discovery", new_callable=AsyncMock, return_value=discovery):
            with patch("app.auth.sso_oidc.create_oidc_client") as mock_create:
                mock_client = AsyncMock()
                mock_client.fetch_token = AsyncMock(return_value={})
                mock_create.return_value = mock_client

                with pytest.raises(ValueError, match="Failed to obtain access token"):
                    await process_oidc_callback(config, "https://myapp.com/callback", "code")

    @pytest.mark.asyncio
    async def test_raises_for_missing_email_in_userinfo(self):
        config = OrgSSOConfig(
            org_id="org1",
            protocol=SSOProtocol.OIDC,
            oidc_client_id="c",
            oidc_client_secret="s",
        )
        discovery = {
            "token_endpoint": "https://idp.test.com/token",
            "userinfo_endpoint": "https://idp.test.com/userinfo",
        }
        mock_token = {"access_token": "at-123"}

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"name": "NoEmail"}
        mock_resp.raise_for_status = MagicMock()
        mock_http = AsyncMock()
        mock_http.get.return_value = mock_resp
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)

        with patch("app.auth.sso_oidc.get_oidc_discovery", new_callable=AsyncMock, return_value=discovery):
            with patch("app.auth.sso_oidc.create_oidc_client") as mock_create:
                mock_client = AsyncMock()
                mock_client.fetch_token = AsyncMock(return_value=mock_token)
                mock_create.return_value = mock_client

                with patch("app.auth.sso_oidc.httpx.AsyncClient", return_value=mock_http):
                    with pytest.raises(ValueError, match="OIDC response missing email"):
                        await process_oidc_callback(config, "https://myapp.com/callback", "code")

    @pytest.mark.asyncio
    async def test_falls_back_to_token_userinfo_when_no_userinfo_endpoint(self):
        config = OrgSSOConfig(
            org_id="org1",
            protocol=SSOProtocol.OIDC,
            oidc_client_id="c",
            oidc_client_secret="s",
        )
        discovery = {"token_endpoint": "https://idp.test.com/token"}
        mock_token = {
            "access_token": "at-123",
            "userinfo": {"email": "embedded@test.com", "preferred_username": "embedded"},
        }

        with patch("app.auth.sso_oidc.get_oidc_discovery", new_callable=AsyncMock, return_value=discovery):
            with patch("app.auth.sso_oidc.create_oidc_client") as mock_create:
                mock_client = AsyncMock()
                mock_client.fetch_token = AsyncMock(return_value=mock_token)
                mock_create.return_value = mock_client

                result = await process_oidc_callback(config, "https://myapp.com/callback", "code")
                assert result.email == "embedded@test.com"
                assert result.name == "embedded"


# ---------------------------------------------------------------------------
# Auth route: SAML callback with missing RelayState
# ---------------------------------------------------------------------------


class TestSamlCallbackEdgeCases:
    @pytest.mark.asyncio
    async def test_post_without_relay_state_redirects_with_error(self, async_client):
        response = await async_client.post(
            "/api/auth/sso/saml/callback",
            data={"SAMLResponse": "base64data"},
            follow_redirects=False,
        )
        assert response.status_code in (302, 307)
        assert "error=saml_missing_org" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_post_with_nonexistent_org_in_relay_state(self, async_client, sso_org_and_config):
        _org, config = sso_org_and_config
        config.protocol = SSOProtocol.SAML
        config.enabled = True
        await config.save()

        with patch("app.routes.auth.process_saml_response", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = SSOCallbackResult(email="x@sso-org.com", name="X")
            response = await async_client.post(
                "/api/auth/sso/saml/callback",
                data={"SAMLResponse": "data", "RelayState": "nonexistent-org-id"},
                follow_redirects=False,
            )
            assert response.status_code in (302, 307)
            location = response.headers.get("location", "")
            assert "error=sso_not_configured" in location or "error=org_not_found" in location


# ---------------------------------------------------------------------------
# Auth route: OIDC login with ValueError
# ---------------------------------------------------------------------------


class TestOidcLoginEdgeCases:
    @pytest.mark.asyncio
    async def test_oidc_login_with_config_error_redirects(self, async_client, sso_org_and_config):
        org, _config = sso_org_and_config

        with patch("app.routes.auth.initiate_oidc_login", new_callable=AsyncMock) as mock_init:
            mock_init.side_effect = ValueError("Discovery failed")
            response = await async_client.get(
                f"/api/auth/sso/oidc/login/{org.id}",
                follow_redirects=False,
            )
            assert response.status_code in (302, 307)
            assert "error=oidc_config_error" in response.headers.get("location", "")


# ---------------------------------------------------------------------------
# Auth route: OIDC callback with ValueError
# ---------------------------------------------------------------------------


class TestOidcCallbackEdgeCases:
    @pytest.mark.asyncio
    async def test_oidc_callback_with_process_error_redirects(self, async_client, sso_org_and_config):
        org, _config = sso_org_and_config
        fixed_token = "edge-token"
        state = f"{org.id}:{fixed_token}"

        with patch("app.routes.auth.secrets.token_urlsafe", return_value=fixed_token):
            with patch("app.routes.auth.initiate_oidc_login", new_callable=AsyncMock) as mock_init:
                mock_init.return_value = f"https://idp.example.com/auth?state={state}"
                login_resp = await async_client.get(
                    f"/api/auth/sso/oidc/login/{org.id}",
                    follow_redirects=False,
                )
            cookies = login_resp.cookies

            with patch("app.routes.auth.process_oidc_callback", new_callable=AsyncMock) as mock_proc:
                mock_proc.side_effect = ValueError("Token exchange failed")
                response = await async_client.get(
                    f"/api/auth/sso/oidc/callback?code=bad-code&state={state}",
                    cookies=dict(cookies),
                    follow_redirects=False,
                )
                assert response.status_code in (302, 307)
                assert "error=oidc_failed" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_oidc_callback_with_nonexistent_org_redirects(self, async_client, sso_org_and_config):
        org, _config = sso_org_and_config
        fixed_token = "edge-token-2"
        fake_org_id = "507f1f77bcf86cd799439011"
        state = f"{fake_org_id}:{fixed_token}"

        with patch("app.routes.auth.secrets.token_urlsafe", return_value=fixed_token):
            with patch("app.routes.auth.initiate_oidc_login", new_callable=AsyncMock) as mock_init:
                mock_init.return_value = f"https://idp.example.com/auth?state={state}"
                login_resp = await async_client.get(
                    f"/api/auth/sso/oidc/login/{org.id}",
                    follow_redirects=False,
                )
            cookies = login_resp.cookies

            with patch("app.routes.auth.process_oidc_callback", new_callable=AsyncMock) as mock_proc:
                mock_proc.return_value = SSOCallbackResult(email="x@sso-org.com", name="X")
                # Manually set session state to match
                response = await async_client.get(
                    f"/api/auth/sso/oidc/callback?code=code&state={state}",
                    cookies=dict(cookies),
                    follow_redirects=False,
                )
                assert response.status_code in (302, 307)
                location = response.headers.get("location", "")
                assert "error=" in location
