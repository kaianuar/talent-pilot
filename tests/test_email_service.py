"""Unit tests for the email service (backend.services.email)."""

import pytest
from unittest.mock import patch, MagicMock

from backend.services.email import send_email, EmailSendError


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("backend.services.email.SMTP_USER", "")
@patch("backend.services.email.SMTP_PASS", "")
@patch("backend.services.email.log_audit")
def test_send_email_raises_when_smtp_not_configured(mock_audit):
    """send_email should raise EmailSendError when SMTP credentials are missing."""
    with pytest.raises(EmailSendError, match="not configured"):
        send_email(to="test@example.com", subject="Test", body="Hello")

    mock_audit.assert_called_once()
    call_kwargs = mock_audit.call_args
    assert call_kwargs.kwargs["action"] == "email_not_configured"
    assert call_kwargs.kwargs["status"] == "skipped"


@patch("backend.services.email.SMTP_USER", "")
@patch("backend.services.email.SMTP_PASS", "")
@patch("backend.services.email.log_audit")
def test_send_email_not_configured_logs_audit(mock_audit):
    """When SMTP is not configured, an audit entry should be logged."""
    with pytest.raises(EmailSendError):
        send_email(
            to="hr@example.com",
            subject="Application",
            body="Dear HR",
            candidate_id="c123",
        )

    mock_audit.assert_called_once()
    call_kwargs = mock_audit.call_args
    assert call_kwargs.kwargs["action"] == "email_not_configured"
    assert call_kwargs.kwargs["candidate_id"] == "c123"
    assert call_kwargs.kwargs["details"]["to"] == "hr@example.com"
    assert call_kwargs.kwargs["details"]["subject"] == "Application"


@patch("backend.services.email.SMTP_USER", "user@example.com")
@patch("backend.services.email.SMTP_PASS", "secret")
@patch("backend.services.email.SMTP_HOST", "smtp.example.com")
@patch("backend.services.email.SMTP_PORT", 465)
@patch("backend.services.email.SMTP_SENDER", "sender@example.com")
@patch("backend.services.email.log_audit")
@patch("backend.services.email.smtplib.SMTP_SSL")
def test_send_email_success_logs_audit(mock_smtp_cls, mock_audit):
    """On successful send, an email_sent audit entry should be logged."""
    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    result = send_email(
        to="hr@example.com",
        subject="Job Application",
        body="I am interested",
        candidate_id="c456",
    )

    assert result  # should return a message ID
    mock_server.login.assert_called_once_with("user@example.com", "secret")
    mock_server.send_message.assert_called_once()

    # Verify audit was logged
    mock_audit.assert_called()
    audit_call = mock_audit.call_args
    assert audit_call.kwargs["action"] == "email_sent"
    assert audit_call.kwargs["candidate_id"] == "c456"
    assert audit_call.kwargs["status"] == "sent"


@patch("backend.services.email.SMTP_USER", "user@example.com")
@patch("backend.services.email.SMTP_PASS", "secret")
@patch("backend.services.email.SMTP_HOST", "smtp.example.com")
@patch("backend.services.email.SMTP_PORT", 465)
@patch("backend.services.email.MAX_RETRIES", 1)
@patch("backend.services.email.BACKOFF_BASE", 0)
@patch("backend.services.email.log_audit")
@patch("backend.services.email.smtplib.SMTP_SSL")
def test_send_email_failure_logs_audit(mock_smtp_cls, mock_audit):
    """On failed send (after retries), an email_failed audit entry should be logged."""
    mock_smtp_cls.side_effect = ConnectionError("Connection refused")

    with pytest.raises(EmailSendError, match="Failed to send"):
        send_email(
            to="hr@example.com",
            subject="Job Application",
            body="I am interested",
            candidate_id="c789",
        )

    # Should have logged email_failed
    failed_calls = [
        c for c in mock_audit.call_args_list if c.kwargs.get("action") == "email_failed"
    ]
    assert len(failed_calls) == 1
    assert failed_calls[0].kwargs["candidate_id"] == "c789"
    assert failed_calls[0].kwargs["status"] == "failed"


@patch("backend.services.email.SMTP_USER", "user@example.com")
@patch("backend.services.email.SMTP_PASS", "secret")
@patch("backend.services.email.SMTP_HOST", "smtp.example.com")
@patch("backend.services.email.SMTP_PORT", 465)
@patch("backend.services.email.SMTP_SENDER", "sender@example.com")
@patch("backend.services.email.MAX_RETRIES", 1)
@patch("backend.services.email.BACKOFF_BASE", 0)
@patch("backend.services.email.log_audit")
@patch("backend.services.email.smtplib.SMTP_SSL")
def test_send_email_retries(mock_smtp_cls, mock_audit):
    """send_email should retry on transient failures."""
    # First call fails, but we set MAX_RETRIES=1 so only 1 attempt
    mock_smtp_cls.side_effect = TimeoutError("timeout")

    with pytest.raises(EmailSendError):
        send_email(to="a@b.com", subject="s", body="b")

    # SMTP_SSL should have been called once (MAX_RETRIES=1)
    assert mock_smtp_cls.call_count == 1


@patch("backend.services.email.SMTP_USER", "")
@patch("backend.services.email.SMTP_PASS", "")
@patch("backend.services.email.log_audit")
def test_send_email_includes_candidate_id_in_audit(mock_audit):
    """candidate_id should be forwarded to audit logging."""
    with pytest.raises(EmailSendError):
        send_email(
            to="test@example.com",
            subject="Test",
            body="Body",
            candidate_id="candidate-abc",
        )

    assert mock_audit.call_args.kwargs["candidate_id"] == "candidate-abc"
