import asyncio
import os
import sys
import sqlite3
import random
import logging
from datetime import datetime, timedelta, timezone

# Ensure parent directory is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from author_engine.author_db import init_author_db, is_author_blacklisted, add_to_author_blacklist, AUTHOR_DB_PATH
from author_engine.author_scraper import AuthorLeadScraper, AUTHOR_GENRES
from author_engine.author_writer import AuthorCopywriter
from verifier.email_verifier import EmailVerifier
from sender.gmail_client import MultiGmailService
from config import DAILY_SEND_LIMIT
from services import get_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AuthorEngine]: %(message)s"
)
logger = logging.getLogger("author_engine")

AUTHOR_STAGE_DELAYS = {
    1: 0,   # Initial send
    2: 3,   # FU1: Day 3
    3: 4,   # FU2: Day 7
    4: 5,   # FU3: Day 12
    5: 5,   # Breakup: Day 17
}

from verifier.deliverability_tester import DeliverabilityTester

class AuthorOutreachEngine:
    def __init__(self):
        init_author_db()
        self.scraper = AuthorLeadScraper()
        self.verifier = EmailVerifier()
        self.gmail_pool = MultiGmailService(mode="all")
        # One mailbox for book trailers, set in mailbox_map.json. No rotation across inboxes.
        self.mailbox = get_service("book_trailer").mailbox
        self.deliverability_tester = DeliverabilityTester()
        self.author_sent_counter = 0

    def get_author_emails_sent_today_count(self) -> int:
        conn = sqlite3.connect(AUTHOR_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM author_sequences
            WHERE DATE(last_sent_at) = DATE('now')
        """)
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def _sender_for(self, sequence_id: int) -> str:
        """The inbox that already wrote to this author keeps the thread; new threads use the book_trailer mailbox."""
        conn = sqlite3.connect(AUTHOR_DB_PATH)
        row = conn.execute("SELECT sender_inbox FROM author_sequences WHERE id = ?", (sequence_id,)).fetchone()
        conn.close()
        return (row[0] if row and row[0] else self.mailbox or "").strip().lower()

    async def send_single_author_now(self, author_id: int, name: str, book_title: str, genre: str, email: str, sequence_id: int, offer_service: str = "book_trailer", stage: int = 1, thread_id: str = None, last_msg_id: str = None) -> bool:
        """Sends one email to an author from the book_trailer mailbox (follow-ups stay in the inbox that started the thread)."""
        subject, body = AuthorCopywriter.generate_email(author_name=name, book_title=book_title, genre=genre, offer_service=offer_service, stage=stage)

        send_res = self.gmail_pool.send_email(
            to_email=email,
            subject=subject,
            body_text=body,
            from_account_email=self._sender_for(sequence_id),
            thread_id=thread_id,
            in_reply_to=last_msg_id
        )

        if send_res:
            from_inbox = send_res.get("from_email")
            next_stage = stage + 1
            delay_days = AUTHOR_STAGE_DELAYS.get(next_stage, 4)
            next_action = (datetime.now(timezone.utc) + timedelta(days=delay_days)).isoformat()

            conn = sqlite3.connect(AUTHOR_DB_PATH)
            cursor = conn.cursor()
            if next_stage > 5:
                cursor.execute("UPDATE author_sequences SET status = 'completed', last_sent_at = CURRENT_TIMESTAMP, sender_inbox = ? WHERE id = ?", (from_inbox, sequence_id))
            else:
                cursor.execute("""
                    UPDATE author_sequences
                    SET stage = ?, next_action_at = ?, last_sent_at = CURRENT_TIMESTAMP,
                        sender_inbox = ?, gmail_thread_id = ?, last_message_id = ?
                    WHERE id = ?
                """, (next_stage, next_action, from_inbox, send_res["thread_id"], send_res["message_id"], sequence_id))
            cursor.execute("UPDATE authors SET status = 'contacted' WHERE id = ?", (author_id,))
            conn.commit()
            conn.close()

            logger.info(f"==> [AUTHOR SEND SUCCESS] Dispatched to {name} <{email}> for '{book_title}' via [{from_inbox}]!")

            # Automated Deliverability Seed Test every 10 author leads
            self.author_sent_counter += 1
            if self.author_sent_counter % 10 == 0 and from_inbox:
                acc_obj = self.gmail_pool.accounts.get(from_inbox)
                if acc_obj and "service" in acc_obj:
                    self.deliverability_tester.run_live_seed_test(from_inbox, acc_obj["service"])

            return True
        elif self.gmail_pool.last_failure == "no_capacity":
            # Our mailbox is not connected or hit a Google limit. Not the author's fault, so no blacklist.
            raise RuntimeError("Book trailer mailbox is not connected or is throttled. Check mailbox_map.json and run: python outreach.py check")
        else:
            # Handle failure: categorize as bounced, mark author invalid, and blacklist
            failed_email = email.strip().lower()
            conn = sqlite3.connect(AUTHOR_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE author_sequences SET status = 'bounced', last_sent_at = CURRENT_TIMESTAMP WHERE id = ?", (sequence_id,))
            cursor.execute("UPDATE authors SET status = 'bounced' WHERE id = ?", (author_id,))
            add_to_author_blacklist(failed_email, "send_failure_or_rejected", conn)
            conn.commit()
            conn.close()
            logger.warning(f"==> [AUTHOR BOUNCE FILTERED] Failed sending to {failed_email}. Categorized as bounced & blacklisted from all future author follow-ups.")
            return False

    async def dispatch_existing_ready_authors(self, max_limit: int = 250) -> int:
        """Dispatches all ready follow-ups and uncontacted authors in queue first."""
        sent_count = 0
        conn = sqlite3.connect(AUTHOR_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT s.id as seq_id, s.stage, s.gmail_thread_id, s.last_message_id,
                   a.id as author_id, a.name, a.book_title, a.genre, a.email
            FROM author_sequences s
            JOIN authors a ON s.author_id = a.id
            WHERE s.status = 'active'
              AND (s.next_action_at IS NULL OR s.next_action_at <= CURRENT_TIMESTAMP)
            ORDER BY s.stage DESC, a.created_at ASC
            LIMIT ?
        """, (max_limit,))
        ready = cursor.fetchall()
        conn.close()

        for row in ready:
            ok = await self.send_single_author_now(
                author_id=row["author_id"],
                name=row["name"],
                book_title=row["book_title"],
                genre=row["genre"],
                email=row["email"],
                sequence_id=row["seq_id"],
                stage=row["stage"],
                thread_id=row["gmail_thread_id"],
                last_msg_id=row["last_message_id"]
            )
            if ok:
                sent_count += 1
                delay = random.randint(180, 480)  # 3 to 8 minutes between emails
                logger.info(f"Pacing delay: waiting {delay}s before next author send...")
                await asyncio.sleep(delay)

        return sent_count

    async def run_live_stream_outreach(self, selected_offer: str = "all", target_daily_quota: int = 250):
        accounts = self.gmail_pool.get_all_accounts()
        total_inboxes = max(1, len(accounts))
        target_quota = min(target_daily_quota, int(os.getenv("SCOUT_DAILY_CAP", "20")))
        available_offers = ["book_trailer", "cover_design", "amazon_aplus", "audiobook", "content_batch", "author_website", "kickstarter_kit"]

        logger.info("=" * 70)
        logger.info(f"STARTING LIVE AUTHOR OUTREACH ({total_inboxes} Inboxes | Offer Mode: {selected_offer.upper()})")
        logger.info("=" * 70)

        # 1. Check inboxes for author replies
        events = self.gmail_pool.check_all_inboxes_for_replies()
        for evt in events:
            if evt["type"] == "reply":
                logger.info(f"HOT AUTHOR REPLY from {evt['from']} on thread {evt['thread_id']}!")
                conn = sqlite3.connect(AUTHOR_DB_PATH)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("UPDATE author_sequences SET status = 'hot', reply_received = 1 WHERE gmail_thread_id = ?", (evt["thread_id"],))
                cursor.execute("""
                    SELECT a.name, a.book_title, a.genre, a.email
                    FROM author_sequences s
                    JOIN authors a ON s.author_id = a.id
                    WHERE s.gmail_thread_id = ?
                """, (evt["thread_id"],))
                row = cursor.fetchone()
                conn.commit()
                conn.close()

                if row:
                    try:
                        from notifier.telegram_notifier import notifier
                        await notifier.notify_author_reply(
                            author_name=row["name"],
                            book_title=row["book_title"],
                            genre=row["genre"],
                            email=row["email"],
                            receiving_inbox=evt.get("account", "")
                        )
                    except Exception as e:
                        logger.debug(f"Telegram author notify error: {e}")

        # 2. Priority Dispatch: Send existing ready author leads first
        sent_today = self.get_author_emails_sent_today_count()
        if sent_today < target_quota:
            remaining = target_quota - sent_today
            initial_sent = await self.dispatch_existing_ready_authors(max_limit=remaining)
            sent_today = self.get_author_emails_sent_today_count()
            logger.info(f">> Dispatched {initial_sent} existing authors. (Total Sent Today: {sent_today}/{target_quota})")

        # 3. Live Stream: Sweep Platforms -> Verify -> Instantly Dispatch
        genres_list = list(AUTHOR_GENRES.keys())
        while sent_today < target_quota:
            genre = random.choice(genres_list)
            keywords = AUTHOR_GENRES[genre]
            keyword = random.choice(keywords)
            offer_to_pitch = random.choice(available_offers) if selected_offer == "all" else selected_offer

            logger.info(f"\n[*] Hunting [{genre.upper()}] Authors | Angle: [{offer_to_pitch.upper()}] | Keyword: '{keyword}'...")
            authors = await self.scraper.search_authors(keyword=keyword, genre=genre, limit=8)

            if not authors:
                logger.info("    [-] Advancing to next author genre...")
                await asyncio.sleep(1)
                continue

            for author in authors:
                if self.get_author_emails_sent_today_count() >= target_quota:
                    break

                email = author["email"].lower()
                conn = sqlite3.connect(AUTHOR_DB_PATH)
                if is_author_blacklisted(email, conn):
                    conn.close()
                    continue

                cursor = conn.cursor()
                cursor.execute("SELECT id FROM authors WHERE email = ?", (email,))
                existing = cursor.fetchone()

                if existing:
                    conn.close()
                    continue

                # Verify email
                v_res = await self.verifier.verify(email)
                if not v_res.get("is_deliverable"):
                    logger.info(f"    [SKIP] Invalid email {email}: {v_res.get('reason')}")
                    conn.close()
                    continue

                # Save author
                cursor.execute("""
                    INSERT INTO authors (name, book_title, genre, website, domain, email, source, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'verified')
                """, (author["name"], author["book_title"], author["genre"], author.get("website"), author.get("domain"), email, author.get("source", "web")))
                author_id = cursor.lastrowid

                # Create initial sequence entry
                cursor.execute("""
                    INSERT INTO author_sequences (author_id, stage, status)
                    VALUES (?, 1, 'active')
                """, (author_id,))
                seq_id = cursor.lastrowid
                conn.commit()
                conn.close()

                # IMMEDIATELY SEND 1-of-1 personalized pitch for selected offer
                logger.info(f">> Live Dispatching [{offer_to_pitch}] pitch to {author['name']} <{email}> for '{author['book_title']}'...")
                ok = await self.send_single_author_now(
                    author_id=author_id,
                    name=author["name"],
                    book_title=author["book_title"],
                    genre=author["genre"],
                    email=email,
                    sequence_id=seq_id,
                    offer_service=offer_to_pitch,
                    stage=1
                )

                if ok:
                    sent_today = self.get_author_emails_sent_today_count()
                    pacing = random.randint(180, 480)  # 3 to 8 minutes between emails
                    logger.info(f"Pacing delay: waiting {pacing}s before next author send... (Daily Total: {sent_today}/{target_quota})")
                    await asyncio.sleep(pacing)

        logger.info(f"\n[DONE] Daily outreach quota of {target_quota} reached across all inboxes.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Author & Book Outreach Engine")
    parser.add_argument("--offer", type=str, default="all", choices=["all", "book_trailer", "cover_design", "amazon_aplus", "audiobook", "content_batch", "author_website", "kickstarter_kit"], help="Service offer to pitch")
    args = parser.parse_args()

    try:
        engine = AuthorOutreachEngine()
        asyncio.run(engine.run_live_stream_outreach(selected_offer=args.offer))
    except KeyboardInterrupt:
        print("\n[!] Author outreach engine stopped by user.")
