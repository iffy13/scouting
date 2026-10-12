from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """Abstract base class for all lead generation scrapers."""
    
    def __init__(self, source_name: str, business_type: str):
        self.source_name = source_name
        self.business_type = business_type # 'local', 'digital', 'ai_tech', 'creator'

    @abstractmethod
    async def search(self, keyword: str, country: str, city: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Executes search on the given source.
        Returns a list of dictionaries with standard keys:
        {
            'name': str,
            'business_type': str,
            'source': str,
            'keyword': str,
            'country': str,
            'city': Optional[str],
            'website': Optional[str],
            'domain': Optional[str],
            'phone': Optional[str],
            'rating': Optional[float],
            'reviews_count': int,
            'is_closed': int (0 or 1),
            'signals': dict
        }
        """
        pass

    @staticmethod
    def extract_domain(url: Optional[str]) -> Optional[str]:
        """Extracts clean root domain from website URL."""
        if not url:
            return None
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain if domain else None
        except Exception:
            return None
