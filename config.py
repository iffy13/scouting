import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# App Configuration
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "outreach.db"))

GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", str(BASE_DIR / "credentials.json"))
GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", str(BASE_DIR / "token.json"))
SENDER_NAME = os.getenv("SENDER_NAME", "Alex")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")

DAILY_SEND_LIMIT = int(os.getenv("DAILY_SEND_LIMIT", "50"))
WARMUP_MODE = os.getenv("WARMUP_MODE", "true").lower() in ("true", "1", "yes")
WARMUP_DAILY_LIMIT = int(os.getenv("WARMUP_DAILY_LIMIT", "10"))

# Mailbox lists live in .env (never in code: this repository is public).
#   AUTHOR_INBOXES=a@gmail.com,b@gmail.com      mailboxes the old author engine may use
#   DISABLED_INBOXES=c@gmail.com,d@gmail.com    mailboxes that must never be loaded
def _list(name: str):
    return [e.strip().lower() for e in os.getenv(name, "").split(",") if e.strip()]


AUTHOR_INBOXES = _list("AUTHOR_INBOXES")
DISABLED_INBOXES = _list("DISABLED_INBOXES")

# Optional API Keys & Notifications
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
PROSPEO_API_KEY = os.getenv("PROSPEO_API_KEY", "")
MILLION_VERIFIER_API_KEY = os.getenv("MILLION_VERIFIER_API_KEY", "")
OUTSCRAPER_API_KEY = os.getenv("OUTSCRAPER_API_KEY", "")
FOURSQUARE_API_KEY = os.getenv("FOURSQUARE_API_KEY", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# Telegram Instant Push Alerts
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Request headers for scrapers / crawlers
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}
