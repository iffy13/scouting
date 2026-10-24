"""
Outreach controller. Every send is previewed, approved and sent from the ONE mailbox
assigned to that service.

  python outreach.py check                                   confirm each mailbox is connected and is the right account
  python outreach.py preview --service whatsapp_api --n 3    see exact messages, nothing is sent
  python outreach.py approve --service whatsapp_api --min-score 70
  python outreach.py approve --service whatsapp_api --ids 4,9,12
  python outreach.py send --service whatsapp_api --limit 10  shows each message, asks y/n, then sends
  python outreach.py connect --service whatsapp_api          sign in to the assigned Gmail so it can send
  python outreach.py telegram                                set up and test Telegram alerts
  python outreach.py replies                                 check for replies once, alerts you on Telegram
  python outreach.py replies --watch                         keep checking every 10 minutes
  python outreach.py report                                  send a status summary to Telegram

Needs these lines in .env (messages refuse to build without them):
  BUSINESS_NAME=Iffy Studios
  POSTAL_ADDRESS=Your full business address
  SCOUT_DAILY_CAP=20
For Telegram alerts also add:
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_CHAT_ID=...
"""
import argparse
import asyncio
import datetime
import json
import os
import re
import sys
import time
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import SENDER_NAME
from safety import mask_email, mask_text
from db import add_to_blacklist, blacklist_domain, get_connection, is_domain_blacklisted, is_email_blacklisted
from scout import CAREFUL_REGIONS, init_scout_tables
import tg
from services import SERVICES, get_service, load_mailbox_map, validate_mailbox_map

BUSINESS_NAME = os.getenv("BUSINESS_NAME", "")
POSTAL_ADDRESS = os.getenv("POSTAL_ADDRESS", "")
DAILY_CAP = int(os.getenv("SCOUT_DAILY_CAP", "20"))


SENDER_TITLE = os.getenv("SENDER_TITLE", "Founder")
WEBSITE_URL = os.getenv("WEBSITE_URL", "")


def website_text() -> str:
    """The site as plain text without https:// (iffystudios.com), the way most cold emailers show it: one clean
    address in the signature, not a clickable button, no shortener, no tracking."""
    w = (WEBSITE_URL or "").strip()
    for prefix in ("https://", "http://"):
        if w.lower().startswith(prefix):
            w = w[len(prefix):]
    return w.rstrip("/")


def footer() -> str:
    """Professional plain text signature: name, role, business, website, postal address, then the opt out line."""
    lines = [SENDER_NAME, f"{SENDER_TITLE}, {BUSINESS_NAME}" if SENDER_TITLE else BUSINESS_NAME]
    # No link in cold emails by default: a URL in a first email from a new mailbox is one of the strongest spam signals.
    # The website is still used when you reply by hand. WEBSITE_IN_EMAILS=true puts it back in the signature.
    if website_text() and os.getenv("WEBSITE_IN_EMAILS", "").lower() in ("true", "1", "yes"):
        lines.append(website_text())
    lines.append(POSTAL_ADDRESS)
    return "\n" + "\n".join(l for l in lines if l) + "\n\nNot relevant? Reply \"stop\" and I won't email you again."


def build_message(service_id: str, lead: Dict[str, Any]) -> Tuple[str, str]:
    """Plain, honest first message. No fake replies, no fake history."""
    from messages import compose
    composed = compose(service_id, lead, footer())
    if composed:
        return composed
    name = lead["name"]
    owner = lead.get("owner_name")
    hello = f"Hi {owner}," if owner else f"Hi {name} team,"
    place = lead.get("city") if lead.get("city") and lead["city"].lower() != "general" else lead.get("country")
    evidence = " ".join(json.loads(lead.get("evidence_json") or "[]")).lower()

    if service_id == "whatsapp_api":
        seen = "I noticed customers can message you on WhatsApp from your website." if "whatsapp click" in evidence else ""
        subject = f"WhatsApp for {name}"
        body = (
            f"{hello}\n\n"
            f"I came across {name} while looking at {lead.get('keyword', 'local')} businesses in {place}. {seen}\n\n"
            "I set up the official WhatsApp Business Platform (Cloud API) with Meta business verification, "
            "so customer chats can be answered faster, shared by a team and connected to a CRM instead of living on one phone.\n\n"
            "If that is something you are thinking about, I can send a short outline of how it works and what it costs."
        )
    elif service_id == "receptionist":
        subject = f"Calls to {name}"
        body = (
            f"{hello}\n\n"
            f"I came across {name} while looking at {lead.get('keyword', 'local')} businesses in {place}.\n\n"
            "I build AI phone assistants that answer calls at any hour, take the customer's details and book the job, "
            "so calls that would hit voicemail are not lost.\n\n"
            "Would a short recorded example of how it sounds for a business like yours be useful?"
        )
    else:
        raise ValueError(f"No message template for service '{service_id}'")
    return subject, body.replace(" \n", "\n") + footer()


def postal_address_problem(address: str) -> Optional[str]:
    """Why POSTAL_ADDRESS is not a usable postal address, or None when it looks fine."""
    a = (address or "").strip()
    low = a.lower()
    if re.search(r"https?:|www\.|\.(com|net|app|io|org|co)\b", low):
        return "it looks like a website, not a postal address"
    if "example" in low or "your full" in low or "<" in a:
        return "it is still placeholder text"
    if not re.search(r"\d", a):
        return "it has no number in it (street number, PO box or postcode)"
    return None


def _require_identity():
    missing = [k for k, v in (("BUSINESS_NAME", BUSINESS_NAME), ("POSTAL_ADDRESS", POSTAL_ADDRESS)) if not v]
    if missing:
        sys.exit(f"Set {', '.join(missing)} in .env first. Messages must show who is writing and where.")
    why = postal_address_problem(POSTAL_ADDRESS)
    if why:
        sys.exit(f"Not sending: POSTAL_ADDRESS {why}. Cold email must carry a real postal address, for example "
                 f"\"12 Main Street, Lagos 100001\". Fix it in .env and in the POSTAL_ADDRESS GitHub secret.")


def _leads(service_id: str, status: str, limit: int, ids: Optional[List[int]] = None,
           countries: Optional[List[str]] = None):
    """Leads of one service and status, best score first. `countries` limits them to those countries."""
    init_scout_tables()
    with get_connection() as conn:
        if ids:
            q = ",".join("?" * len(ids))
            return conn.execute(f"SELECT * FROM scout_leads WHERE service_id=? AND id IN ({q})", [service_id, *ids]).fetchall()
        where, args = "service_id=? AND status=?", [service_id, status]
        if countries is not None:
            if not countries:
                return []
            where += f" AND country IN ({','.join('?' * len(countries))})"
            args += list(countries)
        return conn.execute(f"SELECT * FROM scout_leads WHERE {where} ORDER BY score DESC LIMIT ?", [*args, limit]).fetchall()


MAILBOX_DAILY_CAP = int(os.getenv("MAILBOX_DAILY_CAP", "10"))
# Warm-up for a new sending mailbox: the most it may send per day in its 1st, 2nd, 3rd... week, counted from its
# first email. A brand-new domain that sends 50 a day lands in spam, so this applies even when MAILBOX_DAILY_CAP is
# set higher. WARMUP_STEPS="" switches it off.
WARMUP_STEPS = [int(x) for x in os.getenv("WARMUP_STEPS", "10,15,20,25,30").split(",") if x.strip().isdigit()]


def warmup_cap(first_sent: Optional[str], today: Optional[datetime.date] = None) -> Optional[int]:
    """The warm-up limit for a mailbox whose first email went out on `first_sent` (YYYY-MM-DD...), or None after
    the last step or when warm-up is off. A mailbox that never sent is in week 1."""
    if not WARMUP_STEPS:
        return None
    today = today or datetime.date.today()
    try:
        start = datetime.date.fromisoformat(str(first_sent)[:10]) if first_sent else today
    except ValueError:
        start = today
    week = max(0, (today - start).days) // 7
    return WARMUP_STEPS[week] if week < len(WARMUP_STEPS) else None


def mailbox_cap(box: str) -> int:
    """Today's limit for this mailbox: MAILBOX_DAILY_CAP, lowered by the warm-up while the mailbox is new."""
    with get_connection() as conn:
        first = conn.execute("SELECT MIN(sent_at) FROM scout_leads WHERE LOWER(sender_inbox)=?", (box.lower(),)).fetchone()[0]
    w = warmup_cap(first)
    return MAILBOX_DAILY_CAP if w is None else min(MAILBOX_DAILY_CAP, w)


def mailbox_room(box: str) -> int:
    """How many more emails this MAILBOX may send today, counting every service that shares it and follow ups.
    Protects a new domain when one mailbox sends for all services (MAILBOX_DAILY_CAP plus the warm-up)."""
    with get_connection() as conn:
        used = conn.execute(
            """SELECT
                 (SELECT COUNT(*) FROM scout_leads WHERE LOWER(sender_inbox)=? AND DATE(sent_at)=DATE('now')) +
                 (SELECT COUNT(*) FROM scout_leads WHERE LOWER(sender_inbox)=? AND DATE(followup_sent_at)=DATE('now'))""",
            (box.lower(), box.lower()),
        ).fetchone()[0]
    return max(0, mailbox_cap(box) - used)


def park_lead(lead_id: int, why: str):
    """Takes a lead out of the send queue for good (status 'skipped', with the reason), so it does not sit at the
    top of the queue every run and does not count toward the backlog that pauses scouting."""
    with get_connection() as conn:
        conn.execute("UPDATE scout_leads SET status='skipped', skip_reason=? WHERE id=?", (why, lead_id))
        conn.commit()


def note_send_failure(lead_id: int) -> bool:
    """Counts a failed send. Returns True (and parks the lead) after the second failure, so an address Gmail keeps
    rejecting is not retried forever. One failure can be a hiccup, so the lead gets one more try."""
    with get_connection() as conn:
        conn.execute("UPDATE scout_leads SET send_attempts=COALESCE(send_attempts,0)+1 WHERE id=?", (lead_id,))
        n = conn.execute("SELECT send_attempts FROM scout_leads WHERE id=?", (lead_id,)).fetchone()[0]
        conn.commit()
    if n >= 2:
        park_lead(lead_id, "gmail refused to send it twice")
        return True
    return False


def cmd_check():
    problems = validate_mailbox_map()
    mapping = load_mailbox_map()
    print("\nService to mailbox assignments")
    print("-" * 60)
    from sender.gmail_client import MultiGmailService
    pool = MultiGmailService(mode="all")
    for sid, svc in SERVICES.items():
        mb = mapping.get(sid)
        if not mb:
            print(f"{sid:14} NOT ASSIGNED")
            continue
        acc = next((a for e, a in pool.accounts.items() if e.lower() == mb), None)
        if not acc:
            print(f"{sid:14} {mb}  TOKEN MISSING. Run: python outreach.py connect --service {sid}")
            continue
        try:
            if acc.get("type") == "smtp":
                from sender import smtp_mailbox
                why = smtp_mailbox.test_login(acc["cfg"], mb)
                print(f"{sid:14} {mb}  {'CONFIRMED (own domain, SMTP + IMAP)' if not why else why}")
                continue
            real = acc["service"].users().getProfile(userId="me").execute().get("emailAddress", "").lower()
            state = "CONFIRMED" if real == mb else f"MISMATCH, token belongs to {real}"
        except Exception as e:
            state = f"TOKEN ERROR ({str(e)[:60]}), reconnect this account"
        print(f"{sid:14} {mb}  {state}")
    for p in problems:
        print("WARNING:", p)
    print()


def cmd_preview(service_id: str, n: int):
    _require_identity()
    svc = get_service(service_id)
    print(f"\nFROM mailbox for {service_id}: {svc.mailbox or 'NOT ASSIGNED'}\n")
    rows = _leads(service_id, "shortlisted", n)
    if not rows:
        print("No shortlisted leads yet. Run: python scout.py --service", service_id)
        return
    for r in rows:
        subject, body = build_message(service_id, dict(r))
        emails = json.loads(r["emails_json"] or "[]")
        print("=" * 70)
        print(f"Lead #{r['id']}  score {r['score']}  {r['country']}")
        print(f"From:    {svc.mailbox}")
        print(f"To:      {emails[0] if emails else '(no email found)'}")
        print(f"Subject: {subject}\n")
        print(body)
        print(f"\nApproach: {r['approach_note']}")
    print("=" * 70)


def cmd_approve(service_id: str, min_score: Optional[int], ids: Optional[List[int]]):
    init_scout_tables()
    with get_connection() as conn:
        if ids:
            q = ",".join("?" * len(ids))
            cur = conn.execute(f"UPDATE scout_leads SET status='approved' WHERE service_id=? AND id IN ({q})", [service_id, *ids])
        else:
            cur = conn.execute(
                "UPDATE scout_leads SET status='approved' WHERE service_id=? AND status='shortlisted' AND score>=?",
                (service_id, min_score or 70),
            )
        conn.commit()
    print(f"Approved {cur.rowcount} leads for {service_id}")


async def site_looks_inactive(website: Optional[str]) -> Optional[str]:
    """Last check before sending: open the lead's home page and look for this or last year. Returns a reason when the
    site looks abandoned (newest year two or more years old) or is gone. None when it looks active or can't tell."""
    if not website:
        return None
    import datetime as _dt
    import requests
    from config import DEFAULT_HEADERS
    from scout_signals import activity
    url = website if website.startswith(("http://", "https://")) else "https://" + website
    try:
        r = await asyncio.to_thread(requests.get, url, headers=DEFAULT_HEADERS, timeout=10)
    except Exception:
        return None  # network hiccup or a site blocking bots: can't tell, so don't throw the lead away
    if r.status_code in (404, 410):
        return f"website is gone (HTTP {r.status_code})"
    latest = activity(r.text).get("latest_year")
    if latest and latest < _dt.datetime.utcnow().year - 1:
        return f"site looks inactive (newest year on it is {latest})"
    return None


async def send_blocker(lead: Dict[str, Any], verifier) -> Tuple[Optional[str], str]:
    """(reason this lead must never be sent, address) or (None, address) when it is fine to send.
    Shared by outreach.py send and send_paced.py so both apply exactly the same rules."""
    from seen import already_emailed
    emails = json.loads(lead.get("emails_json") or "[]")
    if lead.get("country") in CAREFUL_REGIONS:
        return "regulated region, use contact form or LinkedIn", ""
    if not emails:
        return "no email found", ""
    emails = [e.lower() for e in emails]
    with get_connection() as conn:
        if is_domain_blacklisted(lead.get("domain"), conn):
            return "on the blacklist", emails[0]
        for e in emails:
            if already_emailed(conn, e):
                return "already emailed before", e
        usable = [e for e in emails if not is_email_blacklisted(e, conn)]
    if not usable:
        return "on the blacklist", emails[0]
    # Up to 3 addresses were found on the site, best first. The first one that passes the check is used.
    stale = await site_looks_inactive(lead.get("website"))
    if stale:
        return stale, usable[0]
    verdicts = []
    for e in usable:
        verdict = (await verifier.verify(e)).get("verdict")
        if verdict == "valid":
            return None, e
        verdicts.append(verdict)
    return f"email check says {'/'.join(verdicts)}", usable[0]


async def cmd_send(service_id: str, limit: int):
    _require_identity()
    svc = get_service(service_id)
    if not svc.mailbox:
        sys.exit(f"No mailbox assigned to {service_id}. Fill mailbox_map.json.")
    from sender.gmail_client import MultiGmailService
    from verifier.email_verifier import EmailVerifier

    pool = MultiGmailService(mode="all")
    box = next((e for e in pool.accounts if e.lower() == svc.mailbox), None)
    if not box:
        sys.exit(f"{svc.mailbox} is not connected. Run python outreach.py check")

    with get_connection() as conn:
        sent_today = conn.execute(
            "SELECT COUNT(*) FROM scout_leads WHERE service_id=? AND DATE(sent_at)=DATE('now')", (service_id,)
        ).fetchone()[0]
    room = max(0, DAILY_CAP - sent_today)
    if room == 0:
        sys.exit(f"Daily cap of {DAILY_CAP} reached for {service_id}.")

    verifier = EmailVerifier()
    sent = 0
    for r in _leads(service_id, "approved", min(limit, room)):
        lead = dict(r)
        why, to = await send_blocker(lead, verifier)
        if why:
            print(f"#{lead['id']} {mask_email(to) or lead['name']}: {why}. Removed from the queue.")
            park_lead(lead["id"], why)
            continue

        subject, body = build_message(service_id, lead)
        print("\n" + "=" * 70)
        print(f"From:    {box}   (assigned mailbox for {service_id})")
        print(f"To:      {to}")
        print(f"Subject: {subject}\n\n{body}")
        print("=" * 70)
        choice = input("Send this one? [y]es / [n]o skip / [q]uit: ").strip().lower()
        if choice == "q":
            break
        if choice != "y":
            continue

        res = pool.send_email(to_email=to, subject=subject, body_text=body, from_account_email=box, strict_sender=True)
        if res:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE scout_leads SET status='contacted', sent_at=CURRENT_TIMESTAMP, sender_inbox=?, gmail_thread_id=?, sent_subject=?, sent_to=?, sent_body=? WHERE id=?",
                    (res["from_email"], res["thread_id"], subject, to, body, lead["id"]),
                )
                conn.commit()
            sent += 1
            print(f"Sent from {res['from_email']}.")
        else:
            if pool.last_failure == "no_capacity":
                print(f"Not sent ({pool.last_failure}). Lead stays approved.")
                break
            gone = note_send_failure(lead["id"])
            print(f"Not sent ({pool.last_failure}). " + ("Removed from the queue." if gone else "Will retry once."))
    print(f"\nDone. Sent {sent}. Today for {service_id}: {sent_today + sent}/{DAILY_CAP}")
    if sent:
        tg.send(
            f"<b>Emails sent: {tg.esc(service_id)}</b>\n"
            f"Sent just now: {sent} from {tg.esc(box)}\n"
            f"Today: {sent_today + sent} of {DAILY_CAP}"
        )


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


def cmd_connect(service_id: str):
    """Sign in to the Gmail assigned to this service and save its token. Refuses a wrong account."""
    svc = get_service(service_id)
    if not svc.mailbox:
        sys.exit(f"No mailbox assigned to {service_id}. Fill mailbox_map.json first.")
    creds_file = Path("credentials.json")
    if not creds_file.exists():
        sys.exit("credentials.json is missing from this folder. It is the Google OAuth file from your Google Cloud project.")
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    print(f"\nA browser will open. Sign in as {svc.mailbox} and click Allow.")
    print("If Google says the app is not verified, click Advanced, then continue.")
    print("If it says access blocked, add this email under Test users in Google Cloud Console first.\n")
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), GMAIL_SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline", login_hint=svc.mailbox)
    real = build("gmail", "v1", credentials=creds).users().getProfile(userId="me").execute().get("emailAddress", "").lower()
    if real != svc.mailbox:
        sys.exit(f"You signed in as {real} but {service_id} is assigned to {svc.mailbox}. Nothing was saved. Run it again and pick the right account.")
    Path("accounts").mkdir(exist_ok=True)
    (Path("accounts") / f"{real}.json").write_text(creds.to_json())
    print(f"\nConnected {real} for {service_id}.")
    tg.send(f"<b>Mailbox connected</b>\n{tg.esc(real)} is now ready to send for {tg.esc(service_id)}.")


def cmd_telegram():
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        print("\nTelegram is not set up yet.")
        print("1. In Telegram, open @BotFather, send /newbot and follow the steps. It gives you a token.")
        print("2. Put it in .env as a new line:  TELEGRAM_BOT_TOKEN=your token")
        print("3. Open your new bot in Telegram and send it the word hello.")
        print("4. Run this command again.")
        return
    if not os.getenv("TELEGRAM_CHAT_ID"):
        found = tg.find_chat_id()
        if not found:
            print("\nToken is there, but the bot has not received a message from you yet.")
            print("Open your bot in Telegram, send it the word hello, then run this command again.")
            return
        print(f"\nYour chat id is {found}")
        print(f"Add this line to .env, save, then run this command again:\n  TELEGRAM_CHAT_ID={found}")
        return
    ok = tg.send("<b>Telegram is connected.</b>\nYou will get scouting, sending and reply alerts here.")
    print("\nTest message sent. Check Telegram." if ok else "\nSend failed. Check the token and chat id in .env.")


# "stop" on its own is too loose ("stop by our office", "non-stop calls"), so it only counts as an opt out when it is
# the whole first line or comes with emailing/contacting/sending. (?<![-\w]) keeps "non-stop" out.
OPT_OUT = re.compile(
    r"(?<![-\w])(unsubscribe|remove (me|us)|take (me|us) off|not interested|no thanks|no thank you|not relevant|"
    r"do not (email|contact|message)|don'?t (email|contact|message)|"
    r"(please )?stop (emailing|contacting|sending|messaging|writing|spamming)|not for us|spam)\b", re.I
)
JUST_NO = {"no", "nope", "no thanks", "no thank you", "not interested", "stop", "please stop", "stop please",
           "stop it", "unsubscribe"}
POSITIVE = re.compile(r"\b(demo|outline|samples?|portfolio|examples?|quote|rates?|yes|yeah|sure|interested|send (it|me|us|over)|how much|price|pricing|cost|call me)\b", re.I)
AUTO_REPLY = re.compile(r"(out of office|automatic reply|auto-?reply|autoreply|vacation)", re.I)
QUOTE_START = re.compile(r"^\s*(on .{3,200}wrote:?\s*$|-{2,}\s*original message\s*-{2,}|from:\s.+|sent from my )", re.I)
FREE_MAIL_HOSTS = ("gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com", "icloud.com")


def reply_text(raw: str) -> str:
    """The new part of a reply: quoted history ("On ... wrote:", lines starting with >) and the signature removed."""
    keep = []
    for line in (raw or "").replace("\r\n", "\n").split("\n"):
        if QUOTE_START.match(line):
            break
        if line.strip() in ("--", "-- "):
            break
        if line.lstrip().startswith(">"):
            continue
        keep.append(line)
    return "\n".join(keep).strip()


def classify_reply(raw: str) -> str:
    """'auto', 'optout', 'positive' or 'other' for the new text of an inbound reply."""
    text = reply_text(raw)
    if AUTO_REPLY.search(text):
        return "auto"
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    first = re.sub(r"[^a-z ]", "", lines[0].lower()).strip() if lines else ""
    if OPT_OUT.search(text) or first in JUST_NO:
        return "optout"
    if POSITIVE.search(text) or "?" in text:
        return "positive"
    return "other"


def _plain_body(payload: Dict[str, Any]) -> str:
    """Decoded text/plain part of a Gmail message payload ('' when there is none)."""
    import base64
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        data = payload["body"]["data"]
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
    for part in payload.get("parts", []) or []:
        found = _plain_body(part)
        if found:
            return found
    return ""


def _header(msg: Dict[str, Any], name: str) -> str:
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def check_replies_once() -> Dict[str, int]:
    """Look at every contacted thread. Alerts on real replies, honours opt outs, flags bounces."""
    init_scout_tables()
    from sender.gmail_client import MultiGmailService

    pool = MultiGmailService(mode="all")
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM scout_leads WHERE status IN ('contacted','replied') "
            "AND gmail_thread_id IS NOT NULL AND sender_inbox IS NOT NULL"
        ).fetchall()
    counts = {"checked": len(rows), "replies": 0, "opt_outs": 0, "bounces": 0}
    for r in rows:
        box = next((e for e in pool.accounts if e.lower() == (r["sender_inbox"] or "").lower()), None)
        if not box:
            continue
        lead_emails = [e.lower() for e in json.loads(r["emails_json"] or "[]")]
        acc = pool.accounts[box]
        if acc.get("type") == "smtp":
            from sender import smtp_mailbox
            try:
                found = smtp_mailbox.latest_inbound(acc["cfg"], box, r["gmail_thread_id"], lead_emails)
            except Exception as e:
                print(f"#{r['id']}: could not read the inbox ({type(e).__name__})")
                continue
            if not found or found["id"] == r["last_reply_id"]:
                continue
            latest = {"id": found["id"]}
            frm, text = found["from"], found["text"]
            snippet = re.sub(r"\s+", " ", reply_text(text))[:200]
        else:
            try:
                thread = acc["service"].users().threads().get(
                    userId="me", id=r["gmail_thread_id"], format="metadata", metadataHeaders=["From", "Subject"]
                ).execute()
            except Exception as e:
                print(f"#{r['id']}: could not read thread ({type(e).__name__})")
                continue
            inbound = [m for m in thread.get("messages", []) if "SENT" not in m.get("labelIds", [])]
            if not inbound or inbound[-1]["id"] == r["last_reply_id"]:
                continue
            latest = inbound[-1]
            frm = _header(latest, "From")
            snippet = (latest.get("snippet") or "").strip()
            try:
                full = acc["service"].users().messages().get(userId="me", id=latest["id"], format="full").execute()
                text = _plain_body(full.get("payload", {})) or snippet
            except Exception:
                text = snippet
        addr = parseaddr(frm)[1].lower()
        new_text = reply_text(text) or snippet

        if "mailer-daemon" in addr or "postmaster" in addr:
            new_status, kind = "skipped", "bounce"
            counts["bounces"] += 1
        else:
            verdict = classify_reply(text)
            if verdict == "auto":
                new_status, kind = r["status"], "auto"
            elif verdict == "optout":
                new_status, kind = "lost", "optout"
                counts["opt_outs"] += 1
            elif verdict == "positive":
                new_status, kind = "replied", "reply"
                counts["replies"] += 1
            else:
                # Answered, but not clearly yes or no: stop follow ups and let you read it, not counted as a lead.
                new_status, kind = "replied", "other"
                counts["other"] = counts.get("other", 0) + 1
        snippet = new_text[:300]

        with get_connection() as conn:
            if kind in ("bounce", "optout"):
                for e in set(lead_emails + ([addr] if kind == "optout" and addr and addr != box.lower() else [])):
                    add_to_blacklist(e, "bounce" if kind == "bounce" else "opted out by reply", conn)
            if kind == "optout":
                # the whole business, for both services: the website domain and any company email domain
                blacklist_domain(r["domain"], "opted out by reply", conn)
                for e in lead_emails + ([addr] if addr else []):
                    host = e.split("@")[-1]
                    if host and host not in FREE_MAIL_HOSTS and host != box.lower().split("@")[-1]:
                        blacklist_domain(host, "opted out by reply", conn)
            conn.execute(
                "UPDATE scout_leads SET status=?, last_reply_id=?, reply_snippet=?, replied_at=CURRENT_TIMESTAMP WHERE id=?",
                (new_status, latest["id"], snippet[:300], r["id"]),
            )
            conn.commit()

        who = f"{tg.esc(r['name'])} ({tg.esc(r['service_id'])})"
        if kind == "reply":
            print(f"REPLY from {r['name']}: {mask_text(snippet[:100])}")
            tg.send(
                f"<b>New reply: {who}</b>\n"
                f"From: {tg.esc(frm)}\n"
                f"Received in: {tg.esc(box)}\n\n"
                f"<i>{tg.esc(snippet[:500])}</i>"
            )
        elif kind == "other":
            print(f"REPLY (not clearly yes or no) from {r['name']}: {mask_text(snippet[:100])}")
            tg.send(
                f"<b>Reply to read: {who}</b>\nNot a clear yes or no, so it is not counted as a lead and no follow up "
                f"will be sent.\nFrom: {tg.esc(frm)}\nReceived in: {tg.esc(box)}\n\n<i>{tg.esc(snippet[:500])}</i>"
            )
        elif kind == "optout":
            print(f"OPT OUT from {r['name']}. Blacklisted.")
            tg.send(f"<b>Opt out: {who}</b>\nThey asked not to be contacted. Added to the blacklist.\n<i>{tg.esc(snippet[:200])}</i>")
        elif kind == "bounce":
            print(f"BOUNCE for {r['name']}. Blacklisted.")
            tg.send(f"<b>Email bounced: {who}</b>\nThe address was not valid. Added to the blacklist.")
    return counts


def cmd_replies(watch: bool):
    while True:
        c = check_replies_once()
        print(f"Checked {c['checked']} threads. Replies {c['replies']}, opt outs {c['opt_outs']}, bounces {c['bounces']}.")
        if not watch:
            return
        print("Checking again in 10 minutes. Press Ctrl+C to stop.\n")
        try:
            time.sleep(600)
        except KeyboardInterrupt:
            print("Stopped.")
            return


def cmd_report():
    init_scout_tables()
    lines = []
    with get_connection() as conn:
        for sid in SERVICES:
            rows = conn.execute(
                "SELECT status, COUNT(*) c FROM scout_leads WHERE service_id=? GROUP BY status", (sid,)
            ).fetchall()
            if rows:
                lines.append(f"<b>{tg.esc(sid)}</b>: " + ", ".join(f"{tg.esc(r['status'])} {r['c']}" for r in rows))
    text = "<b>Scouting report</b>\n" + ("\n".join(lines) if lines else "No leads yet.")
    print(re.sub(r"<[^>]+>", "", text))
    if tg.configured():
        tg.send(text)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("telegram")
    sub.add_parser("report")
    pc = sub.add_parser("connect")
    pc.add_argument("--service", required=True, choices=list(SERVICES))
    pr = sub.add_parser("replies")
    pr.add_argument("--watch", action="store_true")
    for name in ("preview", "approve", "send"):
        p = sub.add_parser(name)
        p.add_argument("--service", required=True, choices=list(SERVICES))
        if name == "preview":
            p.add_argument("--n", type=int, default=3)
        if name == "approve":
            p.add_argument("--min-score", type=int)
            p.add_argument("--ids", default="")
        if name == "send":
            p.add_argument("--limit", type=int, default=10)
    a = ap.parse_args()

    if a.cmd == "check":
        cmd_check()
    elif a.cmd == "telegram":
        cmd_telegram()
    elif a.cmd == "report":
        cmd_report()
    elif a.cmd == "connect":
        cmd_connect(a.service)
    elif a.cmd == "replies":
        cmd_replies(a.watch)
    elif a.cmd == "preview":
        cmd_preview(a.service, a.n)
    elif a.cmd == "approve":
        cmd_approve(a.service, a.min_score, [int(x) for x in a.ids.split(",") if x.strip()])
    elif a.cmd == "send":
        asyncio.run(cmd_send(a.service, a.limit))


if __name__ == "__main__":
    main()
