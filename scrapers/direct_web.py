import aiohttp
import asyncio
import re
import urllib.parse
from bs4 import BeautifulSoup
import logging
from typing import List, Dict, Any, Optional
from scrapers.base import BaseScraper
from config import DEFAULT_HEADERS
from offers.cleaner import is_valid_prospect_domain, clean_business_name

logger = logging.getLogger(__name__)

# Full country names for broad country-level scouting
COUNTRY_NAMES = {
    "US": "United States", "UK": "United Kingdom", "CA": "Canada", "AU": "Australia",
    "NZ": "New Zealand", "IE": "Ireland", "NO": "Norway", "SE": "Sweden",
    "DK": "Denmark", "FI": "Finland", "IS": "Iceland", "CH": "Switzerland",
    "DE": "Germany", "NL": "Netherlands", "AT": "Austria", "BE": "Belgium",
    "LU": "Luxembourg", "FR": "France", "MC": "Monaco", "LI": "Liechtenstein",
    "ES": "Spain", "IT": "Italy", "PT": "Portugal", "GR": "Greece",
    "CY": "Cyprus", "MT": "Malta", "EE": "Estonia", "PL": "Poland",
    "CZ": "Czech Republic", "LT": "Lithuania", "LV": "Latvia", "SK": "Slovakia",
    "SI": "Slovenia", "HU": "Hungary", "HR": "Croatia", "RO": "Romania",
    "AE": "United Arab Emirates", "SA": "Saudi Arabia", "QA": "Qatar",
    "KW": "Kuwait", "BH": "Bahrain", "OM": "Oman", "SG": "Singapore",
    "HK": "Hong Kong", "JP": "Japan", "KR": "South Korea", "TW": "Taiwan",
    "MY": "Malaysia", "TH": "Thailand"
}

# Commercial cities mapping for targeted city-level scouting
COUNTRY_CITIES = {
    # Tier 1: Core English Hubs
    "US": [
        "Austin", "Houston", "Dallas", "San Antonio", "Fort Worth",
        "Phoenix", "Atlanta", "Miami", "Tampa", "Orlando",
        "Denver", "Charlotte", "Nashville", "Las Vegas", "Seattle",
        "San Diego", "Los Angeles", "Chicago", "Indianapolis", "Columbus",
        "Jacksonville", "Raleigh", "Salt Lake City", "Kansas City", "Portland"
    ],
    "UK": [
        "London", "Manchester", "Birmingham", "Leeds", "Glasgow",
        "Liverpool", "Bristol", "Edinburgh", "Sheffield", "Newcastle"
    ],
    "CA": [
        "Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa",
        "Edmonton", "Winnipeg", "Mississauga", "Quebec City", "Hamilton"
    ],
    "AU": [
        "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Gold Coast"
    ],
    "NZ": ["Auckland", "Wellington", "Christchurch", "Hamilton"],
    "IE": ["Dublin", "Cork", "Galway", "Limerick"],

    # Tier 2: Nordic High-Income Hubs
    "NO": ["Oslo", "Bergen", "Trondheim", "Stavanger"],
    "SE": ["Stockholm", "Gothenburg", "Malmo", "Uppsala"],
    "DK": ["Copenhagen", "Aarhus", "Odense", "Aalborg"],
    "FI": ["Helsinki", "Espoo", "Tampere", "Vantaa", "Oulu"],
    "IS": ["Reykjavik", "Kopavogur", "Hafnarfjordur"],

    # Tier 3: Western & Central Europe
    "CH": ["Zurich", "Geneva", "Basel", "Lausanne", "Bern"],
    "DE": ["Berlin", "Munich", "Frankfurt", "Hamburg", "Cologne", "Stuttgart", "Dusseldorf"],
    "NL": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven"],
    "AT": ["Vienna", "Salzburg", "Graz", "Innsbruck", "Linz"],
    "BE": ["Brussels", "Antwerp", "Ghent", "Bruges", "Liege"],
    "LU": ["Luxembourg City", "Esch-sur-Alzette", "Differdange"],
    "FR": ["Paris", "Lyon", "Marseille", "Toulouse", "Nice", "Bordeaux", "Strasbourg"],
    "MC": ["Monaco", "Monte Carlo"],
    "LI": ["Vaduz", "Schaan"],

    # Tier 4: Southern & Mediterranean Europe
    "ES": ["Madrid", "Barcelona", "Valencia", "Seville", "Malaga", "Bilbao"],
    "IT": ["Rome", "Milan", "Naples", "Turin", "Florence", "Bologna"],
    "PT": ["Lisbon", "Porto", "Braga", "Coimbra"],
    "GR": ["Athens", "Thessaloniki", "Patras"],
    "CY": ["Nicosia", "Limassol", "Larnaca", "Paphos"],
    "MT": ["Valletta", "Birkirkara", "Sliema", "St Julians"],

    # Tier 5: Central & Baltic Tech Hubs
    "EE": ["Tallinn", "Tartu", "Narva", "Parnu"],
    "PL": ["Warsaw", "Krakow", "Wroclaw", "Gdansk", "Poznan"],
    "CZ": ["Prague", "Brno", "Ostrava", "Plzen"],
    "LT": ["Vilnius", "Kaunas", "Klaipeda"],
    "LV": ["Riga", "Daugavpils", "Liepaja"],
    "SK": ["Bratislava", "Kosice", "Presov"],
    "SI": ["Ljubljana", "Maribor", "Kranj"],
    "HU": ["Budapest", "Debrecen", "Szeged"],
    "HR": ["Zagreb", "Split", "Rijeka"],
    "RO": ["Bucharest", "Cluj-Napoca", "Timisoara", "Iasi"],

    # Tier 6: Gulf GCC Wealth Hubs
    "AE": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman"],
    "SA": ["Riyadh", "Jeddah", "Dammam", "Khobar", "Mecca"],
    "QA": ["Doha", "Al Rayyan", "Al Wakrah"],
    "KW": ["Kuwait City", "Salmiya", "Hawalli"],
    "BH": ["Manama", "Riffa", "Muharraq"],
    "OM": ["Muscat", "Salalah", "Sohar"],

    # Tier 7: Asia-Pacific High-Income Tech Hubs
    "SG": ["Singapore"],
    "HK": ["Hong Kong", "Kowloon", "Central"],
    "JP": ["Tokyo", "Osaka", "Yokohama", "Nagoya", "Kyoto", "Fukuoka"],
    "KR": ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon"],
    "TW": ["Taipei", "Kaohsiung", "Taichung", "Tainan", "Hsinchu"],
    "MY": ["Kuala Lumpur", "George Town", "Johor Bahru", "Petaling Jaya", "Shah Alam"],
    "TH": ["Bangkok", "Chiang Mai", "Phuket", "Pattaya"]
}

class DirectWebScraper(BaseScraper):
    """Dual-mode business hunter: runs both broad nationwide queries and localized city searches."""

    def __init__(self):
        super().__init__(source_name="web_search", business_type="local")

    def get_country_full_name(self, country: str) -> str:
        return COUNTRY_NAMES.get(country.upper(), country)

    def get_cities_for_country(self, country: str) -> List[str]:
        return COUNTRY_CITIES.get(country.upper(), [])

    async def search(self, keyword: str, country: str = "US", city: Optional[str] = None, limit: int = 15) -> List[Dict[str, Any]]:
        country_name = self.get_country_full_name(country)
        
        # Build search queries: General Country-Level or Specific City-Level
        if not city or city == "General" or city == country:
            queries = [
                f"{keyword} in {country_name} official site",
                f"best {keyword} company in {country_name}",
                f"top {keyword} services {country_name}"
            ]
            display_location = country_name
        else:
            queries = [
                f"{keyword} {city} {country_name} official site",
                f"best {keyword} in {city} {country}",
                f"{keyword} company in {city}"
            ]
            display_location = city

        results = []
        seen_domains = set()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            for query in queries:
                if len(results) >= limit:
                    break

                try:
                    async with session.post("https://html.duckduckgo.com/html/", data={"q": query}, timeout=6) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            soup = BeautifulSoup(html, "lxml")
                            
                            for res in soup.select(".result"):
                                link_el = res.select_one(".result__title a.result__a")
                                if not link_el:
                                    continue
                                
                                raw_href = link_el.get("href", "")
                                name = link_el.get_text(strip=True).split("-")[0].split("|")[0].strip()
                                
                                match = re.search(r"uddg=([^&]+)", raw_href)
                                actual_url = urllib.parse.unquote(match.group(1)) if match else raw_href

                                domain = self.extract_domain(actual_url)
                                if not domain or domain in seen_domains:
                                    continue
                                if not is_valid_prospect_domain(domain, actual_url):
                                    continue

                                seen_domains.add(domain)
                                clean_name = clean_business_name(name, domain)

                                results.append({
                                    "name": clean_name,
                                    "business_type": "local",
                                    "source": "web_search",
                                    "keyword": keyword,
                                    "country": country,
                                    "city": display_location,
                                    "website": actual_url,
                                    "domain": domain,
                                    "phone": None,
                                    "rating": None,
                                    "reviews_count": 0,
                                    "is_closed": 0,
                                    "signals": {"has_website": True, "source_type": "web"}
                                })

                                if len(results) >= limit:
                                    break
                except Exception as e:
                    logger.debug(f"Search query error: {e}")
                    continue

        return results[:limit]
