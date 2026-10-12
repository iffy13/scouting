import asyncio
import aiohttp
import logging
from typing import List, Dict, Any, Optional
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Top business hub cities per country for lightning-fast, high-density queries
TOP_CITIES = {
    "US": ["New York", "Los Angeles", "Chicago", "Houston", "Dallas", "Austin", "Miami", "Atlanta", "Phoenix", "Seattle", "Denver"],
    "UK": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Liverpool", "Bristol", "Edinburgh"],
    "CA": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa", "Edmonton"],
    "AU": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
    "NZ": ["Auckland", "Wellington", "Christchurch"],
    "IE": ["Dublin", "Cork", "Galway"],
    "DE": ["Berlin", "Munich", "Frankfurt", "Hamburg", "Cologne"],
    "NL": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht"],
    "FR": ["Paris", "Lyon", "Marseille", "Toulouse", "Nice"],
    "ES": ["Madrid", "Barcelona", "Valencia", "Seville"],
    "IT": ["Rome", "Milan", "Naples", "Turin"],
    "SG": ["Singapore"],
    "AE": ["Dubai", "Abu Dhabi"],
}

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

class OSMScraper(BaseScraper):
    """Free global lead discovery using OpenStreetMap Overpass API with city routing."""

    def __init__(self):
        super().__init__(source_name="osm", business_type="local")

    async def search(self, keyword: str, country: str = "US", city: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        country_code = country.upper()
        target_cities = [city] if city else TOP_CITIES.get(country_code, [country_code])
        
        results = []
        headers = {"User-Agent": "OutreachScout/2.0 (contact: akdamdigitals@gmail.com)"}

        for target_city in target_cities[:3]: # Scan top 3 cities for fast responses
            ql_query = f"""
            [out:json][timeout:15];
            area["name"="{target_city}"]["boundary"="administrative"]->.a;
            (
              node["craft"~"{keyword}",i](area.a);
              node["name"~"{keyword}",i](area.a);
              way["name"~"{keyword}",i](area.a);
              node["shop"~"{keyword}",i](area.a);
            );
            out center {limit};
            """

            for endpoint in OVERPASS_ENDPOINTS:
                try:
                    async with aiohttp.ClientSession(headers=headers) as session:
                        async with session.post(endpoint, data={"data": ql_query}, timeout=15) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                elements = data.get("elements", [])
                                for el in elements:
                                    tags = el.get("tags", {})
                                    name = tags.get("name")
                                    if not name:
                                        continue

                                    website = tags.get("website") or tags.get("contact:website") or tags.get("url")
                                    phone = tags.get("phone") or tags.get("contact:phone")
                                    email = tags.get("email") or tags.get("contact:email")
                                    resolved_city = target_city or tags.get("addr:city")

                                    results.append({
                                        "name": name,
                                        "business_type": "local",
                                        "source": self.source_name,
                                        "keyword": keyword,
                                        "country": country,
                                        "city": resolved_city,
                                        "website": website,
                                        "domain": self.extract_domain(website),
                                        "phone": phone,
                                        "direct_email": email,
                                        "rating": None,
                                        "reviews_count": 0,
                                        "is_closed": 0,
                                        "signals": {
                                            "has_website": bool(website),
                                            "osm_tags": tags,
                                            "source_type": "osm"
                                        }
                                    })
                                if len(results) >= limit:
                                    return results[:limit]
                except Exception as e:
                    logger.debug(f"Overpass endpoint error on {target_city}: {e}")
                    continue

        return results[:limit]
