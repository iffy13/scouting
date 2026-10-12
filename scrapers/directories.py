import aiohttp
from bs4 import BeautifulSoup
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from scrapers.base import BaseScraper
from config import DEFAULT_HEADERS

logger = logging.getLogger(__name__)

class DirectoryScraper(BaseScraper):
    """Scrapes country directories (YellowPages, Brownbook, etc.) for local businesses."""

    def __init__(self):
        super().__init__(source_name="directories", business_type="local")

    async def search(self, keyword: str, country: str = "US", city: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        results = []
        loc = city or "Austin"
        encoded_kw = quote_plus(keyword)
        encoded_loc = quote_plus(loc)

        url = f"https://www.yellowpages.com/search?search_terms={encoded_kw}&geo_location_terms={encoded_loc}"
        
        try:
            async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, "lxml")
                        cards = soup.select(".result, .info")
                        for card in cards[:limit]:
                            name_el = card.select_one(".business-name")
                            if not name_el:
                                continue
                            name = name_el.get_text(strip=True)

                            phone_el = card.select_one(".phone")
                            phone = phone_el.get_text(strip=True) if phone_el else None

                            website_el = card.select_one("a.track-visit-website")
                            website = website_el["href"] if website_el and "href" in website_el.attrs else None

                            domain = self.extract_domain(website)

                            results.append({
                                "name": name,
                                "business_type": "local",
                                "source": "yellowpages",
                                "keyword": keyword,
                                "country": country,
                                "city": loc,
                                "website": website,
                                "domain": domain,
                                "phone": phone,
                                "rating": None,
                                "reviews_count": 0,
                                "is_closed": 0,
                                "signals": {
                                    "has_website": bool(website),
                                    "source_type": "directory"
                                }
                            })
        except Exception as e:
            logger.debug(f"Yellowpages scrape error: {e}")

        return results
