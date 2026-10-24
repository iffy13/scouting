"""
Google Maps lead source, using the official Google Places API (New) Text Search.

Why the official API and not a Maps scraper:
  - Scraping the Google Maps website breaks Google's terms and gets blocked from GitHub's servers.
  - The API works from GitHub Actions, returns real businesses only (no articles or directories),
    and comes with the website, phone, rating, review count, category and open/closed status.

What it costs (Google price list, checked 24 Oct 2026):
  We ask for websiteUri, rating, userRatingCount and the phone, which puts each call in the
  "Text Search Enterprise" SKU: 1,000 calls free per month, then $35 per 1,000 calls.
  One call returns up to 20 businesses, so the free month covers up to about 20,000 businesses.
  PLACES_DAILY_CALLS (default 30) keeps us under the free 1,000 a month. Also set a quota
  limit in Google Cloud (see PLACES-SETUP.md) so a bug can never run up a bill.

Terms we follow (Google Maps Platform terms):
  - Only the place id may be stored long term. Everything else from Google (rating, review count,
    phone, photos) is used in memory to score the lead at scout time and is NOT saved.
  - The email address and owner name still come from the business's own website, as before.
  - Maps data is not shown on a map that is not Google's, and is not resold.

Use:
  from scrapers.google_places import GooglePlacesScraper, maps_fit
  maps = GooglePlacesScraper()                     # reads GOOGLE_PLACES_API_KEY
  leads = await maps.search(keyword="emergency plumber", country="US", limit=20)
  points, evidence, junk = maps_fit(lead, "receptionist")

Each lead has the same keys the other scrapers return (name, domain, website, phone, city, country,
source) plus a "maps" dict with the extra signals and "place_id".

Self-test (no network, no key needed):  python -m scrapers.google_places
"""
import asyncio
import json
import logging
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger("google_places")

API_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.addressComponents",
    "places.websiteUri", "places.nationalPhoneNumber", "places.internationalPhoneNumber",
    "places.rating", "places.userRatingCount", "places.businessStatus",
    "places.primaryType", "places.types", "places.photos", "places.regularOpeningHours",
    "nextPageToken",
])

# Cities per country. Mid-size cities give more small, owner-run businesses than the biggest metros.
# The scout picks a random city each call, so runs do not keep finding the same businesses.
CITIES: Dict[str, List[str]] = {
    "US": ["Austin", "Tampa", "Raleigh", "Columbus", "Charlotte", "Nashville", "Denver", "Phoenix",
           "San Antonio", "Jacksonville", "Indianapolis", "Kansas City", "Omaha", "Tulsa", "Boise",
           "Sacramento", "Salt Lake City", "Richmond", "Louisville", "Birmingham", "Albuquerque",
           "Spokane", "Knoxville", "Greenville", "Fort Myers", "Scottsdale", "Plano", "Naperville"],
    "CA": ["Calgary", "Edmonton", "Ottawa", "Winnipeg", "Hamilton", "Kitchener", "London Ontario",
           "Halifax", "Victoria", "Saskatoon", "Regina", "Kelowna", "Mississauga", "Surrey"],
    "AU": ["Brisbane", "Perth", "Adelaide", "Gold Coast", "Newcastle NSW", "Canberra",
           "Sunshine Coast", "Geelong", "Townsville", "Hobart", "Wollongong", "Parramatta"],
    "NZ": ["Auckland", "Wellington", "Christchurch", "Hamilton NZ", "Tauranga", "Dunedin"],
    "AE": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Al Ain", "Ras Al Khaimah"],
    "SA": ["Riyadh", "Jeddah", "Dammam", "Khobar", "Mecca", "Medina"],
    "QA": ["Doha", "Al Wakrah", "Lusail"],
    "KW": ["Kuwait City", "Hawalli", "Salmiya"],
    "BH": ["Manama", "Muharraq", "Riffa"],
    "OM": ["Muscat", "Sohar", "Salalah"],
    "SG": ["Singapore"],
    "MY": ["Kuala Lumpur", "Petaling Jaya", "Penang", "Johor Bahru", "Shah Alam", "Ipoh"],
    "ZA": ["Johannesburg", "Cape Town", "Durban", "Pretoria", "Port Elizabeth", "Sandton"],
}

# Places API wants CLDR region codes. The tool uses "UK" for Britain.
REGION_CODE = {"UK": "GB"}

# Very large review counts usually mean a chain or a big company, not a small business.
CHAIN_REVIEWS = 1500

USAGE_FILE = Path(os.getenv("PLACES_USAGE_FILE", "places_usage.json"))


class PlacesBudgetReached(Exception):
    pass


def _domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        host = urlparse(url if "://" in url else "https://" + url).netloc.lower()
    except Exception:
        return None
    host = host.split(":")[0]
    return host[4:] if host.startswith("www.") else host or None


def _city(place: Dict[str, Any]) -> Optional[str]:
    for comp in place.get("addressComponents") or []:
        if "locality" in (comp.get("types") or []):
            return comp.get("longText") or comp.get("shortText")
    return None


class _Usage:
    """Counts API calls per UTC day so one day can never spend more than PLACES_DAILY_CALLS.
    On GitHub Actions the default file is wiped every run, so pass a store that lives in the
    database (see get_count / add_count in the constructor)."""

    def __init__(self, get_count: Optional[Callable[[str], int]] = None,
                 add_count: Optional[Callable[[str, int], None]] = None):
        self._get, self._add = get_count, add_count

    @staticmethod
    def today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def used(self) -> int:
        if self._get:
            return self._get(self.today())
        try:
            data = json.loads(USAGE_FILE.read_text("utf-8"))
            return int(data.get(self.today(), 0))
        except Exception:
            return 0

    def add(self, n: int = 1):
        if self._add:
            self._add(self.today(), n)
            return
        try:
            data = json.loads(USAGE_FILE.read_text("utf-8"))
        except Exception:
            data = {}
        data = {k: v for k, v in data.items() if k >= self.today()[:8]}  # keep this month only
        data[self.today()] = int(data.get(self.today(), 0)) + n
        USAGE_FILE.write_text(json.dumps(data), "utf-8")


class GooglePlacesScraper:
    def __init__(self, api_key: Optional[str] = None, daily_calls: Optional[int] = None,
                 get_count: Optional[Callable[[str], int]] = None,
                 add_count: Optional[Callable[[str, int], None]] = None,
                 transport: Optional[Callable[..., Any]] = None):
        self.api_key = api_key if api_key is not None else os.getenv("GOOGLE_PLACES_API_KEY", "")
        self.daily_calls = daily_calls if daily_calls is not None else int(os.getenv("PLACES_DAILY_CALLS", "30"))
        self.usage = _Usage(get_count, add_count)
        self._transport = transport  # tests pass a fake here

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def calls_left_today(self) -> int:
        return max(0, self.daily_calls - self.usage.used())

    async def _post(self, body: Dict[str, Any]) -> Dict[str, Any]:
        if self.calls_left_today() <= 0:
            raise PlacesBudgetReached(f"Google Places daily limit of {self.daily_calls} calls reached")
        self.usage.add(1)
        if self._transport:
            return await self._transport(body)
        import aiohttp
        headers = {"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": FIELD_MASK,
                   "Content-Type": "application/json"}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
            async with s.post(API_URL, json=body, headers=headers) as r:
                data = await r.json(content_type=None)
                if r.status != 200:
                    msg = (data or {}).get("error", {}).get("message", "") if isinstance(data, dict) else ""
                    raise RuntimeError(f"Google Places error {r.status}: {msg[:200]}")
                return data or {}

    async def search(self, keyword: str, country: str, city: str = "General", limit: int = 20,
                     max_pages: int = 1) -> List[Dict[str, Any]]:
        """Up to `limit` businesses for one keyword in one city of `country`.
        city="General" picks a random city from CITIES. Each page is one paid call (20 results)."""
        if not self.enabled:
            logger.info("GOOGLE_PLACES_API_KEY not set, Google Maps source skipped")
            return []
        ctry = country.upper()
        if not city or city == "General":
            city = random.choice(CITIES.get(ctry) or [""])
        query = f"{keyword} in {city}" if city else keyword
        body: Dict[str, Any] = {"textQuery": query, "pageSize": min(20, max(1, limit)),
                                "regionCode": REGION_CODE.get(ctry, ctry)}
        out: List[Dict[str, Any]] = []
        for _ in range(max(1, max_pages)):
            try:
                data = await self._post(body)
            except PlacesBudgetReached as e:
                logger.info(str(e))
                break
            for p in data.get("places") or []:
                lead = self._to_lead(p, keyword, ctry, city)
                if lead:
                    out.append(lead)
            token = data.get("nextPageToken")
            if not token or len(out) >= limit:
                break
            body = {**body, "pageToken": token}
            await asyncio.sleep(2)  # page tokens need a moment before they work
        logger.info(f"Google Maps: [{query}] gave {len(out)} businesses")
        return out[:limit]

    @staticmethod
    def _to_lead(p: Dict[str, Any], keyword: str, country: str, city: str) -> Optional[Dict[str, Any]]:
        name = (p.get("displayName") or {}).get("text")
        if not name:
            return None
        website = p.get("websiteUri")
        hours = p.get("regularOpeningHours") or {}
        return {
            "name": name,
            "website": website,
            "domain": _domain(website),
            # Phone is for scoring only. Do not store it (Google terms); scout.py should save
            # lead["phone"] only when it came from the business's own site.
            "phone": None,
            "city": _city(p) or city,
            "country": country,
            "keyword": keyword,
            "source": "google_maps",
            "place_id": p.get("id"),
            # The existing scorers read these two keys (Serper leads have them too). Used for scoring only.
            "rating": p.get("rating"),
            "reviews_count": int(p.get("userRatingCount") or 0),
            "maps": {
                "phone": p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber"),
                "rating": p.get("rating"),
                "reviews": int(p.get("userRatingCount") or 0),
                "photos": len(p.get("photos") or []),       # the API returns at most 10
                "status": p.get("businessStatus") or "OPERATIONAL",
                "primary_type": p.get("primaryType"),
                "types": p.get("types") or [],
                "has_hours": bool(hours.get("periods") or hours.get("weekdayDescriptions")),
                "open_24h": _open_24h(hours),
            },
        }


def _open_24h(hours: Dict[str, Any]) -> bool:
    for d in hours.get("weekdayDescriptions") or []:
        if "24 hours" in d.lower() or "open 24" in d.lower():
            return True
    return False


def maps_fit(lead: Dict[str, Any], service_id: str) -> Tuple[int, List[str], Optional[str]]:
    """Extra points from Google Maps signals, added on top of the service's site score.
    Returns (points, evidence lines, junk reason). A junk reason means: do not keep this lead.
    Points are kept small (at most about 25) so the website signals still decide most of the score."""
    m = lead.get("maps") or {}
    if not m:
        return 0, [], None
    status = m.get("status")
    if status and status != "OPERATIONAL":
        return 0, [], "closed on Google Maps"
    if not lead.get("website"):
        return 0, [], "no website on Google Maps, so no email to find"
    reviews, rating, photos = m.get("reviews", 0), m.get("rating"), m.get("photos", 0)
    if reviews >= CHAIN_REVIEWS:
        return 0, [], f"{reviews} Google reviews, likely a chain or a big company"

    pts, ev = 0, []
    # Small and established: real customers, but not a big company with staff for everything.
    if 5 <= reviews <= 150:
        pts += 8
        ev.append(f"small local business on Google Maps ({reviews} reviews)")
    elif reviews < 5:
        pts += 2
        ev.append("very new or quiet on Google Maps")

    # The phone is not scored here: scout.py hands it to the service scorer, which already pays for it.
    if service_id == "receptionist":
        if m.get("has_hours") and not m.get("open_24h"):
            pts += 7
            ev.append("set opening hours, so after-hours calls go unanswered")
    elif service_id == "whatsapp_api":
        if reviews >= 20:
            pts += 5
            ev.append("busy enough to get many customer messages")
    elif service_id == "render_3d":
        if photos <= 3:
            pts += 10
            ev.append("few project photos on Google Maps")
        if rating is not None and rating >= 4.3:
            pts += 4
            ev.append("good reviews, likely winning work that needs visuals")
    return pts, ev, None


# ---------------------------------------------------------------- self-test (no network)
def _self_test() -> int:
    problems = 0

    def check(ok: bool, what: str):
        nonlocal problems
        if not ok:
            problems += 1
            print("PROBLEM:", what)

    sample = {"places": [
        {"id": "p1", "displayName": {"text": "Joe's Plumbing"}, "websiteUri": "https://www.joesplumbing.com/",
         "nationalPhoneNumber": "(512) 555-0100", "rating": 4.6, "userRatingCount": 42,
         "businessStatus": "OPERATIONAL", "primaryType": "plumber",
         "addressComponents": [{"longText": "Austin", "types": ["locality", "political"]}],
         "regularOpeningHours": {"weekdayDescriptions": ["Monday: 8:00 AM - 5:00 PM"]}},
        {"id": "p2", "displayName": {"text": "No Site Plumbing"}, "userRatingCount": 3,
         "businessStatus": "OPERATIONAL"},
        {"id": "p3", "displayName": {"text": "Big Chain Plumbing"}, "websiteUri": "https://bigchain.com",
         "userRatingCount": 9000, "businessStatus": "OPERATIONAL"},
        {"id": "p4", "displayName": {"text": "Closed Plumbing"}, "websiteUri": "https://closed.com",
         "userRatingCount": 20, "businessStatus": "CLOSED_PERMANENTLY"},
    ], "nextPageToken": "tok"}
    sent: List[Dict[str, Any]] = []

    async def fake(body):
        sent.append(body)
        return sample if "pageToken" not in body else {"places": []}

    counts: Dict[str, int] = {}
    sc = GooglePlacesScraper(api_key="test", daily_calls=2, transport=fake,
                             get_count=lambda d: counts.get(d, 0),
                             add_count=lambda d, n: counts.__setitem__(d, counts.get(d, 0) + n))
    leads = asyncio.run(sc.search("emergency plumber", "US", city="Austin", limit=20, max_pages=1))
    check(len(leads) == 4, f"expected 4 leads, got {len(leads)}")
    check(sent[0]["textQuery"] == "emergency plumber in Austin", "query text")
    check(sent[0]["regionCode"] == "US", "region code")
    joe = leads[0]
    check(joe["domain"] == "joesplumbing.com", f"domain parse: {joe['domain']}")
    check(joe["phone"] is None and joe["maps"]["phone"], "Google phone must not be in the stored phone field")
    check(joe["city"] == "Austin", "city from address")

    pts, ev, junk = maps_fit(joe, "receptionist")
    check(junk is None and pts == 15, f"receptionist fit for Joe: {pts} {junk}")
    check(maps_fit(leads[1], "receptionist")[2] is not None, "no website must be rejected")
    check("chain" in (maps_fit(leads[2], "receptionist")[2] or ""), "chain must be rejected")
    check("closed" in (maps_fit(leads[3], "receptionist")[2] or ""), "closed must be rejected")
    check(maps_fit(joe, "render_3d")[0] == 22, f"render_3d fit: {maps_fit(joe, 'render_3d')[0]}")
    check(maps_fit({"name": "x"}, "receptionist") == (0, [], None), "non-Maps lead gets nothing")

    # daily budget: 2 calls allowed, one used above
    asyncio.run(sc.search("hvac repair", "UK", city="General"))
    check(sent[-1]["regionCode"] == "GB", "UK must become GB")
    before = len(sent)
    third = asyncio.run(sc.search("hvac repair", "US"))
    check(len(sent) == before and third == [], "budget must stop the third call")

    check(asyncio.run(GooglePlacesScraper(api_key="").search("x", "US")) == [], "no key means no results")
    for c, cities in CITIES.items():
        check(len(cities) >= 1, f"no cities for {c}")
    print(f"{problems} problems")
    return problems


if __name__ == "__main__":
    raise SystemExit(1 if _self_test() else 0)
