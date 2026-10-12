import sqlite3
import os
from author_engine.author_db import AUTHOR_DB_PATH
from config import AUTHOR_INBOXES, DISABLED_INBOXES

def show_author_dashboard():
    print("\n" + "="*80)
    print("                 AUTHOR OUTREACH ENGINE - LIVE STATUS")
    print("="*80)

    if not os.path.exists(AUTHOR_DB_PATH):
        print("[-] Author database does not exist yet. Run RUN_BOOK_OUTREACH.bat to initialize.")
        return

    conn = sqlite3.connect(AUTHOR_DB_PATH)
    cursor = conn.cursor()

    # Total Authors
    cursor.execute("SELECT COUNT(*) FROM authors")
    total_authors = cursor.fetchone()[0]

    # Authors by Status
    cursor.execute("SELECT status, COUNT(*) FROM authors GROUP BY status")
    status_counts = dict(cursor.fetchall())

    # Sequences by Stage
    cursor.execute("SELECT stage, COUNT(*) FROM author_sequences WHERE status = 'active' GROUP BY stage")
    stage_counts = dict(cursor.fetchall())

    # Sequences Sent Today
    cursor.execute("SELECT COUNT(*) FROM author_sequences WHERE DATE(last_sent_at) = DATE('now')")
    sent_today = cursor.fetchone()[0]

    # Total Lifetime Sent
    cursor.execute("SELECT COUNT(*) FROM author_sequences WHERE last_sent_at IS NOT NULL")
    sent_lifetime = cursor.fetchone()[0]

    # Hot Replies
    cursor.execute("SELECT COUNT(*) FROM author_sequences WHERE status = 'hot' OR reply_received = 1")
    hot_replies = cursor.fetchone()[0]

    # Bounces
    cursor.execute("SELECT COUNT(*) FROM author_sequences WHERE status = 'bounced'")
    bounces = cursor.fetchone()[0]

    print(f"\n[1] AUTHOR PIPELINE METRICS")
    print(f"    * Total Authors Scouted:        {total_authors}")
    print(f"    * Verified Deliverable Authors: {status_counts.get('verified', 0) + status_counts.get('contacted', 0)}")
    print(f"    * Emails Sent Today:            {sent_today}")
    print(f"    * Total Emails Sent (Lifetime): {sent_lifetime}")
    print(f"    * Hot Replies (Interested!):    {hot_replies}")
    print(f"    * Filtered Bounces:             {bounces}")

    # Breakdown by Genre
    print(f"\n[2] SCOUTED AUTHORS BY GENRE")
    cursor.execute("SELECT genre, COUNT(*) FROM authors GROUP BY genre ORDER BY COUNT(*) DESC")
    genre_counts = cursor.fetchall()
    if genre_counts:
        for g, count in genre_counts:
            print(f"    * {g.upper():<20}: {count} authors")
    else:
        print("    * No authors categorized yet.")

    # Breakdown by Follow-up Stage
    print(f"\n[3] ACTIVE FOLLOW-UP SEQUENCES")
    if stage_counts:
        for s in range(1, 6):
            print(f"    * Stage {s} Sequences: {stage_counts.get(s, 0)}")
    else:
        print("    * No active follow-up sequences in queue.")

    print("\n" + "="*80 + "\n")
    conn.close()

if __name__ == "__main__":
    show_author_dashboard()
