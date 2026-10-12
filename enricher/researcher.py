import re
import aiohttp
import asyncio
import logging
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse
from config import DEFAULT_HEADERS
from offers.cleaner import clean_service_name

logger = logging.getLogger(__name__)

# Key pages to crawl for business intelligence
RESEARCH_PATHS = [
    "",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/services"
]

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

class DeepBusinessResearcher:
    """Performs lightning-fast deep research on a prospect website in parallel."""

    def __init__(self, timeout: int = 4):
        self.timeout = timeout

    async def _fetch_page(self, session: aiohttp.ClientSession, base_url: str, path: str) -> tuple[str, str]:
        target_url = urljoin(base_url, path)
        try:
            async with session.get(target_url, timeout=self.timeout, ssl=False, allow_redirects=True) as resp:
                if resp.status < 400:
                    html = await resp.text(errors="ignore")
                    return path, html
        except Exception:
            pass
        return path, ""

    async def research_business(self, website_url: str) -> Dict[str, Any]:
        """
        Deeply inspects the business website across subpages in parallel to extract:
        - Founder / Owner / Key personnel names
        - Flagship services and specialties
        - Company background / years in business
        - Contact emails & phones
        - Operational & conversion gaps
        """
        if not website_url.startswith(("http://", "https://")):
            website_url = "https://" + website_url

        parsed = urlparse(website_url)
        domain = parsed.netloc.lower().replace("www.", "")

        research_data: Dict[str, Any] = {
            "domain": domain,
            "website": website_url,
            "emails": [],
            "founder_name": None,
            "flagship_services": [],
            "company_background": None,
            "recent_projects": [],
            "signals": {
                "has_booking_chat": False,
                "has_youtube": False,
                "copyright_year": None,
                "is_mobile_friendly": True
            },
            "research_summary": ""
        }

        found_emails = set()
        JUNK_EMAIL_DOMAINS = {
            "sentry.io", "wixpress.com", "example.com", "domain.com", "email.com",
            "yourcompany.com", "bootstrap.com", "cloudflare.com", "googleapis.com",
            "schema.org", "wordpress.org", "gravatar.com", "w3.org", "wix.com",
            "squarespace.com", "shopify.com", "weebly.com"
        }
        IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js", ".ico")

        def is_valid_candidate_email(cand: str) -> bool:
            cand = cand.strip().lower()
            if not cand or "@" not in cand or any(cand.endswith(ext) for ext in IMAGE_EXTS):
                return False
            u, d = cand.split("@", 1) if "@" in cand else ("", "")
            if d in JUNK_EMAIL_DOMAINS or any(d.endswith("." + jd) for jd in JUNK_EMAIL_DOMAINS):
                return False
            if any(u.startswith(p) for p in ["noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster"]):
                return False
            return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", cand))

        connector = aiohttp.TCPConnector(ssl=False, limit=10)
        async with aiohttp.ClientSession(headers=DEFAULT_HEADERS, connector=connector) as session:
            tasks = [self._fetch_page(session, website_url, p) for p in RESEARCH_PATHS]
            pages = await asyncio.gather(*tasks)

            for path, html in pages:
                if not html:
                    continue
                try:
                    soup = BeautifulSoup(html, "lxml")

                    # 1. Extract Emails
                    for mailto in soup.select('a[href^="mailto:"]'):
                        em = mailto.get("href", "").replace("mailto:", "").split("?")[0].strip().lower()
                        em = re.sub(r"^(?:u003e|[<>\"\'\\])+", "", em)
                        if is_valid_candidate_email(em):
                            found_emails.add(em)
                    for em in EMAIL_REGEX.findall(html):
                        em_clean = re.sub(r"^(?:u003e|[<>\"\'\\])+", "", em.strip().lower())
                        if is_valid_candidate_email(em_clean):
                            found_emails.add(em_clean)

                    # 2. Extract Founder / Owner Names
                    if path in ("/about", "/about-us", "/team", "") and not research_data["founder_name"]:
                        for el in soup.find_all(["h2", "h3", "h4", "p", "strong"]):
                            text = el.get_text(strip=True)
                            match = re.search(r"(?i)\b(?:founder|owner|president|ceo|director|managing partner)\b[:\-]?\s*([A-Z][a-z]+ [A-Z][a-z]+)", text)
                            if match:
                                research_data["founder_name"] = match.group(1).strip()
                                break
                            
                            founded_match = re.search(r"(?i)(?:founded in|established in|serving [a-zA-Z\s]+ since)\s*(19\d\d|20\d\d)", text)
                            if founded_match and not research_data["company_background"]:
                                research_data["company_background"] = f"In business since {founded_match.group(1)}"

                    # 3. Extract Core Services
                    if path in ("/services", "/our-services", ""):
                        for service_header in soup.select("h2, h3, h4, .service-title, li.service-item"):
                            s_text = service_header.get_text(strip=True)
                            cleaned_s = clean_service_name(s_text)
                            if cleaned_s and cleaned_s not in research_data["flagship_services"]:
                                research_data["flagship_services"].append(cleaned_s)

                    # 4. Tech & Conversion Gap Signals
                    lower_html = html.lower()
                    if any(w in lower_html for w in ["calendly.com", "tidio", "intercom", "crisp.chat", "drift.com", "acuityscheduling"]):
                        research_data["signals"]["has_booking_chat"] = True

                    if "youtube.com" in lower_html or "youtu.be" in lower_html:
                        research_data["signals"]["has_youtube"] = True

                    copy_match = re.search(r"©\s*(20\d\d)", html)
                    if copy_match:
                        research_data["signals"]["copyright_year"] = int(copy_match.group(1))

                except Exception:
                    continue

        research_data["emails"] = sorted(list(found_emails))
        services_preview = ", ".join(research_data["flagship_services"][:3]) if research_data["flagship_services"] else "General services"
        
        # Build clean research summary
        summary_parts = []
        if research_data["founder_name"]:
            summary_parts.append(f"Owner/Founder: {research_data['founder_name']}")
        if research_data["company_background"]:
            summary_parts.append(research_data["company_background"])
        if research_data["flagship_services"]:
            summary_parts.append(f"Specializes in: {services_preview}")
        if not research_data["signals"]["has_booking_chat"]:
            summary_parts.append("Has no instant 24/7 calendar booking or live chat")
        if research_data["signals"]["has_youtube"]:
            summary_parts.append("Produces long-form video content on YouTube")

        research_data["research_summary"] = ". ".join(summary_parts)
        return research_data
