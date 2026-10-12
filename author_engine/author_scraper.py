import re
import asyncio
import aiohttp
import base64
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import logging
from urllib.parse import urljoin, urlparse, unquote, quote_plus
from config import DEFAULT_HEADERS
from offers.cleaner import is_valid_prospect_domain

logger = logging.getLogger(__name__)

AUTHOR_GENRES = {
    "thriller": [
        "psychological thriller author", "domestic thriller novel author", "crime mystery writer",
        "suspense fiction author", "detective thriller author"
    ],
    "fantasy": [
        "epic fantasy author", "dark fantasy writer", "urban fantasy author",
        "indie fantasy author", "high fantasy author"
    ],
    "romance": [
        "dark romance author", "contemporary romance writer", "romantic comedy author",
        "indie romance novelist", "mafia romance writer"
    ],
    "scifi": [
        "space opera author", "cyberpunk writer", "dystopian sci fi author",
        "hard science fiction writer", "indie scifi author"
    ],
    "horror": [
        "psychological horror author", "supernatural horror writer", "gothic horror author",
        "haunted house thriller writer", "indie horror novelist"
    ],
    "nonfiction": [
        "business book author", "self help author", "memoir writer",
        "personal finance author", "leadership author"
    ],
    "ya_fiction": [
        "young adult fantasy author", "ya fiction writer", "teen thriller author",
        "ya romance novelist"
    ]
}

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

IGNORE_EMAILS = {
    "support@amazon.com", "press@amazon.com", "privacy@goodreads.com", "support@goodreads.com",
    "help@goodreads.com", "contact@wix.com", "example@domain.com", "sentry@io.com",
    "info@kickstarter.com", "press@kickstarter.com", "support@reedsy.com", "privacy@reedsy.com",
    "admin@wordpress.com", "help@squarespace.com", "support@shopify.com", "support@github.com",
    "abuse@cloudflare.com", "privacy@wix.com", "info@wix.com", "support@squarespace.com"
}

def decode_search_url(raw_href: str) -> str:
    """Decodes actual destination URL from Bing/DuckDuckGo tracking links."""
    if not raw_href:
        return ""
    
    # Bing format: ...&u=a1<BASE64>...
    if "u=a1" in raw_href:
        match = re.search(r"u=a1([a-zA-Z0-9_-]+)", raw_href)
        if match:
            try:
                b64 = match.group(1)
                b64 += "=" * (-len(b64) % 4)
                return base64.urlsafe_b64decode(b64).decode("utf-8", errors="ignore")
            except Exception:
                pass

    # DuckDuckGo format: ...uddg=<URL_ENCODED>...
    if "uddg=" in raw_href:
        match = re.search(r"uddg=([^&]+)", raw_href)
        if match:
            return unquote(match.group(1))

    return raw_href

class AuthorLeadScraper:
    """
    Multi-Engine Resilient Author Hunter:
    Queries Bing and direct author search routes with concurrent parallel crawling.
    """

    def __init__(self):
        self.headers = DEFAULT_HEADERS

    async def search_authors(self, keyword: str, genre: str = "fiction", limit: int = 10) -> List[Dict[str, Any]]:
        """Searches for author sites and extracts verified direct email contacts."""
        queries = [
            f"{keyword} author official website contact",
            f"{keyword} author contact email OR newsletter",
            f"{keyword} novelist books contact me",
            f"{keyword} books \"about the author\" contact"
        ]

        raw_candidates = []
        seen_domains = set()

        async with aiohttp.ClientSession(headers=self.headers) as session:
            for query in queries:
                if len(raw_candidates) >= 15:
                    break

                # 1. Bing Search
                try:
                    bing_url = f"https://www.bing.com/search?q={quote_plus(query)}"
                    async with session.get(bing_url, timeout=5) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            soup = BeautifulSoup(html, "lxml")
                            for item in soup.select("li.b_algo"):
                                h2 = item.select_one("h2 a")
                                if not h2:
                                    continue
                                raw_title = h2.get_text(strip=True)
                                raw_href = h2.get("href", "")
                                actual_url = decode_search_url(raw_href)

                                domain = urlparse(actual_url).netloc.lower().replace("www.", "")
                                if not domain or domain in seen_domains:
                                    continue
                                if not is_valid_prospect_domain(domain, actual_url):
                                    continue

                                seen_domains.add(domain)
                                name, title = self._parse_author_title(raw_title)
                                raw_candidates.append({
                                    "name": name,
                                    "book_title": title,
                                    "genre": genre,
                                    "url": actual_url,
                                    "domain": domain
                                })
                except Exception as e:
                    logger.debug(f"Bing search query error: {e}")

                # 2. DuckDuckGo Search Fallback
                if len(raw_candidates) < 6:
                    try:
                        async with session.post("https://html.duckduckgo.com/html/", data={"q": query}, timeout=4) as resp:
                            if resp.status == 200:
                                html = await resp.text()
                                soup = BeautifulSoup(html, "lxml")
                                for res in soup.select(".result"):
                                    link_el = res.select_one(".result__title a.result__a")
                                    if not link_el:
                                        continue
                                    raw_title = link_el.get_text(strip=True)
                                    raw_href = link_el.get("href", "")
                                    actual_url = decode_search_url(raw_href)

                                    domain = urlparse(actual_url).netloc.lower().replace("www.", "")
                                    if not domain or domain in seen_domains:
                                        continue
                                    if not is_valid_prospect_domain(domain, actual_url):
                                        continue

                                    seen_domains.add(domain)
                                    name, title = self._parse_author_title(raw_title)
                                    raw_candidates.append({
                                        "name": name,
                                        "book_title": title,
                                        "genre": genre,
                                        "url": actual_url,
                                        "domain": domain
                                    })
                    except Exception:
                        pass

            if not raw_candidates:
                return []

            # Parallel Concurrent Crawling of Author Websites
            tasks = [self._crawl_single_author(session, cand) for cand in raw_candidates[:12]]
            crawled = await asyncio.gather(*tasks, return_exceptions=True)

            results = []
            for item in crawled:
                if isinstance(item, dict) and item.get("email"):
                    if item["email"] not in [r["email"] for r in results]:
                        results.append(item)
                        logger.info(f"    [+] Scouted Author: {item['name']} ('{item['book_title']}') -> {item['email']}")
                        if len(results) >= limit:
                            break

            return results[:limit]

    def _parse_author_title(self, raw_title: str) -> tuple[str, str]:
        """Extracts clean author name and book title from snippet title."""
        clean = re.sub(r'\s+by\s+', ' by ', raw_title).replace("|", "-").replace(":", "-").replace("–", "-")
        parts = [p.strip() for p in clean.split("-") if p.strip()]

        if len(parts) >= 2:
            name_candidate = parts[0].replace("Home", "").replace("Official Site", "").replace("Website", "").replace("Books", "").strip()
            title_candidate = parts[1].replace("Author", "").replace("Novels", "").strip()
        else:
            name_candidate = clean.split()[0] if clean else "Author"
            title_candidate = clean

        for b in ["Official Site", "Home", "Website", "Goodreads", "Amazon", "Books", "Novels"]:
            name_candidate = name_candidate.replace(b, "").strip()

        return name_candidate or "Author", title_candidate or "Recent Novel"

    async def _crawl_single_author(self, session: aiohttp.ClientSession, cand: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Crawls a single author website and its contact page in parallel."""
        url = cand["url"]
        try:
            async with session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
                soup = BeautifulSoup(html, "lxml")

                emails = EMAIL_REGEX.findall(html)
                clean_emails = [
                    e.lower() for e in emails 
                    if e.lower() not in IGNORE_EMAILS and not e.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js"))
                ]

                if not clean_emails:
                    for a_tag in soup.find_all("a", href=True):
                        href = a_tag["href"].lower()
                        if any(k in href for k in ["contact", "about", "press", "inquir"]):
                            sub_url = urljoin(url, a_tag["href"])
                            try:
                                async with session.get(sub_url, timeout=4) as sub_resp:
                                    if sub_resp.status == 200:
                                        sub_html = await sub_resp.text()
                                        sub_emails = EMAIL_REGEX.findall(sub_html)
                                        clean_emails.extend([
                                            e.lower() for e in sub_emails 
                                            if e.lower() not in IGNORE_EMAILS and not e.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js"))
                                        ])
                            except Exception:
                                pass
                            if clean_emails:
                                break

                if clean_emails:
                    return {
                        "name": cand["name"],
                        "book_title": cand["book_title"],
                        "genre": cand["genre"],
                        "website": url,
                        "domain": cand["domain"],
                        "email": clean_emails[0],
                        "source": "web"
                    }
        except Exception:
            pass
        return None
