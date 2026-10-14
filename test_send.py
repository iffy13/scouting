"""
Spam test. Sends the REAL first email (same wording, subject and signature a lead would get) from your mailboxes to
an address you choose, so you can see whether it lands in Inbox, Promotions or Spam. Nothing is marked as sent and
no lead is touched.

  python test_send.py --to you@gmail.com                         one email from each of the 3 mailboxes
  python test_send.py --to you@gmail.com --service whatsapp_api  only that mailbox
  python test_send.py --to test-abc@srv1.mail-tester.com --service receptionist   score it on mail-tester.com

There is no "TEST" in the subject on purpose: spam filters must judge exactly what a lead would receive.
"""
import argparse
import json
import sys

from db import get_connection
from outreach import _require_identity, build_message
from scout import init_scout_tables
from services import load_mailbox_map
from safety import mask_email

SAMPLE = {
    "whatsapp_api": {"name": "Glow Med Spa", "domain": "glowmedspa.ae", "keyword": "med spa", "country": "AE",
                     "evidence_json": json.dumps(["uses a WhatsApp click to chat link (manual WhatsApp today)"])},
    "receptionist": {"name": "Bright Plumbing", "domain": "brightplumbing.com", "keyword": "emergency plumber",
                     "country": "US", "evidence_json": json.dumps(["pays for traffic, missed calls cost real money"])},
    "render_3d": {"name": "Palm Villas", "domain": "palmvillas.ae", "keyword": "villa developer", "country": "AE",
                  "evidence_json": json.dumps(["mentions upcoming, proposed or under construction work"])},
}


def real_lead(service_id: str):
    """The next lead in the queue, so the test uses exactly what would go out next. Falls back to a sample."""
    init_scout_tables()
    with get_connection() as conn:
        r = conn.execute(
            "SELECT * FROM scout_leads WHERE service_id=? AND status='approved' ORDER BY score DESC LIMIT 1", (service_id,)
        ).fetchone()
    return (dict(r), "next lead in your queue") if r else (dict(SAMPLE[service_id]), "sample lead")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True, help="the address to send the test to")
    ap.add_argument("--service", choices=list(SAMPLE), help="only this mailbox (default: all three)")
    a = ap.parse_args()
    to = a.to.strip().lower()
    if "@" not in to:
        sys.exit("That does not look like an email address.")
    _require_identity()
    from sender.gmail_client import MultiGmailService

    pool = MultiGmailService(mode="all")
    mapping = load_mailbox_map()
    for sid in ([a.service] if a.service else list(SAMPLE)):
        mb = mapping.get(sid)
        box = next((e for e in pool.accounts if e.lower() == (mb or "")), None)
        if not box:
            print(f"{sid:13} mailbox {mb or 'not set'} is not connected here. Run: python outreach.py connect --service {sid}")
            continue
        lead, where = real_lead(sid)
        subject, body = build_message(sid, lead)
        res = pool.send_email(to_email=to, subject=subject, body_text=body, from_account_email=box, strict_sender=True)
        print("=" * 60)
        print(f"{sid}: {'SENT' if res else 'FAILED (' + str(pool.last_failure) + ')'} from {mask_email(box)} to {mask_email(to)}  ({where})")
        print(f"Subject: {subject}\n\n{body}")
    print("=" * 60)
    print("Now check where each one landed: Inbox, Promotions or Spam. On mail-tester.com, click 'Then check your score'.")


if __name__ == "__main__":
    main()
