"""
Sends the REAL outreach message to an address you control, so you see exactly what a business would see.
Nothing is sent to any business. Nothing in the database changes.

  python test_real.py you@gmail.com          sample business, one email per service that has a template
  python test_real.py you@gmail.com 12       the real message that lead number 12 would get, sent to you instead
"""
import json
import sys

import tg
from db import get_connection
from outreach import _require_identity, build_message
from scout import init_scout_tables
from services import SERVICES, load_mailbox_map

SAMPLE = {
    "name": "Sample Dental Clinic",
    "owner_name": None,
    "city": "Dubai",
    "country": "AE",
    "keyword": "dental clinic",
    "evidence_json": json.dumps(["WhatsApp click to chat link on the website"]),
}


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python test_real.py you@gmail.com [lead number]")
    to = sys.argv[1].replace(" ", "").strip().lower()
    if "@" not in to or "." not in to.split("@")[-1]:
        sys.exit(f"'{to}' does not look like an email address.")
    _require_identity()

    jobs = []
    if len(sys.argv) > 2:
        init_scout_tables()
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM scout_leads WHERE id=?", (int(sys.argv[2]),)).fetchone()
        if not row:
            sys.exit(f"No lead number {sys.argv[2]}.")
        jobs.append((row["service_id"], dict(row)))
    else:
        jobs = [(sid, SAMPLE) for sid in SERVICES]

    from sender.gmail_client import MultiGmailService

    pool = MultiGmailService(mode="all")
    mapping = load_mailbox_map()
    results = []
    for sid, lead in jobs:
        mb = mapping.get(sid)
        box = next((e for e in pool.accounts if e.lower() == mb), None) if mb else None
        if not box:
            print(f"{sid:14} mailbox not connected, skipped.")
            continue
        try:
            subject, body = build_message(sid, lead)
        except ValueError:
            print(f"{sid:14} has no message template yet, skipped.")
            continue
        res = pool.send_email(
            to_email=to, subject="TEST: " + subject, body_text=body,
            from_account_email=box, strict_sender=True,
        )
        ok = bool(res)
        print(f"{sid:14} from {box}  {'SENT' if ok else 'FAILED (' + str(pool.last_failure) + ')'}")
        results.append((sid, box, ok))

    print(f"\n{sum(1 for r in results if r[2])} real message(s) sent to {to}. Check the inbox and Spam.")
    if results:
        tg.send("<b>Real message test</b>\n" + "\n".join(f"{tg.esc(s)}: {'sent' if o else 'failed'}" for s, _, o in results))


if __name__ == "__main__":
    main()
