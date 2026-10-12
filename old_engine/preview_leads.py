import asyncio
import json
import sqlite3
from db import get_connection
from offers.ai_writer import DynamicAIWriter
from offers.cleaner import clean_business_name

async def display_dossier_async():
    print("\n" + "="*80)
    print(" DISCOVERED LEADS & DYNAMIC 1-OF-1 AI DRAFT PREVIEWS")
    print("="*80)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.name, b.keyword, b.country, b.city, b.website, b.phone, b.rating, b.reviews_count, b.signals_json,
                   e.id as email_id, e.email, e.verdict, e.first_name,
                   s.stage, s.offer_type, s.status as seq_status
            FROM businesses b
            LEFT JOIN emails e ON b.id = e.business_id
            LEFT JOIN sequences s ON e.id = s.email_id
            WHERE e.verdict = 'valid'
            ORDER BY b.id DESC
            LIMIT 5
        """)
        rows = cursor.fetchall()

        if not rows:
            print("\nNo valid leads to preview right now. Run a discovery batch first!\n")
            return

        for idx, row in enumerate(rows, 1):
            signals = json.loads(row["signals_json"] or "{}")
            clean_name = clean_business_name(row["name"])
            print(f"\n[{idx}] BUSINESS: {clean_name}")
            print(f"    * Niche/Location:  {row['keyword'].title()} in {row['city'] or row['country']}")
            print(f"    * Website:         {row['website'] or 'None'}")
            print(f"    * Contact Email:   {row['email']} [{row['verdict'].upper()}]")
            
            # Generate 1-of-1 AI Draft
            biz_dict = dict(row)
            biz_dict["clean_name"] = clean_name
            subject, body = await DynamicAIWriter.generate_email(
                business=biz_dict,
                signals=signals,
                stage=row["stage"] or 1
            )
            print(f"    * Generated Subject: {subject}")
            print("    * 1-of-1 Human Email:")
            for line in body.split("\n"):
                print(f"        {line}")
            print("-" * 80)

if __name__ == "__main__":
    asyncio.run(display_dossier_async())
