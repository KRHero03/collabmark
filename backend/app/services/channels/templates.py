"""Branded HTML email templates matching CollabMark web UI design.

Uses inline CSS and table-based layout for maximum email client compatibility.
Gradient accent (#2563eb -> #7c3aed), Inter font family, clean card layout.
"""

import html as html_mod

from app.config import settings

_FONT_STACK = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"

_BASE_WRAPPER = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:{font_stack};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background-color:#f8fafc;padding:40px 0;">
<tr><td align="center">
<table role="presentation" width="560" cellpadding="0" cellspacing="0"
       style="max-width:560px;width:100%;background:#ffffff;border-radius:16px;
              overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06);">

  <!-- Gradient header -->
  <tr><td style="background:linear-gradient(135deg,#2563eb,#7c3aed);
                  padding:28px 32px;text-align:center;">
    <span style="font-size:22px;font-weight:800;color:#ffffff;
                 letter-spacing:-0.3px;">CollabMark</span>
  </td></tr>

  <!-- Body -->
  <tr><td style="padding:32px 32px 24px;">
    {body}
  </td></tr>

  <!-- CTA -->
  <tr><td style="padding:0 32px 32px;text-align:center;">
    <a href="{cta_url}" target="_blank" rel="noopener"
       style="display:inline-block;padding:12px 32px;
              background:linear-gradient(135deg,#2563eb,#7c3aed);
              color:#ffffff;font-size:15px;font-weight:600;
              text-decoration:none;border-radius:10px;
              letter-spacing:0.2px;">{cta_label}</a>
  </td></tr>

  <!-- Divider -->
  <tr><td style="padding:0 32px;">
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:0;">
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:20px 32px 28px;text-align:center;">
    <p style="margin:0 0 8px;font-size:12px;color:#94a3b8;line-height:1.5;">
      {footer_reason}
    </p>
    <p style="margin:0;font-size:12px;color:#94a3b8;">
      <a href="{frontend_url}" style="color:#64748b;text-decoration:underline;">
        CollabMark</a>
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _build_email(
    *,
    subject: str,
    body_html: str,
    cta_url: str,
    cta_label: str,
    footer_reason: str,
) -> tuple[str, str]:
    """Build a complete HTML email from parts. Returns (subject, html_body)."""
    html = _BASE_WRAPPER.format(
        subject=_esc(subject),
        font_stack=_FONT_STACK,
        body=body_html,
        cta_url=cta_url,
        cta_label=cta_label,
        footer_reason=footer_reason,
        frontend_url=settings.frontend_url,
    )
    return subject, html


def _esc(value: str) -> str:
    """HTML-escape user-supplied values to prevent injection in email templates."""
    return html_mod.escape(value, quote=True)


def render_document_shared(
    *,
    recipient_name: str,
    shared_by: str,
    document_title: str,
    document_id: str,
    permission: str,
) -> tuple[str, str]:
    """Render the 'document shared' email. Returns (subject, html)."""
    safe_shared_by = _esc(shared_by)
    safe_title = _esc(document_title)
    safe_recipient = _esc(recipient_name)
    subject = f'{shared_by} shared "{document_title}" with you'
    perm_label = "edit" if permission == "edit" else "view-only"
    body = (
        f'<p style="margin:0 0 16px;font-size:16px;color:#0f172a;line-height:1.6;">'
        f"Hi {safe_recipient},</p>"
        f'<p style="margin:0 0 16px;font-size:16px;color:#0f172a;line-height:1.6;">'
        f"<strong>{safe_shared_by}</strong> shared a document with you:</p>"
        f'<div style="background:#f1f5f9;border-radius:10px;padding:16px 20px;'
        f'margin:0 0 24px;">'
        f'<p style="margin:0 0 4px;font-size:18px;font-weight:700;color:#0f172a;">'
        f"{safe_title}</p>"
        f'<p style="margin:0;font-size:13px;color:#64748b;">'
        f"You have <strong>{perm_label}</strong> access</p>"
        f"</div>"
    )
    doc_url = f"{settings.frontend_url}/?doc={document_id}"
    return _build_email(
        subject=subject,
        body_html=body,
        cta_url=doc_url,
        cta_label="Open Document",
        footer_reason=("You received this email because someone shared a document with you on CollabMark."),
    )


def render_folder_shared(
    *,
    recipient_name: str,
    shared_by: str,
    folder_name: str,
    folder_id: str,
    permission: str,
) -> tuple[str, str]:
    """Render the 'folder shared' email. Returns (subject, html)."""
    safe_shared_by = _esc(shared_by)
    safe_folder = _esc(folder_name)
    safe_recipient = _esc(recipient_name)
    subject = f'{shared_by} shared the folder "{folder_name}" with you'
    perm_label = "edit" if permission == "edit" else "view-only"
    body = (
        f'<p style="margin:0 0 16px;font-size:16px;color:#0f172a;line-height:1.6;">'
        f"Hi {safe_recipient},</p>"
        f'<p style="margin:0 0 16px;font-size:16px;color:#0f172a;line-height:1.6;">'
        f"<strong>{safe_shared_by}</strong> shared a folder with you:</p>"
        f'<div style="background:#f1f5f9;border-radius:10px;padding:16px 20px;'
        f'margin:0 0 24px;">'
        f'<p style="margin:0 0 4px;font-size:18px;font-weight:700;color:#0f172a;">'
        f"&#128193; {safe_folder}</p>"
        f'<p style="margin:0;font-size:13px;color:#64748b;">'
        f"You have <strong>{perm_label}</strong> access</p>"
        f"</div>"
    )
    folder_url = f"{settings.frontend_url}/?folder={folder_id}"
    return _build_email(
        subject=subject,
        body_html=body,
        cta_url=folder_url,
        cta_label="Open Folder",
        footer_reason="You received this email because someone shared a folder with you on CollabMark.",
    )


def render_comment_added(
    *,
    recipient_name: str,
    commenter: str,
    document_title: str,
    document_id: str,
    comment_preview: str,
) -> tuple[str, str]:
    """Render the 'comment added' email. Returns (subject, html)."""
    safe_commenter = _esc(commenter)
    safe_title = _esc(document_title)
    safe_recipient = _esc(recipient_name)
    subject = f'{commenter} commented on "{document_title}"'
    preview = comment_preview[:150]
    if len(comment_preview) > 150:
        preview += "..."
    safe_preview = _esc(preview)
    body = (
        f'<p style="margin:0 0 16px;font-size:16px;color:#0f172a;line-height:1.6;">'
        f"Hi {safe_recipient},</p>"
        f'<p style="margin:0 0 16px;font-size:16px;color:#0f172a;line-height:1.6;">'
        f"<strong>{safe_commenter}</strong> left a comment on "
        f"<strong>{safe_title}</strong>:</p>"
        f'<div style="background:#f1f5f9;border-radius:10px;padding:16px 20px;'
        f'margin:0 0 24px;border-left:4px solid #7c3aed;">'
        f'<p style="margin:0;font-size:14px;color:#334155;line-height:1.6;'
        f'font-style:italic;">&ldquo;{safe_preview}&rdquo;</p>'
        f"</div>"
    )
    doc_url = f"{settings.frontend_url}/?doc={document_id}"
    return _build_email(
        subject=subject,
        body_html=body,
        cta_url=doc_url,
        cta_label="View Document",
        footer_reason=("You received this email because someone commented on a document you own on CollabMark."),
    )
