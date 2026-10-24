"""
Paced sending. Sends your approved leads one at a time with a gap between each email.
Uses the same checks as outreach.py send: the service's own mailbox only, verified address,
blacklist, regulated region skip, and the daily cap.

  python send_paced.py --service whatsapp_api --limit 10
  python send_paced.py --service whatsapp_api --limit 10 --min-gap 4 --max-gap 9
  python send_paced.py --service whatsapp_api --limit 10 --auto

Gap is in minutes, picked at random between min and max for each email (default 3 to 8,
or set SEND_GAP_MIN_MINUTES and SEND_GAP_MAX_MINUTES in .env). The gap can never be under 1 minute.
Without --auto it still asks y, n or q for every message. With --auto it sends the leads you
already approved without asking each time, and waits the gap between them.
Press Ctrl+C at any time to stop. Nothing is lost.
"""
import argparse
import asyncio
import os
import random
import sys
import time
from typing import List, Optional

import tg
from db import get_connection
from outreach import DAILY_CAP, mailbox_cap, mailbox_room, service_share, _leads, _require_identity, build_message, note_send_failure, park_lead, send_blocker
from safety import mask_email, mask_text
from scout import init_scout_tables
from services import SERVICES, get_service

MIN_GAP_FLOOR = 1.0  # minutes


class _MailboxStopped(Exception):
    """The mailbox is disconnected or hit a Google limit: stop this run, keep the lead approved."""


def wait_gap(lo: float, hi: float):
    seconds = int(random.uniform(lo, hi) * 60)
    print("Waiting before the next email. Ctrl+C to stop.")
    while seconds > 0:
        print(f"\r  next send in {seconds // 60}m {seconds % 60:02d}s   ", end="", flush=True)
        time.sleep(1)
        seconds -= 1
    print("\r" + " " * 40 + "\r", end="")


async def run(service_id: str, limit: int, lo: float, hi: float, auto: bool, countries: Optional[List[str]] = None):
    """Sends up to `limit` approved leads. `countries` (optional) limits sending to those countries, used by the
    autopilot to only email countries that are in business hours right now."""
    _require_identity()
    init_scout_tables()
    svc = get_service(service_id)
    if not svc.mailbox:
        sys.exit(f"No mailbox assigned to {service_id}. Fill mailbox_map.json.")
    from sender.gmail_client import MultiGmailService
    from verifier.email_verifier import EmailVerifier

    pool = MultiGmailService(mode="all")
    box = next((e for e in pool.accounts if e.lower() == svc.mailbox), None)
    if not box:
        sys.exit(f"{svc.mailbox} is not connected. Run: python outreach.py connect --service {service_id}")

    with get_connection() as conn:
        sent_today = conn.execute(
            "SELECT COUNT(*) FROM scout_leads WHERE service_id=? AND DATE(sent_at)=DATE('now')", (service_id,)
        ).fetchone()[0]
    room = max(0, DAILY_CAP - sent_today)
    if room == 0:
        sys.exit(f"Daily cap of {DAILY_CAP} reached for {service_id}.")
    box_room = mailbox_room(box)
    if box_room == 0:
        sys.exit(f"Daily cap reached: the mailbox already sent {mailbox_cap(box)} emails today (all services together, warm-up included).")
    share = service_share(box, service_id)
    if sent_today >= share:
        sys.exit(f"{service_id} already sent its share of {share} today (the mailbox limit is split between the services).")
    room = min(room, box_room, share - sent_today)
    target = min(limit, room)

    verifier = EmailVerifier()
    # Fetched in rounds: leads that can never be sent are taken out of the queue (park_lead), so the next round
    # brings up fresh ones instead of the same blocked leads every run.
    sent = 0
    tried = set()
    try:
        while sent < target:
            leads = [r for r in _leads(service_id, "approved", (target - sent) * 3, countries=countries) if r["id"] not in tried]
            if not leads:
                break
            for r in leads:
                if sent >= target:
                    break
                lead = dict(r)
                tried.add(lead["id"])
                why, to = await send_blocker(lead, verifier)
                if why:
                    print(f"#{lead['id']} {mask_email(to) or lead['name']}: {why}. Removed from the queue.")
                    park_lead(lead["id"], why)
                    continue

                subject, body = build_message(service_id, lead)
                print("\n" + "=" * 70)
                print(f"From:    {mask_email(box)}   (assigned mailbox for {service_id})")
                print(f"To:      {mask_email(to)}  ({lead['country']})")
                print(f"Subject: {subject}\n\n{mask_text(body)}")
                print("=" * 70)
                if not auto:
                    choice = input("Send this one? [y]es / [n]o skip / [q]uit: ").strip().lower()
                    if choice == "q":
                        raise KeyboardInterrupt
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
                    print(f"Sent. ({sent} of {target})")
                    if sent < target:
                        wait_gap(lo, hi)
                elif pool.last_failure == "no_capacity":
                    print(f"Not sent ({pool.last_failure}). Lead stays approved.")
                    raise _MailboxStopped
                else:
                    gone = note_send_failure(lead["id"])
                    print(f"Not sent ({pool.last_failure}). " + ("Removed from the queue." if gone else "Will retry once."))
    except KeyboardInterrupt:
        print("\nStopped by you. Leads not sent stay approved.")
    except _MailboxStopped:
        pass

    print(f"\nDone. Sent {sent}. Today for {service_id}: {sent_today + sent}/{DAILY_CAP}")
    if sent and not os.getenv("AUTOPILOT_RUN"):  # the autopilot sends one combined message instead
        tg.send(
            f"<b>Paced sending finished: {tg.esc(service_id)}</b>\n"
            f"Sent just now: {sent} from {tg.esc(box)}\nToday: {sent_today + sent} of {DAILY_CAP}"
        )
    return sent


def main():
    ap = argparse.ArgumentParser(description="Paced sending")
    ap.add_argument("--service", required=True, choices=list(SERVICES))
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--min-gap", type=float, default=float(os.getenv("SEND_GAP_MIN_MINUTES", "3")))
    ap.add_argument("--max-gap", type=float, default=float(os.getenv("SEND_GAP_MAX_MINUTES", "8")))
    ap.add_argument("--auto", action="store_true")
    a = ap.parse_args()
    lo = max(MIN_GAP_FLOOR, a.min_gap)
    hi = max(lo, a.max_gap)
    print(f"Pacing: {lo:g} to {hi:g} minutes between emails.")
    asyncio.run(run(a.service, a.limit, lo, hi, a.auto))


if __name__ == "__main__":
    main()
