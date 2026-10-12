import asyncio
import argparse
import logging
import random
import json
import time
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
from db import init_db, get_connection, add_to_blacklist, is_email_blacklisted
from scrapers.google_maps import GoogleMapsScraper
from scrapers.direct_web import DirectWebScraper
from scrapers.web_directory import WebDirectoryScraper
from scrapers.osm import OSMScraper
from scrapers.trustpilot import TrustpilotScraper
from scrapers.multi_platform import MultiPlatformScraper
from enricher.researcher import DeepBusinessResearcher
from verifier.email_verifier import EmailVerifier
from offers.ai_writer import DynamicAIWriter
from offers.cleaner import clean_business_name, is_valid_prospect_domain
from sender.gmail_client import MultiGmailService
from rotation_manager import RotationManager
from config import DAILY_SEND_LIMIT, WARMUP_MODE, WARMUP_DAILY_LIMIT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("outreach_engine")

STAGE_DELAYS = {
    1: 0,   # Initial send
    2: 3,   # FU1: Day 3
    3: 4,   # FU2: Day 7
    4: 5,   # FU3: Day 12
    5: 5,   # FU4: Day 17
    6: 7,   # FU5: Day 24
}

from verifier.deliverability_tester import DeliverabilityTester

class OutreachEngine:
    def __init__(self):
        init_db()
        self.google_maps = GoogleMapsScraper()
        self.direct_scraper = DirectWebScraper()
        self.web_scraper = WebDirectoryScraper()
        self.osm_scraper = OSMScraper()
        self.trustpilot_scraper = TrustpilotScraper()
        self.multi_platform = MultiPlatformScraper()
        self.researcher = DeepBusinessResearcher(timeout=10)
        self.verifier = EmailVerifier()
        self.gmail_pool = MultiGmailService(mode="b2b")
        self.rotation = RotationManager()
        self.deliverability_tester = DeliverabilityTester()
        self.leads_sent_counter = 0

    def get_emails_sent_today_count(self) -> int:
        """Returns total emails sent today across all inboxes."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM sequences
                WHERE DATE(last_sent_at) = DATE('now')
            """)
            return cursor.fetchone()[0]

    async def send_single_lead_now(self, business_data: Dict[str, Any], email_data: Dict[str, Any], sequence_id: int, stage: int = 1) -> bool:
        """Immediately writes and dispatches 1-of-1 email using the next round-robin Gmail inbox."""
        research = business_data.get("research", {})
        signals = research.get("signals", {})

        subject, body = await DynamicAIWriter.generate_email(
            business=business_data,
            signals=signals,
            stage=stage
        )

        send_res = self.gmail_pool.send_email(
            to_email=email_data["email"],
            subject=subject,
            body_text=body,
            thread_id=email_data.get("thread_id"),
            in_reply_to=email_data.get("last_message_id")
        )

        if send_res:
            from_inbox = send_res.get("from_email")
            next_stage = stage + 1
            delay_days = STAGE_DELAYS.get(next_stage, 4)
            next_action = (datetime.now(timezone.utc) + timedelta(days=delay_days)).isoformat()

            with get_connection() as conn:
                cursor = conn.cursor()
                if next_stage > 6:
                    cursor.execute("UPDATE sequences SET status = 'completed', last_sent_at = CURRENT_TIMESTAMP, sender_inbox = ? WHERE id = ?", (from_inbox, sequence_id))
                else:
                    cursor.execute("""
                        UPDATE sequences
                        SET stage = ?, next_action_at = ?, last_sent_at = CURRENT_TIMESTAMP,
                            sender_inbox = ?, gmail_thread_id = ?, last_message_id = ?
                        WHERE id = ?
                    """, (next_stage, next_action, from_inbox, send_res["thread_id"], send_res["message_id"], sequence_id))
                conn.commit()

            logger.info(f"==> [LIVE SEND SUCCESS] Dispatched to {email_data['email']} via [{from_inbox}]!")
            
            # Automated Deliverability Seed Test every 10 leads
            self.leads_sent_counter += 1
            if self.leads_sent_counter % 10 == 0 and from_inbox:
                acc_obj = self.gmail_pool.accounts.get(from_inbox)
                if acc_obj and "service" in acc_obj:
                    self.deliverability_tester.run_live_seed_test(from_inbox, acc_obj["service"])

            return True
        else:
            if getattr(self.gmail_pool, "last_failure", None) == "no_capacity":
                # Not the lead's fault: every inbox is capped or throttled. Keep the lead for the next run.
                logger.warning(f"No sending capacity left, keeping {email_data['email']} queued for the next run.")
                return False
            # Handle failure: immediately categorize as bounced, mark email invalid, and blacklist
            failed_email = email_data["email"].strip().lower()
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE sequences SET status = 'bounced', last_sent_at = CURRENT_TIMESTAMP WHERE id = ?", (sequence_id,))
                cursor.execute("UPDATE emails SET verdict = 'invalid' WHERE email = ?", (failed_email,))
                add_to_blacklist(failed_email, "send_failure_or_rejected", conn)
                conn.commit()
            logger.warning(f"==> [BOUNCE/ERROR FILTERED] Failed sending to {failed_email}. Categorized as bounced & permanently blacklisted from all future sequences.")
            return False

    async def dispatch_existing_ready_leads(self, max_limit: int = 250) -> int:
        """Dispatches all existing ready leads in queue first (Follow-ups + Unsent Stage 1 leads)."""
        sent_count = 0
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.id, s.stage, s.offer_type, s.gmail_thread_id, s.last_message_id,
                       e.email, e.first_name, b.id as business_id, b.name, b.keyword, b.country, b.city, b.website, b.signals_json
                FROM sequences s
                JOIN emails e ON s.email_id = e.id
                JOIN businesses b ON s.business_id = b.id
                WHERE s.status = 'active'
                  AND e.verdict = 'valid'
                  AND (s.next_action_at IS NULL OR s.next_action_at <= CURRENT_TIMESTAMP)
                ORDER BY s.stage DESC, s.created_at ASC
                LIMIT ?
            """, (max_limit,))
            ready_leads = cursor.fetchall()
            logger.info(f"Found {len(ready_leads)} existing verified leads in queue ready for immediate sending.")

            for row in ready_leads:
                research = json.loads(row["signals_json"] or "{}")
                biz = {
                    "name": row["name"],
                    "clean_name": row["name"],
                    "founder_name": research.get("founder_name") or row["first_name"],
                    "flagship_services": research.get("flagship_services", []),
                    "research_summary": research.get("research_summary", ""),
                    "keyword": row["keyword"],
                    "country": row["country"],
                    "city": row["city"],
                    "website": row["website"],
                    "research": research
                }
                em = {"email": row["email"], "thread_id": row["gmail_thread_id"], "last_message_id": row["last_message_id"]}
                ok = await self.send_single_lead_now(biz, em, row["id"], stage=row["stage"])
                if ok:
                    sent_count += 1
                    pacing = random.randint(5, 8)
                    logger.info(f"Pacing delay: waiting {pacing}s before next send...")
                    await asyncio.sleep(pacing)

        return sent_count

    async def process_existing_unextracted_businesses(self, max_sends: int = 250) -> int:
        """
        PRIORITY 1: Drains the backlog of all already-scouted businesses in the database.
        Deeply inspects their websites, extracts emails, verifies deliverability, and sends immediately!
        """
        sent_count = 0
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT b.id, b.name, b.business_type, b.source, b.keyword, b.country, b.city, b.website, b.domain, b.signals_json
                FROM businesses b
                WHERE b.website IS NOT NULL AND b.website != ''
                  AND b.id NOT IN (SELECT business_id FROM emails)
                ORDER BY b.id ASC
            """)
            unprocessed = cursor.fetchall()

        if not unprocessed:
            logger.info("No unextracted scouted businesses in database backlog.")
            return 0

        logger.info(f"==> [BACKLOG PRIORITY] Found {len(unprocessed)} already-scouted businesses waiting for email extraction & sending!")

        for row in unprocessed:
            if self.get_emails_sent_today_count() >= (sent_count + max_sends):
                break

            biz_id = row["id"]
            website = row["website"]
            b_name = row["name"]
            domain = row["domain"]
            b_type = row["business_type"]
            kw = row["keyword"]
            country = row["country"]
            city = row["city"]

            if not is_valid_prospect_domain(domain, website):
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO emails (business_id, email, verdict, is_verified, source)
                        VALUES (?, ?, 'invalid', 0, 'crawler_filtered_domain')
                    """, (biz_id, f"filtered_{biz_id}@{domain or 'filtered.com'}"))
                    conn.commit()
                continue

            logger.info(f"[BACKLOG] Researching [{b_name}] ({website})...")
            try:
                research = await self.researcher.research_business(website)
            except Exception as e:
                logger.debug(f"Error researching {website}: {e}")
                research = {}

            emails_found = research.get("emails", [])
            founder_name = research.get("founder_name")
            flagship_services = research.get("flagship_services", [])
            research_summary = research.get("research_summary", "")

            # Update business signals in DB
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE businesses SET signals_json = ? WHERE id = ?", (json.dumps(research), biz_id))
                conn.commit()

            if not emails_found:
                # Insert placeholder so we don't re-crawl repeatedly
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO emails (business_id, email, verdict, is_verified, source)
                        VALUES (?, ?, 'invalid', 0, 'crawler_no_email_found')
                    """, (biz_id, f"no_email_{biz_id}@{domain or 'website.com'}"))
                    conn.commit()
                continue

            for em in emails_found:
                clean_em = em.strip().lower()
                with get_connection() as conn:
                    cursor = conn.cursor()
                    if is_email_blacklisted(clean_em, conn):
                        continue

                    cursor.execute("SELECT id, verdict FROM emails WHERE email = ?", (clean_em,))
                    existing_email = cursor.fetchone()

                    if existing_email:
                        email_id = existing_email["id"]
                        verdict = existing_email["verdict"]
                    else:
                        v_res = await self.verifier.verify(clean_em)
                        verdict = v_res.get("verdict", "unverified")
                        first_name = founder_name or (clean_em.split("@")[0].capitalize() if "." not in clean_em.split("@")[0] else None)
                        cursor.execute("""
                            INSERT INTO emails (business_id, email, first_name, source, verdict, is_verified, verified_at)
                            VALUES (?, ?, ?, 'crawler', ?, ?, CURRENT_TIMESTAMP)
                        """, (biz_id, clean_em, first_name, verdict, 1 if verdict == "valid" else 0))
                        conn.commit()
                        email_id = cursor.lastrowid
                        logger.info(f"Verified backlog email [{clean_em}] -> Verdict: {verdict.upper()}")

                    if verdict == "valid":
                        offer = "book_trailer" if b_type == "author" else ("video_clips" if research.get("signals", {}).get("has_youtube") else ("website" if not website else "receptionist"))
                        cursor.execute("""
                            INSERT OR IGNORE INTO sequences (email_id, business_id, offer_type, stage, status, next_action_at)
                            VALUES (?, ?, ?, 1, 'active', CURRENT_TIMESTAMP)
                        """, (email_id, biz_id, offer))
                        conn.commit()
                        seq_id = cursor.lastrowid

                        biz_payload = {
                            "name": b_name,
                            "clean_name": b_name,
                            "founder_name": founder_name,
                            "flagship_services": flagship_services,
                            "research_summary": research_summary,
                            "keyword": kw,
                            "country": country,
                            "city": city,
                            "website": website,
                            "research": research
                        }
                        em_payload = {"email": clean_em}
                        sent_ok = await self.send_single_lead_now(biz_payload, em_payload, seq_id, stage=1)
                        if sent_ok:
                            sent_count += 1
                            pacing = random.randint(5, 8)
                            logger.info(f"Pacing delay: waiting {pacing}s before next send...")
                            await asyncio.sleep(pacing)

        return sent_count

    async def run_live_stream_outreach(self, target_daily_quota: Optional[int] = None):
        """
        Instant Live Streaming Outreach Engine:
        1. Checks inboxes and replies.
        2. Sends ALL existing unsent leads and due follow-ups in queue FIRST.
        3. Extracts and sends ALL previously scouted businesses in database backlog.
        4. ONLY then continues scouting new leads live and sending them immediately!
        """
        accounts = self.gmail_pool.get_all_accounts()
        if not accounts:
            logger.info("Waiting 4s for network connection to initialize Gmail pool...")
            await asyncio.sleep(4)
            self.gmail_pool._load_all_accounts()
            accounts = self.gmail_pool.get_all_accounts()

        total_inboxes = max(1, len(accounts))
        target_quota = target_daily_quota or (total_inboxes * DAILY_SEND_LIMIT)

        logger.info("=" * 70)
        logger.info(f"STARTING LIVE OUTREACH ENGINE ({total_inboxes} Active Inboxes | Target: {target_quota} Sends/Day)")
        logger.info("=" * 70)

        # 1. Scan for replies & bounces
        events = self.gmail_pool.check_all_inboxes_for_replies()
        for evt in events:
            if evt["type"] == "reply":
                logger.info(f"HOT REPLY from {evt['from']} on thread {evt['thread_id']}!")
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE sequences SET status = 'hot' WHERE gmail_thread_id = ?", (evt["thread_id"],))
                    # Fetch business name and email for Telegram push notification
                    cursor.execute("""
                        SELECT b.name, b.keyword, e.email, s.offer_type
                        FROM sequences s
                        JOIN businesses b ON s.business_id = b.id
                        JOIN emails e ON s.email_id = e.id
                        WHERE s.gmail_thread_id = ?
                    """, (evt["thread_id"],))
                    row = cursor.fetchone()
                    conn.commit()

                    if row:
                        from notifier.telegram_notifier import notifier
                        await notifier.notify_hot_reply(
                            lead_name=row["name"],
                            company=row["name"],
                            email=row["email"],
                            offer_type=row["offer_type"],
                            snippet=evt.get("snippet", ""),
                            receiving_inbox=evt.get("account", "")
                        )
            elif evt["type"] == "bounce":
                logger.warning(f"BOUNCE/ERROR detected on thread {evt['thread_id']} from {evt.get('from')}! Quarantining lead...")
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE sequences SET status = 'bounced' WHERE gmail_thread_id = ?", (evt["thread_id"],))
                    cursor.execute("SELECT email_id FROM sequences WHERE gmail_thread_id = ?", (evt["thread_id"],))
                    row = cursor.fetchone()
                    if row:
                        cursor.execute("UPDATE emails SET verdict = 'invalid' WHERE id = ?", (row["email_id"],))
                        cursor.execute("SELECT email FROM emails WHERE id = ?", (row["email_id"],))
                        em_row = cursor.fetchone()
                        if em_row:
                            add_to_blacklist(em_row["email"], "bounce_inbox_feedback", conn)
                    conn.commit()

        # 2. Priority Dispatch: Send all existing unsent leads and follow-ups in queue first!
        sent_today = self.get_emails_sent_today_count()
        if sent_today < target_quota:
            remaining_cap = target_quota - sent_today
            logger.info(f">> Dispatching existing ready leads in queue (Up to {remaining_cap} emails)...")
            initial_sent = await self.dispatch_existing_ready_leads(max_limit=remaining_cap)
            sent_today = self.get_emails_sent_today_count()
            logger.info(f">> Dispatched {initial_sent} existing leads from queue. (Total Sent Today: {sent_today}/{target_quota})")

        # 3. Priority Dispatch: Extract and send ALL already-scouted businesses in backlog!
        if sent_today < target_quota:
            remaining_cap = target_quota - sent_today
            logger.info(f">> Extracting & dispatching scouted businesses from DB backlog (Up to {remaining_cap} emails)...")
            backlog_sent = await self.process_existing_unextracted_businesses(max_sends=remaining_cap)
            sent_today = self.get_emails_sent_today_count()
            logger.info(f">> Dispatched {backlog_sent} leads from backlog. (Total Sent Today: {sent_today}/{target_quota})")

        # 4. Live Stream: ONLY after existing leads & backlog are exhausted -> Scout new leads!
        while sent_today < target_quota:
            # Continuously ensure any pending scouted backlog is 100% drained first
            remaining_cap = target_quota - self.get_emails_sent_today_count()
            if remaining_cap > 0:
                await self.process_existing_unextracted_businesses(max_sends=remaining_cap)
                sent_today = self.get_emails_sent_today_count()
                if sent_today >= target_quota:
                    break

            slot = self.rotation.get_current_slot()
            if not slot:
                logger.info("All rotation slots across all countries have completed!")
                break

            kw = slot["keyword"]
            ctry = slot["country"]
            b_type = slot["business_type"]
            country_name = self.direct_scraper.get_country_full_name(ctry)
            cities = ["General"] + self.direct_scraper.get_cities_for_country(ctry)

            logger.info(f"\n--- Active Slot: [{kw.upper()}] in [{country_name} ({ctry})] (Nationwide + {len(cities)-1} Cities) ---")

            # Verify active internet connection before proceeding with the slot
            def is_online() -> bool:
                for target, port in [("1.1.1.1", 443), ("8.8.8.8", 443), ("www.google.com", 80)]:
                    try:
                        import socket
                        s = socket.create_connection((target, port), timeout=2)
                        s.close()
                        return True
                    except OSError:
                        continue
                return False

            while not is_online():
                logger.warning("[NETWORK PAUSED] Waiting 5s for internet connection...")
                await asyncio.sleep(5)

            for loc in cities:
                if self.get_emails_sent_today_count() >= target_quota:
                    break

                loc_label = f"Nationwide ({country_name})" if loc == "General" else f"{loc}, {ctry}"
                logger.info(f">> Hunting [{kw}] in {loc_label}...")

                # Multi-Platform Sweep in Parallel: Google Maps, Web Index + All Approved Platforms
                direct_res, platform_res = await asyncio.gather(
                    self.direct_scraper.search(keyword=kw, country=ctry, city=loc, limit=8),
                    self.multi_platform.search_all_approved_platforms(keyword=kw, country=ctry, city=loc, per_platform_limit=2),
                    return_exceptions=True
                )
                direct_leads = direct_res if isinstance(direct_res, list) else []
                platform_leads = platform_res if isinstance(platform_res, list) else []
                raw_leads = direct_leads + platform_leads

                seen_slot_domains = set()
                valid_candidates = []
                for lead in raw_leads:
                    domain = lead.get("domain")
                    website = lead.get("website")
                    if not domain or domain in seen_slot_domains or not is_valid_prospect_domain(domain, website):
                        continue
                    seen_slot_domains.add(domain)
                    lead["clean_name"] = clean_business_name(lead["name"], domain)
                    valid_candidates.append(lead)

                # Parallel Concurrent Deep Research on all candidate websites
                if valid_candidates:
                    research_tasks = [
                        self.researcher.research_business(l["website"]) if l.get("website") else asyncio.sleep(0)
                        for l in valid_candidates
                    ]
                    research_results = await asyncio.gather(*research_tasks, return_exceptions=True)
                else:
                    research_results = []

                for idx, lead in enumerate(valid_candidates):
                    if self.get_emails_sent_today_count() >= target_quota:
                        break

                    res_obj = research_results[idx] if idx < len(research_results) and isinstance(research_results[idx], dict) else {}
                    emails_found = res_obj.get("emails", [])
                    lead["founder_name"] = res_obj.get("founder_name")
                    lead["flagship_services"] = res_obj.get("flagship_services", [])
                    lead["research_summary"] = res_obj.get("research_summary", "")
                    lead["research"] = res_obj

                    # Save Business to DB
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        try:
                            cursor.execute("""
                                INSERT OR IGNORE INTO businesses (
                                    name, business_type, source, keyword, country, city, website, domain, phone, rating, reviews_count, is_closed, signals_json
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                lead["clean_name"], lead["business_type"], lead["source"], lead["keyword"],
                                lead["country"], lead.get("city"), lead.get("website"), lead.get("domain"),
                                lead.get("phone"), lead.get("rating"), lead.get("reviews_count", 0),
                                lead.get("is_closed", 0), json.dumps(res_obj)
                            ))
                            conn.commit()
                        except Exception:
                            continue

                        cursor.execute("SELECT id FROM businesses WHERE name = ? AND country = ?", (lead["clean_name"], lead["country"]))
                        row = cursor.fetchone()
                        if not row:
                            continue
                        business_id = row["id"]

                        # Verify & IMMEDIATELY SEND valid emails
                        for em in emails_found:
                            if self.get_emails_sent_today_count() >= target_quota:
                                break

                            clean_em = em.strip().lower()
                            if is_email_blacklisted(clean_em, conn):
                                continue

                            cursor.execute("SELECT id, verdict FROM emails WHERE email = ?", (clean_em,))
                            existing_email = cursor.fetchone()

                            if existing_email:
                                email_id = existing_email["id"]
                                verdict = existing_email["verdict"]
                            else:
                                v_res = await self.verifier.verify(clean_em)
                                verdict = v_res.get("verdict", "unverified")
                                first_name = lead.get("founder_name") or (clean_em.split("@")[0].capitalize() if "." not in clean_em.split("@")[0] else None)
                                cursor.execute("""
                                    INSERT INTO emails (business_id, email, first_name, source, verdict, is_verified, verified_at)
                                    VALUES (?, ?, ?, 'crawler', ?, ?, CURRENT_TIMESTAMP)
                                """, (business_id, clean_em, first_name, verdict, 1 if verdict == "valid" else 0))
                                conn.commit()
                                email_id = cursor.lastrowid
                                logger.info(f"Verified email [{clean_em}] -> Verdict: {verdict.upper()}")

                            if verdict == "valid":
                                offer = "book_trailer" if b_type == "author" else ("video_clips" if res_obj.get("signals", {}).get("has_youtube") else ("website" if not lead.get("website") else "receptionist"))
                                cursor.execute("""
                                    INSERT OR IGNORE INTO sequences (email_id, business_id, offer_type, stage, status, next_action_at)
                                    VALUES (?, ?, ?, 1, 'active', CURRENT_TIMESTAMP)
                                """, (email_id, business_id, offer))
                                conn.commit()
                                seq_id = cursor.lastrowid

                                # REAL-TIME DISPATCH: Send this email right now!
                                email_data = {"email": clean_em, "thread_id": None, "last_message_id": None}
                                sent_ok = await self.send_single_lead_now(lead, email_data, seq_id, stage=1)
                                if sent_ok:
                                    current_sent = self.get_emails_sent_today_count()
                                    logger.info(f"==> Progress: {current_sent}/{target_quota} sent today.")
                                    # Fast Round-Robin Pacing delay (5-8 seconds)
                                    pacing = random.randint(5, 8)
                                    logger.info(f"Pacing delay: waiting {pacing}s before next send...")
                                    await asyncio.sleep(pacing)

            # Mark slot completed and advance to next country/keyword
            self.rotation.mark_slot_completed(kw, ctry)
            sent_today = self.get_emails_sent_today_count()

        logger.info(f"\n============================================================")
        logger.info(f" DAILY RUN FINISHED: Total Sent Today: {self.get_emails_sent_today_count()}/{target_quota}")
        logger.info(f"============================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Universal Lead Outreach Engine")
    parser.add_argument("--action", choices=["discover", "send", "full"], default="full", help="Action to perform")
    parser.add_argument("--quota", type=int, default=None, help="Target sends across inboxes today")

    args = parser.parse_args()
    engine = OutreachEngine()

    asyncio.run(engine.run_live_stream_outreach(target_daily_quota=args.quota))
