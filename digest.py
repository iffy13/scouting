#!/usr/bin/env python3
"""Daily Telegram digest.

Routine news (new leads, hiring posts, what was emailed, run summaries) is written to a file during the day and sent
ONCE a day as one short summary plus the full file. Urgent news (a lead replied, sending stopped, credits ran out)
still goes to Telegram straight away.

The file lives in the scout state folder, which the scout and outreach workflows already save between runs.

Run:  python digest.py --send       send today's digest now (the daily workflow does this)
      python digest.py --selftest
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

STATE_DIR = os.getenv("ROBLOX_SCOUT_STATE", "roblox_scout_state")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
FILE = lambda: os.path.join(STATE_DIR, "digest.txt")
STATS = lambda: os.path.join(STATE_DIR, "digest_stats.json")
COUNTERS = [("buyer_posts", "Buyer posts found"), ("email_leads", "New email leads"),
            ("emails_sent", "First emails sent"), ("followups", "Follow ups sent"),
            ("replies", "Replies"), ("bounces", "Bounces")]


def _now():
    return datetime.now(timezone.utc)


def add(section, text):
    """Adds a block to today's digest file."""
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(FILE(), "a", encoding="utf-8") as f:
        f.write(f"\n===== {section}  ({_now().strftime('%H:%M UTC')}) =====\n{text.strip()}\n")


def bump(**counts):
    stats = _load_stats()
    for k, v in counts.items():
        stats[k] = stats.get(k, 0) + int(v or 0)
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATS(), "w") as f:
        json.dump(stats, f)


def note(key, value):
    """Keeps the latest value of something for the summary (for example the Serper balance)."""
    stats = _load_stats()
    stats.setdefault("notes", {})[key] = value
    with open(STATS(), "w") as f:
        json.dump(stats, f)


def _load_stats():
    try:
        with open(STATS()) as f:
            return json.load(f)
    except Exception:
        return {}


def urgent(text):
    """Sends straight to Telegram. Use only for things that need action now."""
    if not (TG_TOKEN and TG_CHAT):
        print("(urgent, no Telegram) " + text)
        return
    time.sleep(0.6)
    data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": text[:3900], "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data, timeout=30)
    except Exception as e:
        print(f"telegram failed: {e}")


def _send_document(name, data, caption):
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{TG_CHAT}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption[:1000]}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{name}\"\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    urllib.request.urlopen(req, timeout=60)


def summary_text(stats):
    day = _now().strftime("%A %d %B")
    lines = [f"Daily digest, {day}"]
    lines += [f"{label}: {stats.get(key, 0)}" for key, label in COUNTERS]
    for k, v in (stats.get("notes") or {}).items():
        lines.append(f"{k}: {v}")
    lines.append("Full details (every lead, post and email) are in the attached file.")
    return "\n".join(lines)


def send():
    """Sends the day's digest and starts a new one. Returns True when something was sent."""
    try:
        with open(FILE(), "rb") as f:
            data = f.read()
    except FileNotFoundError:
        data = b""
    stats = _load_stats()
    if not data.strip() and not any(stats.get(k) for k, _ in COUNTERS):
        print("nothing to send today")
        return False
    text = summary_text(stats)
    if not (TG_TOKEN and TG_CHAT):
        print(text + "\n" + data.decode("utf-8", "ignore")[:2000])
    else:
        name = f"digest_{_now().strftime('%Y-%m-%d')}.txt"
        header = (text + "\n\n").encode()
        try:
            _send_document(name, header + data, text)
        except Exception as e:
            print(f"digest file failed ({e}), sending the summary as a message")
            urgent(text)
    for p in (FILE(), STATS()):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
    return True


def selftest():
    import tempfile
    global STATE_DIR
    STATE_DIR = tempfile.mkdtemp()
    add("Email leads", "1. Some channel <a@b.com>")
    bump(email_leads=3, emails_sent=10)
    bump(emails_sent=5, replies=1)
    note("Serper credits left", 812)
    st = _load_stats()
    assert st["emails_sent"] == 15 and st["replies"] == 1, st
    t = summary_text(st)
    assert "First emails sent: 15" in t and "Serper credits left: 812" in t, t
    assert send() is True and not os.path.exists(FILE()) and send() is False
    print("selftest passed")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif "--send" in sys.argv:
        send()
    else:
        sys.exit("usage: python digest.py --send | --selftest")
