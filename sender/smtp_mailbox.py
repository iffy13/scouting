"""
Mailboxes on your own domain (Namecheap cPanel, Zoho, any normal host): send over SMTP, read replies over IMAP.
Used by MultiGmailService next to the Gmail accounts, so the rest of the tool does not care which kind a mailbox is.

Settings come from the SMTP_ACCOUNTS_JSON secret on GitHub, or smtp_accounts.json on your PC (never committed):
  {"samuel@iffystudio.site": {"host": "server123.web-hosting.com", "port": 465,
                              "imap_host": "server123.web-hosting.com", "imap_port": 993,
                              "password": "..."}}
Add one with:   python add_smtp.py

Threads: for these mailboxes the "thread id" stored for a lead is the Message-ID of the first email. Replies and
bounces are found by searching the inbox for that Message-ID (In-Reply-To, References or quoted in a bounce) or for
mail from the lead's addresses.
"""
import email
import email.utils
import imaplib
import json
import os
import re
import smtplib
import ssl
import time
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

LOCAL_FILE = Path("smtp_accounts.json")


class SendLimited(Exception):
    """The server is refusing for now (rate limit, temporary error): stop this run, keep the lead."""


def load_accounts() -> Dict[str, Dict[str, Any]]:
    raw = os.getenv("SMTP_ACCOUNTS_JSON", "").strip()
    if not raw and LOCAL_FILE.exists():
        raw = LOCAL_FILE.read_text("utf-8")
    if not raw:
        return {}
    data = json.loads(raw)
    return {k.strip().lower(): v for k, v in data.items()}


def _smtp(cfg: Dict[str, Any], user: str):
    host, port = cfg["host"], int(cfg.get("port", 465))
    ctx = ssl.create_default_context()
    if port == 465:
        s = smtplib.SMTP_SSL(host, port, context=ctx, timeout=30)
    else:
        s = smtplib.SMTP(host, port, timeout=30)
        s.starttls(context=ctx)
    s.login(cfg.get("user", user), cfg["password"])
    return s


def _imap(cfg: Dict[str, Any], user: str):
    m = imaplib.IMAP4_SSL(cfg.get("imap_host", cfg["host"]), int(cfg.get("imap_port", 993)), timeout=30)
    m.login(cfg.get("user", user), cfg["password"])
    return m


def test_login(cfg: Dict[str, Any], user: str) -> str:
    """'' when SMTP and IMAP both accept the login, otherwise what failed."""
    try:
        _smtp(cfg, user).quit()
    except Exception as e:
        return f"SMTP login failed ({type(e).__name__}: {str(e)[:80]})"
    try:
        _imap(cfg, user).logout()
    except Exception as e:
        return f"IMAP login failed ({type(e).__name__}: {str(e)[:80]})"
    return ""


def _save_to_sent(cfg: Dict[str, Any], user: str, raw: bytes):
    """Puts a copy in the Sent folder so you see it in your mailbox like any email you sent yourself."""
    try:
        m = _imap(cfg, user)
        for folder in ("INBOX.Sent", "Sent", "Sent Items", "Sent Messages"):
            typ, _ = m.select(f'"{folder}"')
            if typ == "OK":
                m.append(f'"{folder}"', "\\Seen", imaplib.Time2Internaldate(time.time()), raw)
                break
        m.logout()
    except Exception:
        pass  # a missing Sent copy must never stop sending


def send(cfg: Dict[str, Any], from_email: str, from_name: str, to: str, subject: str, body: str,
         in_reply_to: Optional[str] = None) -> str:
    """Sends one plain text email. Returns its Message-ID. Raises SendLimited for temporary refusals and other
    exceptions for permanent ones (bad recipient and so on)."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = email.utils.formataddr((from_name, from_email))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg_id = email.utils.make_msgid(domain=from_email.split("@", 1)[1])
    msg["Message-ID"] = msg_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    try:
        s = _smtp(cfg, from_email)
        s.sendmail(from_email, [to], msg.as_bytes())
        s.quit()
    except smtplib.SMTPRecipientsRefused:
        raise
    except smtplib.SMTPResponseException as e:
        if 400 <= e.smtp_code < 500 or "limit" in str(e.smtp_error).lower():
            raise SendLimited(f"server said {e.smtp_code}")
        raise
    except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, OSError) as e:
        raise SendLimited(f"could not reach the mail server ({type(e).__name__})")
    _save_to_sent(cfg, from_email, msg.as_bytes())
    return msg_id


def _plain(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
                return re.sub(r"<[^>]+>", " ", html)
        return ""
    return (msg.get_payload(decode=True) or b"").decode(msg.get_content_charset() or "utf-8", "replace")


def latest_inbound(cfg: Dict[str, Any], user: str, our_msgid: str, lead_emails: List[str]) -> Optional[Dict[str, str]]:
    """Newest message in the inbox that answers our email: it quotes our Message-ID (a reply or a bounce) or it comes
    from one of the lead's addresses. Returns {"id", "from", "text"} or None."""
    m = _imap(cfg, user)
    try:
        m.select("INBOX", readonly=True)
        uids = set()
        mid = (our_msgid or "").strip()
        if mid:
            for crit in (f'HEADER In-Reply-To "{mid}"', f'HEADER References "{mid}"', f'BODY "{mid.strip("<>")}"'):
                typ, data = m.uid("SEARCH", None, crit)
                if typ == "OK" and data and data[0]:
                    uids.update(data[0].split())
        for addr in lead_emails:
            typ, data = m.uid("SEARCH", None, f'FROM "{addr}"')
            if typ == "OK" and data and data[0]:
                uids.update(data[0].split())
        if not uids:
            return None
        newest = max(uids, key=lambda u: int(u))
        typ, data = m.uid("FETCH", newest, "(RFC822)")
        if typ != "OK" or not data or not data[0]:
            return None
        msg = email.message_from_bytes(data[0][1])
        return {"id": msg.get("Message-ID") or f"uid:{newest.decode()}", "from": msg.get("From", ""), "text": _plain(msg)}
    finally:
        try:
            m.logout()
        except Exception:
            pass
