import os
import sqlite3
import urllib.parse
import json
from datetime import datetime
from config import DB_PATH

WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "447853164638")

def format_whatsapp_link(lead_name, company, email, offer_type):
    text = f"Hi {lead_name}, thanks for connecting regarding {company} and our {offer_type} solution! Let's chat."
    encoded = urllib.parse.quote(text)
    return f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded}"

def display_replies():
    print("=" * 80)
    print("           HOT REPLIES & PROSPECTS DASHBOARD")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Find hot leads / replies recorded in sequences
    cursor.execute("""
        SELECT 
            b.name, b.phone, b.city, b.country, b.website,
            e.email, s.offer_type, s.stage, s.status, s.sender_inbox, s.last_sent_at, s.history_json
        FROM sequences s
        JOIN businesses b ON s.business_id = b.id
        JOIN emails e ON s.email_id = e.id
        WHERE s.status = 'hot'
        ORDER BY s.last_sent_at DESC
    """)
    replies = cursor.fetchall()

    if not replies:
        print("\n  [i] No active 'HOT' replies logged yet in outreach.db.")
        print("      (When prospects reply, Gmail listener marks their sequence as 'hot')\n")
    else:
        print(f"\n  [+] Found {len(replies)} HOT PROSPECTS in database:\n")
        for i, row in enumerate(replies, 1):
            name, phone, city, country, website, email, offer, stage, status, inbox, last_sent, history_raw = row
            wa_link = format_whatsapp_link(name, name, email, offer)
            
            print(f"  --- [{i}] HOT PROSPECT: {name} ---")
            print(f"      Email:         {email}")
            print(f"      Phone:         {phone or 'N/A'}")
            print(f"      Location:      {city or 'N/A'}, {country}")
            print(f"      Website:       {website or 'N/A'}")
            print(f"      Offer:         {offer}")
            print(f"      Stage:         Follow-up #{stage}")
            print(f"      Receiving Box: {inbox or 'Default Account'}")
            print(f"      Last Action:   {last_sent}")
            print(f"      WhatsApp Link: {wa_link}")
            print("  " + "-" * 76)

    # Show overall active outreach statistics
    cursor.execute("""
        SELECT offer_type, stage, COUNT(*)
        FROM sequences
        GROUP BY offer_type, stage
        ORDER BY offer_type, stage
    """)
    stage_counts = cursor.fetchall()

    print("\n  --- ACTIVE PIPELINE BREAKDOWN ---")
    if stage_counts:
        for offer, stage, count in stage_counts:
            stage_label = f"Stage {stage} (Initial)" if stage == 1 else f"Stage {stage} (Follow-up)"
            print(f"      - {offer:<16} | {stage_label:<20} : {count} leads")
    else:
        print("      - No active sequences found yet.")
    
    conn.close()
    print("\n" + "=" * 80)

if __name__ == "__main__":
    display_replies()
