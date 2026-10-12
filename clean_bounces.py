import sqlite3
from config import DB_PATH

def clean_database_bounces():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # List of known bounced addresses from user screenshots
    bounced_emails = ["info@digitalsilk.com", "hello@mrtoqeer.com"]

    for b_em in bounced_emails:
        # Find email_id
        cursor.execute("SELECT id FROM emails WHERE email = ?", (b_em,))
        row = cursor.fetchone()
        if row:
            em_id = row[0]
            cursor.execute("UPDATE sequences SET status = 'bounced' WHERE email_id = ?", (em_id,))
            cursor.execute("UPDATE emails SET verdict = 'invalid' WHERE id = ?", (em_id,))
            cursor.execute("INSERT OR IGNORE INTO blacklist (email, reason) VALUES (?, 'mailer_daemon_bounce')", (b_em,))
            print(f"[CLEANED] Marked {b_em} as bounced and blacklisted.")

    conn.commit()
    conn.close()
    print("[+] Database cleaned successfully.")

if __name__ == "__main__":
    clean_database_bounces()
