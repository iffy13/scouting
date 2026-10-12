import os
import sys
import time
import asyncio
import uuid
import random
import logging
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from config import BASE_DIR, SENDER_NAME, DISABLED_INBOXES, AUTHOR_INBOXES

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

ACCOUNTS_DIR = BASE_DIR / "accounts"

NATURAL_SEED_TOPICS = [
    {
        "subject": "Quick check on the project updates",
        "body": "Hi there,\n\nFollowing up on our discussion from yesterday regarding the project milestone and schedule. Let me know when you have a moment to connect.\n\nBest regards,\nAlex"
    },
    {
        "subject": "Question about our meeting timeline",
        "body": "Hi,\n\nHope your week is going well. Just wanted to touch base regarding the timeline we discussed earlier. Let me know if that timeframe still works for you.\n\nBest,\nAlex"
    },
    {
        "subject": "Follow up regarding our conversation",
        "body": "Hello,\n\nJust circling back on our conversation earlier this week. Looking forward to hearing your thoughts when you get a chance.\n\nWarm regards,\nAlex"
    }
]

class DeliverabilityTester:
    """
    Automated Peer-to-Peer Inbox Placement & Warmup Engine.
    1. Dispatches realistic conversational emails across connected inboxes.
    2. Inspects Google's folder placement (Primary Inbox vs Spam vs Promotions).
    3. Auto-rescues any email landing in Spam by removing SPAM label, adding INBOX/STARRED,
       and dispatching a 2-way reply to train Google's spam filters that your accounts are trusted.
    """

    def __init__(self):
        self.accounts: Dict[str, Any] = {}
        self.seed_index = 0
        self._load_seed_accounts()

    def _load_seed_accounts(self):
        """Loads all available accounts to use as seed receivers."""
        if not ACCOUNTS_DIR.exists():
            return

        for acc_path in sorted(list(ACCOUNTS_DIR.glob("*.json"))):
            email = acc_path.stem.strip().lower()
            try:
                creds = Credentials.from_authorized_user_file(str(acc_path), SCOPES)
                service = build("gmail", "v1", credentials=creds, static_discovery=True)
                self.accounts[email] = {
                    "email": email,
                    "service": service,
                    "token_file": str(acc_path)
                }
            except Exception as e:
                logger.debug(f"Could not load seed account {email}: {e}")

    def get_seed_receivers(self, exclude_email: str = "") -> List[str]:
        """Returns list of seed receiver emails, preferring paused accounts or rotating active ones."""
        all_emails = list(self.accounts.keys())
        paused_available = [e for e in all_emails if e in [d.lower() for d in DISABLED_INBOXES] and e != exclude_email.lower()]
        if paused_available:
            return paused_available
        return [e for e in all_emails if e != exclude_email.lower()]

    def get_next_seed_receiver(self, sender_email: str) -> Optional[str]:
        """Returns next rotating seed recipient email distinct from the sender."""
        receivers = self.get_seed_receivers(exclude_email=sender_email)
        if not receivers:
            return None
        selected = receivers[self.seed_index % len(receivers)]
        self.seed_index += 1
        return selected

    async def check_and_warmup_placement(self, sender_email: str, receiver_email: str, search_query: str, auto_rescue: bool = True, wait_seconds: int = 5) -> Dict[str, Any]:
        """
        Inspects the receiver's inbox via Gmail API.
        If in SPAM: moves to INBOX, stars it, and sends a 2-way reply to boost reputation.
        """
        acc_info = self.accounts.get(receiver_email.lower())
        if not acc_info:
            return {"status": "unknown", "label": "[NO API ACCESS]", "folder": "UNKNOWN"}

        service = acc_info["service"]
        await asyncio.sleep(wait_seconds)

        try:
            res = service.users().messages().list(
                userId="me",
                q=f"from:{sender_email} {search_query}",
                includeSpamTrash=True,
                maxResults=5
            ).execute()

            messages = res.get("messages", [])
            if not messages:
                await asyncio.sleep(4)
                res = service.users().messages().list(
                    userId="me",
                    q=f"from:{sender_email}",
                    includeSpamTrash=True,
                    maxResults=5
                ).execute()
                messages = res.get("messages", [])

            if not messages:
                return {"status": "not_found", "label": "[NOT DELIVERED / DELAYED]", "folder": "NOT_FOUND"}

            msg_id = messages[0]["id"]
            thread_id = messages[0].get("threadId", msg_id)
            msg_data = service.users().messages().get(userId="me", id=msg_id, format="minimal").execute()
            label_ids = msg_data.get("labelIds", [])

            if "SPAM" in label_ids:
                if auto_rescue:
                    # Auto-Rescue: Remove SPAM, Add INBOX and STARRED
                    try:
                        service.users().messages().modify(
                            userId="me",
                            id=msg_id,
                            body={"removeLabelIds": ["SPAM", "UNREAD"], "addLabelIds": ["INBOX", "STARRED"]}
                        ).execute()

                        # Send 2-way Warmup Reply
                        import email.utils
                        reply_body = f"Thanks for the note! Let's touch base on this soon."
                        reply_msg = MIMEText(reply_body, "plain", "utf-8")
                        reply_msg["To"] = sender_email
                        reply_msg["From"] = f"{SENDER_NAME} <{receiver_email}>"
                        reply_msg["Subject"] = f"Re: {search_query}"
                        reply_msg["Date"] = email.utils.formatdate(localtime=True)
                        reply_msg["Message-ID"] = email.utils.make_msgid(domain="gmail.com")
                        reply_msg["MIME-Version"] = "1.0"
                        raw_reply = base64.urlsafe_b64encode(reply_msg.as_bytes()).decode()
                        service.users().messages().send(userId="me", body={"raw": raw_reply, "threadId": thread_id}).execute()
                        logger.info(f">> [AUTO-RESCUED & WARMED] Rescued email from SPAM -> Moved to INBOX & sent 2-way reply to {sender_email}!")
                        return {"status": "rescued", "label": "[SPAM -> AUTO-RESCUED TO INBOX] (Reputation Boosted)", "folder": "SPAM_RESCUED"}
                    except Exception as e:
                        logger.debug(f"Auto rescue modify error: {e}")

                return {"status": "spam", "label": "[SPAM FOLDER]", "folder": "SPAM", "labels": label_ids}

            elif "CATEGORY_PROMOTIONS" in label_ids:
                return {"status": "promotions", "label": "[PROMOTIONS TAB]", "folder": "PROMOTIONS", "labels": label_ids}
            elif "INBOX" in label_ids:
                # Mark as read/starred to signal high engagement
                try:
                    service.users().messages().modify(
                        userId="me",
                        id=msg_id,
                        body={"removeLabelIds": ["UNREAD"], "addLabelIds": ["STARRED"]}
                    ).execute()
                except Exception:
                    pass
                return {"status": "inbox", "label": "[PRIMARY INBOX] (Healthy)", "folder": "INBOX", "labels": label_ids}
            else:
                return {"status": "delivered", "label": f"[DELIVERED: {', '.join(label_ids)}]", "folder": "INBOX", "labels": label_ids}

        except Exception as e:
            logger.warning(f"Error checking placement in {receiver_email}: {e}")
            return {"status": "error", "label": f"[ERROR: {e}]", "folder": "ERROR"}

    async def run_live_seed_test(self, sender_email: str, gmail_service: Any) -> Optional[Dict[str, Any]]:
        """Sends a single seed test during live outreach, inspects placement, and auto-rescues if needed."""
        receiver = self.get_next_seed_receiver(sender_email)
        if not receiver:
            return None

        topic = random.choice(NATURAL_SEED_TOPICS)
        tracking_code = uuid.uuid4().hex[:6]
        subject = f"{topic['subject']} #{tracking_code}"
        body = f"{topic['body']}\n\nRef: #{tracking_code}"

        try:
            import email.utils
            msg = MIMEText(body, "plain", "utf-8")
            msg["To"] = receiver
            msg["From"] = f"{SENDER_NAME} <{sender_email}>"
            msg["Subject"] = subject
            msg["Date"] = email.utils.formatdate(localtime=True)
            msg["Message-ID"] = email.utils.make_msgid(domain="gmail.com")
            msg["MIME-Version"] = "1.0"
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

            send_res = gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
            if send_res:
                logger.info(f">> [SEED TEST SENT] {sender_email} -> {receiver} (Ref: #{tracking_code})")
                placement = await self.check_and_warmup_placement(
                    sender_email=sender_email,
                    receiver_email=receiver,
                    search_query=tracking_code,
                    auto_rescue=True,
                    wait_seconds=5
                )
                logger.info(f"   [SEED PLACEMENT] Placement: {placement.get('label')}")
                return {
                    "sender": sender_email,
                    "receiver": receiver,
                    "ref": tracking_code,
                    "placement": placement
                }
        except Exception as e:
            logger.warning(f"Failed sending seed test from {sender_email}: {e}")
        return None
