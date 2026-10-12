import html
import os
import aiohttp
import asyncio
import urllib.parse
import logging
from typing import Optional
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "447853164638")

class TelegramNotifier:
    """
    Sends real-time push alerts to your Telegram phone app when:
    1. A genuine lead replies to your cold email.
    2. An author expresses interest in Book Trailers / Covers.
    3. An inbox hits its daily limit.
    """

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage" if self.bot_token else None

    async def send_message(self, text: str) -> bool:
        if not self.bot_token or not self.chat_id or not self.base_url:
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, json=payload, timeout=8) as resp:
                    if resp.status == 200:
                        return True
                    else:
                        err_body = await resp.text()
                        logger.warning(f"Telegram API response ({resp.status}): {err_body}")
        except Exception as e:
            logger.debug(f"Telegram notification error: {e}")
        return False

    async def notify_hot_reply(
        self,
        lead_name: str,
        company: str,
        email: str,
        offer_type: str,
        snippet: str,
        receiving_inbox: str
    ):
        """Sends rich alert for incoming prospect replies."""
        wa_text = f"Hi {lead_name}, thanks for replying regarding {company}! Let's connect."
        encoded_wa = urllib.parse.quote(wa_text)
        wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded_wa}"

        safe_lead_name = html.escape(str(lead_name))
        safe_company = html.escape(str(company))
        safe_email = html.escape(str(email))
        safe_offer_type = html.escape(str(offer_type))
        safe_inbox = html.escape(str(receiving_inbox))
        safe_snippet = html.escape(str(snippet))

        message = (
            f"🔥 <b>NEW HOT PROSPECT REPLY!</b>\n\n"
            f"👤 <b>Lead:</b> {safe_lead_name}\n"
            f"🏢 <b>Company:</b> {safe_company}\n"
            f"📧 <b>Email:</b> <code>{safe_email}</code>\n"
            f"💼 <b>Offer:</b> {safe_offer_type}\n"
            f"📬 <b>Received In:</b> {safe_inbox}\n\n"
            f"💬 <b>Reply Snippet:</b>\n"
            f"<i>\"{safe_snippet}\"</i>\n\n"
            f"📲 <a href=\"{wa_link}\">👉 <b>Reply on WhatsApp Directly</b></a>"
        )
        await self.send_message(message)

    async def notify_author_reply(
        self,
        author_name: str,
        book_title: str,
        genre: str,
        email: str,
        receiving_inbox: str
    ):
        """Sends rich alert for author replies."""
        wa_text = f"Hi {author_name}, thanks for connecting regarding '{book_title}'! Let's discuss the trailer."
        encoded_wa = urllib.parse.quote(wa_text)
        wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={encoded_wa}"

        safe_author_name = html.escape(str(author_name))
        safe_book_title = html.escape(str(book_title))
        safe_genre = html.escape(str(genre))
        safe_email = html.escape(str(email))
        safe_inbox = html.escape(str(receiving_inbox))

        message = (
            f"📚 <b>HOT AUTHOR REPLY! (Akdam Studios)</b>\n\n"
            f"✍️ <b>Author:</b> {safe_author_name}\n"
            f"📖 <b>Book:</b> {safe_book_title}\n"
            f"🎭 <b>Genre:</b> {safe_genre}\n"
            f"📧 <b>Email:</b> <code>{safe_email}</code>\n"
            f"📬 <b>Received In:</b> {safe_inbox}\n\n"
            f"📲 <a href=\"{wa_link}\">👉 <b>Open WhatsApp Chat with Author</b></a>"
        )
        await self.send_message(message)

    async def notify_inbox_throttled(self, inbox_email: str, reason: str = "Daily send limit reached"):
        """Alerts when a Gmail account is throttled by Google."""
        safe_email = html.escape(str(inbox_email))
        safe_reason = html.escape(str(reason))
        message = (
            f"⚠️ <b>GMAIL INBOX THROTTLED</b>\n\n"
            f"📬 <b>Account:</b> {safe_email}\n"
            f"ℹ️ <b>Reason:</b> {safe_reason}\n"
            f"🔄 <i>Engine has automatically paused this inbox for today and routed traffic to remaining active inboxes.</i>"
        )
        await self.send_message(message)

# Global singleton
notifier = TelegramNotifier()

if __name__ == "__main__":
    async def test():
        print("Testing Telegram Notifier...")
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("[!] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env.")
            print("    Add them to .env to enable instant mobile notifications.")
            return
        t = TelegramNotifier()
        ok = await t.notify_hot_reply(
            lead_name="Toby Dames",
            company="23 Digital Agency",
            email="toby@23digital.com.au",
            offer_type="video_clips",
            snippet="Hey, thanks for reaching out. What are your packages for video repurposing?",
            receiving_inbox="damkruger@gmail.com"
        )
        if ok:
            print("[SUCCESS] Test notification sent to your Telegram phone app!")
        else:
            print("[ERROR] Failed to send Telegram message. Check token and chat ID.")
    asyncio.run(test())
