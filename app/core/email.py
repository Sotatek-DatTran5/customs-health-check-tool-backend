import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str, html: str | None = None):
    """
    Send email via SMTP (MailHog in dev, real SMTP in prod).
    Falls back to console log if SMTP not configured.
    """
    if not settings.SMTP_HOST:
        _log_email(to, subject, body)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to

    # Always attach plain text
    msg.attach(MIMEText(body, "plain"))

    # Attach HTML if provided
    if html:
        msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [to], msg.as_string())
        logger.info(f"[EMAIL] Sent to {to}: {subject}")
    except Exception as e:
        logger.warning(f"[EMAIL] SMTP failed ({e}), logging instead")
        _log_email(to, subject, body)


def _log_email(to: str, subject: str, body: str):
    logger.info(
        f"[EMAIL STUB] To: {to} | Subject: {subject} | Body: {body[:200]}"
    )
