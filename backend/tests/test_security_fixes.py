"""Tests for security vulnerability fixes.

Covers: C1 (media auth), C2 (email XSS), C3 (folder org boundary),
H2 (SVG upload), H4 (security headers), H5 (CLI auth code),
M1 (OIDC SSRF), M2 (timing-safe compare), M3 (avatar URL validation),
M4 (WS message size), M5 (CORS), M6 (session secret), L2 (default creds),
L5 (Content-Disposition).
"""

import html as html_mod
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.auth.jwt import create_access_token
from app.models.folder import Folder
from app.models.organization import Organization
from app.models.user import User, UserUpdate
from app.services.channels.templates import (
    render_comment_added,
    render_document_shared,
    render_folder_shared,
)
from fastapi import HTTPException
from httpx import AsyncClient


def _cookies(user: User) -> dict[str, str]:
    return {"access_token": create_access_token(str(user.id))}


async def _make_user(email: str, org_id: str | None = None) -> User:
    user = User(email=email, name=email.split("@")[0], org_id=org_id)
    await user.insert()
    return user


async def _make_org(slug: str) -> Organization:
    org = Organization(name=f"Org {slug}", slug=slug, verified_domains=[f"{slug}.com"])
    await org.insert()
    return org


async def _make_folder(owner: User, ga: str = "restricted", org_id: str | None = None) -> Folder:
    folder = Folder(
        name="Test Folder",
        owner_id=str(owner.id),
        owner_name=owner.name,
        owner_email=owner.email,
        general_access=ga,
        org_id=org_id,
    )
    await folder.insert()
    return folder


# ---------------------------------------------------------------------------
# C3: Folder org boundary bypass
# ---------------------------------------------------------------------------


class TestFolderOrgBoundaryFix:
    """_assert_folder_access must enforce org boundary on general_access."""

    @pytest.mark.asyncio
    async def test_cross_org_anyone_view_denied(self):
        from app.models.share_link import Permission
        from app.services.folder_service import _assert_folder_access

        org_a = await _make_org("c3-orgA")
        org_b = await _make_org("c3-orgB")
        owner = await _make_user("own@c3a.com", org_id=str(org_a.id))
        outsider = await _make_user("spy@c3b.com", org_id=str(org_b.id))
        folder = await _make_folder(owner, ga="anyone_view", org_id=str(org_a.id))

        with pytest.raises(HTTPException) as exc_info:
            await _assert_folder_access(folder, outsider, Permission.VIEW)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_cross_org_anyone_edit_denied(self):
        from app.models.share_link import Permission
        from app.services.folder_service import _assert_folder_access

        org_a = await _make_org("c3-orgC")
        org_b = await _make_org("c3-orgD")
        owner = await _make_user("own@c3c.com", org_id=str(org_a.id))
        outsider = await _make_user("spy@c3d.com", org_id=str(org_b.id))
        folder = await _make_folder(owner, ga="anyone_edit", org_id=str(org_a.id))

        with pytest.raises(HTTPException) as exc_info:
            await _assert_folder_access(folder, outsider, Permission.EDIT)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_same_org_anyone_view_allowed(self):
        from app.models.share_link import Permission
        from app.services.folder_service import _assert_folder_access

        org = await _make_org("c3-orgE")
        owner = await _make_user("own@c3e.com", org_id=str(org.id))
        peer = await _make_user("peer@c3e.com", org_id=str(org.id))
        folder = await _make_folder(owner, ga="anyone_view", org_id=str(org.id))

        await _assert_folder_access(folder, peer, Permission.VIEW)


# ---------------------------------------------------------------------------
# C2: Email template HTML escaping
# ---------------------------------------------------------------------------


class TestEmailTemplateEscaping:
    def test_xss_in_shared_by_is_escaped(self):
        malicious = '<script>alert("xss")</script>'
        escaped = html_mod.escape(malicious, quote=True)
        _subject, body = render_document_shared(
            recipient_name="Alice",
            shared_by=malicious,
            document_title="Test Doc",
            document_id="abc123",
            permission="edit",
        )
        assert f"<strong>{malicious}</strong>" not in body
        assert f"<strong>{escaped}</strong>" in body

    def test_xss_in_document_title_is_escaped(self):
        malicious = '<img src=x onerror="steal()">'
        escaped = html_mod.escape(malicious, quote=True)
        _subject, body = render_document_shared(
            recipient_name="Alice",
            shared_by="Bob",
            document_title=malicious,
            document_id="abc123",
            permission="view",
        )
        assert escaped in body

    def test_xss_in_folder_name_is_escaped(self):
        malicious = '"><script>alert(1)</script>'
        escaped = html_mod.escape(malicious, quote=True)
        _subject, body = render_folder_shared(
            recipient_name="Alice",
            shared_by="Bob",
            folder_name=malicious,
            folder_id="folder123",
            permission="edit",
        )
        assert escaped in body
        assert f"&#128193; {malicious}" not in body

    def test_xss_in_comment_preview_is_escaped(self):
        malicious = '<iframe src="evil.com"></iframe>'
        escaped = html_mod.escape(malicious, quote=True)
        _subject, body = render_comment_added(
            recipient_name="Alice",
            commenter="Eve",
            document_title="Doc",
            document_id="doc123",
            comment_preview=malicious,
        )
        assert escaped in body

    def test_xss_in_recipient_name_is_escaped(self):
        malicious = '<b onmouseover="hack()">User</b>'
        escaped = html_mod.escape(malicious, quote=True)
        _subject, body = render_document_shared(
            recipient_name=malicious,
            shared_by="Bob",
            document_title="Doc",
            document_id="abc",
            permission="view",
        )
        assert f"Hi {malicious}" not in body
        assert f"Hi {escaped}" in body


# ---------------------------------------------------------------------------
# H4: Security headers
# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    @pytest.mark.asyncio
    async def test_api_response_has_security_headers(self, async_client: AsyncClient):
        resp = await async_client.get("/api/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "camera=()" in resp.headers.get("Permissions-Policy", "")

    @pytest.mark.asyncio
    async def test_api_response_has_no_store(self, async_client: AsyncClient):
        resp = await async_client.get("/api/health")
        assert resp.headers.get("Cache-Control") == "no-store"


# ---------------------------------------------------------------------------
# C1: Media endpoint requires authentication
# ---------------------------------------------------------------------------


class TestMediaAuth:
    @pytest.mark.asyncio
    async def test_media_unauthenticated_returns_401(self, async_client: AsyncClient):
        resp = await async_client.get("/media/documents/abc/test.png")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_media_invalid_token_returns_401(self, async_client: AsyncClient):
        async_client.cookies.update({"access_token": "invalid-token"})
        resp = await async_client.get("/media/documents/abc/test.png")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# L5: Content-Disposition on non-image files
# ---------------------------------------------------------------------------


class TestContentDisposition:
    @pytest.mark.asyncio
    async def test_pdf_served_as_attachment(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_cookies(test_user))
        mock_body = MagicMock()
        mock_body.read.return_value = b"%PDF-1.4 fake content"
        mock_obj = {"Body": mock_body, "ContentType": "application/pdf"}
        with patch("app.main._get_s3_client") as mock_client:
            mock_client.return_value.get_object.return_value = mock_obj
            resp = await async_client.get("/media/documents/abc/report.pdf")
        assert resp.status_code == 200
        assert "attachment" in resp.headers.get("Content-Disposition", "")

    @pytest.mark.asyncio
    async def test_image_served_inline(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_cookies(test_user))
        mock_body = MagicMock()
        mock_body.read.return_value = b"\x89PNG\r\n fake"
        mock_obj = {"Body": mock_body, "ContentType": "image/png"}
        with patch("app.main._get_s3_client") as mock_client:
            mock_client.return_value.get_object.return_value = mock_obj
            resp = await async_client.get("/media/documents/abc/image.png")
        assert resp.status_code == 200
        assert "Content-Disposition" not in resp.headers


# ---------------------------------------------------------------------------
# H2: SVG upload disallowed for org logos
# ---------------------------------------------------------------------------


class TestSvgUploadBlocked:
    @pytest.mark.asyncio
    async def test_svg_logo_upload_rejected(self):
        from app.services.org_service import ALLOWED_EXTENSIONS

        assert ".svg" not in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# M3: Avatar URL validation
# ---------------------------------------------------------------------------


class TestAvatarUrlValidation:
    def test_https_url_accepted(self):
        update = UserUpdate(avatar_url="https://example.com/avatar.png")
        assert update.avatar_url == "https://example.com/avatar.png"

    def test_javascript_url_rejected(self):
        with pytest.raises(ValueError):
            UserUpdate(avatar_url="javascript:alert(1)")

    def test_data_url_rejected(self):
        with pytest.raises(ValueError):
            UserUpdate(avatar_url="data:text/html,<script>alert(1)</script>")

    def test_none_accepted(self):
        update = UserUpdate(avatar_url=None)
        assert update.avatar_url is None

    def test_empty_string_accepted(self):
        update = UserUpdate(avatar_url="")
        assert update.avatar_url == ""

    @pytest.mark.asyncio
    async def test_javascript_avatar_url_rejected_via_api(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_cookies(test_user))
        resp = await async_client.put("/api/users/me", json={"avatar_url": "javascript:alert(1)"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# M1: OIDC discovery URL SSRF protection
# ---------------------------------------------------------------------------


class TestOidcSsrfProtection:
    def test_localhost_rejected(self):
        from app.auth.sso_oidc import _validate_url_not_internal

        with pytest.raises(ValueError, match="non-public"):
            _validate_url_not_internal("https://localhost/.well-known/openid-configuration")

    def test_private_ip_rejected(self):
        from app.auth.sso_oidc import _validate_url_not_internal

        with pytest.raises(ValueError, match="non-public"):
            _validate_url_not_internal("https://192.168.1.1/.well-known/openid-configuration")

    def test_loopback_rejected(self):
        from app.auth.sso_oidc import _validate_url_not_internal

        with pytest.raises(ValueError, match="non-public"):
            _validate_url_not_internal("https://127.0.0.1/.well-known/openid-configuration")


# ---------------------------------------------------------------------------
# H5: CLI auth code exchange
# ---------------------------------------------------------------------------


class TestCliAuthCodeExchange:
    @pytest.mark.asyncio
    async def test_exchange_invalid_code_returns_401(self, async_client: AsyncClient):
        resp = await async_client.post("/api/auth/cli/exchange", json={"code": "invalid"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_exchange_valid_code_returns_token(self, async_client: AsyncClient, test_user: User):
        from app.routes.auth import _CLI_AUTH_CODES

        token = create_access_token(str(test_user.id))
        code = "test-code-123"
        _CLI_AUTH_CODES[code] = (token, time.monotonic())

        resp = await async_client.post("/api/auth/cli/exchange", json={"code": code})
        assert resp.status_code == 200
        assert resp.json()["token"] == token
        assert code not in _CLI_AUTH_CODES

    @pytest.mark.asyncio
    async def test_exchange_code_single_use(self, async_client: AsyncClient, test_user: User):
        from app.routes.auth import _CLI_AUTH_CODES

        token = create_access_token(str(test_user.id))
        code = "single-use-code"
        _CLI_AUTH_CODES[code] = (token, time.monotonic())

        resp1 = await async_client.post("/api/auth/cli/exchange", json={"code": code})
        assert resp1.status_code == 200

        resp2 = await async_client.post("/api/auth/cli/exchange", json={"code": code})
        assert resp2.status_code == 401

    @pytest.mark.asyncio
    async def test_exchange_expired_code_returns_401(self, async_client: AsyncClient, test_user: User):
        from app.routes.auth import _CLI_AUTH_CODES, _CLI_CODE_TTL

        token = create_access_token(str(test_user.id))
        code = "expired-code"
        _CLI_AUTH_CODES[code] = (token, time.monotonic() - _CLI_CODE_TTL - 10)

        resp = await async_client.post("/api/auth/cli/exchange", json={"code": code})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# M2: Timing-safe comparison (structural test)
# ---------------------------------------------------------------------------


class TestTimingSafeComparison:
    def test_api_key_module_uses_hmac(self):
        import app.auth.api_key as mod

        source = Path(mod.__file__).read_text()
        assert "hmac.compare_digest" in source

    def test_scim_auth_module_uses_hmac(self):
        import app.auth.scim_auth as mod

        source = Path(mod.__file__).read_text()
        assert "hmac.compare_digest" in source


# ---------------------------------------------------------------------------
# M4: WebSocket message size limit
# ---------------------------------------------------------------------------


class TestWsMessageSizeLimit:
    def test_max_ws_message_size_configured(self):
        from app.ws.handler import _MAX_WS_MESSAGE_SIZE

        assert _MAX_WS_MESSAGE_SIZE == 5 * 1024 * 1024


# ---------------------------------------------------------------------------
# M5: CORS restricts methods and headers
# ---------------------------------------------------------------------------


class TestCorsConfig:
    @pytest.mark.asyncio
    async def test_options_returns_restricted_methods(self, async_client: AsyncClient):
        resp = await async_client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        allowed_methods = resp.headers.get("access-control-allow-methods", "")
        assert "*" not in allowed_methods


# ---------------------------------------------------------------------------
# M6: Session secret key separation
# ---------------------------------------------------------------------------


class TestSessionSecretSeparation:
    def test_session_key_not_same_as_jwt_key(self):
        from app.config import settings

        assert settings.session_secret_key != settings.jwt_secret_key or settings.debug


# ---------------------------------------------------------------------------
# L2: Default credentials enforcement
# ---------------------------------------------------------------------------


class TestDefaultCredsEnforcement:
    def test_config_module_raises_on_default_secret_in_prod(self):
        source = Path(__file__).resolve().parent.parent.joinpath("app", "config.py").read_text()
        assert "RuntimeError" in source
        assert "JWT_SECRET_KEY must be changed" in source
