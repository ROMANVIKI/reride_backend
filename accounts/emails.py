"""Transactional e-mail helpers (OTP delivery and internal notifications)."""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail

logger = logging.getLogger(__name__)


_BASE_STYLE = """
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  background:#f5f4ef; color:#15181a; margin:0; padding:32px 16px;
"""


def _wrap(title, body_html):
    return f"""<!doctype html>
<html><body style="{_BASE_STYLE}">
  <div style="max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #dcd9d0;">
    <div style="background:#1f4d3a;padding:20px 28px;">
      <span style="color:#ffffff;font-size:18px;font-weight:600;letter-spacing:-0.02em;">
        SriBalajiBikes
      </span>
    </div>
    <div style="padding:28px;">
      <h1 style="margin:0 0 16px;font-size:20px;font-weight:600;">{title}</h1>
      {body_html}
    </div>
    <div style="padding:18px 28px;border-top:1px solid #dcd9d0;color:#6b7178;font-size:12px;">
      You are receiving this because someone used this address on SriBalajiBikes.
      If that wasn't you, you can ignore this e-mail.
    </div>
  </div>
</body></html>"""


def _code_block(code):
    return (
        f'<div style="margin:20px 0;padding:16px;background:#f5f4ef;border:1px solid #dcd9d0;'
        f'text-align:center;font-family:monospace;font-size:30px;letter-spacing:10px;'
        f'font-weight:600;color:#1f4d3a;">{code}</div>'
    )


_PURPOSE_COPY = {
    "register": (
        "Verify your e-mail address",
        "Thanks for signing up. Use the code below to finish creating your "
        "SriBalajiBikes account.",
    ),
    "password_reset": (
        "Reset your password",
        "We received a request to reset your password. Use the code below to "
        "set a new one.",
    ),
    "email_change": (
        "Confirm your new e-mail address",
        "Use the code below to confirm this address on your SriBalajiBikes "
        "account.",
    ),
}


def send_otp_email(otp):
    """Send a one-time password. Returns True when the send succeeded."""
    title, intro = _PURPOSE_COPY.get(otp.purpose, _PURPOSE_COPY["register"])
    ttl = settings.OTP_TTL_MINUTES

    html = _wrap(
        title,
        f'<p style="margin:0;font-size:15px;line-height:1.6;color:#2a2f33;">{intro}</p>'
        + _code_block(otp.code)
        + f'<p style="margin:0;font-size:13px;color:#6b7178;">This code expires in '
        f"{ttl} minutes and can only be used once.</p>",
    )
    text = f"{title}\n\n{intro}\n\nYour code: {otp.code}\n\nIt expires in {ttl} minutes."

    try:
        message = EmailMultiAlternatives(
            subject=f"{otp.code} is your SriBalajiBikes code",
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[otp.email],
        )
        message.attach_alternative(html, "text/html")
        message.send(fail_silently=False)
        return True
    except Exception:
        # A mail outage should never break registration — the user can retry
        # with "resend code" once mail is restored.
        logger.exception("Failed to send OTP e-mail to %s", otp.email)
        return False


def send_welcome_email(user):
    html = _wrap(
        "Your account is ready",
        f'<p style="margin:0;font-size:15px;line-height:1.6;color:#2a2f33;">'
        f"Hi {user.get_short_name()}, your e-mail is verified and your account "
        f"is live. You can now post listings, save favourites, book test rides "
        f"and track your enquiries.</p>"
        f'<p style="margin:20px 0 0;"><a href="{settings.FRONTEND_URL}/dashboard" '
        f'style="background:#1f4d3a;color:#ffffff;padding:12px 20px;'
        f'text-decoration:none;font-size:14px;display:inline-block;">'
        f"Go to your dashboard</a></p>",
    )
    try:
        message = EmailMultiAlternatives(
            subject="Welcome to SriBalajiBikes",
            body=(
                f"Hi {user.get_short_name()}, your account is verified and ready. "
                f"Visit {settings.FRONTEND_URL}/dashboard to get started."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        message.attach_alternative(html, "text/html")
        message.send(fail_silently=True)
    except Exception:
        logger.exception("Failed to send welcome e-mail to %s", user.email)


def notify_team(subject, body):
    """Ping the internal team about a new lead. No-op if NOTIFY_EMAILS is blank."""
    recipients = [e for e in getattr(settings, "NOTIFY_EMAILS", []) if e]
    if not recipients:
        return
    try:
        send_mail(
            subject=f"[SriBalajiBikes] {subject}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=True,
        )
    except Exception:
        logger.exception("Failed to send team notification: %s", subject)
