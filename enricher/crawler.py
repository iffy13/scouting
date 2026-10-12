import re
import aiohttp
import asyncio
import logging
from bs4 import BeautifulSoup
from typing import Set, Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse
from config import DEFAULT_HEADERS

logger = logging.getLogger(__name__)

# Regex for email extraction
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
)

# Common generic / noise extensions or emails to ignore
IGNORE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".css", ".js", ".svg", ".webp", ".pdf", ".zip"}
IGNORE_EMAILS = {"wixpress.com", "sentry.io", "example.com", "domain.com", "email.com", "bootstrap.com"}

CONTACT_SUBPATHS = [
    "",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/team",
    "/impressum",
    "/imprint",
]

class WebsiteCrawler:
    """Async website crawler for email extraction and site signal analysis."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def crawl_site(self, base_url: str) -> Dict[str, Any]:
        """
        Crawls homepage and subpages to extract emails, social links, and tech signals.
        """
        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url

        parsed_base = urlparse(base_url)
        domain = parsed_base.netloc.lower().replace("www.", "")

        found_emails: Set[str] = set()
        social_links: Dict[str, str] = {}
        signals: Dict[str, Any] = {
            "is_live": False,
            "has_booking_chat": False,
            "has_youtube": False,
            "has_instagram": False,
            "has_linkedin": False,
            "copyright_year": None,
        }

        async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
            # Check homepage first
            for path in CONTACT_SUBPATHS:
                target_url = urljoin(base_url, path)
                try:
                    # Deliberately use ssl=False to handle sites with broken or misconfigured SSL certificates
                    async with session.get(target_url, timeout=self.timeout, allow_redirects=True, ssl=False) as resp:
                        if resp.status >= 400:
                            continue
                        
                        signals["is_live"] = True
                        content_type = resp.headers.get("Content-Type", "")
                        if "text/html" not in content_type:
                            continue

                        # Check Content-Length if present to prevent memory exhaustion (>5MB)
                        content_len = resp.headers.get("Content-Length")
                        if content_len and int(content_len) > 5_000_000:
                            continue

                        raw_content = await resp.content.read(5_000_000)
                        html = raw_content.decode("utf-8", errors="ignore")
                        soup = BeautifulSoup(html, "lxml")

                        # 1. Extract mailto: links
                        for mailto in soup.select('a[href^="mailto:"]'):
                            href = mailto.get("href", "")
                            clean_email = href.replace("mailto:", "").split("?")[0].strip().lower()
                            if self._is_valid_email_candidate(clean_email, domain):
                                found_emails.add(clean_email)

                        # 2. Extract regex matches from text
                        text_emails = EMAIL_REGEX.findall(html)
                        for em in text_emails:
                            em_clean = em.strip().lower()
                            if self._is_valid_email_candidate(em_clean, domain):
                                found_emails.add(em_clean)

                        # 3. Signals: Chat/booking widgets (Intercom, Tidio, Calendly, Crisp, Drift)
                        lower_html = html.lower()
                        if any(w in lower_html for w in ["calendly.com", "tidio", "intercom", "crisp.chat", "drift.com", "hubspot-messages-iframe"]):
                            signals["has_booking_chat"] = True

                        # 4. Signals: Social links (YouTube, Instagram, LinkedIn, TikTok)
                        for a in soup.find_all("a", href=True):
                            href = a["href"]
                            if "youtube.com" in href or "youtu.be" in href:
                                signals["has_youtube"] = True
                                social_links["youtube"] = href
                            elif "instagram.com" in href:
                                signals["has_instagram"] = True
                                social_links["instagram"] = href
                            elif "linkedin.com/company" in href or "linkedin.com/in" in href:
                                signals["has_linkedin"] = True
                                social_links["linkedin"] = href

                        # 5. Signals: Copyright year (check for outdated sites)
                        copyright_match = re.search(r"©\s*(20\d\d)", html) or re.search(r"copyright\s*(20\d\d)", html, re.I)
                        if copyright_match:
                            signals["copyright_year"] = int(copyright_match.group(1))

                except Exception as e:
                    # Timeout or unreachable path
                    continue

        # Score / sort emails: prefer domain-matching emails (e.g. hello@domain.com over info@gmail.com)
        sorted_emails = sorted(
            list(found_emails),
            key=lambda e: (domain in e, not e.startswith("info@"), not e.startswith("contact@")),
            reverse=True
        )

        return {
            "emails": sorted_emails,
            "primary_email": sorted_emails[0] if sorted_emails else None,
            "social_links": social_links,
            "signals": signals
        }

    def _is_valid_email_candidate(self, email: str, domain: str) -> bool:
        if not email or "@" not in email:
            return False
        if any(email.endswith(ext) for ext in IGNORE_EXTENSIONS):
            return False
        email_domain = email.split("@")[-1]
        if any(ign in email_domain for ign in IGNORE_EMAILS):
            return False
        return True
