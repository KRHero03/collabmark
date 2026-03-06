"""Security tests: verify that all document-scoped endpoints reject unauthorized access.

Every test creates a document owned by one user, then attempts to access it as
a different user who has NO permission.  The expected result is always 403.
"""

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.models.comment import Comment
from app.models.document import Document_
from app.models.user import User


def _cookies(user: User) -> dict[str, str]:
    return {"access_token": create_access_token(str(user.id))}


async def _make_user(gid: str, email: str, name: str) -> User:
    user = User(google_id=gid, email=email, name=name)
    await user.insert()
    return user


async def _make_doc(owner: User) -> Document_:
    doc = Document_(title="Private Doc", content="# Secret", owner_id=str(owner.id))
    await doc.insert()
    return doc


async def _make_comment(doc: Document_, author: User) -> Comment:
    comment = Comment(
        document_id=str(doc.id),
        author_id=str(author.id),
        author_name=author.name or "Author",
        content="Owner comment",
        anchor_from=0,
        anchor_to=5,
        quoted_text="# Sec",
    )
    await comment.insert()
    return comment


# ---- Unauthenticated access (no JWT cookie at all) ----

class TestUnauthenticatedAccess:
    """All protected endpoints must return 401 when no credentials are provided."""

    @pytest.mark.asyncio
    async def test_versions_list_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.get("/api/documents/000000000000000000000000/versions")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_versions_get_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.get("/api/documents/000000000000000000000000/versions/1")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_versions_create_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/documents/000000000000000000000000/versions",
            json={"content": "nope"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_comments_list_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.get("/api/documents/000000000000000000000000/comments")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_comments_create_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/documents/000000000000000000000000/comments",
            json={"content": "nope"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_comment_reply_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/comments/000000000000000000000000/reply",
            json={"content": "nope"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_comment_resolve_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.post("/api/comments/000000000000000000000000/resolve")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_comment_reanchor_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.patch(
            "/api/comments/000000000000000000000000/reanchor",
            json={"anchor_from": 0, "anchor_to": 5},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_comment_orphan_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.patch("/api/comments/000000000000000000000000/orphan")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_comment_delete_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.delete("/api/comments/000000000000000000000000")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_record_view_unauthenticated(self, async_client: AsyncClient):
        resp = await async_client.post("/api/documents/000000000000000000000000/view")
        assert resp.status_code == 401


# ---- Unauthorized (foreign user) access on VERSIONS ----

class TestVersionsUnauthorizedAccess:
    """A user with no access to a document must get 403 on all version endpoints."""

    @pytest.mark.asyncio
    async def test_create_version_forbidden(
        self, async_client: AsyncClient, test_user: User
    ):
        stranger = await _make_user("stranger-v1", "stranger-v@test.com", "Stranger")
        doc = await _make_doc(test_user)

        async_client.cookies.update(_cookies(stranger))
        resp = await async_client.post(
            f"/api/documents/{doc.id}/versions",
            json={"content": "hacked content"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_versions_forbidden(
        self, async_client: AsyncClient, test_user: User
    ):
        stranger = await _make_user("stranger-v2", "stranger-vl@test.com", "Stranger")
        doc = await _make_doc(test_user)

        async_client.cookies.update(_cookies(stranger))
        resp = await async_client.get(f"/api/documents/{doc.id}/versions")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_get_version_forbidden(
        self, async_client: AsyncClient, test_user: User
    ):
        stranger = await _make_user("stranger-v3", "stranger-vg@test.com", "Stranger")
        doc = await _make_doc(test_user)

        # Owner creates a version first
        async_client.cookies.update(_cookies(test_user))
        await async_client.post(
            f"/api/documents/{doc.id}/versions",
            json={"content": "secret version"},
        )

        # Stranger tries to read it
        async_client.cookies.update(_cookies(stranger))
        resp = await async_client.get(f"/api/documents/{doc.id}/versions/1")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_owner_can_access_versions(
        self, async_client: AsyncClient, test_user: User
    ):
        """Sanity check: the document owner CAN access all version endpoints."""
        doc = await _make_doc(test_user)
        async_client.cookies.update(_cookies(test_user))

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/versions",
            json={"content": "owner version"},
        )
        assert create_resp.status_code == 201

        list_resp = await async_client.get(f"/api/documents/{doc.id}/versions")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        get_resp = await async_client.get(f"/api/documents/{doc.id}/versions/1")
        assert get_resp.status_code == 200
        assert get_resp.json()["content"] == "owner version"


# ---- Unauthorized (foreign user) access on COMMENTS ----

class TestCommentsUnauthorizedAccess:
    """A user with no access to a document must get 403 on all comment endpoints."""

    @pytest.mark.asyncio
    async def test_create_comment_forbidden(
        self, async_client: AsyncClient, test_user: User
    ):
        stranger = await _make_user("stranger-c1", "stranger-c1@test.com", "Stranger")
        doc = await _make_doc(test_user)

        async_client.cookies.update(_cookies(stranger))
        resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={"content": "unauthorized comment"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_comments_forbidden(
        self, async_client: AsyncClient, test_user: User
    ):
        stranger = await _make_user("stranger-c2", "stranger-c2@test.com", "Stranger")
        doc = await _make_doc(test_user)

        async_client.cookies.update(_cookies(stranger))
        resp = await async_client.get(f"/api/documents/{doc.id}/comments")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_reply_to_comment_forbidden(
        self, async_client: AsyncClient, test_user: User
    ):
        stranger = await _make_user("stranger-c3", "stranger-c3@test.com", "Stranger")
        doc = await _make_doc(test_user)
        comment = await _make_comment(doc, test_user)

        async_client.cookies.update(_cookies(stranger))
        resp = await async_client.post(
            f"/api/comments/{comment.id}/reply",
            json={"content": "unauthorized reply"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_resolve_comment_forbidden(
        self, async_client: AsyncClient, test_user: User
    ):
        stranger = await _make_user("stranger-c4", "stranger-c4@test.com", "Stranger")
        doc = await _make_doc(test_user)
        comment = await _make_comment(doc, test_user)

        async_client.cookies.update(_cookies(stranger))
        resp = await async_client.post(f"/api/comments/{comment.id}/resolve")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_reanchor_comment_forbidden(
        self, async_client: AsyncClient, test_user: User
    ):
        stranger = await _make_user("stranger-c5", "stranger-c5@test.com", "Stranger")
        doc = await _make_doc(test_user)
        comment = await _make_comment(doc, test_user)

        async_client.cookies.update(_cookies(stranger))
        resp = await async_client.patch(
            f"/api/comments/{comment.id}/reanchor",
            json={"anchor_from": 0, "anchor_to": 1},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_orphan_comment_forbidden(
        self, async_client: AsyncClient, test_user: User
    ):
        stranger = await _make_user("stranger-c6", "stranger-c6@test.com", "Stranger")
        doc = await _make_doc(test_user)
        comment = await _make_comment(doc, test_user)

        async_client.cookies.update(_cookies(stranger))
        resp = await async_client.patch(f"/api/comments/{comment.id}/orphan")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_comment_forbidden_no_doc_access(
        self, async_client: AsyncClient, test_user: User
    ):
        """Even the comment author can't delete if they lost document access."""
        stranger = await _make_user("stranger-c7", "stranger-c7@test.com", "Stranger")
        doc = await _make_doc(test_user)
        # Stranger somehow authored a comment (e.g. had access previously)
        comment = await _make_comment(doc, stranger)

        async_client.cookies.update(_cookies(stranger))
        resp = await async_client.delete(f"/api/comments/{comment.id}")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_owner_can_access_comments(
        self, async_client: AsyncClient, test_user: User
    ):
        """Sanity check: the document owner CAN use all comment endpoints."""
        doc = await _make_doc(test_user)
        async_client.cookies.update(_cookies(test_user))

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={"content": "owner comment"},
        )
        assert create_resp.status_code == 201
        comment_id = create_resp.json()["id"]

        list_resp = await async_client.get(f"/api/documents/{doc.id}/comments")
        assert list_resp.status_code == 200

        reply_resp = await async_client.post(
            f"/api/comments/{comment_id}/reply",
            json={"content": "owner reply"},
        )
        assert reply_resp.status_code == 201

        resolve_resp = await async_client.post(f"/api/comments/{comment_id}/resolve")
        assert resolve_resp.status_code == 200

        delete_resp = await async_client.delete(f"/api/comments/{comment_id}")
        assert delete_resp.status_code == 204


# ---- Unauthorized access on RECORD VIEW ----

class TestRecordViewUnauthorizedAccess:
    """Recording a document view requires VIEW access."""

    @pytest.mark.asyncio
    async def test_record_view_forbidden(
        self, async_client: AsyncClient, test_user: User
    ):
        stranger = await _make_user("stranger-rv", "stranger-rv@test.com", "Stranger")
        doc = await _make_doc(test_user)

        async_client.cookies.update(_cookies(stranger))
        resp = await async_client.post(f"/api/documents/{doc.id}/view")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_record_view_nonexistent_doc(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_cookies(test_user))
        resp = await async_client.post("/api/documents/000000000000000000000000/view")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_owner_can_record_view(
        self, async_client: AsyncClient, test_user: User
    ):
        """Sanity check: the document owner CAN record views."""
        doc = await _make_doc(test_user)
        async_client.cookies.update(_cookies(test_user))
        resp = await async_client.post(f"/api/documents/{doc.id}/view")
        assert resp.status_code == 204


# ---- Cross-endpoint enumeration: wrong doc_id for versions/comments ----

class TestCrossDocumentEnumeration:
    """Ensure a user cannot use version/comment endpoints with a doc they don't own."""

    @pytest.mark.asyncio
    async def test_version_create_on_other_users_doc(
        self, async_client: AsyncClient, test_user: User
    ):
        other = await _make_user("other-enum1", "other-e1@test.com", "Other")
        doc = await _make_doc(test_user)

        async_client.cookies.update(_cookies(other))
        resp = await async_client.post(
            f"/api/documents/{doc.id}/versions",
            json={"content": "injected version"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_comment_create_on_other_users_doc(
        self, async_client: AsyncClient, test_user: User
    ):
        other = await _make_user("other-enum2", "other-e2@test.com", "Other")
        doc = await _make_doc(test_user)

        async_client.cookies.update(_cookies(other))
        resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={"content": "injected comment"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_nonexistent_doc_returns_404_for_versions(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_cookies(test_user))
        resp = await async_client.get("/api/documents/000000000000000000000000/versions")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_nonexistent_doc_returns_404_for_comments(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_cookies(test_user))
        resp = await async_client.get("/api/documents/000000000000000000000000/comments")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_malformed_doc_id_returns_404(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_cookies(test_user))
        resp = await async_client.get("/api/documents/not-a-valid-id/versions")
        assert resp.status_code == 404
