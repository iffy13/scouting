"""
One polite follow up per business. Same mailbox as the first email. Never a second follow up.

  python followup.py test --to you@gmail.com       sends a sample follow up from each service mailbox to YOU
  python followup.py send --service whatsapp_api --days 5 --limit 10
  python followup.py send --service whatsapp_api --days 5 --limit 10 --auto

'send' only picks leads that were emailed at least N days ago, did not reply, did not opt out,
and have not had a follow up yet. Same pacing gap as send_paced.py.
"""
import argparse
import json
import random
import sys

import tg
from db import get_connection, is_email_blacklisted
from outreach import CAREFUL_REGIONS, DAILY_CAP, _require_identity, footer
from scout import init_scout_tables
from services import SERVICES, get_service, load_mailbox_map

BODIES = {
    "whatsapp_api": [
        "I wrote a few days ago about setting up the official WhatsApp Business Platform for {name}. I know inboxes get busy, so I wanted to check once whether it is relevant.\n\nIf it is, I can send a short outline of how it works and what it costs. If it is not, no problem at all.",
        "A quick note in case my last email got buried. I help businesses like {name} set up the official WhatsApp Business Platform with Meta verification, so customer messages are handled in one place.\n\nIf that is useful, reply and I will send a short outline. If not, I will not write again.",
    ],
    "receptionist": [
        "I wrote a few days ago about an AI phone assistant that answers calls for businesses like {name}. I know things get busy, so I wanted to check once whether it is relevant.\n\nIf it is, I can send a short recording of how it handles a call. If it is not, no problem at all.",
        "A quick note in case my last email got buried. I build AI phone assistants that answer every call, take the details and book the job for businesses like {name}.\n\nIf that is useful, reply and I will send a short example. If not, I will not write again.",
    ],
}
SUBJECTS = {
    "whatsapp_api": ["A quick follow up for {name}", "Following up about {name}"],
    "receptionist": ["A quick follow up for {name}", "Following up about calls at {name}"],
}
SAMPLE = {"name": "Sample Dental Clinic", "domain": "sample.com", "owner_name": None}


def build_followup(service_id, lead):
    rnd = random.Random(f"fu:{service_id}:{lead.get('domain') or lead.get('name')}")
    name = lead["name"]
    who = lead.get("owner_name") or f"{name} team"
    body = f"Hi {who},\n\n" + rnd.choice(BODIES[service_id]).format(name=name) + footer()
    return rnd.choice(SUBJECTS[service_id]).format(name=name), body


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


def cmd_send(service_id, days, limit, lo, hi, auto):
    from send_paced import wait_gap
    _require_identity()
    init_scout_tables()
    with get_connection() as conn:
        try:
            conn.execute("ALTER TABLE scout_leads ADD COLUMN followup_sent_at TIMESTAMP")
        except Exception:
            pass
        conn.commit()
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
            if not emails or lead["country"] in CAREFUL_REGIONS or is_email_blacklisted(emails[0].lower(), conn):
                continue
            eligible.append((lead, emails[0].lower()))
    eligible = eligible[:limit]
    if not eligible:
        print("No leads are ready for a follow up yet.")
        return
    sent = 0
    try:
        for i, (lead, to) in enumerate(eligible):
            subject, body = build_followup(service_id, lead)
            print("\n" + "=" * 70 + f"\nFrom:    {box}\nTo:      {to}\nSubject: {subject}\n\n{body}\n" + "=" * 70)
            if not auto:
                c = input("Send this follow up? [y]es / [n]o skip / [q]uit: ").strip().lower()
                if c == "q":
                    break
                if c != "y":
                    continue
            res = pool.send_email(to_email=to, subject=subject, body_text=body, from_account_email=box, strict_sender=True)
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
