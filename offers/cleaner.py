import re
import os
import json
import logging
import urllib.parse
from typing import Dict, Any, Optional

from lead_filter import BAD_NAMES

logger = logging.getLogger(__name__)

# Mega platforms, directory aggregators, news media, and job boards to strictly ignore
IGNORED_DOMAINS = {
    "youtube.com", "google.com", "bing.com", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "linkedin.com", "tiktok.com", "wikipedia.org",
    "jooble.org", "indeed.com", "glassdoor.com", "hotnigerianjobs.com",
    "businesslist.com", "hoyoverse.com", "goatgames.com", "hadesstar.com",
    "funplus.com", "play.google.com", "apps.apple.com", "expertise.com",
    "yelp.com", "yellowpages.com", "angi.com", "thumbtack.com", "bbb.org",
    "tripadvisor.com", "houzz.com", "trustpilot.com", "clutch.co", "g2.com",
    "capterra.com", "mapquest.com", "superpages.com", "dexknows.com",
    "manta.com", "citysearch.com", "bark.com", "checkatrade.com",
    "theplumbingdirectory.com", "plumbersbyzip.com", "bestplumbers.com",
    "trustamai.com", "daibau.ng", "myplumberinc.com", "myplumber.com",
    "statesman.com", "patch.com", "reddit.com", "medium.com", "quora.com",
    "usatoday.com", "nytimes.com", "forbes.com", "bloomberg.com"
}

# Generic directory and aggregator patterns in domain
DIRECTORY_KEYWORDS = [
    "directory", "yellowpages", "byzip", "finda", "findmy", "toprated",
    "chamberofcommerce", "localpages", "bestplumbers", "allplumbers",
    "plumbingguide", "contractorfind", "servicepros", "quotes"
]

# Strictly excluded countries and low-GDP markets (Zero outreach to these)
BANNED_TLDS = (
    ".ng", ".com.ng", ".gov.ng", ".edu.ng", ".org.ng",
    ".pk", ".in", ".co.in", ".ph", ".ke", ".gh", ".za"
)

BANNED_LOCATION_WORDS = [
    "nigeria", "onitsha", "lagos", "abuja", "ibadan", "kano", "port harcourt",
    "pakistan", "india", "philippines", "kenya", "ghana", "bangladesh"
]

BANNED_SERVICE_WORDS = {
    "call", "phone", "give us", "contact", "schedule", "book", "estimate",
    "quote", "emergency", "service area", "location", "hours", "review",
    "testimonial", "about", "navigation", "menu", "quick link", "copyright",
    "rights reserved", "terms", "privacy", "cookie", "discount", "special",
    "offer", "coupon", "get in touch", "message us"
}

def clean_business_name(raw_name: str, domain: Optional[str] = None) -> str:
    """Extracts a clean, human brand name from raw titles and removes SEO spam."""
    if not raw_name:
        if domain:
            return domain.split(".")[0].replace("-", " ").title()
        return "your team"

    # Remove pipe, dash, and colon SEO splits
    name = re.split(r"[-|:—–•]", raw_name)[0].strip()

    # Remove common SEO spam words and business suffixes
    name = re.sub(r"(?i)\b(parts for|excavators and|bulldozers|plumbers in|best|top|near me|services|llc|inc)\b", "", name).strip()
    name = re.sub(r"(?i)(?:,\s*Co\.?$|\bCo\.\b)", "", name).strip()
    name = re.sub(r"\s+", " ", name).strip()

    if (len(name) < 3 or name.lower() in BAD_NAMES) and domain:
        return domain.lower().replace("www.", "").split(".")[0].replace("-", " ").title()

    return name if name else "your business"

def clean_service_name(raw_service: str) -> Optional[str]:
    """Validates that extracted service text is an actual trade/craft and not phone or CTA buttons."""
    if not raw_service:
        return None
    
    # Strip any digits/phone numbers
    if re.search(r"\d", raw_service):
        return None
    
    cleaned = raw_service.strip().lower()
    if any(banned in cleaned for banned in BANNED_SERVICE_WORDS):
        return None
    
    if len(raw_service) < 4 or len(raw_service) > 35:
        return None
        
    return raw_service.strip()

# Scouting for lead_gen targets every market, so scout.py switches the market ban off while it runs.
ALLOW_ALL_MARKETS = False


def allow_all_markets(on: bool):
    global ALLOW_ALL_MARKETS
    ALLOW_ALL_MARKETS = bool(on)


def is_valid_prospect_domain(domain: Optional[str], website: Optional[str]) -> bool:
    """
    Ensures we NEVER email:
    1. Excluded / low-GDP locations (.ng, Nigeria, Onitsha, Lagos, India, Pakistan, etc.)
    2. Mega tech platforms / video game studios / app stores
    3. Generic directory and aggregator sites
    """
    if not domain:
        return False
        
    domain_clean = domain.lower().replace("www.", "").strip()
    website_clean = (website or "").lower()

    # 1. Reject Banned TLDs
    if not ALLOW_ALL_MARKETS and domain_clean.endswith(BANNED_TLDS):
        return False

    # 2. Reject Banned Location URLs
    if not ALLOW_ALL_MARKETS and any(banned_loc in website_clean for banned_loc in BANNED_LOCATION_WORDS):
        return False

    # 3. Reject Mega Platforms and Aggregators
    if any(ign in domain_clean for ign in IGNORED_DOMAINS):
        return False

    # 4. Reject Directory and Aggregator keywords
    if any(kw in domain_clean for kw in DIRECTORY_KEYWORDS):
        return False

    return True
