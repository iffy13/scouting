import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from config import DB_PATH

logger = logging.getLogger(__name__)

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(db_path: str = DB_PATH):
    """Initialize all SQLite tables, indexes, and constraints."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Businesses Table (All business types: local, digital, ai_tech, creator)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                business_type TEXT NOT NULL DEFAULT 'local', -- 'local', 'digital', 'ai_tech', 'creator'
                source TEXT NOT NULL, -- 'osm', 'google_maps', 'trustpilot', 'producthunt', 'youtube', 'foursquare', etc.
                keyword TEXT NOT NULL,
                country TEXT NOT NULL,
                city TEXT,
                website TEXT,
                domain TEXT,
                phone TEXT,
                rating REAL,
                reviews_count INTEGER DEFAULT 0,
                is_closed INTEGER DEFAULT 0, -- 1 if permanently closed
                signals_json TEXT, -- JSON blob for website health, tech stack, social links, channel stats
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, domain, country)
            )
        """)

        # 2. Emails Table (Global Dedup: unique email address)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                email TEXT UNIQUE NOT NULL,
                first_name TEXT,
                source TEXT NOT NULL, -- 'crawler', 'hunter', 'prospeo', 'direct'
                verdict TEXT DEFAULT 'unverified', -- 'valid', 'catchall', 'risky', 'invalid', 'unverified'
                is_verified INTEGER DEFAULT 0,
                verified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES businesses (id) ON DELETE CASCADE
            )
        """)

        # 3. Campaign Queue & State Table (Keyword-first rotation across countries)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaign_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                country TEXT NOT NULL,
                business_type TEXT NOT NULL DEFAULT 'local',
                status TEXT DEFAULT 'queued', -- 'queued', 'in_progress', 'completed', 'paused'
                leads_scraped INTEGER DEFAULT 0,
                leads_contacted INTEGER DEFAULT 0,
                last_run_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(keyword, country, business_type)
            )
        """)

        # 4. Sequences / Outreach Ladder Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sequences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                business_id INTEGER NOT NULL,
                offer_type TEXT NOT NULL, -- 'website', 'receptionist', 'video_clips', 'custom'
                stage INTEGER DEFAULT 1, -- 1: Day 1, 2: Day 3, 3: Day 7, 4: Day 12, 5: Day 17, 6: Day 24
                status TEXT DEFAULT 'active', -- 'active', 'hot', 'bounced', 'paused', 'completed'
                next_action_at TIMESTAMP,
                last_sent_at TIMESTAMP,
                sender_inbox TEXT,
                gmail_thread_id TEXT,
                last_message_id TEXT,
                history_json TEXT, -- Logs of sent subjects, body previews, dates
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES emails (id) ON DELETE CASCADE,
                FOREIGN KEY (business_id) REFERENCES businesses (id) ON DELETE CASCADE,
                UNIQUE(email_id)
            )
        """)

        # 5. Blacklist Table (Bounces, unsubscribes, manual opt-outs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                reason TEXT NOT NULL, -- 'bounce', 'unsubscribe', 'manual'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for fast lookup
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_businesses_keyword_country ON businesses (keyword, country)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_verdict ON emails (verdict)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sequences_status_next_action ON sequences (status, next_action_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_blacklist_email ON blacklist (email)")

        conn.commit()
        logger.info("Database initialized successfully.")

import urllib.parse

def _domain_key(domain: str) -> str:
    d = (domain or "").strip().lower()
    d = d.split("@")[-1]
    # Strip protocol if present
    if "://" in d:
        parsed = urllib.parse.urlparse(d)
        d = parsed.netloc or parsed.path
    elif "/" in d:
        d = d.split("/")[0]
    # Strip port if present
    if ":" in d:
        d = d.split(":")[0]
    # Strip common subdomains beyond just www.
    common_subdomains = ("www.", "m.", "mail.", "web.", "app.", "api.", "dev.", "staging.")
    for sub in common_subdomains:
        if d.startswith(sub):
            d = d[len(sub):]
            break
    return "@" + d


def is_email_blacklisted(email: str, conn: sqlite3.Connection) -> bool:
    """True when this address, or its whole domain (stored as '@domain'), is on the blacklist."""
    e = email.strip().lower()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM blacklist WHERE email IN (?, ?)", (e, _domain_key(e)))
    return cursor.fetchone() is not None


def is_domain_blacklisted(domain: str, conn: sqlite3.Connection) -> bool:
    if not domain:
        return False
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM blacklist WHERE email = ?", (_domain_key(domain),))
    return cursor.fetchone() is not None


def blacklist_domain(domain: str, reason: str, conn: sqlite3.Connection):
    if domain:
        add_to_blacklist(_domain_key(domain), reason, conn)

def add_to_blacklist(email: str, reason: str, conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO blacklist (email, reason)
        VALUES (?, ?)
    """, (email.strip().lower(), reason))
    conn.commit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database and tables initialized at:", DB_PATH)
