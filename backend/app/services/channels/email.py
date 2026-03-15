"""Email notification channel: Resend API or generic SMTP delivery."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.config import settings
from app.models.notification import Notification, NotificationEvent
from app.services.channels.base import BaseChannel
from app.services.channels.templates import render_comment_added, render_document_shared

logger = logging.getLogger(__name__)

_TEMPLATE_MAP = {
    NotificationEvent.DOCUMENT_SHARED: render_document_shared,
    NotificationEvent.COMMENT_ADDED: render_comment_added,
}


class EmailChannel(BaseChannel):
    """Delivers notifications via email using Resend API or SMTP."""

    async def send(self, notification: Notification) -> bool:
        renderer = _TEMPLATE_MAP.get(notification.event_type)
        if renderer is None:
            logger.warning("No email template for event %s", notification.event_type)
            return False

        subject, html = renderer(**notification.payload)

        if settings.notification_email_provider == "resend":
            return await self._send_resend(notification.recipient_email, subject, html)
        return await self._send_smtp(notification.recipient_email, subject, html)

    async def _send_resend(self, to: str, subject: str, html: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {settings.resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": settings.notification_from_email,
                        "to": [to],
                        "subject": subject,
                        "html": html,
                    },
                )
                if resp.status_code in (200, 201):
                    logger.info("Email sent via Resend to %s", to)
                    return True
                logger.error("Resend API error %s: %s", resp.status_code, resp.text)
                return False
        except httpx.HTTPError as exc:
            logger.error("Resend request failed: %s", exc)
            return False

    async def _send_smtp(self, to: str, subject: str, html: str) -> bool:
        if not settings.smtp_host:
            logger.error("SMTP not configured — smtp_host is empty")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = settings.notification_from_email
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.ehlo()
                if server.has_extn("starttls"):
                    server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.notification_from_email, [to], msg.as_string())
            logger.info("Email sent via SMTP to %s", to)
            return True
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("SMTP send failed: %s", exc)
            return False
