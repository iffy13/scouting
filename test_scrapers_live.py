import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

async def test_scrapers():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }

    # Test Trustpilot (Digital / Local / Services)
    print("Testing Trustpilot...")
    tp_url = f"https://www.trustpilot.com/search?query=plumber+austin"
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(tp_url, timeout=10) as resp:
            print(f"Trustpilot status: {resp.status}")
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, "lxml")
                cards = soup.select('div[class*="styles_businessUnitCard"], div[class*="paper_paper"]')
                print(f"Trustpilot found {len(cards)} cards")

    # Test DuckDuckGo HTML search for local business websites
    print("\nTesting DuckDuckGo search for live business domains...")
    ddg_url = f"https://html.duckduckgo.com/html/?q=plumber+in+Austin+Texas+website"
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(ddg_url, timeout=10) as resp:
            print(f"DDG status: {resp.status}")
            if resp.status == 200:
                html = await resp.text()
                soup = BeautifulSoup(html, "lxml")
                links = soup.select(".result__url, .result__snippet, .result__title a")
                print(f"DDG found {len(links)} search results")

if __name__ == "__main__":
    asyncio.run(test_scrapers())
