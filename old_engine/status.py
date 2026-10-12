import sqlite3
from db import get_connection
from rotation_manager import RotationManager
from sender.gmail_client import MultiGmailService

STAGE_NAMES = {
    1: "Initial Outreach (Stage 1)",
    2: "Follow-up 1 (Stage 2 - Demo/Sample Link)",
    3: "Follow-up 2 (Stage 3 - Case Study/Proof)",
    4: "Follow-up 3 (Stage 4 - Pain Reminder)",
    5: "Follow-up 4 (Stage 5 - Direct Question)",
    6: "Follow-up 5 (Stage 6 - Final Breakup)"
}

OFFER_NAMES = {
    "receptionist": "24/7 AI Voice Receptionist / Phone Assistant",
    "video_clips": "Video Repurposing / Viral Shorts & Reels",
    "website": "High-Converting Mobile Funnel / Website",
    "book_trailer": "3D Cinematic Book Trailers / BookTok"
}

def show_live_dashboard():
    print("\n" + "="*80)
    print("                 OUTREACH MACHINE - LIVE STATUS DASHBOARD")
    print("="*80)

    # 1. Accounts Pool
    from pathlib import Path
    from config import AUTHOR_INBOXES, DISABLED_INBOXES
    account_files = sorted(list(Path("accounts").glob("*.json")))
    active_b2b = [f.stem for f in account_files if f.stem.lower() not in [d.lower() for d in DISABLED_INBOXES] and f.stem.lower() not in [a.lower() for a in AUTHOR_INBOXES]]
    active_author = [f.stem for f in account_files if f.stem.lower() not in [d.lower() for d in DISABLED_INBOXES] and f.stem.lower() in [a.lower() for a in AUTHOR_INBOXES]]
    disabled_accs = [f.stem for f in account_files if f.stem.lower() in [d.lower() for d in DISABLED_INBOXES]]

    print(f"\n[1] CONNECTED SENDING INBOXES ({len(active_b2b) + len(active_author)} Active | {len(disabled_accs)} Paused)")
    with get_connection() as conn:
        cursor = conn.cursor()
        if active_b2b:
            print(f"  -- Active B2B Outreach Inboxes ({len(active_b2b)} Inboxes - Capacity: {len(active_b2b)*50}/day) --")
            for idx, email_name in enumerate(active_b2b, 1):
                cursor.execute("SELECT COUNT(*) FROM sequences WHERE sender_inbox = ? AND DATE(last_sent_at) = DATE('now')", (email_name,))
                sent_count = cursor.fetchone()[0]
                print(f"    * #{idx}: {email_name.ljust(30)} [{sent_count}/50 sent today]")

        if active_author:
            print(f"  -- Active Author Book Outreach Inboxes ({len(active_author)} Inboxes - Capacity: {len(active_author)*50}/day) --")
            for idx, email_name in enumerate(active_author, 1):
                cursor.execute("SELECT COUNT(*) FROM sequences WHERE sender_inbox = ? AND DATE(last_sent_at) = DATE('now')", (email_name,))
                sent_count = cursor.fetchone()[0]
                print(f"    * #{idx}: {email_name.ljust(30)} [{sent_count}/50 sent today]")

        if disabled_accs:
            print(f"  -- Paused / Excluded Inboxes ({len(disabled_accs)} Inboxes) --")
            for idx, email_name in enumerate(disabled_accs, 1):
                print(f"    * [PAUSED] {email_name.ljust(30)}")

    # 2. Database Metrics
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM businesses")
        total_biz = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM emails WHERE verdict = 'valid'")
        valid_emails = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sequences WHERE status = 'hot'")
        hot_replies = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sequences WHERE DATE(last_sent_at) = DATE('now')")
        sent_today = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sequences WHERE last_sent_at IS NOT NULL")
        total_sent_lifetime = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM businesses b
            WHERE b.website IS NOT NULL AND b.website != ''
              AND b.id NOT IN (SELECT business_id FROM emails)
        """)
        pending_backlog = cursor.fetchone()[0]

        print(f"\n[2] PIPELINE HEALTH & SUMMARY")
        print(f"    * Total Businesses Scouted:     {total_biz}")
        print(f"    * Scouted Backlog Pending Send: {pending_backlog}")
        print(f"    * Verified Deliverable Leads:    {valid_emails}")
        print(f"    * Emails Sent Today:            {sent_today}")
        print(f"    * Total Emails Sent (All-Time): {total_sent_lifetime}")
        print(f"    * Hot Replies (Interested!):     {hot_replies}")

        # 3. Granular Breakdown by Offer Type
        print(f"\n[3] BREAKDOWN BY OFFER TYPE")
        cursor.execute("""
            SELECT offer_type,
                   COUNT(CASE WHEN last_sent_at IS NOT NULL THEN 1 END) as sent_count,
                   COUNT(CASE WHEN last_sent_at IS NULL THEN 1 END) as pending_count,
                   COUNT(*) as total_count
            FROM sequences
            GROUP BY offer_type
        """)
        for row in cursor.fetchall():
            o_name = OFFER_NAMES.get(row[0], row[0].title())
            print(f"    * {o_name}:")
            print(f"        - Dispatched Emails: {row[1]} | Pending in Queue: {row[2]} | Total: {row[3]}")

        # 4. Granular Breakdown by Sequence Stage
        print(f"\n[4] BREAKDOWN BY SEQUENCE STAGE (Active Pipeline)")
        cursor.execute("""
            SELECT stage,
                   COUNT(CASE WHEN next_action_at IS NULL OR next_action_at <= CURRENT_TIMESTAMP THEN 1 END) as ready_now,
                   COUNT(CASE WHEN next_action_at > CURRENT_TIMESTAMP THEN 1 END) as scheduled_future,
                   COUNT(*) as total_active
            FROM sequences
            WHERE status = 'active'
            GROUP BY stage
            ORDER BY stage ASC
        """)
        stage_rows = cursor.fetchall()
        if stage_rows:
            for row in stage_rows:
                s_name = STAGE_NAMES.get(row[0], f"Stage {row[0]}")
                if row[0] == 1:
                    print(f"    * {s_name}:")
                    print(f"        - Ready for Immediate Send: {row[1]} | Total Active: {row[3]}")
                else:
                    print(f"    * {s_name}:")
                    print(f"        - Due Now: {row[1]} | Scheduled (Awaiting Follow-Up Window): {row[2]} | Total Active: {row[3]}")
        else:
            print("    * No active sequences pending in queue.")

        cursor.execute("SELECT COUNT(*) FROM sequences WHERE status = 'bounced'")
        bounced_count = cursor.fetchone()[0]
        print(f"    * Quarantined Bounces (Permanently Filtered): {bounced_count}")

    # 5. Rotation Position & Queue Breakdown
    mgr = RotationManager()
    current = mgr.get_current_slot()
    print(f"\n[5] KEYWORD & COUNTRY ROTATION ENGINE")
    if current:
        print(f"    * Current Active Keyword: {current['keyword'].upper()} (Type: {current['business_type']})")
        print(f"    * Current Active Country: {current['country']}")
        print(f"    * Slot Progress Status:   {current['status']}")
    else:
        print("    * All rotation slots completed!")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM campaign_state WHERE status = 'completed'")
        completed_slots = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM campaign_state WHERE status = 'queued'")
        queued_slots = cursor.fetchone()[0]
        print(f"    * Rotation Queue Progress: {completed_slots} completed / {queued_slots + completed_slots} total target slots")

    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    show_live_dashboard()
