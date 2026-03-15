"""Tests for the notification system: models, dispatcher, scheduler, channels, routes."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.auth.jwt import create_access_token
from app.models.comment import Comment
from app.models.document import Document_
from app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationEvent,
    NotificationPreference,
    NotificationStatus,
)
from app.models.share_link import DocumentAccess, Permission
from app.models.user import User
from app.services.notification_dispatcher import NotificationDispatcher
from httpx import AsyncClient


def _auth_cookies(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"access_token": token}


async def _make_user(email: str, name: str) -> User:
    user = User(google_id=f"gid-{email}", email=email, name=name)
    await user.insert()
    return user


async def _make_doc(owner: User, title: str = "Test Doc") -> Document_:
    doc = Document_(title=title, content="# Hello", owner_id=str(owner.id))
    await doc.insert()
    return doc


class TestNotificationModel:
    @pytest.mark.asyncio
    async def test_create_notification(self, test_user: User):
        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            recipient_name=test_user.name,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            channel=NotificationChannel.EMAIL,
            payload={"document_title": "Doc"},
        )
        await notif.insert()
        assert notif.id is not None
        assert notif.status == NotificationStatus.SCHEDULED

    @pytest.mark.asyncio
    async def test_notification_default_status_is_scheduled(self, test_user: User):
        notif = Notification(
            recipient_id=str(test_user.id),
            event_type=NotificationEvent.COMMENT_ADDED,
        )
        await notif.insert()
        assert notif.status == NotificationStatus.SCHEDULED


class TestNotificationPreference:
    @pytest.mark.asyncio
    async def test_default_preferences_all_enabled(self, test_user: User):
        pref = NotificationPreference(user_id=str(test_user.id))
        await pref.insert()
        assert pref.is_enabled("document_shared", "email") is True
        assert pref.is_enabled("comment_added", "email") is True

    @pytest.mark.asyncio
    async def test_disable_specific_event(self, test_user: User):
        pref = NotificationPreference(
            user_id=str(test_user.id),
            preferences={
                "document_shared": {"email": False},
                "comment_added": {"email": True},
            },
        )
        await pref.insert()
        assert pref.is_enabled("document_shared", "email") is False
        assert pref.is_enabled("comment_added", "email") is True

    @pytest.mark.asyncio
    async def test_unknown_event_defaults_enabled(self, test_user: User):
        pref = NotificationPreference(user_id=str(test_user.id))
        await pref.insert()
        assert pref.is_enabled("future_event", "email") is True


class TestNotificationDispatcher:
    @pytest.mark.asyncio
    async def test_schedule_creates_notification_and_pushes_to_redis(self, test_user: User):
        redis_mock = AsyncMock()
        dispatcher = NotificationDispatcher(redis_client=redis_mock)

        notifs = await dispatcher.schedule(
            event_type=NotificationEvent.DOCUMENT_SHARED,
            recipients=[
                {
                    "user_id": str(test_user.id),
                    "email": test_user.email,
                    "name": test_user.name,
                }
            ],
            action_ref_id="fake-access-id",
            document_id="fake-doc-id",
            payload={
                "recipient_name": test_user.name,
                "shared_by": "Owner",
                "document_title": "Test",
                "document_id": "fake-doc-id",
                "permission": "view",
            },
        )
        assert len(notifs) == 1
        assert notifs[0].status == NotificationStatus.SCHEDULED
        assert notifs[0].action_ref_id == "fake-access-id"
        redis_mock.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_respects_disabled_preferences(self, test_user: User):
        pref = NotificationPreference(
            user_id=str(test_user.id),
            preferences={"document_shared": {"email": False}},
        )
        await pref.insert()

        redis_mock = AsyncMock()
        dispatcher = NotificationDispatcher(redis_client=redis_mock)
        notifs = await dispatcher.schedule(
            event_type=NotificationEvent.DOCUMENT_SHARED,
            recipients=[
                {
                    "user_id": str(test_user.id),
                    "email": test_user.email,
                    "name": test_user.name,
                }
            ],
            action_ref_id="ref-123",
            payload={
                "recipient_name": test_user.name,
                "shared_by": "Owner",
                "document_title": "Doc",
                "document_id": "doc-123",
                "permission": "view",
            },
        )
        assert len(notifs) == 0
        redis_mock.zadd.assert_not_called()

    @pytest.mark.asyncio
    async def test_schedule_disabled_when_notifications_off(self, test_user: User):
        redis_mock = AsyncMock()
        dispatcher = NotificationDispatcher(redis_client=redis_mock)
        with patch("app.services.notification_dispatcher.settings") as mock_settings:
            mock_settings.notifications_enabled = False
            notifs = await dispatcher.schedule(
                event_type=NotificationEvent.DOCUMENT_SHARED,
                recipients=[
                    {
                        "user_id": str(test_user.id),
                        "email": test_user.email,
                        "name": test_user.name,
                    }
                ],
                action_ref_id="ref-123",
                payload={
                    "recipient_name": test_user.name,
                    "shared_by": "Owner",
                    "document_title": "Doc",
                    "document_id": "doc-123",
                    "permission": "view",
                },
            )
        assert len(notifs) == 0

    @pytest.mark.asyncio
    async def test_send_success(self, test_user: User):
        channel_mock = AsyncMock()
        channel_mock.send.return_value = True

        dispatcher = NotificationDispatcher()
        dispatcher.register_channel(NotificationChannel.EMAIL, channel_mock)

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            status=NotificationStatus.PENDING,
            payload={
                "recipient_name": test_user.name,
                "shared_by": "Owner",
                "document_title": "Doc",
                "document_id": "doc-123",
                "permission": "view",
            },
        )
        await notif.insert()

        ok = await dispatcher.send(notif)
        assert ok is True

        refreshed = await Notification.get(notif.id)
        assert refreshed.status == NotificationStatus.SENT
        assert refreshed.sent_at is not None

    @pytest.mark.asyncio
    async def test_send_failure_increments_retry_count(self, test_user: User):
        channel_mock = AsyncMock()
        channel_mock.send.return_value = False

        dispatcher = NotificationDispatcher()
        dispatcher.register_channel(NotificationChannel.EMAIL, channel_mock)

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            status=NotificationStatus.PENDING,
            payload={
                "recipient_name": test_user.name,
                "shared_by": "Owner",
                "document_title": "Doc",
                "document_id": "doc-123",
                "permission": "view",
            },
        )
        await notif.insert()

        ok = await dispatcher.send(notif)
        assert ok is False

        refreshed = await Notification.get(notif.id)
        assert refreshed.status == NotificationStatus.FAILED
        assert refreshed.retry_count == 1


class TestSchedulerValidation:
    """Tests for _validate_action_exists in notification_scheduler."""

    @pytest.mark.asyncio
    async def test_validate_comment_exists(self, test_user: User):
        from app.services.notification_scheduler import _validate_action_exists

        doc = await _make_doc(test_user)
        comment = Comment(
            document_id=str(doc.id),
            author_id=str(test_user.id),
            author_name=test_user.name,
            content="Test comment",
        )
        await comment.insert()

        notif = Notification(
            recipient_id=str(test_user.id),
            event_type=NotificationEvent.COMMENT_ADDED,
            action_ref_id=str(comment.id),
        )
        assert await _validate_action_exists(notif) is True

    @pytest.mark.asyncio
    async def test_validate_deleted_comment_fails(self, test_user: User):
        from app.services.notification_scheduler import _validate_action_exists

        doc = await _make_doc(test_user)
        comment = Comment(
            document_id=str(doc.id),
            author_id=str(test_user.id),
            author_name=test_user.name,
            content="Ephemeral comment",
        )
        await comment.insert()
        comment_id = str(comment.id)
        await comment.delete()

        notif = Notification(
            recipient_id=str(test_user.id),
            event_type=NotificationEvent.COMMENT_ADDED,
            action_ref_id=comment_id,
        )
        assert await _validate_action_exists(notif) is False

    @pytest.mark.asyncio
    async def test_validate_access_exists(self, test_user: User):
        from app.services.notification_scheduler import _validate_action_exists

        doc = await _make_doc(test_user)
        other = await _make_user("other@example.com", "Other")
        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(other.id),
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await access.insert()

        notif = Notification(
            recipient_id=str(other.id),
            event_type=NotificationEvent.DOCUMENT_SHARED,
            action_ref_id=str(access.id),
        )
        assert await _validate_action_exists(notif) is True

    @pytest.mark.asyncio
    async def test_validate_revoked_access_fails(self, test_user: User):
        from app.services.notification_scheduler import _validate_action_exists

        doc = await _make_doc(test_user)
        other = await _make_user("revoked@example.com", "Revoked")
        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(other.id),
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await access.insert()
        access_id = str(access.id)
        await access.delete()

        notif = Notification(
            recipient_id=str(other.id),
            event_type=NotificationEvent.DOCUMENT_SHARED,
            action_ref_id=access_id,
        )
        assert await _validate_action_exists(notif) is False

    @pytest.mark.asyncio
    async def test_validate_no_ref_id_passes(self, test_user: User):
        from app.services.notification_scheduler import _validate_action_exists

        notif = Notification(
            recipient_id=str(test_user.id),
            event_type=NotificationEvent.DOCUMENT_SHARED,
            action_ref_id=None,
        )
        assert await _validate_action_exists(notif) is True


class TestSchedulerProcessing:
    """Tests for the scheduler's due notification processing."""

    @pytest.mark.asyncio
    async def test_process_due_notification_sends(self, test_user: User):
        from app.services.notification_scheduler import _process_due_notifications

        doc = await _make_doc(test_user)
        other = await _make_user("notify@example.com", "Notify Me")
        access = DocumentAccess(
            document_id=str(doc.id),
            user_id=str(other.id),
            permission=Permission.VIEW,
            granted_by=str(test_user.id),
        )
        await access.insert()

        notif = Notification(
            recipient_id=str(other.id),
            recipient_email=other.email,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            status=NotificationStatus.SCHEDULED,
            action_ref_id=str(access.id),
            payload={
                "recipient_name": other.name,
                "shared_by": test_user.name,
                "document_title": doc.title,
                "document_id": str(doc.id),
                "permission": "view",
            },
        )
        await notif.insert()

        redis_mock = AsyncMock()
        redis_mock.zrangebyscore.return_value = [json.dumps({"notification_id": str(notif.id)})]

        channel_mock = AsyncMock()
        channel_mock.send.return_value = True
        dispatcher = NotificationDispatcher(redis_client=redis_mock)
        dispatcher.register_channel(NotificationChannel.EMAIL, channel_mock)

        await _process_due_notifications(redis_mock, dispatcher)

        refreshed = await Notification.get(notif.id)
        assert refreshed.status == NotificationStatus.SENT

    @pytest.mark.asyncio
    async def test_process_due_notification_skips_reverted(self, test_user: User):
        from app.services.notification_scheduler import _process_due_notifications

        doc = await _make_doc(test_user)
        comment = Comment(
            document_id=str(doc.id),
            author_id="someone-else",
            author_name="Commenter",
            content="Deleted quickly",
        )
        await comment.insert()
        comment_id = str(comment.id)
        await comment.delete()

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.COMMENT_ADDED,
            status=NotificationStatus.SCHEDULED,
            action_ref_id=comment_id,
            payload={
                "recipient_name": test_user.name,
                "commenter": "Commenter",
                "document_title": doc.title,
                "document_id": str(doc.id),
                "comment_preview": "Deleted quickly",
            },
        )
        await notif.insert()

        redis_mock = AsyncMock()
        redis_mock.zrangebyscore.return_value = [json.dumps({"notification_id": str(notif.id)})]

        dispatcher = NotificationDispatcher(redis_client=redis_mock)

        await _process_due_notifications(redis_mock, dispatcher)

        refreshed = await Notification.get(notif.id)
        assert refreshed.status == NotificationStatus.SKIPPED
        assert "reverted" in refreshed.error.lower()


class TestEmailChannel:
    @pytest.mark.asyncio
    async def test_send_resend_success(self, test_user: User):
        from app.services.channels.email import EmailChannel

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            payload={
                "recipient_name": test_user.name,
                "shared_by": "Owner",
                "document_title": "My Doc",
                "document_id": "doc-123",
                "permission": "edit",
            },
        )
        await notif.insert()

        channel = EmailChannel()
        with patch("app.services.channels.email.settings") as mock_settings:
            mock_settings.notification_email_provider = "resend"
            mock_settings.resend_api_key = "re_test_123"
            mock_settings.notification_from_email = "test@test.com"
            with patch("app.services.channels.email.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post.return_value = MagicMock(status_code=200)
                mock_client_cls.return_value = mock_client
                result = await channel.send(notif)

        assert result is True

    @pytest.mark.asyncio
    async def test_send_smtp_success(self, test_user: User):
        from app.services.channels.email import EmailChannel

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.COMMENT_ADDED,
            payload={
                "recipient_name": test_user.name,
                "commenter": "Commenter",
                "document_title": "My Doc",
                "document_id": "doc-123",
                "comment_preview": "Nice work!",
            },
        )
        await notif.insert()

        channel = EmailChannel()
        with (
            patch("app.services.channels.email.settings") as mock_settings,
            patch("app.services.channels.email.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_settings.notification_email_provider = "smtp"
            mock_settings.smtp_host = "smtp.example.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_user = "user"
            mock_settings.smtp_password = "pass"
            mock_settings.notification_from_email = "test@test.com"

            mock_smtp = MagicMock()
            mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
            mock_smtp.__exit__ = MagicMock(return_value=False)
            mock_smtp.has_extn.return_value = True
            mock_smtp_cls.return_value = mock_smtp

            result = await channel.send(notif)

        assert result is True
        mock_smtp.sendmail.assert_called_once()
        mock_smtp.starttls.assert_called_once()


class TestEmailTemplates:
    def test_document_shared_template(self):
        from app.services.channels.templates import render_document_shared

        subject, html = render_document_shared(
            recipient_name="Alice",
            shared_by="Bob",
            document_title="Sprint Notes",
            document_id="doc-abc",
            permission="edit",
        )
        assert "Bob" in subject
        assert "Sprint Notes" in subject
        assert "CollabMark" in html
        assert "Alice" in html
        assert "edit" in html
        assert "Open Document" in html
        assert "doc-abc" in html

    def test_comment_added_template(self):
        from app.services.channels.templates import render_comment_added

        subject, html = render_comment_added(
            recipient_name="Alice",
            commenter="Charlie",
            document_title="Roadmap",
            document_id="doc-xyz",
            comment_preview="This section needs revision",
        )
        assert "Charlie" in subject
        assert "Roadmap" in subject
        assert "CollabMark" in html
        assert "Alice" in html
        assert "This section needs revision" in html
        assert "View Document" in html

    def test_comment_preview_truncation(self):
        from app.services.channels.templates import render_comment_added

        long_comment = "x" * 200
        _, html = render_comment_added(
            recipient_name="Alice",
            commenter="Bob",
            document_title="Doc",
            document_id="d-1",
            comment_preview=long_comment,
        )
        assert "..." in html


class TestNotificationRoutes:
    @pytest.mark.asyncio
    async def test_list_notifications(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))

        notif = Notification(
            recipient_id=str(test_user.id),
            event_type=NotificationEvent.DOCUMENT_SHARED,
            payload={"document_title": "Shared Doc"},
        )
        await notif.insert()

        resp = await async_client.get("/api/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["event_type"] == "document_shared"

    @pytest.mark.asyncio
    async def test_list_notifications_excludes_other_users(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))

        other = await _make_user("other2@example.com", "Other2")
        notif = Notification(
            recipient_id=str(other.id),
            event_type=NotificationEvent.DOCUMENT_SHARED,
            payload={},
        )
        await notif.insert()

        resp = await async_client.get("/api/notifications")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_mark_notification_read(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))

        notif = Notification(
            recipient_id=str(test_user.id),
            event_type=NotificationEvent.COMMENT_ADDED,
            payload={},
        )
        await notif.insert()

        resp = await async_client.patch(f"/api/notifications/{notif.id}/read")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_mark_other_users_notification_returns_404(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))

        other = await _make_user("hacker@example.com", "Hacker")
        notif = Notification(
            recipient_id=str(other.id),
            event_type=NotificationEvent.COMMENT_ADDED,
            payload={},
        )
        await notif.insert()

        resp = await async_client.patch(f"/api/notifications/{notif.id}/read")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_preferences_default(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.get("/api/notifications/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["preferences"]["document_shared"]["email"] is True
        assert data["preferences"]["comment_added"]["email"] is True

    @pytest.mark.asyncio
    async def test_update_preferences(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.put(
            "/api/notifications/preferences",
            json={"preferences": {"document_shared": {"email": False}, "comment_added": {"email": True}}},
        )
        assert resp.status_code == 200
        assert resp.json()["preferences"]["document_shared"]["email"] is False

        resp2 = await async_client.get("/api/notifications/preferences")
        assert resp2.json()["preferences"]["document_shared"]["email"] is False


class TestRetryWorker:
    """Tests for notification_retry.py: push_to_retry and _process_retry_queue."""

    @pytest.mark.asyncio
    async def test_push_to_retry(self, test_user: User):
        from app.services.notification_retry import REDIS_RETRY_KEY, push_to_retry

        redis_mock = AsyncMock()
        await push_to_retry(redis_mock, "notif-abc")
        redis_mock.rpush.assert_called_once()
        call_args = redis_mock.rpush.call_args
        assert call_args[0][0] == REDIS_RETRY_KEY
        assert "notif-abc" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_process_retry_queue_success(self, test_user: User):
        from app.services.notification_retry import _process_retry_queue

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            status=NotificationStatus.FAILED,
            retry_count=1,
            payload={
                "recipient_name": test_user.name,
                "shared_by": "Owner",
                "document_title": "Doc",
                "document_id": "d-1",
                "permission": "view",
            },
        )
        await notif.insert()

        redis_mock = AsyncMock()
        redis_mock.lpop.return_value = json.dumps({"notification_id": str(notif.id)})

        channel_mock = AsyncMock()
        channel_mock.send.return_value = True
        dispatcher = NotificationDispatcher()
        dispatcher.register_channel(NotificationChannel.EMAIL, channel_mock)

        with patch("app.services.notification_retry.asyncio.sleep", new_callable=AsyncMock):
            await _process_retry_queue(redis_mock, dispatcher)

        refreshed = await Notification.get(notif.id)
        assert refreshed.status == NotificationStatus.SENT

    @pytest.mark.asyncio
    async def test_process_retry_queue_empty(self):
        from app.services.notification_retry import _process_retry_queue

        redis_mock = AsyncMock()
        redis_mock.lpop.return_value = None
        dispatcher = NotificationDispatcher()
        await _process_retry_queue(redis_mock, dispatcher)

    @pytest.mark.asyncio
    async def test_process_retry_queue_max_retries_exceeded(self, test_user: User):
        from app.services.notification_retry import _process_retry_queue

        notif = Notification(
            recipient_id=str(test_user.id),
            event_type=NotificationEvent.DOCUMENT_SHARED,
            status=NotificationStatus.FAILED,
            retry_count=3,
            payload={},
        )
        await notif.insert()

        redis_mock = AsyncMock()
        redis_mock.lpop.return_value = json.dumps({"notification_id": str(notif.id)})
        dispatcher = NotificationDispatcher()

        await _process_retry_queue(redis_mock, dispatcher)

        refreshed = await Notification.get(notif.id)
        assert refreshed.status == NotificationStatus.FAILED
        assert "retries" in refreshed.error.lower()

    @pytest.mark.asyncio
    async def test_process_retry_queue_malformed_entry(self):
        from app.services.notification_retry import _process_retry_queue

        redis_mock = AsyncMock()
        redis_mock.lpop.return_value = "not-valid-json{{"
        dispatcher = NotificationDispatcher()
        await _process_retry_queue(redis_mock, dispatcher)

    @pytest.mark.asyncio
    async def test_process_retry_queue_invalid_objectid(self):
        from app.services.notification_retry import _process_retry_queue

        redis_mock = AsyncMock()
        redis_mock.lpop.return_value = json.dumps({"notification_id": "not-an-oid"})
        dispatcher = NotificationDispatcher()
        await _process_retry_queue(redis_mock, dispatcher)

    @pytest.mark.asyncio
    async def test_process_retry_queue_notification_not_found(self):
        from app.services.notification_retry import _process_retry_queue

        redis_mock = AsyncMock()
        redis_mock.lpop.return_value = json.dumps({"notification_id": "000000000000000000000000"})
        dispatcher = NotificationDispatcher()
        await _process_retry_queue(redis_mock, dispatcher)

    @pytest.mark.asyncio
    async def test_process_retry_queue_repushes_on_failure(self, test_user: User):
        from app.services.notification_retry import _process_retry_queue

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            status=NotificationStatus.FAILED,
            retry_count=0,
            payload={
                "recipient_name": test_user.name,
                "shared_by": "Owner",
                "document_title": "Doc",
                "document_id": "d-1",
                "permission": "view",
            },
        )
        await notif.insert()

        redis_mock = AsyncMock()
        redis_mock.lpop.return_value = json.dumps({"notification_id": str(notif.id)})

        channel_mock = AsyncMock()
        channel_mock.send.return_value = False
        dispatcher = NotificationDispatcher()
        dispatcher.register_channel(NotificationChannel.EMAIL, channel_mock)

        with patch("app.services.notification_retry.asyncio.sleep", new_callable=AsyncMock):
            await _process_retry_queue(redis_mock, dispatcher)

        assert redis_mock.rpush.called


class TestRetryLoop:
    """Tests for the retry_loop wrapper function."""

    @pytest.mark.asyncio
    async def test_retry_loop_handles_cancellation(self):
        import asyncio

        from app.services.notification_retry import retry_loop

        redis_mock = AsyncMock()
        redis_mock.lpop.return_value = None
        dispatcher = NotificationDispatcher()

        with patch("app.services.notification_retry.POLL_INTERVAL_SECONDS", 0):
            task = asyncio.create_task(retry_loop(redis_mock, dispatcher))
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    @pytest.mark.asyncio
    async def test_retry_loop_handles_unexpected_error(self):
        import asyncio

        from app.services.notification_retry import retry_loop

        redis_mock = AsyncMock()
        redis_mock.lpop.side_effect = [RuntimeError("boom"), None]
        dispatcher = NotificationDispatcher()

        with patch("app.services.notification_retry.POLL_INTERVAL_SECONDS", 0):
            task = asyncio.create_task(retry_loop(redis_mock, dispatcher))
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


class TestSchedulerLoop:
    """Tests for the scheduler_loop wrapper function."""

    @pytest.mark.asyncio
    async def test_scheduler_loop_handles_cancellation(self):
        import asyncio

        from app.services.notification_scheduler import scheduler_loop

        redis_mock = AsyncMock()
        redis_mock.zrangebyscore.return_value = []
        dispatcher = NotificationDispatcher()

        with patch("app.services.notification_scheduler.POLL_INTERVAL_SECONDS", 0):
            task = asyncio.create_task(scheduler_loop(redis_mock, dispatcher))
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    @pytest.mark.asyncio
    async def test_scheduler_loop_handles_unexpected_error(self):
        import asyncio

        from app.services.notification_scheduler import scheduler_loop

        redis_mock = AsyncMock()
        redis_mock.zrangebyscore.side_effect = [RuntimeError("boom"), []]
        dispatcher = NotificationDispatcher()

        with patch("app.services.notification_scheduler.POLL_INTERVAL_SECONDS", 0):
            task = asyncio.create_task(scheduler_loop(redis_mock, dispatcher))
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


class TestSchedulerEdgeCases:
    """Edge case tests for notification_scheduler._process_due_notifications."""

    @pytest.mark.asyncio
    async def test_process_empty_zset(self):
        from app.services.notification_scheduler import _process_due_notifications

        redis_mock = AsyncMock()
        redis_mock.zrangebyscore.return_value = []
        dispatcher = NotificationDispatcher()
        await _process_due_notifications(redis_mock, dispatcher)
        redis_mock.zremrangebyscore.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_malformed_json_in_zset(self):
        from app.services.notification_scheduler import _process_due_notifications

        redis_mock = AsyncMock()
        redis_mock.zrangebyscore.return_value = ["not-json{{"]
        dispatcher = NotificationDispatcher()
        await _process_due_notifications(redis_mock, dispatcher)

    @pytest.mark.asyncio
    async def test_process_invalid_objectid_in_zset(self):
        from app.services.notification_scheduler import _process_due_notifications

        redis_mock = AsyncMock()
        redis_mock.zrangebyscore.return_value = [json.dumps({"notification_id": "bad-oid"})]
        dispatcher = NotificationDispatcher()
        await _process_due_notifications(redis_mock, dispatcher)

    @pytest.mark.asyncio
    async def test_process_notification_not_found(self):
        from app.services.notification_scheduler import _process_due_notifications

        redis_mock = AsyncMock()
        redis_mock.zrangebyscore.return_value = [json.dumps({"notification_id": "000000000000000000000000"})]
        dispatcher = NotificationDispatcher()
        await _process_due_notifications(redis_mock, dispatcher)

    @pytest.mark.asyncio
    async def test_process_already_sent_notification_skipped(self, test_user: User):
        from app.services.notification_scheduler import _process_due_notifications

        notif = Notification(
            recipient_id=str(test_user.id),
            event_type=NotificationEvent.DOCUMENT_SHARED,
            status=NotificationStatus.SENT,
            payload={},
        )
        await notif.insert()

        redis_mock = AsyncMock()
        redis_mock.zrangebyscore.return_value = [json.dumps({"notification_id": str(notif.id)})]
        dispatcher = NotificationDispatcher()
        await _process_due_notifications(redis_mock, dispatcher)

        refreshed = await Notification.get(notif.id)
        assert refreshed.status == NotificationStatus.SENT

    @pytest.mark.asyncio
    async def test_validate_invalid_action_ref_id(self, test_user: User):
        from app.services.notification_scheduler import _validate_action_exists

        notif = Notification(
            recipient_id=str(test_user.id),
            event_type=NotificationEvent.COMMENT_ADDED,
            action_ref_id="not-a-valid-oid",
        )
        assert await _validate_action_exists(notif) is False

    @pytest.mark.asyncio
    async def test_validate_unknown_event_type_passes(self, test_user: User):
        from app.services.notification_scheduler import _validate_action_exists

        notif = Notification(
            recipient_id=str(test_user.id),
            event_type=NotificationEvent.DOCUMENT_SHARED,
            action_ref_id=None,
        )
        assert await _validate_action_exists(notif) is True


class TestEmailChannelEdgeCases:
    @pytest.mark.asyncio
    async def test_unknown_event_type_returns_false(self, test_user: User):
        from app.services.channels.email import EmailChannel

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            payload={},
        )
        await notif.insert()

        channel = EmailChannel()
        with patch.dict("app.services.channels.email._TEMPLATE_MAP", {}, clear=True):
            result = await channel.send(notif)
        assert result is False

    @pytest.mark.asyncio
    async def test_smtp_not_configured_returns_false(self, test_user: User):
        from app.services.channels.email import EmailChannel

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            payload={
                "recipient_name": test_user.name,
                "shared_by": "Owner",
                "document_title": "Doc",
                "document_id": "d-1",
                "permission": "view",
            },
        )
        await notif.insert()

        channel = EmailChannel()
        with patch("app.services.channels.email.settings") as mock_settings:
            mock_settings.notification_email_provider = "smtp"
            mock_settings.smtp_host = ""
            result = await channel.send(notif)
        assert result is False

    @pytest.mark.asyncio
    async def test_resend_api_error_returns_false(self, test_user: User):
        from app.services.channels.email import EmailChannel

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            payload={
                "recipient_name": test_user.name,
                "shared_by": "Owner",
                "document_title": "Doc",
                "document_id": "d-1",
                "permission": "view",
            },
        )
        await notif.insert()

        channel = EmailChannel()
        with patch("app.services.channels.email.settings") as mock_settings:
            mock_settings.notification_email_provider = "resend"
            mock_settings.resend_api_key = "re_test"
            mock_settings.notification_from_email = "test@test.com"
            with patch("app.services.channels.email.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post.return_value = MagicMock(status_code=400, text="Bad request")
                mock_client_cls.return_value = mock_client
                result = await channel.send(notif)
        assert result is False

    @pytest.mark.asyncio
    async def test_resend_http_error_returns_false(self, test_user: User):
        import httpx as httpx_mod
        from app.services.channels.email import EmailChannel

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            payload={
                "recipient_name": test_user.name,
                "shared_by": "Owner",
                "document_title": "Doc",
                "document_id": "d-1",
                "permission": "view",
            },
        )
        await notif.insert()

        channel = EmailChannel()
        with patch("app.services.channels.email.settings") as mock_settings:
            mock_settings.notification_email_provider = "resend"
            mock_settings.resend_api_key = "re_test"
            mock_settings.notification_from_email = "test@test.com"
            with patch("app.services.channels.email.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post.side_effect = httpx_mod.ConnectError("connection refused")
                mock_client_cls.return_value = mock_client
                result = await channel.send(notif)
        assert result is False

    @pytest.mark.asyncio
    async def test_smtp_exception_returns_false(self, test_user: User):
        import smtplib

        from app.services.channels.email import EmailChannel

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.COMMENT_ADDED,
            payload={
                "recipient_name": test_user.name,
                "commenter": "Bob",
                "document_title": "Doc",
                "document_id": "d-1",
                "comment_preview": "hi",
            },
        )
        await notif.insert()

        channel = EmailChannel()
        with (
            patch("app.services.channels.email.settings") as mock_settings,
            patch("app.services.channels.email.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_settings.notification_email_provider = "smtp"
            mock_settings.smtp_host = "smtp.example.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_user = ""
            mock_settings.notification_from_email = "test@test.com"
            mock_smtp_cls.side_effect = smtplib.SMTPConnectError(421, "Service unavailable")
            result = await channel.send(notif)
        assert result is False

    @pytest.mark.asyncio
    async def test_smtp_no_starttls_extension_skips_starttls(self, test_user: User):
        from app.services.channels.email import EmailChannel

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            payload={
                "recipient_name": test_user.name,
                "shared_by": "Owner",
                "document_title": "Doc",
                "document_id": "d-1",
                "permission": "view",
            },
        )
        await notif.insert()

        channel = EmailChannel()
        with (
            patch("app.services.channels.email.settings") as mock_settings,
            patch("app.services.channels.email.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_settings.notification_email_provider = "smtp"
            mock_settings.smtp_host = "smtp.example.com"
            mock_settings.smtp_port = 1025
            mock_settings.smtp_user = ""
            mock_settings.notification_from_email = "test@test.com"

            mock_smtp = MagicMock()
            mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
            mock_smtp.__exit__ = MagicMock(return_value=False)
            mock_smtp.has_extn.return_value = False
            mock_smtp_cls.return_value = mock_smtp

            result = await channel.send(notif)
        assert result is True
        mock_smtp.starttls.assert_not_called()
        mock_smtp.has_extn.assert_called_once_with("starttls")


class TestDispatcherEdgeCases:
    def test_get_dispatcher_before_init_raises(self):
        from app.services.notification_dispatcher import get_dispatcher

        with patch("app.services.notification_dispatcher._dispatcher", None):
            with pytest.raises(RuntimeError, match="not initialized"):
                get_dispatcher()

    def test_set_dispatcher(self):
        from app.services.notification_dispatcher import (
            _dispatcher,
            get_dispatcher,
            set_dispatcher,
        )

        d = NotificationDispatcher()
        original = _dispatcher
        try:
            set_dispatcher(d)
            assert get_dispatcher() is d
        finally:
            set_dispatcher(original)

    @pytest.mark.asyncio
    async def test_send_with_no_handler(self, test_user: User):
        dispatcher = NotificationDispatcher()

        notif = Notification(
            recipient_id=str(test_user.id),
            recipient_email=test_user.email,
            event_type=NotificationEvent.DOCUMENT_SHARED,
            status=NotificationStatus.PENDING,
            payload={},
        )
        await notif.insert()

        ok = await dispatcher.send(notif)
        assert ok is False

        refreshed = await Notification.get(notif.id)
        assert refreshed.status == NotificationStatus.FAILED
        assert "no handler" in refreshed.error.lower()

    @pytest.mark.asyncio
    async def test_schedule_without_redis(self, test_user: User):
        dispatcher = NotificationDispatcher(redis_client=None)
        notifs = await dispatcher.schedule(
            event_type=NotificationEvent.DOCUMENT_SHARED,
            recipients=[
                {
                    "user_id": str(test_user.id),
                    "email": test_user.email,
                    "name": test_user.name,
                }
            ],
            action_ref_id="ref-123",
            payload={
                "recipient_name": test_user.name,
                "shared_by": "Owner",
                "document_title": "Doc",
                "document_id": "doc-1",
                "permission": "view",
            },
        )
        assert len(notifs) == 1
        assert notifs[0].status == NotificationStatus.SCHEDULED


class TestNotificationRoutesEdgeCases:
    @pytest.mark.asyncio
    async def test_mark_read_invalid_id_returns_404(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))
        resp = await async_client.patch("/api/notifications/not-a-valid-id/read")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_existing_preferences(self, async_client: AsyncClient, test_user: User):
        async_client.cookies.update(_auth_cookies(test_user))

        pref = NotificationPreference(
            user_id=str(test_user.id),
            preferences={"document_shared": {"email": True}, "comment_added": {"email": True}},
        )
        await pref.insert()

        resp = await async_client.put(
            "/api/notifications/preferences",
            json={"preferences": {"document_shared": {"email": False}, "comment_added": {"email": False}}},
        )
        assert resp.status_code == 200
        assert resp.json()["preferences"]["document_shared"]["email"] is False
        assert resp.json()["preferences"]["comment_added"]["email"] is False


class TestIntegrationShareNotification:
    """Integration: add_collaborator triggers notification scheduling."""

    @pytest.mark.asyncio
    async def test_add_collaborator_schedules_notification(self, test_user: User):
        doc = await _make_doc(test_user, "Shared Doc")
        collab = await _make_user("collab@example.com", "Collaborator")

        mock_dispatcher = AsyncMock(spec=NotificationDispatcher)
        mock_dispatcher.schedule = AsyncMock(return_value=[])

        with patch(
            "app.services.share_service.get_dispatcher",
            return_value=mock_dispatcher,
        ):
            from app.services.share_service import add_collaborator

            await add_collaborator(str(doc.id), test_user, collab.email, Permission.EDIT)

        mock_dispatcher.schedule.assert_called_once()
        call_kwargs = mock_dispatcher.schedule.call_args.kwargs
        assert call_kwargs["event_type"] == NotificationEvent.DOCUMENT_SHARED
        assert call_kwargs["payload"]["shared_by"] == test_user.name
        assert call_kwargs["payload"]["document_title"] == "Shared Doc"


class TestIntegrationCommentNotification:
    """Integration: create_comment triggers notification scheduling for doc owner."""

    @pytest.mark.asyncio
    async def test_comment_schedules_notification_for_owner(self, test_user: User):
        from app.models.comment import CommentCreate

        commenter = await _make_user("commenter@example.com", "Commenter")
        doc = await _make_doc(test_user, "Commented Doc")

        mock_dispatcher = AsyncMock(spec=NotificationDispatcher)
        mock_dispatcher.schedule = AsyncMock(return_value=[])

        with patch(
            "app.services.comment_service.get_dispatcher",
            return_value=mock_dispatcher,
        ):
            from app.services.comment_service import create_comment

            payload = CommentCreate(content="Great document!")
            await create_comment(str(doc.id), commenter, payload)

        mock_dispatcher.schedule.assert_called_once()
        call_kwargs = mock_dispatcher.schedule.call_args.kwargs
        assert call_kwargs["event_type"] == NotificationEvent.COMMENT_ADDED
        assert call_kwargs["payload"]["commenter"] == "Commenter"
        assert call_kwargs["recipients"][0]["user_id"] == str(test_user.id)

    @pytest.mark.asyncio
    async def test_owner_commenting_own_doc_no_notification(self, test_user: User):
        from app.models.comment import CommentCreate

        doc = await _make_doc(test_user, "My Doc")

        mock_dispatcher = AsyncMock(spec=NotificationDispatcher)
        mock_dispatcher.schedule = AsyncMock(return_value=[])

        with patch(
            "app.services.comment_service.get_dispatcher",
            return_value=mock_dispatcher,
        ):
            from app.services.comment_service import create_comment

            payload = CommentCreate(content="Note to self")
            await create_comment(str(doc.id), test_user, payload)

        mock_dispatcher.schedule.assert_not_called()
