import sqlite3
import os
import urllib.parse
from datetime import datetime

AUTHOR_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "author_outreach.db")
WHATSAPP_NUMBER = "447853164638"

def format_whatsapp_link(author_name, book_title, email):
    text = f"Hi {author_name}, thanks for replying regarding your book '{book_title}'! Let's connect about the trailer."
    encoded = urllib.parse.quote(text)
    return f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded}"

def display_author_dashboard():
    print("=" * 80)
    print("       BOOK TRAILERS & AUTHOR REPLIES DASHBOARD")
    print("=" * 80)
    
    if not os.path.exists(AUTHOR_DB_PATH):
        print(f"\n  [!] Database not created yet. Run RUN_BOOK_OUTREACH.bat first.\n")
        return

    conn = sqlite3.connect(AUTHOR_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Hot replies
    cursor.execute("""
        SELECT a.name, a.book_title, a.genre, a.website, a.email,
               s.stage, s.status, s.sender_inbox, s.last_sent_at, s.subject
        FROM author_sequences s
        JOIN authors a ON s.author_id = a.id
        WHERE s.status = 'hot' OR s.reply_received = 1
        ORDER BY s.last_sent_at DESC
    """)
    hot_authors = cursor.fetchall()

    if not hot_authors:
        print("\n  [i] No active 'HOT' author replies logged yet.")
        print("      (When authors reply, they will be logged here with 1-click WhatsApp links)\n")
    else:
        print(f"\n  [+] Found {len(hot_authors)} HOT AUTHOR REPLIES:\n")
        for i, row in enumerate(hot_authors, 1):
            wa_link = format_whatsapp_link(row["name"], row["book_title"], row["email"])
            print(f"  --- [{i}] AUTHOR: {row['name']} ---")
            print(f"      Book Title:    {row['book_title']}")
            print(f"      Genre:         {row['genre']}")
            print(f"      Email:         {row['email']}")
            print(f"      Website:       {row['website'] or 'N/A'}")
            print(f"      Receiving Box: {row['sender_inbox'] or 'Default'}")
            print(f"      Stage:         Stage #{row['stage']}")
            print(f"      Last Sent:     {row['last_sent_at']}")
            print(f"      WhatsApp Link: {wa_link}")
            print("  " + "-" * 76)

    # 2. Pipeline breakdown
    cursor.execute("SELECT COUNT(*) FROM authors")
    total_authors = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM authors WHERE status = 'contacted'")
    contacted_authors = cursor.fetchone()[0]

    cursor.execute("SELECT stage, COUNT(*) FROM author_sequences WHERE status = 'active' GROUP BY stage")
    stages = cursor.fetchall()

    print("\n  --- AUTHOR OUTREACH STATS ---")
    print(f"      Total Authors Scouted:    {total_authors}")
    print(f"      Total Pitches Sent:       {contacted_authors}")
    for row in stages:
        label = "Stage 1 (Initial Pitch)" if row[0] == 1 else f"Stage {row[0]} (Follow-up)"
        print(f"      - {label:<24}: {row[1]} active authors")

    conn.close()
    print("\n" + "=" * 80)

if __name__ == "__main__":
    display_author_dashboard()
