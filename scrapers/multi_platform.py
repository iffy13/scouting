import aiohttp
import asyncio
import re
import urllib.parse
from bs4 import BeautifulSoup
import logging
from typing import List, Dict, Any, Optional
from scrapers.base import BaseScraper
from offers.cleaner import is_valid_prospect_domain, clean_business_name

logger = logging.getLogger(__name__)

# Dedicated directory & platform dork templates for the 21 approved platforms
PLATFORM_DORKS = {
    "google_maps": 'site:google.com/maps "{keyword}" "{location}"',
    "osm": '"{keyword}" "{location}" address website phone',
    "yelp": 'site:yelp.com/biz/ "{keyword}" "{location}"',
    "yellowpages": 'site:yellowpages.com "{keyword}" "{location}"',
    "yell_uk": 'site:yell.com/biz/ "{keyword}" "{location}"',
    "truelocal_au": 'site:truelocal.com.au/business/ "{keyword}" "{location}"',
    "bbb": 'site:bbb.org/us/ "{keyword}" "{location}"',
    "trustpilot": 'site:trustpilot.com/review/ "{keyword}"',
    "checkatrade": 'site:checkatrade.com/trades/ "{keyword}" "{location}"',
    "bark": 'site:bark.com/en/company/ "{keyword}"',
    "houzz": 'site:houzz.com/professionals/ "{keyword}" "{location}"',
    "foursquare": 'site:foursquare.com/v/ "{keyword}" "{location}"',
    "clutch": 'site:clutch.co/profile/ "{keyword}"',
    "goodfirms": 'site:goodfirms.co/company/ "{keyword}"',
    "upcity": 'site:upcity.com/profiles/ "{keyword}"',
    "designrush": 'site:designrush.com/agency/profile/ "{keyword}"',
    "crunchbase": 'site:crunchbase.com/organization/ "{keyword}"',
    "producthunt": 'site:producthunt.com/posts/ "{keyword}"',
    "betalist": 'site:betalist.com/startups/ "{keyword}"',
    "builtwith": 'site:builtwith.com/ "{keyword}"',
    "storeleads": 'site:storeleads.app/stores/ "{keyword}"'
}

# Directory and aggregator domains that should never be treated as direct business leads
DIRECTORY_DOMAINS = {
    "google.com", "osm.org", "openstreetmap.org", "yelp.com", "yellowpages.com",
    "yell.com", "truelocal.com.au", "bbb.org", "trustpilot.com", "checkatrade.com",
    "bark.com", "houzz.com", "foursquare.com", "clutch.co", "goodfirms.co",
    "upcity.com", "designrush.com", "crunchbase.com", "producthunt.com",
    "betalist.com", "builtwith.com", "storeleads.app", "g2.com", "capterra.com",
    "angi.com", "thumbtack.com", "manta.com", "expertise.com", "tripadvisor.com"
}

class MultiPlatformScraper(BaseScraper):
    """
    Unified Multi-Platform Scraper covering all 21 approved platforms:
    - Google Maps, OSM, Yelp, YellowPages/Yell/TrueLocal, BBB, Trustpilot, Checkatrade/Bark/Houzz, Foursquare
    - Clutch, GoodFirms, UpCity/DesignRush, Crunchbase, Product Hunt, BetaList
    - BuiltWith/Wappalyzer, Store Leads
    """

    def __init__(self):
        super().__init__(source_name="multi_platform", business_type="multi")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def search_platform(self, platform_key: str, keyword: str, country: str = "US", city: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Searches a specific platform using targeted footprint dorks."""
        dork_template = PLATFORM_DORKS.get(platform_key)
        if not dork_template:
            return []

        location = city or country
        query = dork_template.format(keyword=keyword, location=location)
        results = []
        seen_domains = set()

        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.post("https://html.duckduckgo.com/html/", data={"q": query}, timeout=6) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, "lxml")

                        for res in soup.select(".result"):
                            link_el = res.select_one(".result__title a.result__a")
                            if not link_el:
                                continue

                            raw_href = link_el.get("href", "")
                            raw_title = link_el.get_text(strip=True)

                            match = re.search(r"uddg=([^&]+)", raw_href)
                            actual_url = urllib.parse.unquote(match.group(1)) if match else raw_href

                            domain = self.extract_domain(actual_url)
                            if not domain or domain in seen_domains:
                                continue

                            # Skip results pointing to directory/platform aggregators instead of the actual business
                            if any(domain == d or domain.endswith("." + d) for d in DIRECTORY_DOMAINS):
                                continue
                            if not is_valid_prospect_domain(domain, actual_url):
                                continue

                            # If the result is the platform page itself, extract the business name
                            clean_name = raw_title.split("-")[0].split("|")[0].split(":")[0].strip()
                            clean_name = clean_business_name(clean_name, domain)

                            seen_domains.add(domain)

                            results.append({
                                "name": clean_name,
                                "business_type": "digital" if platform_key in ["clutch", "goodfirms", "producthunt", "betalist", "crunchbase"] else "local",
                                "source": platform_key,
                                "keyword": keyword,
                                "country": country,
                                "city": location,
                                "website": actual_url,
                                "domain": domain,
                                "phone": None,
                                "rating": None,
                                "reviews_count": 0,
                                "is_closed": 0,
                                "signals": {"platform_source": platform_key, "dork_matched": True}
                            })

                            if len(results) >= limit:
                                break
        except Exception as e:
            logger.debug(f"Multi-platform search error for {platform_key}: {e}")

        return results

    async def search_all_approved_platforms(self, keyword: str, country: str = "US", city: Optional[str] = None, per_platform_limit: int = 3) -> List[Dict[str, Any]]:
        """Sweeps across the approved platforms relevant to the niche."""
        tasks = []
        # Group platforms based on keyword intent
        is_digital_or_agency = any(k in keyword.lower() for k in ["agency", "saas", "software", "tech", "video", "marketing", "media", "seo"])
        
        if is_digital_or_agency:
            platforms_to_sweep = ["clutch", "goodfirms", "upcity", "designrush", "producthunt", "betalist", "crunchbase", "trustpilot"]
        else:
            platforms_to_sweep = ["yelp", "yellowpages", "bbb", "checkatrade", "trustpilot", "houzz", "foursquare"]

        for platform in platforms_to_sweep:
            tasks.append(self.search_platform(platform, keyword, country, city, limit=per_platform_limit))

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        aggregated = []
        for res in results_lists:
            if isinstance(res, list):
                aggregated.extend(res)
        return aggregated

    async def search(self, keyword: str, country: str = "US", city: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Standard search implementation implementing BaseScraper contract."""
        per_plat = max(1, limit // 4)
        results = await self.search_all_approved_platforms(keyword=keyword, country=country, city=city, per_platform_limit=per_plat)
        return results[:limit]
