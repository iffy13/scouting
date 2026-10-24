"""
Free lead source: OpenStreetMap, through the public Overpass API. No key, no card, no account.

Why: Google Places needs a billing account with a card. OpenStreetMap is the free map that many apps use.
It lists fewer small businesses than Google Maps, but every result is a real place (not an article or a
directory page), and we only keep businesses that have their own website, so the scout can find an email.

How a search works:
  "emergency plumber" in US  ->  a random US city from CITIES  ->  every place within 20 km tagged as a
  plumber (craft=plumber), or whose name contains the keyword, that has a website.
Branded places (chains such as franchise outlets carry a "brand" tag) and closed places are dropped.

Rules we follow:
  - Overpass is a shared free service: at most OSM_MAX_QUERIES per run (default 16), a pause between
    queries, a clear User-Agent, and a second public server only when the first one is busy.
  - OpenStreetMap data is under the ODbL licence. Storing it is allowed; credit "© OpenStreetMap
    contributors" if a list is ever shown or sold to someone else (lead_gen samples).

Self-test (no network):  python -m scrapers.osm_leads
"""
import asyncio
import logging
import os
import random
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger("osm_leads")

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "IffyStudiosScout/1.0 (+https://github.com/iffy13/scouting)"
RADIUS_M = 20000

# Mid-size cities give more small, owner-run businesses than the biggest metros. (name, lat, lon)
CITIES: Dict[str, List[Tuple[str, float, float]]] = {
    "US": [("Austin", 30.267, -97.743), ("Tampa", 27.951, -82.457), ("Raleigh", 35.780, -78.639),
           ("Columbus", 39.961, -82.999), ("Charlotte", 35.227, -80.843), ("Nashville", 36.163, -86.781),
           ("Denver", 39.739, -104.990), ("Phoenix", 33.448, -112.074), ("San Antonio", 29.424, -98.494),
           ("Jacksonville", 30.332, -81.656), ("Indianapolis", 39.768, -86.158), ("Kansas City", 39.100, -94.578),
           ("Omaha", 41.257, -95.934), ("Tulsa", 36.154, -95.993), ("Boise", 43.615, -116.202),
           ("Sacramento", 38.582, -121.494), ("Salt Lake City", 40.761, -111.891), ("Richmond", 37.541, -77.436),
           ("Louisville", 38.253, -85.759), ("Portland", 45.515, -122.679), ("Seattle", 47.606, -122.332),
           ("Minneapolis", 44.978, -93.265), ("Pittsburgh", 40.441, -79.996), ("San Diego", 32.716, -117.161)],
    "CA": [("Calgary", 51.045, -114.072), ("Edmonton", 53.546, -113.494), ("Ottawa", 45.421, -75.697),
           ("Winnipeg", 49.895, -97.138), ("Hamilton", 43.256, -79.869), ("Kitchener", 43.452, -80.493),
           ("Halifax", 44.649, -63.575), ("Victoria", 48.428, -123.366), ("Vancouver", 49.283, -123.121),
           ("Toronto", 43.653, -79.383), ("Saskatoon", 52.157, -106.670), ("Kelowna", 49.888, -119.496)],
    "AU": [("Brisbane", -27.470, 153.026), ("Perth", -31.951, 115.861), ("Adelaide", -34.929, 138.601),
           ("Gold Coast", -28.017, 153.400), ("Newcastle", -32.927, 151.776), ("Canberra", -35.281, 149.129),
           ("Melbourne", -37.814, 144.963), ("Sydney", -33.869, 151.209), ("Hobart", -42.882, 147.327),
           ("Geelong", -38.149, 144.361), ("Sunshine Coast", -26.650, 153.067)],
    "NZ": [("Auckland", -36.848, 174.763), ("Wellington", -41.287, 174.776), ("Christchurch", -43.532, 172.636),
           ("Hamilton", -37.787, 175.279), ("Tauranga", -37.687, 176.165), ("Dunedin", -45.879, 170.503)],
    "AE": [("Dubai", 25.205, 55.271), ("Abu Dhabi", 24.454, 54.377), ("Sharjah", 25.346, 55.421),
           ("Ajman", 25.405, 55.514), ("Al Ain", 24.207, 55.745)],
    "SA": [("Riyadh", 24.713, 46.675), ("Jeddah", 21.485, 39.193), ("Dammam", 26.420, 50.089),
           ("Khobar", 26.217, 50.197)],
    "QA": [("Doha", 25.286, 51.531)],
    "KW": [("Kuwait City", 29.376, 47.977), ("Salmiya", 29.334, 48.071)],
    "BH": [("Manama", 26.228, 50.586)],
    "OM": [("Muscat", 23.588, 58.383), ("Sohar", 24.347, 56.709)],
    "SG": [("Singapore", 1.352, 103.820)],
    "MY": [("Kuala Lumpur", 3.139, 101.687), ("Petaling Jaya", 3.107, 101.607), ("Penang", 5.414, 100.329),
           ("Johor Bahru", 1.492, 103.741)],
    "HK": [("Hong Kong", 22.319, 114.169)],
    "PH": [("Manila", 14.600, 120.984), ("Cebu City", 10.316, 123.885), ("Makati", 14.555, 121.024)],
    "IN": [("Bengaluru", 12.972, 77.594), ("Mumbai", 19.076, 72.878), ("Pune", 18.520, 73.857),
           ("Hyderabad", 17.385, 78.487), ("Delhi", 28.614, 77.209)],
    "NG": [("Lagos", 6.524, 3.379), ("Abuja", 9.077, 7.399), ("Port Harcourt", 4.816, 7.050)],
    "GH": [("Accra", 5.604, -0.187), ("Kumasi", 6.688, -1.624)],
    "KE": [("Nairobi", -1.292, 36.822), ("Mombasa", -4.043, 39.668)],
    "UK": [("Manchester", 53.481, -2.242), ("Leeds", 53.801, -1.549), ("Bristol", 51.455, -2.588)],
    "IE": [("Dublin", 53.350, -6.260), ("Cork", 51.899, -8.476)],
}

# keyword words -> OpenStreetMap tags (key, value). The first matching rule wins, so specific rules come first.
# Every search also matches places whose NAME contains the keyword's main words.
TAG_RULES: List[Tuple[Tuple[str, ...], List[Tuple[str, str]]]] = [
    (("plumb",), [("craft", "plumber")]),
    (("hvac", "heating", "air condition"), [("craft", "hvac"), ("craft", "heating_engineer")]),
    (("electric",), [("craft", "electrician")]),
    (("roof",), [("craft", "roofer")]),
    (("solar",), [("craft", "solar_installer"), ("craft", "photovoltaic")]),
    (("window",), [("craft", "window_construction"), ("craft", "glaziery")]),
    (("garage door",), [("craft", "garage_door")]),
    (("pest",), [("craft", "pest_control"), ("shop", "pest_control")]),
    (("water damage", "restoration"), [("craft", "restoration")]),
    (("dent", "dental"), [("amenity", "dentist"), ("healthcare", "dentist")]),
    (("lawyer", "attorney", "law firm"), [("office", "lawyer")]),
    (("med spa", "aesthetic", "cosmetic surgery"), [("shop", "beauty"), ("healthcare", "clinic"), ("amenity", "clinic")]),
    (("physio",), [("healthcare", "physiotherapist")]),
    (("chiropract",), [("healthcare", "chiropractor"), ("healthcare", "alternative")]),
    (("clinic",), [("amenity", "clinic"), ("healthcare", "clinic")]),
    (("real estate agency",), [("office", "estate_agent"), ("shop", "estate_agent")]),
    (("developer",), [("office", "property_developer"), ("office", "construction_company")]),
    (("travel",), [("shop", "travel_agency"), ("office", "travel_agent")]),
    (("language school",), [("amenity", "language_school")]),
    (("private school",), [("amenity", "school")]),
    (("car dealer",), [("shop", "car")]),
    (("beauty", "salon"), [("shop", "beauty"), ("shop", "hairdresser")]),
    (("fitness", "gym"), [("leisure", "fitness_centre")]),
    (("furniture",), [("shop", "furniture")]),
    (("restaurant",), [("amenity", "restaurant")]),
    (("interior",), [("shop", "interior_decoration"), ("office", "interior_design"), ("craft", "interior_work")]),
    (("architect",), [("office", "architect")]),
    (("home builder", "design build", "renovation", "remodel", "fit out"),
     [("craft", "builder"), ("office", "construction_company"), ("craft", "carpenter"), ("shop", "kitchen")]),
    (("landscape", "outdoor living"), [("craft", "gardener"), ("office", "landscape_architect")]),
    (("pool",), [("shop", "swimming_pool"), ("craft", "builder")]),
    (("marketing", "seo", "web design", "branding", "social media"),
     [("office", "advertising_agency"), ("office", "marketing")]),
    (("coach", "consult", "sales training"), [("office", "consulting")]),
    (("it services", "it support"), [("office", "it"), ("craft", "computer")]),
    (("accounting", "bookkeeping"), [("office", "accountant"), ("office", "tax_advisor")]),
    (("cleaning",), [("craft", "cleaning"), ("office", "cleaning")]),
    (("staffing", "recruitment"), [("office", "employment_agency")]),
    (("insurance",), [("office", "insurance")]),
]
# Words that add nothing to a name match.
STOP_WORDS = {"company", "firm", "services", "service", "studio", "contractor", "agency", "store", "clinic",
              "repair", "emergency", "commercial", "residential", "custom", "luxury", "personal", "injury",
              "the", "and", "of", "in"}


def tags_for(keyword: str) -> List[Tuple[str, str]]:
    k = keyword.lower()
    for words, tags in TAG_RULES:
        if any(w in k for w in words):
            return tags
    return []


def name_pattern(keyword: str) -> Optional[str]:
    words = [w for w in re.findall(r"[a-z]+", keyword.lower()) if w not in STOP_WORDS and len(w) > 2]
    if not words:
        return None
    return " ".join(words)


def build_query(keyword: str, lat: float, lon: float, limit: int) -> str:
    near = f"(around:{RADIUS_M},{lat},{lon})"
    site = '[~"^(website|contact:website)$"~"."]'
    parts = [f'nwr["{k}"="{v}"]{site}{near};' for k, v in tags_for(keyword)]
    pat = name_pattern(keyword)
    if pat:
        parts.append(f'nwr["name"~"{pat}",i]{site}{near};')
    return f"[out:json][timeout:60];({''.join(parts)});out tags center {max(limit * 3, 30)};"


def _domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        host = urlparse(url if "://" in url else "https://" + url).netloc.lower().split(":")[0]
    except Exception:
        return None
    return (host[4:] if host.startswith("www.") else host) or None


def element_to_lead(el: Dict[str, Any], keyword: str, country: str, city: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Returns (lead, "") or (None, reason it was dropped)."""
    t = el.get("tags") or {}
    name = t.get("name") or t.get("name:en")
    if not name:
        return None, "no name"
    if t.get("brand") or t.get("brand:wikidata"):
        return None, "chain brand"
    if any(k.startswith(("disused:", "abandoned:", "was:")) for k in t) or t.get("opening_hours") == "closed":
        return None, "closed"
    website = t.get("website") or t.get("contact:website")
    if website and "://" not in website:
        website = "https://" + website
    domain = _domain(website)
    if not domain:
        return None, "no website"
    email = t.get("email") or t.get("contact:email")
    return {
        "name": name,
        "business_type": "local",
        "source": "osm",
        "keyword": keyword,
        "country": country,
        "city": t.get("addr:city") or city,
        "website": website,
        "domain": domain,
        "phone": t.get("phone") or t.get("contact:phone"),
        "direct_email": email,
        "place_id": f"osm:{el.get('type')}/{el.get('id')}",
        "rating": None,
        "reviews_count": 0,
        "is_closed": 0,
        "signals": {"has_website": True, "source_type": "osm", "has_hours": bool(t.get("opening_hours"))},
    }, ""


class OSMLeadScraper:
    def __init__(self, max_queries: Optional[int] = None, transport=None):
        self.max_queries = max_queries if max_queries is not None else int(os.getenv("OSM_MAX_QUERIES") or 16)
        self.queries = 0
        self._transport = transport  # tests pass a fake here

    @property
    def exhausted(self) -> bool:
        return self.queries >= self.max_queries

    async def _fetch(self, query: str) -> Dict[str, Any]:
        if self._transport:
            return await self._transport(query)
        import aiohttp
        last = ""
        for url in ENDPOINTS:
            try:
                async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as s:
                    async with s.post(url, data={"data": query}, timeout=aiohttp.ClientTimeout(total=75)) as r:
                        if r.status == 200:
                            return await r.json(content_type=None)
                        last = f"HTTP {r.status}"  # 429 or 504 means busy: try the other server
            except Exception as e:
                last = type(e).__name__
            await asyncio.sleep(3)
        raise RuntimeError(f"OpenStreetMap servers busy ({last})")

    async def search(self, keyword: str, country: str, city: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        ctry = country.upper()
        options = CITIES.get(ctry) or []
        if city and city != "General":
            options = [c for c in options if c[0].lower() == city.lower()] or options
        if not options or self.exhausted:
            return []
        cname, lat, lon = random.choice(options)
        self.queries += 1
        if self.queries > 1:
            await asyncio.sleep(2)  # be polite to the free servers
        try:
            data = await self._fetch(build_query(keyword, lat, lon, limit))
        except Exception as e:
            logger.warning(f"OpenStreetMap search failed for [{keyword}] in {cname}: {str(e)[:120]}")
            return []
        out, seen, dropped = [], set(), {}
        elements = data.get("elements") or []
        random.shuffle(elements)  # so repeat runs don't always take the same first ones
        for el in elements:
            lead, why = element_to_lead(el, keyword, ctry, cname)
            if not lead:
                dropped[why] = dropped.get(why, 0) + 1
                continue
            if lead["domain"] in seen:
                continue
            seen.add(lead["domain"])
            out.append(lead)
            if len(out) >= limit:
                break
        logger.info(f"OpenStreetMap: [{keyword}] near {cname} gave {len(out)} businesses"
                    + (f" (dropped: {', '.join(f'{v} {k}' for k, v in dropped.items())})" if dropped else ""))
        return out


# ---------------------------------------------------------------- self-test (no network)
def _self_test() -> int:
    problems = 0

    def check(ok: bool, what: str):
        nonlocal problems
        if not ok:
            problems += 1
            print("PROBLEM:", what)

    q = build_query("emergency plumber", 43.6, -116.2, 20)
    check('"craft"="plumber"' in q and '"name"~"plumber",i' in q and "around:20000" in q, f"plumber query: {q}")
    check(tags_for("interior design studio")[0] == ("shop", "interior_decoration"), "interior tags")
    check(tags_for("cosmetic dentist") and tags_for("cosmetic dentist")[0][1] == "dentist", "dentist wins over cosmetic")
    check(name_pattern("company services") is None, "stop words only")
    # every service keyword should get either tags or a name pattern
    from services import SERVICES
    for s in SERVICES.values():
        for k in s.keywords:
            check(bool(tags_for(k) or name_pattern(k)), f"keyword has no OSM search: {k}")
        for c in s.countries:
            if c not in CITIES and c not in ("UK", "IE"):
                print(f"note: no OSM cities for {s.id} {c}")

    sample = {"elements": [
        {"type": "node", "id": 1, "tags": {"name": "Acme Plumbing", "craft": "plumber", "website": "acmeplumbing.com",
                                           "phone": "+1 208 555 0100", "opening_hours": "Mo-Fr 08:00-17:00"}},
        {"type": "node", "id": 2, "tags": {"name": "Roto-Rooter", "craft": "plumber", "brand": "Roto-Rooter",
                                           "website": "https://rotorooter.com"}},
        {"type": "way", "id": 3, "tags": {"name": "Old Pipes", "disused:craft": "plumber", "website": "https://oldpipes.com"}},
        {"type": "node", "id": 4, "tags": {"name": "Acme Plumbing 2", "contact:website": "https://www.acmeplumbing.com/x"}},
        {"type": "node", "id": 5, "tags": {"craft": "plumber", "website": "https://noname.com"}},
    ]}
    calls = []

    async def fake(query):
        calls.append(query)
        return sample

    sc = OSMLeadScraper(max_queries=2, transport=fake)
    import scrapers.osm_leads as me
    real_sleep = me.asyncio.sleep

    async def no_sleep(_):
        return None
    me.asyncio.sleep = no_sleep
    try:
        leads = asyncio.run(sc.search("emergency plumber", "US", limit=20))
        check(len(leads) == 1, f"expected 1 lead, got {len(leads)}: {[l['name'] for l in leads]}")
        if leads:
            a = leads[0]
            # two places share acmeplumbing.com, the shuffle decides which one is kept
            check(a["domain"] == "acmeplumbing.com" and a["website"].startswith("https://"), "website/domain")
            check(a["place_id"] in ("osm:node/1", "osm:node/4") and a["source"] == "osm", "ids")
        asyncio.run(sc.search("hvac repair", "AE"))
        check(asyncio.run(sc.search("x", "US")) == [] and len(calls) == 2, "query limit must stop the third call")
        check(asyncio.run(OSMLeadScraper(transport=fake).search("x", "ZZ")) == [], "unknown country gives nothing")
    finally:
        me.asyncio.sleep = real_sleep
    print(f"{problems} problems")
    return problems


if __name__ == "__main__":
    raise SystemExit(1 if _self_test() else 0)
