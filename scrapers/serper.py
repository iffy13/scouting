"""
Google results through the Serper.dev API (needs SERPER_API_KEY). Works from cloud servers such as
GitHub Actions, where DuckDuckGo blocks the plain web search. Each query costs one Serper credit.
"""
import logging
import os
import random
from typing import Any, Dict, List, Optional

import aiohttp

from scrapers.base import BaseScraper
from scrapers.direct_web import COUNTRY_NAMES
from offers.cleaner import clean_business_name, is_valid_prospect_domain

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"
# Google Maps results through Serper: the same businesses as the Google Maps app, without a Google Cloud account
# or a card. Uses the same SERPER_API_KEY and credits as the web search.
SERPER_MAPS_URL = "https://google.serper.dev/maps"


class SerperUnavailable(Exception):
    """Raised when Serper refuses the key: credits used up, key wrong, or rate limited."""


class SerperScraper(BaseScraper):
    def __init__(self, api_key: str = ""):
        super().__init__(source_name="serper", business_type="local")
        self.api_key = api_key or os.getenv("SERPER_API_KEY", "")
        self.queries = 0

    async def _post(self, url: str, payload: Dict[str, Any], what: str) -> Dict[str, Any]:
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        self.queries += 1
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as r:
                    if r.status in (400, 401, 402, 403, 429):
                        body = (await r.text())[:120]
                        raise SerperUnavailable(f"Serper answered HTTP {r.status}: {body}")
                    if r.status != 200:
                        logger.warning(f"Serper HTTP {r.status} for {what}")
                        return {}
                    return await r.json()
        except SerperUnavailable:
            raise
        except Exception as e:
            logger.warning(f"Serper request failed: {type(e).__name__}")
            return {}

    async def search_maps(self, keyword: str, country: str = "US", city: Optional[str] = None,
                          limit: int = 20) -> List[Dict[str, Any]]:
        """Businesses from Google Maps for one keyword in one city (a random mid-size city of the country when
        city is not given). Same lead shape as scrapers/google_places.py, source "google_maps"."""
        import localize
        from scrapers.google_places import CITIES
        ctry = country.upper()
        city = city if city and city != "General" else random.choice(CITIES.get(ctry) or [""])
        local_kw = localize.search_keyword(keyword, ctry)
        connector = localize.CONNECTOR.get(localize.language_for(ctry), "in")
        country_name = COUNTRY_NAMES.get(ctry, country)
        q = f"{local_kw} {connector} {city}" if city else f"{local_kw} {connector} {country_name}"
        payload: Dict[str, Any] = {"q": q, "gl": "gb" if ctry == "UK" else ctry.lower()}
        lang = localize.language_for(ctry)
        if lang in ("es", "pt", "ar"):
            payload["hl"] = {"es": "es", "pt": "pt-br", "ar": "ar"}[lang]
        data = await self._post(SERPER_MAPS_URL, payload, f"maps [{q}]")
        out, seen = [], set()
        for p in data.get("places") or []:
            lead = maps_place_to_lead(p, keyword, ctry, city or country_name)
            if not lead or lead["domain"] in seen or not is_valid_prospect_domain(lead["domain"], lead["website"]):
                continue
            seen.add(lead["domain"])
            out.append(lead)
            if len(out) >= limit:
                break
        logger.info(f"Google Maps (Serper): [{q}] gave {len(out)} businesses with a website")
        return out

    async def search(self, keyword: str, country: str = "US", city: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        country_name = COUNTRY_NAMES.get(country.upper(), country)
        gl = "gb" if country.upper() == "UK" else country.lower()
        import localize
        q = localize.search_query(keyword, country, country_name)  # "clínica dental en México" for MX
        if city:
            q = f"{q} {city}"
        payload = {"q": q, "gl": gl, "num": 20, "page": random.choice([1, 1, 2, 3])}
        lang = localize.language_for(country)
        if lang in ("es", "pt"):
            payload["hl"] = "pt-br" if lang == "pt" else "es"
        data = await self._post(SERPER_URL, payload, f"[{keyword}] in [{country}]")
        if not data:
            return []

        results, seen = [], set()
        for item in (data.get("places") or []) + (data.get("organic") or []):
            url = item.get("website") or item.get("link")
            domain = self.extract_domain(url)
            if not domain or domain in seen or not is_valid_prospect_domain(domain, url):
                continue
            seen.add(domain)
            name = (item.get("title") or domain).split(" - ")[0].split("|")[0].strip()
            results.append({
                "name": clean_business_name(name, domain),
                "business_type": "local",
                "source": "serper",
                "keyword": keyword,
                "country": country,
                "city": item.get("address") or city or country_name,
                "website": url,
                "domain": domain,
                "phone": item.get("phoneNumber"),
                "rating": item.get("rating"),
                "reviews_count": item.get("ratingCount") or 0,
                "is_closed": 0,
                "signals": {"has_website": True, "source_type": "serper"},
            })
            if len(results) >= limit:
                break
        return results


def maps_place_to_lead(p: Dict[str, Any], keyword: str, country: str, city: str) -> Optional[Dict[str, Any]]:
    """One Serper Maps place -> lead. Only the business's own website is kept for contact details; the Maps phone,
    rating and reviews are used for scoring (lead["maps"]), not stored as contact data."""
    from scrapers.google_places import _domain
    name = (p.get("title") or "").strip()
    website = p.get("website")
    domain = _domain(website)
    if not name or not domain:
        return None
    hours = p.get("openingHours") or {}
    reviews = int(p.get("ratingCount") or 0)
    hour_text = " ".join(str(v) for v in hours.values()).lower() if isinstance(hours, dict) else ""
    return {
        "name": clean_business_name(name, domain),
        "website": website if "://" in website else "https://" + website,
        "domain": domain,
        "phone": None,
        "city": city,
        "country": country,
        "keyword": keyword,
        "source": "google_maps",
        "place_id": p.get("placeId") or (f"cid:{p['cid']}" if p.get("cid") else None),
        "rating": p.get("rating"),
        "reviews_count": reviews,
        "maps": {
            "phone": p.get("phoneNumber"),
            "rating": p.get("rating"),
            "reviews": reviews,
            "photos": None,  # Serper does not say how many photos a place has
            "status": "OPERATIONAL",
            "primary_type": p.get("type"),
            "types": p.get("types") or [],
            "has_hours": bool(hours),
            "open_24h": "24 hours" in hour_text or "open 24" in hour_text,
        },
    }
