from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from outreach_app.config import settings


class SMTPConfigError(RuntimeError):
    pass


def send_smtp(msg: EmailMessage) -> str:
    """Sends email via SMTP. Returns a provider message id if available.

    Raises:
        SMTPConfigError: if any required SMTP settings are missing.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASS:
        raise SMTPConfigError("Missing SMTP settings. Please configure SMTP_HOST/SMTP_USER/SMTP_PASS in .env")

    from_email = settings.SMTP_FROM or settings.SMTP_USER
    # Ensure From header present (avoid duplicates)
    if msg.get("From") != from_email:
        msg["From"] = from_email

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
        server.ehlo()
        if settings.SMTP_USE_TLS:
            server.starttls(context=context)
            server.ehlo()
        server.login(settings.SMTP_USER, settings.SMTP_PASS)
        server.send_message(msg)
        # smtplib doesn't expose message-id reliably; return empty on success
        return ""
