"""
Autopilot. One window that runs the whole outreach day for you and keeps you posted on Telegram.

  python autopilot_local.py              run until you close the window (START_AUTOPILOT.bat does this)
  python autopilot_local.py --once       run one full cycle now (scout, approve, send, follow ups) and stop
  python autopilot_local.py --dry-run    show what it would do right now, nothing is scouted or sent

What it does, every day:
  1. Scouts each service for new businesses, once a day, and approves the usable ones
     (has an email, not a list or directory, not a regulated country). Same rules as run_all.py.
  2. When it is a working day and business hours (08:00 to 17:00) in a service's target countries, it sends to
     those countries only:
       first the one polite follow up to leads emailed FOLLOWUP_DAYS ago with no reply,
       then new approved leads, 3 to 8 minutes apart, from that service's one mailbox.
     Follow ups and new emails together never go over SCOUT_DAILY_CAP per service per day.
  3. Checks every contacted thread for replies every 10 minutes, all day. A real reply goes to
     Telegram straight away. Opt outs are blacklisted, bounces are blacklisted.
  4. Sends you a Telegram summary once a day after the last window closes.
If anything breaks, you get a Telegram message with the error and it carries on with the next job.

It refuses to start unless .env has LOCAL_AUTOPILOT_SENDS=true. GitHub Actions also sends, from its own copy of
the database, so running both would email the same businesses twice. Turn the GitHub workflows off first
(Actions tab, each workflow, "Disable workflow"), then set LOCAL_AUTOPILOT_SENDS=true here.

Settings (optional, in .env):
  SCOUT_DAILY_CAP=20             most emails per service per day, follow ups included
  AUTOPILOT_SCOUT_MAX=60         new businesses to scout per service per day
  FOLLOWUP_DAYS=5                days to wait before the single follow up
  SEND_GAP_MIN_MINUTES=3         gap between emails
  SEND_GAP_MAX_MINUTES=8
"""
import argparse
import asyncio
import os
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import tg
from config import BASE_DIR
from db import get_connection
from scout import init_scout_tables

# Target countries per service, the same lists GitHub Actions uses. Each country is emailed only in its own
# business hours on its own working days (safety.py).
from autopilot import COUNTRIES as TARGETS
from safety import open_countries

WINDOWS = TARGETS  # kept under the old name: daily_summary loops over it
SCOUT_ARGS = {sid: ["--countries", ",".join(c)] for sid, c in TARGETS.items()}
DAILY_CAP = int(os.getenv("SCOUT_DAILY_CAP", "20"))
SCOUT_MAX = int(os.getenv("AUTOPILOT_SCOUT_MAX", "60"))
FOLLOWUP_DAYS = int(os.getenv("FOLLOWUP_DAYS", "5"))
GAP_LO = max(1.0, float(os.getenv("SEND_GAP_MIN_MINUTES", "3")))
GAP_HI = max(GAP_LO, float(os.getenv("SEND_GAP_MAX_MINUTES", "8")))
REPLY_EVERY = 600  # seconds
LOCK = BASE_DIR / "autopilot.lock"

stop = threading.Event()


def log(msg: str):
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] {msg}", flush=True)


def alert_error(job: str, err: BaseException):
    log(f"{job} failed: {err}")
    tg.send(f"<b>Autopilot problem: {tg.esc(job)}</b>\n<code>{tg.esc(str(err)[:500])}</code>\nIt will try again later.")


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def open_now(service_id: str, now_utc: datetime) -> list:
    """The service's countries where it is business hours right now."""
    return open_countries(TARGETS[service_id], now_utc)


def sent_today(service_id: str) -> int:
    """New emails plus follow ups sent today (UTC day, same as the rest of the tool)."""
    with get_connection() as conn:
        new = conn.execute(
            "SELECT COUNT(*) FROM scout_leads WHERE service_id=? AND DATE(sent_at)=DATE('now')", (service_id,)
        ).fetchone()[0]
        try:
            fu = conn.execute(
                "SELECT COUNT(*) FROM scout_leads WHERE service_id=? AND DATE(followup_sent_at)=DATE('now')", (service_id,)
            ).fetchone()[0]
        except Exception:
            fu = 0
    return new + fu


def ensure_followup_column():
    with get_connection() as conn:
        try:
            conn.execute("ALTER TABLE scout_leads ADD COLUMN followup_sent_at TIMESTAMP")
            conn.commit()
        except Exception:
            pass


# ---------------------------------------------------------------- jobs

def job_scout():
    from run_all import approve_all
    for sid, extra in SCOUT_ARGS.items():
        if stop.is_set():
            return
        log(f"Scouting {sid}, up to {SCOUT_MAX} businesses")
        subprocess.run([sys.executable, "scout.py", "--service", sid, "--max", str(SCOUT_MAX)] + extra, cwd=BASE_DIR)
    lines = approve_all()
    tg.send("<b>Daily scouting finished</b>\n" + "\n".join(tg.esc(l) for l in lines))
    log("Scouting and approval done")


def job_send(service_id: str, countries: list):
    """Follow ups first, then new leads, inside the cap, only to `countries`.
    Returns True when there is nothing more to do for these countries today."""
    import followup
    import send_paced

    room = DAILY_CAP - sent_today(service_id)
    if room <= 0:
        log(f"{service_id}: daily cap of {DAILY_CAP} reached")
        return True
    try:
        followup.cmd_send(service_id, FOLLOWUP_DAYS, room, GAP_LO, GAP_HI, auto=True, countries=countries)
    except SystemExit as e:
        alert_error(f"follow ups for {service_id}", e)
        return True
    room = DAILY_CAP - sent_today(service_id)
    if room <= 0:
        return True
    with get_connection() as conn:
        waiting = conn.execute(
            "SELECT COUNT(*) FROM scout_leads WHERE service_id=? AND status='approved'", (service_id,)
        ).fetchone()[0]
    if not waiting:
        log(f"{service_id}: no approved leads waiting")
        return False  # scouting later today may add some
    try:
        asyncio.run(send_paced.run(service_id, room, GAP_LO, GAP_HI, auto=True, countries=countries))
    except SystemExit as e:
        # mailbox not connected, or cap reached
        if "cap" not in str(e).lower():
            alert_error(f"sending for {service_id}", e)
        return True
    return DAILY_CAP - sent_today(service_id) <= 0


def daily_summary():
    lines = []
    with get_connection() as conn:
        for sid in WINDOWS:
            row = conn.execute(
                """SELECT
                     SUM(CASE WHEN DATE(sent_at)=DATE('now') THEN 1 ELSE 0 END),
                     SUM(CASE WHEN DATE(replied_at)=DATE('now') AND status='replied' THEN 1 ELSE 0 END),
                     SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END),
                     SUM(CASE WHEN status='replied' THEN 1 ELSE 0 END),
                     SUM(CASE WHEN status='contacted' THEN 1 ELSE 0 END)
                   FROM scout_leads WHERE service_id=?""",
                (sid,),
            ).fetchone()
            new, rep, waiting, rep_all, contacted = [x or 0 for x in row]
            lines.append(
                f"<b>{tg.esc(sid)}</b>: sent today {sent_today(sid)} ({new} new), replies today {rep}, "
                f"waiting to send {waiting}, total replied {rep_all}, awaiting reply {contacted}"
            )
    tg.send("<b>Daily outreach summary</b>\n" + "\n".join(lines))


# ---------------------------------------------------------------- loops

def reply_watcher():
    from outreach import check_replies_once
    while not stop.is_set():
        try:
            c = check_replies_once()
            log(f"Replies checked: {c['checked']} threads, {c['replies']} new replies, {c['opt_outs']} opt outs, {c['bounces']} bounces")
        except Exception as e:
            alert_error("reply check", e)
        stop.wait(REPLY_EVERY)


def plan(now_utc: datetime, state: dict) -> list:
    """Returns the jobs that are due right now."""
    jobs = []
    today = now_utc.strftime("%Y-%m-%d")
    if state.get("scouted") != today:
        jobs.append(("scout", None))
    for sid in TARGETS:
        region = ",".join(open_now(sid, now_utc))
        if region and state.get(f"done:{sid}:{region}") != today:
            jobs.append(("send", sid))
    if now_utc.hour >= 22 and state.get("summary") != today:
        jobs.append(("summary", None))
    return jobs


def run_job(kind: str, sid, state: dict, today: str):
    try:
        if kind == "scout":
            job_scout()
            state["scouted"] = today
        elif kind == "send":
            region = open_now(sid, datetime.now(timezone.utc))
            if job_send(sid, region):
                state[f"done:{sid}:{','.join(region)}"] = today
            else:
                state[f"retry:{sid}"] = time.time() + 3600
        elif kind == "summary":
            daily_summary()
            state["summary"] = today
    except Exception as e:
        alert_error(f"{kind} {sid or ''}".strip(), e)
        traceback.print_exc()
        if kind == "scout":
            state["scouted"] = today  # do not loop on a broken scout, try again tomorrow
        if kind == "send":
            state[f"retry:{sid}"] = time.time() + 1800


def main_loop(once: bool):
    state: dict = {}
    if not once:
        threading.Thread(target=reply_watcher, daemon=True).start()
    while not stop.is_set():
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        for kind, sid in plan(now, state):
            if kind == "send" and state.get(f"retry:{sid}", 0) > time.time():
                continue
            if once and kind == "summary":
                continue
            run_job(kind, sid, state, today)
            if stop.is_set():
                break
        if once:
            from outreach import check_replies_once
            c = check_replies_once()
            log(f"Replies checked: {c['replies']} new replies")
            return
        stop.wait(60)


def dry_run():
    now = datetime.now(timezone.utc)
    print(f"Now (UTC): {now:%Y-%m-%d %H:%M}")
    for sid in TARGETS:
        region = open_now(sid, now)
        print(f"{sid:14} in business hours now: {', '.join(region) or 'none'}  sent today {sent_today(sid)}/{DAILY_CAP}")
    print("Jobs due now:", ", ".join(f"{k}{' ' + s if s else ''}" for k, s in plan(now, {})) or "none")


def main():
    ap = argparse.ArgumentParser(description="Runs scouting, sending, follow ups and reply alerts on a schedule")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    os.chdir(BASE_DIR)
    init_scout_tables()
    ensure_followup_column()
    if a.dry_run:
        dry_run()
        return
    from outreach import _require_identity
    _require_identity()
    if os.getenv("LOCAL_AUTOPILOT_SENDS", "").lower() not in ("true", "1", "yes"):
        sys.exit("Not starting: LOCAL_AUTOPILOT_SENDS is not true in .env.\n"
                 "GitHub Actions is probably sending too, from its own database, and running both would email the same\n"
                 "businesses twice. Disable the GitHub workflows first, then add LOCAL_AUTOPILOT_SENDS=true to .env.")

    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 120:
        sys.exit("Autopilot already seems to be running in another window. Close it first.")

    def heartbeat():
        while not stop.is_set():
            LOCK.write_text(str(os.getpid()))
            stop.wait(60)

    threading.Thread(target=heartbeat, daemon=True).start()
    tg.send(
        "<b>Autopilot started</b>\n"
        f"Cap {DAILY_CAP} emails per service per day, {GAP_LO:g} to {GAP_HI:g} minutes apart.\n"
        "Replies are checked every 10 minutes."
    )
    try:
        main_loop(a.once)
    except KeyboardInterrupt:
        log("Stopped by you.")
    except Exception as e:
        alert_error("autopilot", e)
        raise
    finally:
        stop.set()
        try:
            LOCK.unlink()
        except Exception:
            pass
        tg.send("<b>Autopilot stopped</b>\nStart it again with START_AUTOPILOT.bat.")


if __name__ == "__main__":
    main()
