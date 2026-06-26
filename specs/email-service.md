# Email Service Spec

## Provider
**Alibaba DirectMail** — transactional email service on Alibaba Cloud.

## SMTP Configuration

| Setting | Value |
|---------|-------|
| Host | `smtpdm.aliyun.com` |
| Port | 465 (SMTPS/SSL) |
| Auth | Username + Password |
| Sender | Configurable via `SMTP_SENDER` env var |

## Environment Variables

```bash
ALIYUN_SMTP_USER=your-smtp-username
ALIYUN_SMTP_PASS=your-smtp-password
SMTP_SENDER=noreply@yourdomain.com
```

## API

```python
def send_email(
    to: str,           # Recipient email
    subject: str,      # Email subject
    body: str,         # Plain text body
    attachment_path: str | None = None,  # Optional PDF attachment
    candidate_id: str | None = None,     # For audit logging
) -> str:              # Returns Message-ID
```

## Email Format

- **Content-Type**: multipart/mixed (text + optional PDF attachment)
- **Body**: Plain text, UTF-8 encoded
- **Attachment**: PDF (candidate's resume), base64 encoded

### Draft Template
```
To: {recruiter_email}
Subject: Application: {candidate_name} for {job_title}

Dear Recruiter,

I am writing to express my interest in the {job_title} position
at {company}.

[Highlight relevant experience]
[Summarize screening answers]

Best regards,
{candidate_name}
```

## Retry Logic

On failure, retry up to 3 times with exponential backoff:

| Attempt | Wait Time | Cumulative |
|---------|-----------|------------|
| 1 | immediate | 0s |
| 2 | 1 second | 1s |
| 3 | 4 seconds | 5s |
| 4 | 16 seconds | 21s |

On final failure: raise `EmailSendError`, log to audit with `status="failed"`.

## Error Handling

```python
try:
    message_id = send_email(to, subject, body, candidate_id=candidate_id)
    # Log success to audit
    return {"status": "sent", "message_id": message_id}
except EmailSendError as e:
    # Log failure to audit
    return {"status": "failed", "error": str(e)}
```

## Audit Logging

Every email attempt is logged:

**Success**:
```json
{
  "action": "email_sent",
  "candidate_id": "...",
  "details": {
    "to": "recruiter@company.com",
    "subject": "Application: ...",
    "message_id": "abc123@directmail"
  },
  "status": "sent"
}
```

**Failure**:
```json
{
  "action": "email_failed",
  "candidate_id": "...",
  "details": {
    "to": "recruiter@company.com",
    "subject": "Application: ...",
    "error": "Authentication failed"
  },
  "status": "failed"
}
```

## Setup Checklist

1. Create Alibaba Cloud account
2. Enable DirectMail service (Singapore region)
3. Add and verify sender domain
4. Create SMTP credentials
5. Send test email via console
6. Store credentials in environment variables

## Fallback

If DirectMail is unavailable:
- Use `smtp.gmail.com` with app password for testing
- This works for demo but disqualifies the "Alibaba Cloud deployment" claim for email
- Keep all other Alibaba Cloud services as deployment proof
