"""Integration tests spanning multiple components, based on user stories.

These tests exercise cross-component flows end-to-end via the HTTP API,
mimicking real user actions. Each test class represents a user story.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.auth.jwt import create_access_token
from app.models.user import User


def _auth_cookies(user: User) -> dict[str, str]:
    """Create JWT auth cookies for the given user."""
    token = create_access_token(str(user.id))
    return {"access_token": token}


@pytest_asyncio.fixture
async def user_b() -> User:
    """Second test user for multi-user scenarios."""
    user = User(
        google_id="google-user-b-456",
        email="userb@example.com",
        name="User B",
        avatar_url="https://example.com/b.png",
    )
    await user.insert()
    return user


class TestDocumentLifecycle:
    """User Story 1: Full document lifecycle by owner.

    User creates document -> verifies in list -> edits title+content ->
    verifies changes persisted -> soft-deletes ->
    verifies gone from list -> restores -> verifies back in list.
    """

    @pytest.mark.asyncio
    async def test_full_owner_document_lifecycle(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))

        # Step 1: Create document
        create_resp = await async_client.post(
            "/api/documents",
            json={"title": "Integration Doc", "content": "# Initial Content"},
        )
        assert create_resp.status_code == 201
        doc = create_resp.json()
        doc_id = doc["id"]
        assert doc["title"] == "Integration Doc"
        assert doc["content"] == "# Initial Content"
        assert doc["owner_id"] == str(test_user.id)
        assert doc["is_deleted"] is False

        # Step 2: Verify document appears in list
        list_resp = await async_client.get("/api/documents")
        assert list_resp.status_code == 200
        docs = list_resp.json()
        assert len(docs) == 1
        assert docs[0]["id"] == doc_id
        assert docs[0]["title"] == "Integration Doc"

        # Step 3: Edit title and content
        update_resp = await async_client.put(
            f"/api/documents/{doc_id}",
            json={"title": "Updated Title", "content": "## Updated Content"},
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["title"] == "Updated Title"
        assert updated["content"] == "## Updated Content"

        # Step 4: Verify changes persisted via GET
        get_resp = await async_client.get(f"/api/documents/{doc_id}")
        assert get_resp.status_code == 200
        persisted = get_resp.json()
        assert persisted["title"] == "Updated Title"
        assert persisted["content"] == "## Updated Content"

        # Step 5: Soft-delete
        del_resp = await async_client.delete(f"/api/documents/{doc_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["is_deleted"] is True

        # Step 7: Verify gone from default list
        list_after_del = await async_client.get("/api/documents")
        assert list_after_del.status_code == 200
        assert len(list_after_del.json()) == 0

        # Step 8: Restore document
        restore_resp = await async_client.post(
            f"/api/documents/{doc_id}/restore"
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["is_deleted"] is False

        # Step 9: Verify back in list
        list_after_restore = await async_client.get("/api/documents")
        assert list_after_restore.status_code == 200
        restored_docs = list_after_restore.json()
        assert len(restored_docs) == 1
        assert restored_docs[0]["id"] == doc_id
        assert restored_docs[0]["title"] == "Updated Title"


class TestAgentApiKeyCrud:
    """User Story 2: Agent uses API keys for programmatic CRUD.

    User creates API key -> agent uses key to create document -> agent reads
    document -> agent updates content -> agent creates another document ->
    agent lists documents (sees both) -> agent deletes a document -> agent
    verifies list updated -> agent reads content field.
    """

    @pytest.mark.asyncio
    async def test_agent_crud_via_api_key(
        self, async_client: AsyncClient, test_user: User
    ):
        # Step 1: User creates API key via JWT auth
        async_client.cookies.update(_auth_cookies(test_user))
        key_resp = await async_client.post(
            "/api/keys", json={"name": "Agent Key"}
        )
        assert key_resp.status_code == 201
        raw_key = key_resp.json()["raw_key"]
        assert raw_key.startswith("cm_")
        async_client.cookies.clear()

        # From now on, agent authenticates via X-API-Key header
        agent_headers = {"X-API-Key": raw_key}

        # Step 2: Agent creates a document
        create_resp = await async_client.post(
            "/api/documents",
            json={
                "title": "Agent Context File",
                "content": "# Agent Notes\n\nThis is stored context.",
            },
            headers=agent_headers,
        )
        assert create_resp.status_code == 201
        doc1 = create_resp.json()
        doc1_id = doc1["id"]
        assert doc1["title"] == "Agent Context File"
        assert doc1["owner_id"] == str(test_user.id)

        # Step 3: Agent reads the document
        get_resp = await async_client.get(
            f"/api/documents/{doc1_id}", headers=agent_headers
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["content"] == "# Agent Notes\n\nThis is stored context."

        # Step 4: Agent updates content
        update_resp = await async_client.put(
            f"/api/documents/{doc1_id}",
            json={"content": "# Agent Notes\n\nUpdated context with new findings."},
            headers=agent_headers,
        )
        assert update_resp.status_code == 200
        assert "Updated context with new findings" in update_resp.json()["content"]

        # Step 5: Agent creates another document
        create2_resp = await async_client.post(
            "/api/documents",
            json={"title": "Agent Summary", "content": "## Summary\n\nKey points."},
            headers=agent_headers,
        )
        assert create2_resp.status_code == 201
        doc2_id = create2_resp.json()["id"]

        # Step 6: Agent lists documents -- sees both
        list_resp = await async_client.get(
            "/api/documents", headers=agent_headers
        )
        assert list_resp.status_code == 200
        docs = list_resp.json()
        assert len(docs) == 2
        doc_ids = {d["id"] for d in docs}
        assert doc1_id in doc_ids
        assert doc2_id in doc_ids

        # Step 7: Agent deletes one document
        del_resp = await async_client.delete(
            f"/api/documents/{doc2_id}", headers=agent_headers
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["is_deleted"] is True

        # Step 8: Agent verifies list updated (only 1 active doc)
        list_after = await async_client.get(
            "/api/documents", headers=agent_headers
        )
        assert list_after.status_code == 200
        active_docs = list_after.json()
        assert len(active_docs) == 1
        assert active_docs[0]["id"] == doc1_id

        # Step 9: Agent reads specific content
        final_get = await async_client.get(
            f"/api/documents/{doc1_id}", headers=agent_headers
        )
        assert final_get.status_code == 200
        assert final_get.json()["title"] == "Agent Context File"
        assert "Updated context with new findings" in final_get.json()["content"]


class TestSharingWorkflow:
    """User Story 3: Sharing workflow between two users.

    Owner creates doc -> adds User B as VIEW collaborator -> User B can read ->
    User B cannot update (403) -> owner upgrades to EDIT -> User B can update ->
    owner sees doc in list, User B sees in 'shared with me'.
    """

    @pytest.mark.asyncio
    async def test_sharing_view_then_edit_upgrade(
        self, async_client: AsyncClient, test_user: User, user_b: User
    ):
        # Owner creates document
        async_client.cookies.update(_auth_cookies(test_user))
        create_resp = await async_client.post(
            "/api/documents",
            json={"title": "Shared Doc", "content": "# Shared Content"},
        )
        assert create_resp.status_code == 201
        doc_id = create_resp.json()["id"]

        # Owner adds User B as VIEW collaborator
        collab_resp = await async_client.post(
            f"/api/documents/{doc_id}/collaborators",
            json={"email": "userb@example.com", "permission": "view"},
        )
        assert collab_resp.status_code == 201
        assert collab_resp.json()["permission"] == "view"

        # User B can READ the document
        async_client.cookies.update(_auth_cookies(user_b))
        read_resp = await async_client.get(f"/api/documents/{doc_id}")
        assert read_resp.status_code == 200
        assert read_resp.json()["title"] == "Shared Doc"
        assert read_resp.json()["content"] == "# Shared Content"

        # User B CANNOT UPDATE (view-only -> 403)
        update_resp = await async_client.put(
            f"/api/documents/{doc_id}",
            json={"content": "# Hacked Content"},
        )
        assert update_resp.status_code == 403

        # Owner upgrades User B to EDIT (re-add with edit)
        async_client.cookies.update(_auth_cookies(test_user))
        upgrade_resp = await async_client.post(
            f"/api/documents/{doc_id}/collaborators",
            json={"email": "userb@example.com", "permission": "edit"},
        )
        assert upgrade_resp.status_code == 201
        assert upgrade_resp.json()["permission"] == "edit"

        # User B can now UPDATE
        async_client.cookies.update(_auth_cookies(user_b))
        update_ok = await async_client.put(
            f"/api/documents/{doc_id}",
            json={"content": "# Collaboratively Edited"},
        )
        assert update_ok.status_code == 200
        assert update_ok.json()["content"] == "# Collaboratively Edited"

        # Owner can still see document in their list
        async_client.cookies.update(_auth_cookies(test_user))
        owner_list = await async_client.get("/api/documents")
        assert owner_list.status_code == 200
        assert len(owner_list.json()) == 1
        assert owner_list.json()[0]["id"] == doc_id

        # User B sees document in 'shared with me'
        async_client.cookies.update(_auth_cookies(user_b))
        shared_list = await async_client.get("/api/documents/shared")
        assert shared_list.status_code == 200
        shared_docs = shared_list.json()
        assert len(shared_docs) == 1
        assert shared_docs[0]["id"] == doc_id
        assert shared_docs[0]["title"] == "Shared Doc"
        assert shared_docs[0]["permission"] == "edit"


class TestVersionHistory:
    """User Story 4: Version history with auto-versioning.

    User creates document -> updates content 3 times (each triggers auto-version)
    -> list versions shows 3 entries in descending order -> fetch version 1
    shows original content -> fetch version 3 shows latest -> verify author
    attribution on each version.
    """

    @pytest.mark.asyncio
    async def test_version_history_auto_snapshot(
        self, async_client: AsyncClient, test_user: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))

        # Create document
        create_resp = await async_client.post(
            "/api/documents",
            json={"title": "Versioned Doc", "content": "# Version 0"},
        )
        assert create_resp.status_code == 201
        doc_id = create_resp.json()["id"]

        # Update content 3 times (each triggers auto-version)
        contents = [
            "# Version 1 - First Edit",
            "# Version 2 - Second Edit",
            "# Version 3 - Third Edit",
        ]
        for content in contents:
            resp = await async_client.put(
                f"/api/documents/{doc_id}",
                json={"content": content},
            )
            assert resp.status_code == 200

        # List versions -- should have 3 entries, newest first
        versions_resp = await async_client.get(
            f"/api/documents/{doc_id}/versions"
        )
        assert versions_resp.status_code == 200
        versions = versions_resp.json()
        assert len(versions) == 3
        assert versions[0]["version_number"] == 3
        assert versions[1]["version_number"] == 2
        assert versions[2]["version_number"] == 1

        # All versions attributed to test_user
        for v in versions:
            assert v["author_name"] == "Test User"
            assert v["author_id"] == str(test_user.id)

        # Fetch version 1 -- shows first edit content
        v1_resp = await async_client.get(
            f"/api/documents/{doc_id}/versions/1"
        )
        assert v1_resp.status_code == 200
        assert v1_resp.json()["content"] == "# Version 1 - First Edit"
        assert v1_resp.json()["version_number"] == 1

        # Fetch version 3 -- shows latest content
        v3_resp = await async_client.get(
            f"/api/documents/{doc_id}/versions/3"
        )
        assert v3_resp.status_code == 200
        assert v3_resp.json()["content"] == "# Version 3 - Third Edit"
        assert v3_resp.json()["version_number"] == 3

        # Current document has latest content
        doc_resp = await async_client.get(f"/api/documents/{doc_id}")
        assert doc_resp.status_code == 200
        assert doc_resp.json()["content"] == "# Version 3 - Third Edit"


class TestCommentsWorkflow:
    """User Story 5: Comments workflow with replies, resolution, deletion.

    User A creates doc -> User A adds doc-level comment -> User A adds inline
    comment with anchor and quoted text -> User B (shared EDIT) replies to
    comment -> User A resolves comment -> User A lists comments (sees resolved
    status, reply nested) -> User A deletes comment (replies cascade).
    """

    @pytest.mark.asyncio
    async def test_comments_full_workflow(
        self, async_client: AsyncClient, test_user: User, user_b: User
    ):
        # User A creates document
        async_client.cookies.update(_auth_cookies(test_user))
        create_resp = await async_client.post(
            "/api/documents",
            json={
                "title": "Commented Doc",
                "content": "# Hello\n\nThis is some text to comment on.",
            },
        )
        assert create_resp.status_code == 201
        doc_id = create_resp.json()["id"]

        # Share with User B (EDIT access) via collaborator API
        collab_resp = await async_client.post(
            f"/api/documents/{doc_id}/collaborators",
            json={"email": "userb@example.com", "permission": "edit"},
        )
        assert collab_resp.status_code == 201

        # User A adds a doc-level comment
        async_client.cookies.update(_auth_cookies(test_user))
        doc_comment_resp = await async_client.post(
            f"/api/documents/{doc_id}/comments",
            json={"content": "This document needs more detail."},
        )
        assert doc_comment_resp.status_code == 201
        doc_comment = doc_comment_resp.json()
        doc_comment_id = doc_comment["id"]
        assert doc_comment["content"] == "This document needs more detail."
        assert doc_comment["author_name"] == "Test User"
        assert doc_comment["anchor_from"] is None
        assert doc_comment["anchor_to"] is None

        # User A adds an inline comment with anchor positions and quoted text
        inline_comment_resp = await async_client.post(
            f"/api/documents/{doc_id}/comments",
            json={
                "content": "Consider rephrasing this section.",
                "anchor_from": 10,
                "anchor_to": 25,
                "quoted_text": "some text to com",
            },
        )
        assert inline_comment_resp.status_code == 201
        inline_comment = inline_comment_resp.json()
        inline_comment_id = inline_comment["id"]
        assert inline_comment["anchor_from"] == 10
        assert inline_comment["anchor_to"] == 25
        assert inline_comment["quoted_text"] == "some text to com"

        # User B replies to the doc-level comment
        async_client.cookies.update(_auth_cookies(user_b))
        reply_resp = await async_client.post(
            f"/api/comments/{doc_comment_id}/reply",
            json={"content": "I agree, let me expand on it."},
        )
        assert reply_resp.status_code == 201
        reply = reply_resp.json()
        assert reply["content"] == "I agree, let me expand on it."
        assert reply["author_name"] == "User B"
        assert reply["parent_id"] == doc_comment_id

        # User A resolves the doc-level comment
        async_client.cookies.update(_auth_cookies(test_user))
        resolve_resp = await async_client.post(
            f"/api/comments/{doc_comment_id}/resolve"
        )
        assert resolve_resp.status_code == 200
        resolved = resolve_resp.json()
        assert resolved["is_resolved"] is True

        # List comments -- doc-level comment is resolved with reply nested
        list_resp = await async_client.get(
            f"/api/documents/{doc_id}/comments"
        )
        assert list_resp.status_code == 200
        comments = list_resp.json()
        assert len(comments) == 2  # 2 top-level comments

        resolved_comment = next(c for c in comments if c["id"] == doc_comment_id)
        assert resolved_comment["is_resolved"] is True
        assert len(resolved_comment["replies"]) == 1
        assert resolved_comment["replies"][0]["content"] == "I agree, let me expand on it."

        inline = next(c for c in comments if c["id"] == inline_comment_id)
        assert inline["anchor_from"] == 10
        assert inline["is_resolved"] is False

        # User A deletes the doc-level comment (reply cascades)
        del_resp = await async_client.delete(
            f"/api/comments/{doc_comment_id}"
        )
        assert del_resp.status_code == 204

        # Verify only inline comment remains
        list_after = await async_client.get(
            f"/api/documents/{doc_id}/comments"
        )
        assert list_after.status_code == 200
        remaining = list_after.json()
        assert len(remaining) == 1
        assert remaining[0]["id"] == inline_comment_id


class TestMultiAgentParallel:
    """User Story 6: Two API keys managing documents in parallel.

    Two API keys for same user -> Agent A creates doc -> Agent B reads it ->
    Agent B updates -> Agent A reads updated content -> both list the doc ->
    Agent A creates share link -> Agent B verifies shared doc.
    """

    @pytest.mark.asyncio
    async def test_multi_agent_parallel_management(
        self, async_client: AsyncClient, test_user: User, user_b: User
    ):
        # Create two API keys for the same user
        async_client.cookies.update(_auth_cookies(test_user))
        key_a_resp = await async_client.post(
            "/api/keys", json={"name": "Agent A Key"}
        )
        assert key_a_resp.status_code == 201
        key_a = key_a_resp.json()["raw_key"]

        key_b_resp = await async_client.post(
            "/api/keys", json={"name": "Agent B Key"}
        )
        assert key_b_resp.status_code == 201
        key_b = key_b_resp.json()["raw_key"]
        async_client.cookies.clear()

        headers_a = {"X-API-Key": key_a}
        headers_b = {"X-API-Key": key_b}

        # Agent A creates a document
        create_resp = await async_client.post(
            "/api/documents",
            json={"title": "Multi-Agent Doc", "content": "# Initial"},
            headers=headers_a,
        )
        assert create_resp.status_code == 201
        doc_id = create_resp.json()["id"]

        # Agent B reads it
        read_resp = await async_client.get(
            f"/api/documents/{doc_id}", headers=headers_b
        )
        assert read_resp.status_code == 200
        assert read_resp.json()["content"] == "# Initial"

        # Agent B updates it
        update_resp = await async_client.put(
            f"/api/documents/{doc_id}",
            json={"content": "# Modified by Agent B"},
            headers=headers_b,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["content"] == "# Modified by Agent B"

        # Agent A reads updated content
        read_updated = await async_client.get(
            f"/api/documents/{doc_id}", headers=headers_a
        )
        assert read_updated.status_code == 200
        assert read_updated.json()["content"] == "# Modified by Agent B"

        # Both agents list the document
        list_a = await async_client.get("/api/documents", headers=headers_a)
        assert list_a.status_code == 200
        assert len(list_a.json()) == 1
        assert list_a.json()[0]["id"] == doc_id

        list_b = await async_client.get("/api/documents", headers=headers_b)
        assert list_b.status_code == 200
        assert len(list_b.json()) == 1
        assert list_b.json()[0]["id"] == doc_id

        # Agent A shares document with User B via collaborator API
        collab_resp = await async_client.post(
            f"/api/documents/{doc_id}/collaborators",
            json={"email": "userb@example.com", "permission": "edit"},
            headers=headers_a,
        )
        assert collab_resp.status_code == 201

        # User B sees the shared doc
        async_client.cookies.update(_auth_cookies(user_b))
        shared_resp = await async_client.get("/api/documents/shared")
        assert shared_resp.status_code == 200
        shared = shared_resp.json()
        assert len(shared) == 1
        assert shared[0]["id"] == doc_id
        assert shared[0]["permission"] == "edit"


class TestApiKeySecurityBoundaries:
    """User Story 7: API key security boundaries.

    Agent with valid key can CRUD -> revoked key gets 401 -> invalid key gets
    401 -> agent cannot access docs owned by other users without sharing.
    """

    @pytest.mark.asyncio
    async def test_valid_key_crud(
        self, async_client: AsyncClient, test_user: User
    ):
        """A valid API key allows full CRUD operations."""
        async_client.cookies.update(_auth_cookies(test_user))
        key_resp = await async_client.post(
            "/api/keys", json={"name": "Valid Key"}
        )
        raw_key = key_resp.json()["raw_key"]
        async_client.cookies.clear()

        headers = {"X-API-Key": raw_key}

        # Create
        resp = await async_client.post(
            "/api/documents",
            json={"title": "Secure Doc", "content": "# Secret"},
            headers=headers,
        )
        assert resp.status_code == 201
        doc_id = resp.json()["id"]

        # Read
        resp = await async_client.get(
            f"/api/documents/{doc_id}", headers=headers
        )
        assert resp.status_code == 200

        # Update
        resp = await async_client.put(
            f"/api/documents/{doc_id}",
            json={"content": "# Updated Secret"},
            headers=headers,
        )
        assert resp.status_code == 200

        # Delete
        resp = await async_client.delete(
            f"/api/documents/{doc_id}", headers=headers
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_revoked_key_rejected(
        self, async_client: AsyncClient, test_user: User
    ):
        """A revoked API key returns 401."""
        async_client.cookies.update(_auth_cookies(test_user))
        key_resp = await async_client.post(
            "/api/keys", json={"name": "Revocable Key"}
        )
        raw_key = key_resp.json()["raw_key"]
        key_id = key_resp.json()["id"]

        # Revoke the key
        revoke_resp = await async_client.delete(f"/api/keys/{key_id}")
        assert revoke_resp.status_code == 204
        async_client.cookies.clear()

        # Try to use the revoked key
        resp = await async_client.get(
            "/api/documents", headers={"X-API-Key": raw_key}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_key_rejected(self, async_client: AsyncClient):
        """An invalid API key returns 401."""
        resp = await async_client.get(
            "/api/documents",
            headers={"X-API-Key": "cm_totally_fake_key_12345"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_agent_cannot_access_other_users_docs(
        self, async_client: AsyncClient, test_user: User, user_b: User
    ):
        """An agent cannot access documents owned by another user without sharing."""
        # User B creates a document
        async_client.cookies.update(_auth_cookies(user_b))
        create_resp = await async_client.post(
            "/api/documents",
            json={"title": "Private Doc B", "content": "# Private"},
        )
        assert create_resp.status_code == 201
        doc_id = create_resp.json()["id"]
        async_client.cookies.clear()

        # test_user's agent tries to read User B's doc -> 403
        async_client.cookies.update(_auth_cookies(test_user))
        key_resp = await async_client.post(
            "/api/keys", json={"name": "Spy Key"}
        )
        spy_key = key_resp.json()["raw_key"]
        async_client.cookies.clear()

        resp = await async_client.get(
            f"/api/documents/{doc_id}",
            headers={"X-API-Key": spy_key},
        )
        assert resp.status_code == 403

        # test_user's agent tries to update User B's doc -> 403
        resp = await async_client.put(
            f"/api/documents/{doc_id}",
            json={"content": "# Hacked"},
            headers={"X-API-Key": spy_key},
        )
        assert resp.status_code == 403

        # test_user's agent tries to delete User B's doc -> 403
        resp = await async_client.delete(
            f"/api/documents/{doc_id}",
            headers={"X-API-Key": spy_key},
        )
        assert resp.status_code == 403


class TestCrossFeatureIntegration:
    """User Story 8: All features coexist without interference.

    Create doc -> add comments -> update content (triggers version) ->
    share with second user -> second user reads comments -> second user reads
    version history -> verify all features work together.
    """

    @pytest.mark.asyncio
    async def test_cross_feature_integration(
        self, async_client: AsyncClient, test_user: User, user_b: User
    ):
        async_client.cookies.update(_auth_cookies(test_user))

        # Step 1: Create document
        create_resp = await async_client.post(
            "/api/documents",
            json={
                "title": "Cross-Feature Doc",
                "content": "# Original Content\n\nParagraph to comment on.",
            },
        )
        assert create_resp.status_code == 201
        doc_id = create_resp.json()["id"]

        # Step 2: Add doc-level comment
        comment_resp = await async_client.post(
            f"/api/documents/{doc_id}/comments",
            json={"content": "Great start, needs more detail."},
        )
        assert comment_resp.status_code == 201
        comment_id = comment_resp.json()["id"]

        # Step 3: Add inline comment
        inline_resp = await async_client.post(
            f"/api/documents/{doc_id}/comments",
            json={
                "content": "Expand this paragraph.",
                "anchor_from": 20,
                "anchor_to": 40,
                "quoted_text": "Paragraph to comment",
            },
        )
        assert inline_resp.status_code == 201

        # Step 4: Update content (triggers auto-version)
        update_resp = await async_client.put(
            f"/api/documents/{doc_id}",
            json={"content": "# Updated Content\n\nExpanded paragraph with more detail."},
        )
        assert update_resp.status_code == 200

        # Step 5: Update again (triggers another version)
        update2_resp = await async_client.put(
            f"/api/documents/{doc_id}",
            json={"content": "# Final Content\n\nFully fleshed out paragraph."},
        )
        assert update2_resp.status_code == 200

        # Verify 2 versions exist
        versions_resp = await async_client.get(
            f"/api/documents/{doc_id}/versions"
        )
        assert versions_resp.status_code == 200
        versions = versions_resp.json()
        assert len(versions) == 2

        # Step 6: Share with User B (edit access) via collaborator API
        collab_resp = await async_client.post(
            f"/api/documents/{doc_id}/collaborators",
            json={"email": "userb@example.com", "permission": "edit"},
        )
        assert collab_resp.status_code == 201

        async_client.cookies.update(_auth_cookies(user_b))

        # Step 7: User B reads comments
        comments_resp = await async_client.get(
            f"/api/documents/{doc_id}/comments"
        )
        assert comments_resp.status_code == 200
        comments = comments_resp.json()
        assert len(comments) == 2

        # Step 8: User B reads version history
        versions_b_resp = await async_client.get(
            f"/api/documents/{doc_id}/versions"
        )
        assert versions_b_resp.status_code == 200
        assert len(versions_b_resp.json()) == 2

        # Step 9: User B can get a specific version
        v1_resp = await async_client.get(
            f"/api/documents/{doc_id}/versions/1"
        )
        assert v1_resp.status_code == 200
        assert v1_resp.json()["content"] == "# Updated Content\n\nExpanded paragraph with more detail."

        # Step 10: User B replies to a comment
        reply_resp = await async_client.post(
            f"/api/comments/{comment_id}/reply",
            json={"content": "Done, added more info."},
        )
        assert reply_resp.status_code == 201
        assert reply_resp.json()["author_name"] == "User B"

        # Step 11: Final state check -- document has final content
        final_doc = await async_client.get(f"/api/documents/{doc_id}")
        assert final_doc.status_code == 200
        assert final_doc.json()["content"] == "# Final Content\n\nFully fleshed out paragraph."
        assert final_doc.json()["title"] == "Cross-Feature Doc"

        # Step 13: Comments still intact with replies
        final_comments = await async_client.get(
            f"/api/documents/{doc_id}/comments"
        )
        assert final_comments.status_code == 200
        final_c = final_comments.json()
        assert len(final_c) == 2
        doc_comment = next(c for c in final_c if c["id"] == comment_id)
        assert len(doc_comment["replies"]) == 1
        assert doc_comment["replies"][0]["content"] == "Done, added more info."
