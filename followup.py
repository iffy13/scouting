"""
One polite follow up per business, as a reply in the same thread and from the same mailbox. Never a second follow up.

  python followup.py test --to you@gmail.com       sends a sample follow up from each service mailbox to YOU
  python followup.py send --service whatsapp_api --days 5 --limit 10
  python followup.py send --service whatsapp_api --days 5 --limit 10 --auto

'send' only picks leads that were emailed at least N days ago, did not reply, did not opt out,
and have not had a follow up yet. Same pacing gap as send_paced.py.
"""
import argparse
import json
import sys

import tg
from safety import mask_email, mask_text
from db import get_connection, is_domain_blacklisted, is_email_blacklisted
from outreach import CAREFUL_REGIONS, DAILY_CAP, _require_identity, footer
from scout import init_scout_tables
from services import SERVICES, get_service, load_mailbox_map

# Copy lives in messages_variants.py (FOLLOWUPS). Kept as the list of services that have a follow up.
BODIES = {"whatsapp_api": None, "receptionist": None, "render_3d": None}
SAMPLE = {"name": "Sample Dental Clinic", "domain": "sample.com", "owner_name": None}


def build_followup(service_id, lead):
    from messages import compose_followup
    return compose_followup(service_id, lead, footer())


def thread_ids(pool, box, thread_id):
    """Message-ID of the first email in the thread, so the follow up lands under it in their inbox too."""
    if not thread_id:
        return None
    try:
        t = pool.accounts[box]["service"].users().threads().get(
            userId="me", id=thread_id, format="metadata", metadataHeaders=["Message-ID", "Message-Id"]
        ).execute()
        for h in t["messages"][0].get("payload", {}).get("headers", []):
            if h.get("name", "").lower() == "message-id":
                return h.get("value")
    except Exception:
        pass
    return None


def has_inbound(pool, box, thread_id) -> bool:
    """True when anyone other than us wrote in this thread. Checked right before each follow up, so a reply that
    arrived since the last reply check still stops it. When the thread cannot be read, no follow up is sent."""
    if not thread_id:
        return False
    try:
        t = pool.accounts[box]["service"].users().threads().get(userId="me", id=thread_id, format="minimal").execute()
    except Exception:
        return True
    return any("SENT" not in m.get("labelIds", []) for m in t.get("messages", []))


def _pool_and_box(service_id, pool):
    mb = load_mailbox_map().get(service_id)
    return next((e for e in pool.accounts if e.lower() == mb), None) if mb else None


def cmd_test(to):
    to = to.replace(" ", "").strip().lower()
    if "@" not in to:
        sys.exit("That does not look like an email address.")
    _require_identity()
    from sender.gmail_client import MultiGmailService
    pool = MultiGmailService(mode="all")
    results = []
    for sid in BODIES:
        box = _pool_and_box(sid, pool)
        if not box:
            print(f"{sid:14} mailbox not connected, skipped.")
            continue
        subject, body = build_followup(sid, SAMPLE)
        ok = bool(pool.send_email(to_email=to, subject="TEST: " + subject, body_text=body, from_account_email=box, strict_sender=True))
        print(f"{sid:14} from {box}  {'SENT' if ok else 'FAILED (' + str(pool.last_failure) + ')'}")
        results.append((sid, ok))
    tg.send("<b>Follow up test</b>\n" + "\n".join(f"{tg.esc(s)}: {'sent' if o else 'failed'}" for s, o in results))


def cmd_send(service_id, days, limit, lo, hi, auto, countries=None):
    """`countries` (optional) limits follow ups to countries that are in business hours right now."""
    from send_paced import wait_gap
    _require_identity()
    init_scout_tables()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM scout_leads WHERE service_id=? AND status='contacted' AND followup_sent_at IS NULL
               AND sent_at IS NOT NULL AND sent_at <= datetime('now', ?) ORDER BY sent_at LIMIT ?""",
            (service_id, f"-{days} days", limit * 3),
        ).fetchall()
    if not rows:
        print(f"No leads are ready for a follow up yet (needs {days} days with no reply).")
        return
    from sender.gmail_client import MultiGmailService
    pool = MultiGmailService(mode="all")
    box = _pool_and_box(service_id, pool)
    if not box:
        sys.exit(f"The mailbox for {service_id} is not connected.")
    eligible = []
    with get_connection() as conn:
        for r in rows:
            lead = dict(r)
            emails = json.loads(lead["emails_json"] or "[]")
            if countries is not None and lead["country"] not in countries:
                continue
            to = (lead.get("sent_to") or (emails[0] if emails else "")).lower()
            if (not to or lead["country"] in CAREFUL_REGIONS or is_email_blacklisted(to, conn)
                    or is_domain_blacklisted(lead.get("domain"), conn)):
                continue
            eligible.append((lead, (lead.get("sent_to") or emails[0]).lower()))  # the address the first email went to
    eligible = eligible[:limit]
    if not eligible:
        print("No leads are ready for a follow up yet.")
        return
    sent = 0
    try:
        for i, (lead, to) in enumerate(eligible):
            if has_inbound(pool, box, lead.get("gmail_thread_id")):
                print(f"#{lead['id']} {lead['name']}: they wrote back (or the thread could not be read). No follow up.")
                continue
            subject, body = build_followup(service_id, lead)
            print("\n" + "=" * 70 + f"\nFrom:    {mask_email(box)}\nTo:      {mask_email(to)}\nSubject: {subject}\n\n{mask_text(body)}\n" + "=" * 70)
            if not auto:
                c = input("Send this follow up? [y]es / [n]o skip / [q]uit: ").strip().lower()
                if c == "q":
                    break
                if c != "y":
                    continue
            res = pool.send_email(
                to_email=to, subject=subject, body_text=body, from_account_email=box, strict_sender=True,
                thread_id=lead.get("gmail_thread_id"), in_reply_to=thread_ids(pool, box, lead.get("gmail_thread_id")),
            )
            if res:
                with get_connection() as conn:
                    conn.execute("UPDATE scout_leads SET followup_sent_at=CURRENT_TIMESTAMP WHERE id=?", (lead["id"],))
                    conn.commit()
                sent += 1
                print(f"Follow up sent. ({sent} of {limit})")
                if i < len(eligible) - 1:
                    wait_gap(lo, hi)
            else:
                print(f"Not sent ({pool.last_failure}).")
                if pool.last_failure == "no_capacity":
                    break
    except KeyboardInterrupt:
        print("\nStopped by you.")
    print(f"\nDone. {sent} follow up(s) sent.")
    if sent:
        tg.send(f"<b>Follow ups sent: {tg.esc(service_id)}</b>\n{sent} from {tg.esc(box)}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("test")
    t.add_argument("--to", required=True)
    s = sub.add_parser("send")
    s.add_argument("--service", required=True, choices=list(BODIES))
    s.add_argument("--days", type=int, default=5)
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--min-gap", type=float, default=3)
    s.add_argument("--max-gap", type=float, default=8)
    s.add_argument("--auto", action="store_true")
    a = ap.parse_args()
    if a.cmd == "test":
        cmd_test(a.to)
    else:
        lo = max(1.0, a.min_gap)
        cmd_send(a.service, a.days, a.limit, lo, max(lo, a.max_gap), a.auto)


if __name__ == "__main__":
    main()
