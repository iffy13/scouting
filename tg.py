"""
Telegram alerts for the scouting and outreach tools.

Needs two lines in .env:
  TELEGRAM_BOT_TOKEN=123456:ABC...      (from @BotFather)
  TELEGRAM_CHAT_ID=123456789            (your own chat id, see python outreach.py telegram)

Alerts never crash the main job. If Telegram is not set up or is unreachable,
the job carries on and prints a short note instead.
"""
import html
import logging

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("tg")


def configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def esc(value) -> str:
    return html.escape(str(value or ""), quote=False)


def send(text: str) -> bool:
    """Send an HTML formatted message. Returns True on success."""
    if not configured():
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text[:3900],
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if r.status_code != 200:
            logger.warning("Telegram said %s: %s", r.status_code, r.text[:200])
        return r.status_code == 200
    except Exception as e:
        logger.warning("Telegram not reachable: %s", e)
        return False


def find_chat_id() -> str:
    """Looks at recent messages sent to the bot and returns the chat id of the latest one."""
    if not TELEGRAM_BOT_TOKEN:
        return ""
    try:
        r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", timeout=10)
        updates = r.json().get("result", [])
        for u in reversed(updates):
            msg = u.get("message") or u.get("channel_post") or {}
            if msg.get("chat", {}).get("id"):
                return str(msg["chat"]["id"])
    except Exception:
        pass
    return ""


def send_document(path: str, caption: str = "") -> bool:
    """Send a file (for example the Excel report) to your Telegram chat. Returns True on success.
    Telegram is private to you, so the report never goes into the public repository or its logs."""
    if not configured():
        return False
    try:
        with open(path, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1000], "parse_mode": "HTML"},
                files={"document": (path.replace("\\", "/").split("/")[-1], f)},
                timeout=60,
            )
        if r.status_code != 200:
            logger.warning("Telegram said %s when sending a file", r.status_code)
        return r.status_code == 200
    except Exception as e:
        logger.warning("Telegram file not sent: %s", type(e).__name__)
        return False
