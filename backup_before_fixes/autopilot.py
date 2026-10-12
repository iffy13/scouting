"""
Unattended runner. Used by GitHub Actions, and works on your own PC too.

  python autopilot.py --service whatsapp_api            scout, approve, send, follow up, check replies
  python autopilot.py --replies-only                    only check replies and opt outs
  python autopilot.py --service receptionist --dry-run  show the plan, do nothing
  python autopilot.py --prepare                         (Actions only) write token files from secrets

It stops by itself and tells you on Telegram when something is wrong: a mailbox that is not
connected, a high bounce rate, or OUTREACH_PAUSED=true. Nothing here removes the opt out line,
your address, the daily cap, the gaps between emails, or the blacklist.
"""
import argparse
import asyncio
import datetime
import json
import os
import random
import sys
import time
from pathlib import Path

import tg
from services import SERVICES, load_mailbox_map

COUNTRIES = {
    "whatsapp_api": ["AE", "SA", "QA", "KW", "BH", "OM", "SG", "MY"],
    "receptionist": ["US", "CA", "AU", "NZ"],
}
TOKEN_SECRETS = {
    "whatsapp_api": "ACCOUNT_WHATSAPP_JSON",
    "receptionist": "ACCOUNT_RECEPTIONIST_JSON",
    "book_trailer": "ACCOUNT_BOOKS_JSON",
}


def log(msg: str):
    print(f"[autopilot] {msg}", flush=True)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def prepare():
    """Writes accounts/<mailbox>.json from the secrets so the mailboxes can send."""
    mapping = load_mailbox_map()
    Path("accounts").mkdir(exist_ok=True)
    wrote = 0
    for sid, env_name in TOKEN_SECRETS.items():
        data, mailbox = os.getenv(env_name, "").strip(), mapping.get(sid)
        if not data or not mailbox:
            continue
        json.loads(data)  # fails loudly if the secret was pasted wrongly
        Path("accounts", f"{mailbox}.json").write_text(data, encoding="utf-8")
        wrote += 1
    log(f"Wrote {wrote} mailbox token file(s).")


def quiet_wait(lo: float, hi: float):
    secs = int(random.uniform(lo, hi) * 60)
    log(f"waiting {secs // 60}m {secs % 60:02d}s before the next email")
    time.sleep(secs)


def mailbox_ready(service_id: str):
    mb = load_mailbox_map().get(service_id)
    if not mb:
        return False, "no mailbox assigned in mailbox_map.json"
    from sender.gmail_client import MultiGmailService

    pool = MultiGmailService(mode="all")
    if any(e.lower() == mb for e in pool.accounts):
        return True, mb
    return False, f"{mb} could not be loaded (token missing, expired or revoked)"


def bounce_problem():
    """Returns a message when too many emails bounced lately, otherwise None."""
    from db import get_connection
    from scout import init_scout_tables

    init_scout_tables()
    with get_connection() as conn:
        sent = conn.execute("SELECT COUNT(*) FROM scout_leads WHERE sent_at >= datetime('now','-7 days')").fetchone()[0]
        try:
            bounced = conn.execute(
                "SELECT COUNT(*) FROM blacklist WHERE reason='bounce' AND created_at >= datetime('now','-7 days')"
            ).fetchone()[0]
        except Exception:
            bounced = 0
    if sent >= 10 and bounced / sent > 0.08:
        return f"{bounced} bounces from {sent} emails in 7 days"
    return None


def sent_today(service_id: str) -> int:
    from db import get_connection

    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM scout_leads WHERE service_id=? AND DATE(sent_at)=DATE('now')", (service_id,)
        ).fetchone()[0]


def check_replies() -> str:
    import outreach

    c = outreach.check_replies_once()
    return f"replies {c['replies']}, opt outs {c['opt_outs']}, bounces {c['bounces']}"


def daily(a):
    sid = a.service
    lo = max(1.0, a.min_gap)
    hi = max(lo, a.max_gap)
    paused = os.getenv("OUTREACH_PAUSED", "").lower() in ("true", "1", "yes")
    notes = []

    ready, info = mailbox_ready(sid)
    if not ready:
        notes.append(f"Mailbox problem: {info}. Reconnect it on your PC and update the GitHub secret.")
    problem = bounce_problem()
    if problem:
        notes.append(f"Sending paused automatically: {problem}.")
    if paused:
        notes.append("Sending is paused (OUTREACH_PAUSED).")
    can_send = ready and not problem and not paused

    plan = f"service {sid}: scout up to {a.scout_max}, approve, send up to {a.send_limit} (gap {lo:g} to {hi:g} min), follow ups up to {a.followup_limit}"
    log(plan)
    for n in notes:
        log(n)
    if a.dry_run:
        log("dry run, nothing done.")
        return

    import scout
    import run_all
    import send_paced
    import followup

    send_paced.wait_gap = quiet_wait  # one short log line per wait instead of a countdown

    before = sent_today(sid)
    if a.scout_max > 0:
        try:
            asyncio.run(scout.scout_service(sid, COUNTRIES[sid], [], a.scout_max))
        except Exception as e:
            notes.append(f"Scouting failed: {str(e)[:120]}")
    try:
        run_all.approve_all()
    except Exception as e:
        notes.append(f"Approval step failed: {str(e)[:120]}")

    if can_send and a.send_limit > 0:
        try:
            asyncio.run(send_paced.run(sid, a.send_limit, lo, hi, True))
        except SystemExit as e:
            notes.append(f"Sending stopped: {e}")
        except Exception as e:
            notes.append(f"Sending failed: {str(e)[:120]}")
        if a.followup_limit > 0 and datetime.datetime.utcnow().weekday() in (1, 3):
            try:
                followup.cmd_send(sid, 5, a.followup_limit, lo, hi, True)
            except SystemExit as e:
                notes.append(f"Follow ups stopped: {e}")
            except Exception as e:
                notes.append(f"Follow ups failed: {str(e)[:120]}")

    try:
        reply_line = check_replies()
    except Exception as e:
        reply_line = f"reply check failed: {str(e)[:80]}"

    sent_now = sent_today(sid) - before
    text = f"<b>Autopilot: {tg.esc(sid)}</b>\nEmails sent this run: {sent_now}\nReplies check: {tg.esc(reply_line)}"
    if notes:
        text += "\n\n<b>Attention</b>\n" + "\n".join(tg.esc(n) for n in notes)
    tg.send(text)
    log(f"finished. sent {sent_now}. {reply_line}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", choices=list(COUNTRIES))
    ap.add_argument("--replies-only", action="store_true")
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--scout-max", type=int, default=env_int("AP_SCOUT_MAX", 20))
    ap.add_argument("--send-limit", type=int, default=env_int("AP_SEND_LIMIT", 6))
    ap.add_argument("--followup-limit", type=int, default=env_int("AP_FOLLOWUP_LIMIT", 4))
    ap.add_argument("--min-gap", type=float, default=float(os.getenv("AP_MIN_GAP") or 2))
    ap.add_argument("--max-gap", type=float, default=float(os.getenv("AP_MAX_GAP") or 4))
    a = ap.parse_args()

    if a.prepare:
        prepare()
        return
    if a.replies_only:
        if a.dry_run:
            log("dry run: would check replies.")
            return
        line = check_replies()
        log(line)
        if "replies 0, opt outs 0, bounces 0" not in line:
            tg.send(f"<b>Reply check</b>\n{tg.esc(line)}")
        return
    if not a.service:
        sys.exit("Use --service whatsapp_api or --service receptionist, or --replies-only.")
    daily(a)


if __name__ == "__main__":
    main()
