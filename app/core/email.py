import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import boto3

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_via_ses(to: str, subject: str, body: str, html: str | None = None):
    ses = boto3.client(
        "ses",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    message: dict = {
        "Subject": {"Data": subject, "Charset": "UTF-8"},
        "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
    }
    if html:
        message["Body"]["Html"] = {"Data": html, "Charset": "UTF-8"}

    ses.send_email(
        Source=settings.SES_SENDER_EMAIL,
        Destination={"ToAddresses": [to]},
        Message=message,
    )
    logger.info(f"[EMAIL] SES sent to {to}: {subject}")


def _send_via_smtp(to: str, subject: str, body: str, html: str | None = None):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(body, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, [to], msg.as_string())
    logger.info(f"[EMAIL] SMTP sent to {to}: {subject}")


def send_email(to: str, subject: str, body: str, html: str | None = None):
    """
    Send email via SES API (preferred) or SMTP fallback.
    Priority: SES_SENDER_EMAIL → SMTP_HOST → console log.
    """
    try:
        if settings.SES_SENDER_EMAIL:
            _send_via_ses(to, subject, body, html)
        elif settings.SMTP_HOST:
            _send_via_smtp(to, subject, body, html)
        else:
            _log_email(to, subject, body)
    except Exception as e:
        logger.warning(f"[EMAIL] Failed ({e}), logging instead")
        _log_email(to, subject, body)


def _log_email(to: str, subject: str, body: str):
    logger.info(
        f"[EMAIL STUB] To: {to} | Subject: {subject} | Body: {body[:200]}"
    )
