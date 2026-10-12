"""
Fit signals and scoring for scouting. Read only: fetches public pages, never sends anything.
"""
import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import render3d
import aiohttp

SCOUT_UA = "IffyStudiosScout/1.0"
PAGES = ["", "/contact", "/contact-us"]

WA_LINK = re.compile(r"(wa\.me/|api\.whatsapp\.com/send|web\.whatsapp\.com/send|whatsapp://send|wa\.link/)", re.I)
WA_WORD = re.compile(r"whatsapp", re.I)

# Providers that mean the business already has WhatsApp API tooling in place
BSP_MARKERS = {
    "twilio": "Twilio", "360dialog": "360dialog", "wati.io": "WATI", "gupshup": "Gupshup",
    "respond.io": "respond.io", "interakt": "Interakt", "gallabox": "Gallabox",
    "aisensy": "AiSensy", "manychat": "ManyChat", "botpress": "Botpress",
    "messagebird": "MessageBird", "infobip": "Infobip", "zoko": "Zoko",
}
CHAT_WIDGETS = ["tidio", "intercom", "crisp.chat", "drift.com", "livechatinc", "tawk.to", "zendesk", "hubspot"]
COMMERCE = ["cdn.shopify.com", "woocommerce", "wp-content/plugins/woocommerce", "bigcommerce", "magento", "add to cart", "add-to-cart"]
BOOKING = ["calendly.com", "acuityscheduling", "setmore", "fresha.com", "booksy", "treatwell", "simplybook", "book now", "book online"]
ADS_PIXELS = ["connect.facebook.net", "fbq(", "googletagmanager.com/gtag", "googleadservices"]


async def _fetch(session: aiohttp.ClientSession, url: str, timeout: int = 8) -> str:
    try:
        async with session.get(url, timeout=timeout, allow_redirects=True) as resp:
            if resp.status < 400:
                return await resp.text(errors="ignore")
    except Exception:
        pass
    return ""


async def allowed_by_robots(session: aiohttp.ClientSession, base_url: str) -> bool:
    p = urlparse(base_url)
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    text = await _fetch(session, robots_url, timeout=5)
    if not text:
        return True
    rp = RobotFileParser()
    rp.parse(text.splitlines())
    return rp.can_fetch(SCOUT_UA, base_url)


def analyse_html(pages: Dict[str, str]) -> Dict[str, Any]:
    """Pure function (easy to test): turns raw HTML into signals."""
    joined = "\n".join(pages.values())
    low = joined.lower()
    wa_link = WA_LINK.search(joined)
    bsp = next((name for key, name in BSP_MARKERS.items() if key in low), None)
    chat = next((w for w in CHAT_WIDGETS if w in low), None)
    return {
        "reachable": bool(joined.strip()),
        "has_wa_link": bool(wa_link),
        "mentions_whatsapp": bool(WA_WORD.search(joined)),
        "bsp_detected": bsp,
        "chat_widget": chat,
        "is_commerce": any(m in low for m in COMMERCE),
        "has_booking": any(m in low for m in BOOKING),
        "runs_ads": any(m in low for m in ADS_PIXELS),
        "has_contact_form": "<form" in low,
    }


def score_whatsapp(sig: Dict[str, Any], lead: Dict[str, Any], contact: Dict[str, Any]) -> Tuple[int, List[str]]:
    ev: List[str] = []
    if not sig["reachable"]:
        return 0, ["site not reachable"]
    if sig["bsp_detected"]:
        return 0, [f"already uses {sig['bsp_detected']}, skip"]
    score = 10
    if sig["has_wa_link"]:
        score += 30
        ev.append("uses a WhatsApp click to chat link (manual WhatsApp today, API upgrade fit)")
    elif sig["mentions_whatsapp"]:
        score += 15
        ev.append("mentions WhatsApp on the site")
    if not sig["chat_widget"]:
        score += 15
        ev.append("no live chat or bot on the site")
    if sig["is_commerce"] or sig["has_booking"]:
        score += 15
        ev.append("sells or books online, so there are customer messages to automate")
    if sig["runs_ads"]:
        score += 10
        ev.append("runs ad tracking, likely pays for leads that need fast replies")
    if (lead.get("reviews_count") or 0) >= 20:
        score += 10
        ev.append(f"{lead.get('reviews_count')} reviews, steady customer volume")
    if contact.get("emails") or contact.get("phone") or sig["has_contact_form"]:
        score += 10
        ev.append("has a public business contact route")
    return min(score, 100), ev


def score_receptionist(sig: Dict[str, Any], lead: Dict[str, Any], contact: Dict[str, Any]) -> Tuple[int, List[str]]:
    ev: List[str] = []
    if not sig["reachable"]:
        return 0, ["site not reachable"]
    score = 10
    if lead.get("phone"):
        score += 25
        ev.append("phone is the main contact route")
    if not sig["chat_widget"] and not sig["has_booking"]:
        score += 25
        ev.append("no chat or online booking, calls are the only way in")
    if (lead.get("reviews_count") or 0) >= 15:
        score += 15
        ev.append("busy business by review count")
    if sig["runs_ads"]:
        score += 15
        ev.append("pays for traffic, missed calls cost real money")
    if contact.get("emails") or sig["has_contact_form"]:
        score += 10
        ev.append("has a public business contact route")
    return min(score, 100), ev


SCORERS = {"whatsapp_api": score_whatsapp, "receptionist": score_receptionist, "render_3d": render3d.score_render3d}


async def inspect_site(session: aiohttp.ClientSession, website: str, sem: asyncio.Semaphore) -> Optional[Dict[str, Any]]:
    """Returns signals, or None if robots.txt disallows us."""
    if not website.startswith(("http://", "https://")):
        website = "https://" + website
    async with sem:
        if not await allowed_by_robots(session, website):
            return None
        pages = {}
        for path in PAGES:
            html = await _fetch(session, urljoin(website, path))
            if html:
                pages[path] = html
        sig = analyse_html(pages)
        sig.update(render3d.analyse_html_render3d(pages))
        sig["pages_fetched"] = list(pages.keys())
        return sig
