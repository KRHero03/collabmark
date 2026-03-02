"""Tests for comments: create, reply, list, resolve, reanchor, orphan, delete."""

import pytest
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.models.comment import Comment
from app.models.document import Document_
from app.models.user import User


def _auth_cookies(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"access_token": token}


async def _make_user(google_id: str, email: str, name: str) -> User:
    user = User(google_id=google_id, email=email, name=name)
    await user.insert()
    return user


async def _make_doc(owner: User) -> Document_:
    doc = Document_(title="Commentable Doc", content="# Content", owner_id=str(owner.id))
    await doc.insert()
    return doc


class TestCreateComment:
    @pytest.mark.asyncio
    async def test_create_doc_level_comment(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={"content": "Great document!"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "Great document!"
        assert data["author_name"] == "Test User"
        assert data["anchor_from"] is None
        assert data["is_resolved"] is False
        assert data["is_orphaned"] is False
        assert data["orphaned_at"] is None

    @pytest.mark.asyncio
    async def test_create_inline_comment(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={
                "content": "This section needs work",
                "anchor_from": 10,
                "anchor_to": 25,
                "quoted_text": "# Content here",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["anchor_from"] == 10
        assert data["anchor_to"] == 25
        assert data["quoted_text"] == "# Content here"

    @pytest.mark.asyncio
    async def test_create_inline_comment_with_relative_positions(
        self, async_client: AsyncClient, test_user: User
    ):
        """Verify that Yjs RelativePosition strings are stored and returned."""
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={
                "content": "Anchored with CRDT positions",
                "anchor_from": 5,
                "anchor_to": 15,
                "anchor_from_relative": "AQRZYW1wbGVfcmVsX3Bvcw==",
                "anchor_to_relative": "BQRZYW1wbGVfcmVsX3Bvcw==",
                "quoted_text": "some text",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["anchor_from"] == 5
        assert data["anchor_to"] == 15
        assert data["anchor_from_relative"] == "AQRZYW1wbGVfcmVsX3Bvcw=="
        assert data["anchor_to_relative"] == "BQRZYW1wbGVfcmVsX3Bvcw=="
        assert data["quoted_text"] == "some text"
        assert data["is_orphaned"] is False


class TestListComments:
    @pytest.mark.asyncio
    async def test_list_with_replies(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp1 = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={"content": "Top level comment"},
        )
        comment_id = resp1.json()["id"]

        await async_client.post(
            f"/api/comments/{comment_id}/reply",
            json={"content": "Reply to comment"},
        )

        resp = await async_client.get(f"/api/documents/{doc.id}/comments")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["content"] == "Top level comment"
        assert len(data[0]["replies"]) == 1
        assert data[0]["replies"][0]["content"] == "Reply to comment"

    @pytest.mark.asyncio
    async def test_empty_comments(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        resp = await async_client.get(f"/api/documents/{doc.id}/comments")
        assert resp.status_code == 200
        assert resp.json() == []


class TestReplyToComment:
    @pytest.mark.asyncio
    async def test_reply_creates_child(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        parent_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={"content": "Parent"},
        )
        parent_id = parent_resp.json()["id"]

        resp = await async_client.post(
            f"/api/comments/{parent_id}/reply",
            json={"content": "Child reply"},
        )
        assert resp.status_code == 201
        assert resp.json()["parent_id"] == parent_id

    @pytest.mark.asyncio
    async def test_cannot_reply_to_reply(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        parent_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={"content": "Parent"},
        )
        parent_id = parent_resp.json()["id"]

        reply_resp = await async_client.post(
            f"/api/comments/{parent_id}/reply",
            json={"content": "First reply"},
        )
        reply_id = reply_resp.json()["id"]

        nested_resp = await async_client.post(
            f"/api/comments/{reply_id}/reply",
            json={"content": "Nested reply"},
        )
        assert nested_resp.status_code == 400


class TestResolveComment:
    @pytest.mark.asyncio
    async def test_resolve_marks_resolved(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={"content": "To resolve"},
        )
        comment_id = create_resp.json()["id"]

        resp = await async_client.post(f"/api/comments/{comment_id}/resolve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_resolved"] is True
        assert data["resolved_by"] == str(test_user.id)
        assert data["resolved_at"] is not None


class TestReanchorComment:
    @pytest.mark.asyncio
    async def test_reanchor_updates_offsets(
        self, async_client: AsyncClient, test_user: User
    ):
        """Reanchoring an inline comment updates its absolute offsets."""
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={
                "content": "Needs reanchor",
                "anchor_from": 10,
                "anchor_to": 25,
                "quoted_text": "original text",
            },
        )
        assert create_resp.status_code == 201
        comment_id = create_resp.json()["id"]

        resp = await async_client.patch(
            f"/api/comments/{comment_id}/reanchor",
            json={"anchor_from": 15, "anchor_to": 30},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["anchor_from"] == 15
        assert data["anchor_to"] == 30
        assert data["quoted_text"] == "original text"

    @pytest.mark.asyncio
    async def test_reanchor_doc_level_comment_fails(
        self, async_client: AsyncClient, test_user: User
    ):
        """Reanchoring a doc-level comment (no anchor) returns 400."""
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={"content": "Doc level, no anchor"},
        )
        comment_id = create_resp.json()["id"]

        resp = await async_client.patch(
            f"/api/comments/{comment_id}/reanchor",
            json={"anchor_from": 0, "anchor_to": 5},
        )
        assert resp.status_code == 400
        assert "document-level" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_reanchor_nonexistent_comment(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.patch(
            "/api/comments/000000000000000000000000/reanchor",
            json={"anchor_from": 0, "anchor_to": 5},
        )
        assert resp.status_code == 404


class TestOrphanComment:
    @pytest.mark.asyncio
    async def test_orphan_marks_comment(
        self, async_client: AsyncClient, test_user: User
    ):
        """Orphaning sets is_orphaned=True and orphaned_at timestamp."""
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={
                "content": "Will be orphaned",
                "anchor_from": 0,
                "anchor_to": 10,
                "quoted_text": "# Content",
            },
        )
        comment_id = create_resp.json()["id"]

        resp = await async_client.patch(f"/api/comments/{comment_id}/orphan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_orphaned"] is True
        assert data["orphaned_at"] is not None
        assert data["anchor_from"] == 0
        assert data["anchor_to"] == 10
        assert data["quoted_text"] == "# Content"

    @pytest.mark.asyncio
    async def test_orphan_already_orphaned_fails(
        self, async_client: AsyncClient, test_user: User
    ):
        """Orphaning an already-orphaned comment returns 400."""
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={
                "content": "Double orphan",
                "anchor_from": 0,
                "anchor_to": 5,
                "quoted_text": "text",
            },
        )
        comment_id = create_resp.json()["id"]

        resp1 = await async_client.patch(f"/api/comments/{comment_id}/orphan")
        assert resp1.status_code == 200

        resp2 = await async_client.patch(f"/api/comments/{comment_id}/orphan")
        assert resp2.status_code == 400
        assert "already orphaned" in resp2.json()["detail"]

    @pytest.mark.asyncio
    async def test_orphaned_comment_still_listed(
        self, async_client: AsyncClient, test_user: User
    ):
        """Orphaned comments still appear in the list response."""
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={
                "content": "Orphan in list",
                "anchor_from": 0,
                "anchor_to": 5,
                "quoted_text": "text",
            },
        )
        comment_id = create_resp.json()["id"]
        await async_client.patch(f"/api/comments/{comment_id}/orphan")

        list_resp = await async_client.get(f"/api/documents/{doc.id}/comments")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert len(data) == 1
        assert data[0]["is_orphaned"] is True
        assert data[0]["quoted_text"] == "text"

    @pytest.mark.asyncio
    async def test_orphaned_comment_can_be_replied_to(
        self, async_client: AsyncClient, test_user: User
    ):
        """Users can still reply to orphaned comments."""
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={
                "content": "Orphan with reply",
                "anchor_from": 0,
                "anchor_to": 5,
                "quoted_text": "text",
            },
        )
        comment_id = create_resp.json()["id"]
        await async_client.patch(f"/api/comments/{comment_id}/orphan")

        reply_resp = await async_client.post(
            f"/api/comments/{comment_id}/reply",
            json={"content": "Reply to orphan"},
        )
        assert reply_resp.status_code == 201
        assert reply_resp.json()["content"] == "Reply to orphan"

    @pytest.mark.asyncio
    async def test_orphaned_comment_can_be_resolved(
        self, async_client: AsyncClient, test_user: User
    ):
        """Orphaned comments can still be resolved."""
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={
                "content": "Orphan to resolve",
                "anchor_from": 0,
                "anchor_to": 5,
                "quoted_text": "text",
            },
        )
        comment_id = create_resp.json()["id"]
        await async_client.patch(f"/api/comments/{comment_id}/orphan")

        resolve_resp = await async_client.post(
            f"/api/comments/{comment_id}/resolve"
        )
        assert resolve_resp.status_code == 200
        data = resolve_resp.json()
        assert data["is_orphaned"] is True
        assert data["is_resolved"] is True


class TestDeleteComment:
    @pytest.mark.asyncio
    async def test_author_can_delete(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={"content": "Deletable"},
        )
        comment_id = create_resp.json()["id"]

        resp = await async_client.delete(f"/api/comments/{comment_id}")
        assert resp.status_code == 204

        list_resp = await async_client.get(f"/api/documents/{doc.id}/comments")
        assert len(list_resp.json()) == 0

    @pytest.mark.asyncio
    async def test_non_author_cannot_delete(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={"content": "Protected"},
        )
        comment_id = create_resp.json()["id"]

        other = await _make_user("g-deleter", "deleter@test.com", "Deleter")
        async_client.cookies.update(_auth_cookies(other))

        resp = await async_client.delete(f"/api/comments/{comment_id}")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_cascades_to_replies(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        parent_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={"content": "Parent to delete"},
        )
        parent_id = parent_resp.json()["id"]

        await async_client.post(
            f"/api/comments/{parent_id}/reply",
            json={"content": "Reply 1"},
        )
        await async_client.post(
            f"/api/comments/{parent_id}/reply",
            json={"content": "Reply 2"},
        )

        resp = await async_client.delete(f"/api/comments/{parent_id}")
        assert resp.status_code == 204

        all_comments = await Comment.find(
            Comment.document_id == str(doc.id)
        ).to_list()
        assert len(all_comments) == 0


class TestCommentAnchorLifecycle:
    """End-to-end lifecycle: create inline → reanchor → orphan → still usable."""

    @pytest.mark.asyncio
    async def test_full_anchor_lifecycle(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))
        doc = await _make_doc(test_user)

        create_resp = await async_client.post(
            f"/api/documents/{doc.id}/comments",
            json={
                "content": "Lifecycle comment",
                "anchor_from": 0,
                "anchor_to": 9,
                "anchor_from_relative": "AQAAAA==",
                "anchor_to_relative": "BQAAAA==",
                "quoted_text": "# Content",
            },
        )
        assert create_resp.status_code == 201
        comment_id = create_resp.json()["id"]
        assert create_resp.json()["is_orphaned"] is False

        reanchor_resp = await async_client.patch(
            f"/api/comments/{comment_id}/reanchor",
            json={"anchor_from": 5, "anchor_to": 14},
        )
        assert reanchor_resp.status_code == 200
        assert reanchor_resp.json()["anchor_from"] == 5
        assert reanchor_resp.json()["anchor_to"] == 14
        assert reanchor_resp.json()["anchor_from_relative"] == "AQAAAA=="
        assert reanchor_resp.json()["quoted_text"] == "# Content"

        orphan_resp = await async_client.patch(
            f"/api/comments/{comment_id}/orphan"
        )
        assert orphan_resp.status_code == 200
        assert orphan_resp.json()["is_orphaned"] is True
        assert orphan_resp.json()["orphaned_at"] is not None

        reply_resp = await async_client.post(
            f"/api/comments/{comment_id}/reply",
            json={"content": "Still active thread"},
        )
        assert reply_resp.status_code == 201

        resolve_resp = await async_client.post(
            f"/api/comments/{comment_id}/resolve"
        )
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["is_resolved"] is True
        assert resolve_resp.json()["is_orphaned"] is True

        list_resp = await async_client.get(f"/api/documents/{doc.id}/comments")
        comments = list_resp.json()
        assert len(comments) == 1
        assert comments[0]["is_orphaned"] is True
        assert comments[0]["is_resolved"] is True
        assert len(comments[0]["replies"]) == 1
        assert comments[0]["replies"][0]["content"] == "Still active thread"
