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
        self.round_robin_index = 0
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
                    logger.info(f"Loaded active Gmail inbox ({self.mode}): {email}")
                    loaded = True
                    break
                except Exception as e:
                    logger.warning(f"Could not load account from {acc_path}: {e}")

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

    def get_next_available_account(self, per_account_cap: int = DAILY_SEND_LIMIT) -> Optional[Dict[str, Any]]:
        """
        True Round-Robin Load Balancer.
        Selects the next active account that is under its daily cap (50/day) and not throttled by Google.
        Cycles evenly across all connected accounts in the active pool.
        """
        account_list = [acc for acc in self.get_all_accounts() if acc["email"] not in self.throttled_inboxes]
        if not account_list:
            logger.warning(f"No available inboxes in '{self.mode}' pool (all throttled or cap reached).")
            return None

        total_accounts = len(account_list)

        # Check accounts starting from current round-robin index
        for i in range(total_accounts):
            idx = (self.round_robin_index + i) % total_accounts
            candidate = account_list[idx]
            sent_today = self.get_account_sent_today_count(candidate["email"])
            
            if sent_today < per_account_cap:
                # Advance round-robin pointer for next send
                self.round_robin_index = (idx + 1) % total_accounts
                return candidate

        logger.warning(f"All {total_accounts} inboxes in '{self.mode}' pool hit their {per_account_cap}/day limit!")
        return None

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
        """Sends an email using the next available round-robin Gmail account.
        strict_sender=True: send ONLY from from_account_email, never fall back or fail over to another inbox."""
        if strict_sender and from_account_email not in self.accounts:
            logger.error(f"Strict sender {from_account_email} is not connected, refusing to send.")
            self.last_failure = "no_capacity"
            return None
        if from_account_email and from_account_email in self.accounts:
            acc = self.accounts[from_account_email]
        else:
            acc = self.get_next_available_account()

        if not acc:
            logger.error("No available Gmail accounts with remaining daily quota.")
            self.last_failure = "no_capacity"
            return None

        service = acc["service"]
        sender_email = acc["email"]
        sent_today = self.get_account_sent_today_count(sender_email)

        import email.utils
        message = MIMEText(body_text, "plain", "utf-8")
        message["To"] = to_email
        message["From"] = f"{SENDER_NAME} <{sender_email}>"
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
            logger.info(f"Dispatched email to {to_email} via [{sender_email}] (Today: {sent_today + 1}/50) | Msg ID: {sent_msg.get('id')}")
            return {
                "message_id": sent_msg.get("id"),
                "thread_id": sent_msg.get("threadId"),
                "from_email": sender_email
            }
        except Exception as e:
            err_str = str(e).lower()
            if any(term in err_str for term in ["limit", "quota", "blocked", "rate limit", "exceeded"]):
                self.throttled_inboxes.add(sender_email)
                if strict_sender:
                    logger.warning(f"[INBOX THROTTLED] {sender_email} hit a Google limit. Strict sender, not failing over.")
                    self.last_failure = "no_capacity"
                    return None
                logger.warning(f"[INBOX THROTTLED] Google limit reached on [{sender_email}]. Pausing inbox and routing to next available inbox...")
                # Automatic failover: retry sending via another healthy inbox
                return self.send_email(
                    to_email=to_email,
                    subject=subject,
                    body_text=body_text,
                    from_account_email=None,
                    thread_id=thread_id,
                    in_reply_to=in_reply_to
                )
            logger.error(f"Failed to send email to {to_email} via {sender_email}: {e}")
            self.last_failure = "rejected"
            return None

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
