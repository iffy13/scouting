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


class SerperUnavailable(Exception):
    """Raised when Serper refuses the key: credits used up, key wrong, or rate limited."""


class SerperScraper(BaseScraper):
    def __init__(self, api_key: str = ""):
        super().__init__(source_name="serper", business_type="local")
        self.api_key = api_key or os.getenv("SERPER_API_KEY", "")
        self.queries = 0

    async def search(self, keyword: str, country: str = "US", city: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        country_name = COUNTRY_NAMES.get(country.upper(), country)
        gl = "gb" if country.upper() == "UK" else country.lower()
        q = f"{keyword} in {country_name}"
        if city:
            q = f"{q} {city}"
        payload = {"q": q, "gl": gl, "num": 20, "page": random.choice([1, 1, 2, 3])}
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        self.queries += 1
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(SERPER_URL, json=payload, headers=headers,
                                  timeout=aiohttp.ClientTimeout(total=20)) as r:
                    if r.status in (400, 401, 402, 403, 429):
                        body = (await r.text())[:120]
                        raise SerperUnavailable(f"Serper answered HTTP {r.status}: {body}")
                    if r.status != 200:
                        logger.warning(f"Serper HTTP {r.status} for [{keyword}] in [{country}]")
                        return []
                    data = await r.json()
        except SerperUnavailable:
            raise
        except Exception as e:
            logger.warning(f"Serper request failed: {type(e).__name__}")
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
