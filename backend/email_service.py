"""
Email intake (IMAP) and outbound delivery (SMTP) service.
Supports both real IMAP/SMTP connections (e.g. Gmail) and instant virtual intake/mocking
for zero-friction demonstrations and tests.
"""

import os
import email
from email.header import decode_header
import imaplib
import smtplib
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from backend.database import get_db, log_audit

load_dotenv()

IMAP_SERVER = os.environ.get("EMAIL_IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.environ.get("EMAIL_IMAP_PORT", "993"))
SMTP_SERVER = os.environ.get("EMAIL_SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
EMAIL_USER = os.environ.get("EMAIL_USERNAME", "")
EMAIL_PASS = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Tech Zephyr Support")


def _clean_header(header_val: Any) -> str:
    if not header_val:
        return ""
    decoded_parts = decode_header(header_val)
    header_text = ""
    for part, enc in decoded_parts:
        if isinstance(part, bytes):
            header_text += part.decode(enc or "utf-8", errors="replace")
        else:
            header_text += str(part)
    return header_text


def fetch_new_emails() -> List[Dict[str, Any]]:
    """
    Connect to IMAP server if credentials are configured,
    fetch unread messages, store them into inbound_emails, mark as read,
    and return list of newly ingested email records.
    """
    ingested_emails = []

    # Check if live credentials are configured and not placeholders
    has_live_credentials = (
        EMAIL_USER
        and EMAIL_PASS
        and "example.com" not in EMAIL_USER
        and "your_app_password" not in EMAIL_PASS
    )

    if has_live_credentials:
        try:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            mail.login(EMAIL_USER, EMAIL_PASS)
            mail.select("INBOX")

            status, search_data = mail.search(None, "UNSEEN")
            if status == "OK" and search_data[0]:
                for num in search_data[0].split():
                    status, msg_data = mail.fetch(num, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    sender = _clean_header(msg.get("From"))
                    # Extract email from format "Name <email@domain>"
                    if "<" in sender and ">" in sender:
                        sender_email = sender.split("<")[1].split(">")[0].strip()
                    else:
                        sender_email = sender.strip()

                    subject = _clean_header(msg.get("Subject"))
                    message_id = msg.get("Message-ID", f"msg_{uuid.uuid4().hex[:12]}")

                    # Extract body text
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                                break
                    else:
                        body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

                    # Mark as read
                    mail.store(num, "+FLAGS", "\\Seen")

                    record = {
                        "email_id": message_id,
                        "sender_email": sender_email,
                        "subject": subject,
                        "body": body.strip(),
                        "received_at": datetime.now().isoformat()
                    }
                    _save_inbound_email(record)
                    ingested_emails.append(record)

            mail.close()
            mail.logout()
        except Exception as e:
            print(f"[EmailService] IMAP poll warning: {e}")

    # Also check unread emails in DB (for virtual/simulated intake)
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT email_id, sender_email, subject, body, received_at FROM inbound_emails WHERE processed = 0"
        )
        for row in cursor.fetchall():
            rec = dict(row)
            if rec not in ingested_emails:
                ingested_emails.append(rec)

    return ingested_emails


def simulate_inbound_email(sender_email: str, subject: str, body: str) -> Dict[str, Any]:
    """
    Directly inject an email into inbound_emails for testing/demo without needing live IMAP credentials.
    """
    record = {
        "email_id": f"sim_email_{uuid.uuid4().hex[:10]}",
        "sender_email": sender_email,
        "subject": subject,
        "body": body,
        "received_at": datetime.now().isoformat()
    }
    _save_inbound_email(record)
    return record


def _save_inbound_email(record: Dict[str, Any]):
    """Save raw copy of inbound email in DB."""
    with get_db() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO inbound_emails 
               (email_id, sender_email, subject, body, received_at, processed) 
               VALUES (?, ?, ?, ?, ?, 0)""",
            (
                record["email_id"],
                record["sender_email"],
                record["subject"],
                record["body"],
                record["received_at"],
            )
        )


def mark_email_processed(email_id: str, case_id: str):
    """Mark an inbound email as processed and link to case_id."""
    with get_db() as conn:
        conn.execute(
            "UPDATE inbound_emails SET processed = 1, case_id = ? WHERE email_id = ?",
            (case_id, email_id)
        )


def send_email(
    to: str,
    subject: str,
    body: str,
    case_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    tone: Optional[str] = "reassuring"
) -> Dict[str, Any]:
    """
    Send outbound reply email to customer:
    - Sets In-Reply-To / References headers for email client threading.
    - Sends via SMTP if credentials are configured.
    - Records in outbound_emails table.
    - Logs to audit_log.
    """
    email_id = f"out_msg_{uuid.uuid4().hex[:12]}"
    sent_via_smtp = False

    has_live_smtp = (
        EMAIL_USER
        and EMAIL_PASS
        and "example.com" not in EMAIL_USER
        and "your_app_password" not in EMAIL_PASS
    )

    if has_live_smtp:
        try:
            msg = MIMEMultipart()
            msg["From"] = f"{EMAIL_FROM_NAME} <{EMAIL_USER}>"
            msg["To"] = to
            msg["Subject"] = subject
            msg["Message-ID"] = f"<{email_id}@{SMTP_SERVER}>"

            if in_reply_to:
                msg["In-Reply-To"] = in_reply_to
                msg["References"] = in_reply_to

            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(EMAIL_USER, EMAIL_PASS)
                server.send_message(msg)
                sent_via_smtp = True
        except Exception as e:
            print(f"[EmailService] SMTP send warning: {e}")

    # Record in outbound_emails
    with get_db() as conn:
        conn.execute(
            """INSERT INTO outbound_emails 
               (email_id, case_id, recipient_email, subject, body, tone, sent_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (email_id, case_id, to, subject, body, tone, datetime.now().isoformat())
        )

    log_audit(
        case_id,
        "Agent7Reply",
        "send_email",
        {
            "email_id": email_id,
            "to": to,
            "subject": subject,
            "sent_via_smtp": sent_via_smtp,
            "tone": tone
        }
    )

    return {
        "sent": True,
        "email_id": email_id,
        "sent_via_smtp": sent_via_smtp,
        "to": to,
        "subject": subject,
        "body": body
    }
