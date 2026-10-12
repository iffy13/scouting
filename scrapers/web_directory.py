import aiohttp
import asyncio
import re
import urllib.parse
from bs4 import BeautifulSoup
import logging
from typing import List, Dict, Any, Optional
from scrapers.base import BaseScraper
from config import DEFAULT_HEADERS

logger = logging.getLogger(__name__)

class WebDirectoryScraper(BaseScraper):
    """
    Scrapes verified local service businesses from YellowPages and commercial registries.
    """

    def __init__(self):
        super().__init__(source_name="yellowpages", business_type="local")

    async def search(self, keyword: str, country: str = "US", city: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        target_city = city or "Austin, TX"
        results = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Query YellowPages directly
        kw_enc = urllib.parse.quote_plus(keyword)
        loc_enc = urllib.parse.quote_plus(target_city)
        yp_url = f"https://www.yellowpages.com/search?search_terms={kw_enc}&geo_location_terms={loc_enc}"

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(yp_url, timeout=15) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, "lxml")
                        
                        # Find organic results
                        for res in soup.select(".result, .organic, .info"):
                            name_el = res.select_one(".business-name")
                            if not name_el:
                                continue
                            name = name_el.get_text(strip=True)
                            
                            phone_el = res.select_one(".phone")
                            phone = phone_el.get_text(strip=True) if phone_el else None
                            
                            website_el = res.select_one("a.track-visit-website")
                            website = website_el["href"] if website_el and "href" in website_el.attrs else None
                            
                            domain = self.extract_domain(website)
                            if not website or not domain:
                                continue

                            results.append({
                                "name": name,
                                "business_type": "local",
                                "source": "yellowpages",
                                "keyword": keyword,
                                "country": country,
                                "city": target_city,
                                "website": website,
                                "domain": domain,
                                "phone": phone,
                                "rating": None,
                                "reviews_count": 0,
                                "is_closed": 0,
                                "signals": {"has_website": True, "source_type": "directory"}
                            })

                            if len(results) >= limit:
                                return results
        except Exception as e:
            logger.debug(f"Yellowpages query error: {e}")

        return results[:limit]
