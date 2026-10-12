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
import json
import os
import re
import sys
import time
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import SENDER_NAME
from db import add_to_blacklist, get_connection, is_email_blacklisted
from scout import CAREFUL_REGIONS, init_scout_tables
import tg
from services import SERVICES, get_service, load_mailbox_map, validate_mailbox_map

BUSINESS_NAME = os.getenv("BUSINESS_NAME", "")
POSTAL_ADDRESS = os.getenv("POSTAL_ADDRESS", "")
DAILY_CAP = int(os.getenv("SCOUT_DAILY_CAP", "20"))


def footer() -> str:
    return (
        f"\n\n{SENDER_NAME}\n{BUSINESS_NAME}\n{POSTAL_ADDRESS}\n\n"
        "If you would rather not hear from me, just reply \"no\" and I will not contact you again."
    )


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


def _require_identity():
    missing = [k for k, v in (("BUSINESS_NAME", BUSINESS_NAME), ("POSTAL_ADDRESS", POSTAL_ADDRESS)) if not v]
    if missing:
        sys.exit(f"Set {', '.join(missing)} in .env first. Messages must show who is writing and where.")


def _leads(service_id: str, status: str, limit: int, ids: Optional[List[int]] = None):
    init_scout_tables()
    with get_connection() as conn:
        if ids:
            q = ",".join("?" * len(ids))
            return conn.execute(f"SELECT * FROM scout_leads WHERE service_id=? AND id IN ({q})", [service_id, *ids]).fetchall()
        return conn.execute(
            "SELECT * FROM scout_leads WHERE service_id=? AND status=? ORDER BY score DESC LIMIT ?",
            (service_id, status, limit),
        ).fetchall()


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
        emails = json.loads(lead["emails_json"] or "[]")
        if lead["country"] in CAREFUL_REGIONS:
            print(f"#{lead['id']} {lead['name']}: regulated region, use contact form or LinkedIn. Skipped.")
            continue
        if not emails:
            print(f"#{lead['id']} {lead['name']}: no email found. Skipped.")
            continue
        to = emails[0].lower()
        with get_connection() as conn:
            if is_email_blacklisted(to, conn):
                print(f"#{lead['id']} {to}: on blacklist. Skipped.")
                continue
        verdict = (await verifier.verify(to)).get("verdict")
        if verdict != "valid":
            print(f"#{lead['id']} {to}: verification says {verdict}. Skipped.")
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
                    "UPDATE scout_leads SET status='contacted', sent_at=CURRENT_TIMESTAMP, sender_inbox=?, gmail_thread_id=? WHERE id=?",
                    (res["from_email"], res["thread_id"], lead["id"]),
                )
                conn.commit()
            sent += 1
            print(f"Sent from {res['from_email']}.")
        else:
            print(f"Not sent ({pool.last_failure}). Lead stays approved.")
            if pool.last_failure == "no_capacity":
                break
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


OPT_OUT = re.compile(
    r"\b(stop|unsubscribe|remove me|do not contact|don'?t contact|take me off|not interested|no thanks|no thank you)\b", re.I
)
AUTO_REPLY = re.compile(r"(out of office|automatic reply|auto-?reply|autoreply|vacation)", re.I)


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
        try:
            thread = pool.accounts[box]["service"].users().threads().get(
                userId="me", id=r["gmail_thread_id"], format="metadata", metadataHeaders=["From", "Subject"]
            ).execute()
        except Exception as e:
            print(f"#{r['id']}: could not read thread ({str(e)[:60]})")
            continue
        inbound = [m for m in thread.get("messages", []) if "SENT" not in m.get("labelIds", [])]
        if not inbound or inbound[-1]["id"] == r["last_reply_id"]:
            continue
        latest = inbound[-1]
        frm = _header(latest, "From")
        addr = parseaddr(frm)[1].lower()
        snippet = (latest.get("snippet") or "").strip()
        lead_emails = [e.lower() for e in json.loads(r["emails_json"] or "[]")]
        flat = re.sub(r"[^a-z ]", "", snippet.lower()).strip()

        if "mailer-daemon" in addr or "postmaster" in addr:
            new_status, kind = "skipped", "bounce"
            counts["bounces"] += 1
        elif AUTO_REPLY.search(snippet):
            new_status, kind = r["status"], "auto"
        elif OPT_OUT.search(snippet) or flat in ("no", "no thanks", "no thank you"):
            new_status, kind = "lost", "optout"
            counts["opt_outs"] += 1
        else:
            new_status, kind = "replied", "reply"
            counts["replies"] += 1

        with get_connection() as conn:
            if kind in ("bounce", "optout"):
                for e in set(lead_emails + ([addr] if kind == "optout" and addr and addr != box.lower() else [])):
                    add_to_blacklist(e, "bounce" if kind == "bounce" else "opted out by reply", conn)
            conn.execute(
                "UPDATE scout_leads SET status=?, last_reply_id=?, reply_snippet=?, replied_at=CURRENT_TIMESTAMP WHERE id=?",
                (new_status, latest["id"], snippet[:300], r["id"]),
            )
            conn.commit()

        who = f"{tg.esc(r['name'])} ({tg.esc(r['service_id'])})"
        if kind == "reply":
            print(f"REPLY from {r['name']}: {snippet[:100]}")
            tg.send(
                f"<b>New reply: {who}</b>\n"
                f"From: {tg.esc(frm)}\n"
                f"Received in: {tg.esc(box)}\n\n"
                f"<i>{tg.esc(snippet[:500])}</i>"
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
