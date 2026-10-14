import os
import base64
import logging
import sqlite3
from pathlib import Path
from email.mime.text import MIMEText
from typing import Optional, Dict, Any, List, Tuple
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from safety import mask_email, mask_emails_in
from config import GMAIL_CREDENTIALS_FILE, GMAIL_TOKEN_FILE, SENDER_NAME, DB_PATH, DAILY_SEND_LIMIT, AUTHOR_INBOXES, DISABLED_INBOXES

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

ACCOUNTS_DIR = Path("accounts")

class MultiGmailService:
    """
    Manages a pool of authenticated Gmail inboxes with strict round-robin load balancing,
    hard per-account daily caps (50/day per account), and dedicated workflow mode partitioning (Author vs B2B).
    """

    def __init__(self, db_path: str = DB_PATH, mode: str = "all"):
        self.db_path = db_path
        self.mode = mode  # "all", "author", "b2b"
        self.accounts: Dict[str, Any] = {}
        self.throttled_inboxes: set = set()
        self.last_failure = None  # 'no_capacity' or 'rejected'
        self._load_all_accounts()

    def _load_all_accounts(self):
        """Loads all connected accounts from accounts/ directory."""
        if not ACCOUNTS_DIR.exists():
            ACCOUNTS_DIR.mkdir(exist_ok=True)

        account_files = sorted(list(ACCOUNTS_DIR.glob("*.json")))
        
        # Fallback to single token.json if accounts dir is empty
        if not account_files and os.path.exists(GMAIL_TOKEN_FILE):
            account_files = [Path(GMAIL_TOKEN_FILE)]

        for acc_path in account_files:
            acc_email = acc_path.stem.strip().lower()
            if acc_email in [d.strip().lower() for d in DISABLED_INBOXES]:
                continue
            if self.mode == "author" and acc_email not in AUTHOR_INBOXES:
                continue
            if self.mode == "b2b" and acc_email in AUTHOR_INBOXES:
                continue

            loaded = False
            for attempt in range(2):
                try:
                    creds = Credentials.from_authorized_user_file(str(acc_path), SCOPES)
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                        with open(acc_path, "w") as f:
                            f.write(creds.to_json())

                    service = build("gmail", "v1", credentials=creds, static_discovery=True)
                    email = acc_path.stem.strip()
                    
                    self.accounts[email] = {
                        "service": service,
                        "email": email,
                        "token_file": str(acc_path)
                    }
                    logger.info(f"Loaded active Gmail inbox ({self.mode}): {mask_email(email)}")
                    loaded = True
                    break
                except Exception as e:
                    logger.warning(f"Could not load account {mask_email(acc_path.stem)}: {type(e).__name__}")

        # Mailboxes on your own domain (SMTP + IMAP). They win over a Gmail token with the same address.
        from sender import smtp_mailbox
        try:
            smtp_accounts = smtp_mailbox.load_accounts()
        except Exception as e:
            smtp_accounts = {}
            logger.warning(f"SMTP_ACCOUNTS_JSON could not be read: {type(e).__name__}")
        for email_addr, cfg in smtp_accounts.items():
            if email_addr in [d.strip().lower() for d in DISABLED_INBOXES]:
                continue
            self.accounts[email_addr] = {"type": "smtp", "email": email_addr, "cfg": cfg}
            logger.info(f"Loaded own-domain mailbox: {mask_email(email_addr)}")

    def get_account_sent_today_count(self, account_email: str) -> int:
        """Returns how many emails this specific inbox has sent today."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM sequences
                WHERE sender_inbox = ? AND DATE(last_sent_at) = DATE('now')
            """, (account_email,))
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """Returns active accounts filtered by workflow mode (Author vs B2B)."""
        if not self.accounts:
            self._load_all_accounts()
        accs = list(self.accounts.values())
        if self.mode == "author":
            filtered = [a for a in accs if a["email"].lower() in AUTHOR_INBOXES]
            return filtered if filtered else accs
        elif self.mode == "b2b":
            filtered = [a for a in accs if a["email"].lower() not in AUTHOR_INBOXES]
            return filtered if filtered else accs
        return accs

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        from_account_email: Optional[str] = None,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        strict_sender: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Sends an email from exactly one named mailbox.
        There is no round-robin and no failover: if from_account_email is missing, not connected
        or throttled, nothing is sent. strict_sender is kept for older callers and has no effect."""
        if not from_account_email or from_account_email not in self.accounts:
            logger.error(f"Sender {mask_email(from_account_email) or '(none given)'} is not connected, refusing to send.")
            self.last_failure = "no_capacity"
            return None
        if from_account_email in self.throttled_inboxes:
            logger.warning(f"{mask_email(from_account_email)} hit a Google limit earlier in this run, not sending.")
            self.last_failure = "no_capacity"
            return None
        acc = self.accounts[from_account_email]
        if acc.get("type") == "smtp":
            return self._send_smtp(acc, to_email, subject, body_text, in_reply_to)

        service = acc["service"]
        sender_email = acc["email"]

        import email.utils
        message = MIMEText(body_text, "plain", "utf-8")
        message["To"] = to_email
        message["From"] = email.utils.formataddr((SENDER_NAME, sender_email))  # encodes accented names correctly
        message["Subject"] = subject
        message["Date"] = email.utils.formatdate(localtime=True)
        message["Message-ID"] = email.utils.make_msgid(domain="gmail.com")
        message["MIME-Version"] = "1.0"

        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
            message["References"] = in_reply_to

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        body = {"raw": raw_message}
        if thread_id:
            body["threadId"] = thread_id

        self.last_failure = None
        try:
            sent_msg = service.users().messages().send(userId="me", body=body).execute()
            logger.info(f"Dispatched email to {mask_email(to_email)} via [{mask_email(sender_email)}]")
            return {
                "message_id": sent_msg.get("id"),
                "thread_id": sent_msg.get("threadId"),
                "from_email": sender_email
            }
        except Exception as e:
            err_str = str(e).lower()
            if any(term in err_str for term in ["limit", "quota", "blocked", "rate limit", "exceeded"]):
                self.throttled_inboxes.add(sender_email)
                logger.warning(f"[INBOX THROTTLED] {mask_email(sender_email)} hit a Google limit. Stopping, no failover to other inboxes.")
                self.last_failure = "no_capacity"
                return None
            logger.error(f"Failed to send email to {mask_email(to_email)}: {mask_emails_in(str(e))[:200]}")
            self.last_failure = "rejected"
            return None

    def _send_smtp(self, acc, to_email, subject, body_text, in_reply_to):
        from sender import smtp_mailbox
        self.last_failure = None
        try:
            msg_id = smtp_mailbox.send(acc["cfg"], acc["email"], SENDER_NAME, to_email, subject, body_text, in_reply_to)
        except smtp_mailbox.SendLimited as e:
            self.throttled_inboxes.add(acc["email"])
            logger.warning(f"[MAILBOX PAUSED] {mask_email(acc['email'])}: {e}. Stopping this run.")
            self.last_failure = "no_capacity"
            return None
        except Exception as e:
            logger.error(f"Failed to send email to {mask_email(to_email)}: {mask_emails_in(str(e))[:200]}")
            self.last_failure = "rejected"
            return None
        logger.info(f"Dispatched email to {mask_email(to_email)} via [{mask_email(acc['email'])}]")
        # For own-domain mailboxes the thread id IS the Message-ID: replies and bounces are matched on it.
        return {"message_id": msg_id, "thread_id": msg_id, "from_email": acc["email"]}

    def check_all_inboxes_for_replies(self) -> List[Dict[str, Any]]:
        """Scans all connected inboxes for replies and bounces with strict filtering."""
        events = []
        bounce_senders = ["mailer-daemon", "postmaster", "mail delivery subsystem", "daemon@", "googlemail.com", "noreply", "no-reply"]
        bounce_subjects = ["delivery status notification", "failure notice", "undelivered mail", "returned to sender", "address not found", "could not be delivered", "delivery failed"]
        bounce_snippets = ["550 5.1.1", "550", "address not found", "recipient address rejected", "user unknown", "does not exist", "unable to receive mail", "wasn't delivered", "message rejected", "mailbox unavailable"]

        import time
        now_ms = time.time() * 1000
        # Only check throttle messages from the last 18 hours (18 * 3600 * 1000 ms)
        MAX_THROTTLE_AGE_MS = 18 * 3600 * 1000

        for email, acc in self.accounts.items():
            if email in self.throttled_inboxes:
                continue
            service = acc["service"]
            try:
                threads_res = service.users().threads().list(userId="me", maxResults=25).execute()
                for t in threads_res.get("threads", []):
                    thread = service.users().threads().get(userId="me", id=t["id"]).execute()
                    messages = thread.get("messages", [])
                    if len(messages) > 1:
                        last_msg = messages[-1]
                        headers = {h["name"].lower(): h["value"] for h in last_msg.get("payload", {}).get("headers", [])}
                        from_hdr = headers.get("from", "").lower()
                        subject_hdr = headers.get("subject", "").lower()
                        snippet = last_msg.get("snippet", "").lower()
                        msg_date_ms = int(last_msg.get("internalDate", 0))

                        # 1. Google Sending Limit / Throttle Notice Check (Active in last 18h)
                        is_throttle_msg = any(t in snippet for t in ["reached a limit for sending mail", "message blocked", "sending limit"])
                        if is_throttle_msg and (now_ms - msg_date_ms < MAX_THROTTLE_AGE_MS):
                            self.throttled_inboxes.add(email)
                            logger.warning(f"[INBOX THROTTLED] Google limit detected on [{email}]. Pausing this inbox for today.")
                            events.append({"type": "throttle", "account": email, "reason": snippet})
                            # Break checking further threads for this inbox to prevent spamming logs
                            break

                        # 2. Strict Bounce & Delivery Failure Check
                        is_bounce = (
                            any(b in from_hdr for b in bounce_senders) or
                            any(b in subject_hdr for b in bounce_subjects) or
                            any(b in snippet for b in bounce_snippets)
                        )

                        if is_bounce:
                            events.append({"type": "bounce", "thread_id": t["id"], "account": email, "from": from_hdr, "snippet": snippet})
                        elif email.lower() not in from_hdr:
                            # 3. Genuine Human Reply
                            events.append({"type": "reply", "thread_id": t["id"], "account": email, "from": from_hdr, "snippet": last_msg.get("snippet", "")})
            except Exception as e:
                logger.warning(f"Error checking inbox {email}: {e}")
        return events

GmailService = MultiGmailService
