import aiohttp
from bs4 import BeautifulSoup
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from scrapers.base import BaseScraper
from config import DEFAULT_HEADERS

logger = logging.getLogger(__name__)

class TrustpilotScraper(BaseScraper):
    """Scraper for digital businesses, SaaS, ecommerce, and online services via Trustpilot."""

    def __init__(self):
        super().__init__(source_name="trustpilot", business_type="digital")

    async def search(self, keyword: str, country: str = "US", city: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        results = []
        encoded_query = quote_plus(keyword)
        url = f"https://www.trustpilot.com/search?query={encoded_query}"

        try:
            async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
                async with session.get(url, timeout=20) as response:
                    if response.status != 200:
                        logger.warning(f"Trustpilot returned status {response.status}")
                        return results

                    html = await response.text()
                    soup = BeautifulSoup(html, "lxml")

                    # Find business cards
                    cards = soup.select('div[class*="styles_businessUnitCard"], div[class*="paper_paper"]')
                    for card in cards[:limit]:
                        name_el = card.select_one('p[class*="styles_displayName"], a[class*="link_internal"]')
                        if not name_el:
                            continue

                        name = name_el.get_text(strip=True)
                        link_el = card.select_one('a[href*="/review/"]')
                        domain = None
                        website = None
                        if link_el and "href" in link_el.attrs:
                            href = link_el["href"]
                            if "/review/" in href:
                                domain = href.split("/review/")[-1].split("?")[0].strip()
                                website = f"https://{domain}"

                        # Rating & reviews
                        rating_el = card.select_one('span[class*="styles_trustScore"], span[class*="typography_body-m"]')
                        reviews_el = card.select_one('span[class*="styles_ratingText"], span[class*="typography_body-s"]')

                        rating = None
                        reviews_count = 0
                        if rating_el:
                            try:
                                rating_text = rating_el.get_text(strip=True).split("/")[0]
                                rating = float(rating_text)
                            except ValueError:
                                pass

                        if reviews_el:
                            try:
                                reviews_text = "".join(filter(str.isdigit, reviews_el.get_text(strip=True)))
                                if reviews_text:
                                    reviews_count = int(reviews_text)
                            except ValueError:
                                pass

                        results.append({
                            "name": name,
                            "business_type": "digital",
                            "source": self.source_name,
                            "keyword": keyword,
                            "country": country,
                            "city": city,
                            "website": website,
                            "domain": domain or self.extract_domain(website),
                            "phone": None,
                            "rating": rating,
                            "reviews_count": reviews_count,
                            "is_closed": 0,
                            "signals": {
                                "has_website": bool(website),
                                "trustpilot_reviews": reviews_count,
                                "trustpilot_score": rating,
                                "source_type": "trustpilot"
                            }
                        })
        except Exception as e:
            logger.error(f"Error scraping Trustpilot for {keyword}: {e}")

        return results
