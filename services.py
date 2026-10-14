"""
Service registry.

Each service has:
  - its own scouting niches and target countries
  - its own fit scoring (see scout_signals.py)
  - exactly ONE sender mailbox (mailbox_map.json), so replies, reputation and
    reporting stay clean per service.

Add a new service by adding one entry to SERVICES. Nothing else needs to change.
"""
import json
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional

from config import BASE_DIR
import render3d

MAILBOX_MAP_FILE = BASE_DIR / "mailbox_map.json"


@dataclass
class Service:
    id: str
    label: str
    business_type: str
    keywords: List[str]
    countries: List[str]
    engine: str = "scout"          # "scout" = scout.py, "author_engine" = author_engine/
    min_score: int = 40            # shortlist threshold (0 to 100)
    description: str = ""
    mailbox: Optional[str] = field(default=None, repr=False)


SERVICES: Dict[str, Service] = {
    "whatsapp_api": Service(
        id="whatsapp_api",
        label="WhatsApp Cloud API setup and Meta verification",
        business_type="local",
        description=(
            "Meta business verification, WhatsApp Cloud API setup, green tick, "
            "chatbots and CRM connections for businesses that already talk to "
            "customers on WhatsApp by hand."
        ),
        keywords=[
            "ecommerce store",
            "dental clinic",
            "med spa",
            "real estate agency",
            "travel agency",
            "language school",
            "private school",
            "car dealership",
            "beauty salon",
            "fitness studio",
            "furniture store",
            "restaurant delivery",
        ],
        # Markets where WhatsApp is the main customer channel. ES, IT, PT, NL, DE and UK were removed:
        # they are in CAREFUL_REGIONS, so the send step always skipped them and scouting them was wasted.
        countries=["AE", "SA", "QA", "KW", "BH", "OM", "SG", "MY"],
        min_score=45,
    ),
    "receptionist": Service(
        id="receptionist",
        label="AI voice receptionist",
        business_type="local",
        description="24/7 AI phone assistant that answers, qualifies and books jobs.",
        keywords=[
            "emergency plumber",
            "hvac repair",
            "electrician contractor",
            "water damage restoration",
            "garage door repair",
            "pest control company",
            "cosmetic dentist",
            "personal injury lawyer",
        ],
        countries=["US", "UK", "CA", "AU", "NZ", "IE"],
        min_score=40,
    ),
    "render_3d": Service(
        id="render_3d",
        label=render3d.LABEL,
        business_type="local",
        description=render3d.DESCRIPTION,
        keywords=render3d.KEYWORDS,
        countries=render3d.COUNTRIES,
        min_score=render3d.MIN_SCORE,
    ),
    # The third mailbox moved to render_3d. Kept for the local author_engine code; it has no mailbox now.
    "book_trailer": Service(
        id="book_trailer",
        label="Author book trailers",
        business_type="author",
        description="Short cinematic trailers and 3D teasers for authors.",
        keywords=[],
        countries=["US", "UK", "CA", "AU"],
        engine="author_engine",
    ),
}


def load_mailbox_map() -> Dict[str, str]:
    if MAILBOX_MAP_FILE.exists():
        try:
            return {k: v.strip().lower() for k, v in json.loads(MAILBOX_MAP_FILE.read_text("utf-8")).items() if v}
        except Exception:
            return {}
    return {}


def get_service(service_id: str) -> Service:
    if service_id not in SERVICES:
        raise KeyError(f"Unknown service '{service_id}'. Choose from: {', '.join(SERVICES)}")
    svc = SERVICES[service_id]
    mailbox = load_mailbox_map().get(service_id)
    return replace(svc, mailbox=mailbox)


def validate_mailbox_map() -> List[str]:
    """Returns a list of problems. Rule: one mailbox per service, no sharing."""
    problems: List[str] = []
    mapping = load_mailbox_map()
    seen: Dict[str, str] = {}
    for sid in SERVICES:
        mb = mapping.get(sid)
        if SERVICES[sid].engine != "scout" and not mb:
            continue  # not run by the workflows (book_trailer gave its mailbox to render_3d)
        if not mb:
            problems.append(f"{sid}: no mailbox assigned in mailbox_map.json")
            continue
        if mb in seen:
            problems.append(f"{sid}: shares {mb} with {seen[mb]} (fine; MAILBOX_DAILY_CAP limits the total)")
        seen[mb] = sid
    return problems
