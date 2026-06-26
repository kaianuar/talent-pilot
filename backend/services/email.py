"""Email service using Alibaba DirectMail SMTP."""

import logging
import smtplib
import time
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from backend.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_SENDER
from backend.db import log_audit

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 1  # seconds


class EmailSendError(Exception):
    """Raised when email sending fails after retries."""
    pass


def send_email(
    to: str,
    subject: str,
    body: str,
    attachment_path: str | Path | None = None,
    candidate_id: str | None = None,
) -> str:
    """Send an email via Alibaba DirectMail SMTP.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain text body.
        attachment_path: Optional path to a PDF attachment.
        candidate_id: For audit logging.

    Returns:
        The Message-ID of the sent email.

    Raises:
        EmailSendError: If sending fails after retries.
    """
    if not SMTP_USER or not SMTP_PASS:
        log_audit(
            action="email_not_configured",
            candidate_id=candidate_id,
            details={"to": to, "subject": subject, "reason": "SMTP credentials not set"},
            status="skipped",
        )
        raise EmailSendError(
            "Email service not configured. To enable email sending, set ALIYUN_SMTP_USER "
            "and ALIYUN_SMTP_PASS in your environment. See specs/email-service.md for setup instructions."
        )

    msg = MIMEMultipart()
    msg["From"] = SMTP_SENDER
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachment_path:
        path = Path(attachment_path)
        if path.exists():
            with open(path, "rb") as f:
                part = MIMEBase("application", "pdf")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
                msg.attach(part)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
                # Extract message ID from the sent message
                message_id = msg.get("Message-ID", str(uuid.uuid4()))
                logger.info("Email sent to %s, Message-ID: %s", to, message_id)
                log_audit(
                    action="email_sent",
                    candidate_id=candidate_id,
                    details={"to": to, "subject": subject, "message_id": message_id},
                    status="sent",
                )
                return message_id
        except Exception as e:
            last_error = e
            wait = BACKOFF_BASE * (4 ** attempt)  # 1s, 4s, 16s
            logger.warning("Email send attempt %d failed: %s. Retrying in %ds.", attempt + 1, e, wait)
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)

    log_audit(
        action="email_failed",
        candidate_id=candidate_id,
        details={"to": to, "subject": subject, "error": str(last_error)},
        status="failed",
    )
    raise EmailSendError(f"Failed to send email after {MAX_RETRIES} attempts: {last_error}")
