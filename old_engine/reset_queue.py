import sqlite3
from config import DB_PATH

def reset_slots():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE campaign_state SET status = 'queued'")
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM campaign_state WHERE status = 'queued'")
    count = cursor.fetchone()[0]
    conn.close()
    print(f"[+] Successfully reset {count} rotation slots back to 'queued' state.")

if __name__ == "__main__":
    reset_slots()
