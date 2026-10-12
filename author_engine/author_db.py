import sqlite3
import os
from datetime import datetime

AUTHOR_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "author_outreach.db")

def init_author_db():
    conn = sqlite3.connect(AUTHOR_DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()

    # 1. Authors Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS authors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            book_title TEXT,
            genre TEXT,
            amazon_url TEXT,
            goodreads_url TEXT,
            website TEXT,
            domain TEXT,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            source TEXT DEFAULT 'goodreads', -- 'goodreads', 'amazon_kdp', 'reedsy', 'kickstarter', 'smashwords', 'booktok', 'web'
            status TEXT DEFAULT 'verified', -- 'verified', 'contacted', 'replied', 'bounced'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(email)
        )
    """)

    # 2. Author Follow-Up Sequence Ladder (Stages 1 to 5)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS author_sequences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL,
            stage INTEGER DEFAULT 1, -- 1: Initial, 2: Day 3 FU, 3: Day 7 FU, 4: Day 12 FU, 5: Day 17 Breakup
            status TEXT DEFAULT 'active', -- 'active', 'hot', 'completed', 'bounced'
            subject TEXT,
            body TEXT,
            sender_inbox TEXT,
            gmail_thread_id TEXT,
            last_message_id TEXT,
            next_action_at TIMESTAMP,
            last_sent_at TIMESTAMP,
            reply_received INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(author_id) REFERENCES authors(id) ON DELETE CASCADE,
            UNIQUE(author_id)
        )
    """)

    # 3. Author Blacklist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS author_blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            reason TEXT NOT NULL, -- 'bounce', 'unsubscribe', 'manual'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_authors_email ON authors (email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_author_seq_status ON author_sequences (status, next_action_at)")

    conn.commit()
    conn.close()

def is_author_blacklisted(email: str, conn: sqlite3.Connection) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM author_blacklist WHERE email = ?", (email.strip().lower(),))
    return cursor.fetchone() is not None

def add_to_author_blacklist(email: str, reason: str, conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO author_blacklist (email, reason) VALUES (?, ?)", (email.strip().lower(), reason))
    conn.commit()

if __name__ == "__main__":
    init_author_db()
    print(f"[+] Author outreach database initialized at: {AUTHOR_DB_PATH}")
