"""
Unattended runner. Used by GitHub Actions, and works on your own PC too.

  python autopilot.py --service whatsapp_api            scout, approve, send, follow up, check replies
  python autopilot.py --replies-only                    only check replies and opt outs
  python autopilot.py --service receptionist --dry-run  show the plan, do nothing
  python autopilot.py --prepare                         (Actions only) write token files from secrets
  python autopilot.py --service whatsapp_api --scout-only   scout and approve, never send
  python autopilot.py --mark | --export-new FILE | --import-leads FILE
                                                        (PC runner) hand new leads to the cloud database

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

import render3d
import tg
from safety import mask_email, mask_emails_in, open_countries
from services import SERVICES, load_mailbox_map

COUNTRIES = {
    "whatsapp_api": ["AE", "SA", "QA", "KW", "BH", "OM", "SG", "MY"],
    "receptionist": ["US", "CA", "AU", "NZ"],
    "render_3d": render3d.COUNTRIES,
}
TOKEN_SECRETS = {
    "whatsapp_api": "ACCOUNT_WHATSAPP_JSON",
    "receptionist": "ACCOUNT_RECEPTIONIST_JSON",
    "render_3d": "ACCOUNT_BOOKS_JSON",  # the third mailbox, formerly book_trailer
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


MARK_FILE = Path(".scout_mark")


def scout_only(sid: str, scout_max: int):
    """Scouts and approves one service, sends nothing. Tells the workflow when search was blocked
    or Serper ran out, so the PC runner can take over."""
    import scout
    import run_all

    result = asyncio.run(scout.scout_service(sid, COUNTRIES[sid], [], scout_max))
    run_all.approve_all()
    log(f"scout only: {result['added']} new for {sid}" + (f", blocked: {result['blocked']}" if result["blocked"] else ""))
    out = os.getenv("GITHUB_OUTPUT")
    if result["blocked"] and out:
        with open(out, "a", encoding="utf-8") as f:
            f.write("fallback=true\n")


def lead_columns(conn) -> list:
    return [r[1] for r in conn.execute("PRAGMA table_info(scout_leads)") if r[1] != "id"]


def mark_leads():
    from db import get_connection
    from scout import init_scout_tables

    init_scout_tables()
    with get_connection() as conn:
        top = conn.execute("SELECT COALESCE(MAX(id), 0) FROM scout_leads").fetchone()[0]
    MARK_FILE.write_text(str(top), encoding="utf-8")
    log(f"marked lead id {top}")


def export_new(path: str):
    from db import get_connection

    since = int(MARK_FILE.read_text(encoding="utf-8").strip() or 0)
    with get_connection() as conn:
        cols = lead_columns(conn)
        rows = conn.execute(f"SELECT {', '.join(cols)} FROM scout_leads WHERE id > ?", (since,)).fetchall()
    data = [dict(zip(cols, tuple(r))) for r in rows]
    Path(path).write_text(json.dumps(data), encoding="utf-8")
    log(f"exported {len(data)} new lead(s)")


def import_leads(path: str):
    """Adds leads found on the PC to this database. Never overwrites: a business already known here is skipped."""
    from db import get_connection
    from scout import init_scout_tables
    from seen import known_domain

    init_scout_tables()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    added = 0
    with get_connection() as conn:
        cols = set(lead_columns(conn))
        for row in data:
            if known_domain(conn, row.get("domain") or ""):
                continue
            keys = [k for k in row if k in cols]
            conn.execute(
                f"INSERT OR IGNORE INTO scout_leads ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
                [row[k] for k in keys],
            )
            added += 1
        conn.commit()
    log(f"imported {added} of {len(data)} lead(s) from the PC runner")


def stop_note(sid: str, reason: str, config: bool):
    """Prints why sending stopped. Config problems also become a GitHub ::error:: annotation."""
    reason = mask_emails_in(reason)
    log(f"Sending stopped for {sid}: {reason}")
    if config and os.getenv("GITHUB_ACTIONS"):
        print(f"::error title=Sending stopped ({sid})::{reason}", flush=True)


def approved_unsent(service_id: str) -> int:
    from db import get_connection
    from scout import init_scout_tables

    init_scout_tables()
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM scout_leads WHERE service_id=? AND status='approved' AND sent_at IS NULL", (service_id,)
        ).fetchone()[0]


def daily(a):
    sid = a.service
    lo = max(1.0, a.min_gap)
    hi = max(lo, a.max_gap)
    paused = os.getenv("OUTREACH_PAUSED", "").lower() in ("true", "1", "yes")
    notes = []

    from outreach import BUSINESS_NAME, DAILY_CAP, POSTAL_ADDRESS, postal_address_problem

    # Problems with the setup (secrets, address, mailbox) fail the run (red in Actions). A pause, the bounce guard,
    # an empty queue or a full daily cap are normal and leave the run green.
    config_problems = []
    address_why = postal_address_problem(POSTAL_ADDRESS) if POSTAL_ADDRESS.strip() else "is not set (missing secret)"
    if not BUSINESS_NAME.strip():
        config_problems.append("BUSINESS_NAME is not set (missing secret)")
    if address_why:
        config_problems.append(f"POSTAL_ADDRESS: {address_why}")
    ready, info = mailbox_ready(sid)
    if not ready:
        config_problems.append(f"mailbox problem: {info}. Reconnect it on your PC and update the GitHub secret")
    problem = bounce_problem()
    open_now = open_countries(COUNTRIES[sid])
    log(f"status {sid}: mailbox {mask_email(load_mailbox_map().get(sid)) or 'NOT ASSIGNED'}, sent today {sent_today(sid)}/{DAILY_CAP}, "
        f"approved and unsent {approved_unsent(sid)}, POSTAL_ADDRESS passes check: {'no' if address_why else 'yes'}, "
        f"countries in business hours now: {', '.join(open_now) or 'none'}")

    plan = f"service {sid}: scout up to {a.scout_max}, approve, send up to {a.send_limit} (gap {lo:g} to {hi:g} min), follow ups up to {a.followup_limit}"
    log(plan)
    for reason in config_problems:
        stop_note(sid, reason, config=True)
        notes.append(f"Sending stopped: {reason}.")
    if problem:
        stop_note(sid, f"paused automatically, {problem}", config=False)
        notes.append(f"Sending paused automatically: {problem}.")
    if paused:
        stop_note(sid, "OUTREACH_PAUSED is true", config=False)
        notes.append("Sending is paused (OUTREACH_PAUSED).")
    if not open_now:
        log("no target country is in business hours right now, so nothing is sent this run (normal)")
    can_send = ready and not problem and not paused and not config_problems and bool(open_now)
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
            asyncio.run(send_paced.run(sid, a.send_limit, lo, hi, True, countries=open_now))
        except SystemExit as e:
            reason = str(e)
            # a full daily cap is normal; a missing or disconnected mailbox is a setup problem
            is_config = not reason.startswith("Daily cap")
            stop_note(sid, reason, config=is_config)
            if is_config:
                config_problems.append(reason)
            notes.append(f"Sending stopped: {mask_emails_in(str(e))}")
        except Exception as e:
            notes.append(f"Sending failed: {str(e)[:120]}")
        if a.followup_limit > 0 and datetime.datetime.utcnow().weekday() in (1, 3):
            try:
                followup.cmd_send(sid, 5, a.followup_limit, lo, hi, True, countries=open_now)
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
    if config_problems:
        sys.exit(f"Run failed: {len(config_problems)} setup problem(s) stopped sending for {sid}, see the lines above.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", choices=list(COUNTRIES))
    ap.add_argument("--replies-only", action="store_true")
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--scout-only", action="store_true")
    ap.add_argument("--mark", action="store_true")
    ap.add_argument("--export-new", metavar="FILE")
    ap.add_argument("--import-leads", metavar="FILE")
    ap.add_argument("--scout-max", type=int, default=env_int("AP_SCOUT_MAX", 20))
    ap.add_argument("--send-limit", type=int, default=env_int("AP_SEND_LIMIT", 6))
    ap.add_argument("--followup-limit", type=int, default=env_int("AP_FOLLOWUP_LIMIT", 4))
    ap.add_argument("--min-gap", type=float, default=float(os.getenv("AP_MIN_GAP") or 2))
    ap.add_argument("--max-gap", type=float, default=float(os.getenv("AP_MAX_GAP") or 4))
    a = ap.parse_args()

    if a.prepare:
        prepare()
        return
    if a.mark:
        mark_leads()
        return
    if a.export_new:
        export_new(a.export_new)
        return
    if a.import_leads:
        import_leads(a.import_leads)
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
    if a.scout_only:
        scout_only(a.service, a.scout_max)
        return
    daily(a)


if __name__ == "__main__":
    main()
