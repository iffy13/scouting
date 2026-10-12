import logging
import sqlite3
from typing import List, Dict, Any, Optional, Tuple
from db import get_connection, init_db

logger = logging.getLogger(__name__)

# Master list of 49 high-GDP, premium target countries (Sorted by Tier)
DEFAULT_COUNTRIES = [
    # Tier 1: Core English Hubs
    "US", "UK", "CA", "AU", "NZ", "IE",
    # Tier 2: Nordic High-Income Hubs
    "NO", "SE", "DK", "FI", "IS",
    # Tier 3: Western & Central Europe
    "CH", "DE", "NL", "AT", "BE", "LU", "FR", "MC", "LI",
    # Tier 4: Southern & Mediterranean Europe
    "ES", "IT", "PT", "GR", "CY", "MT",
    # Tier 5: Central & Baltic Tech Hubs
    "EE", "PL", "CZ", "LT", "LV", "SK", "SI", "HU", "HR", "RO",
    # Tier 6: Gulf GCC Wealth Hubs
    "AE", "SA", "QA", "KW", "BH", "OM",
    # Tier 7: Asia-Pacific High-Income Tech Hubs
    "SG", "HK", "JP", "KR", "TW", "MY", "TH"
]

# Exhaustive Master List of 60+ High-Ticket Niches
DEFAULT_KEYWORDS = [
    # --- 1. Emergency Local Trades (AI Voice Receptionist) ---
    ("emergency plumber", "local"),
    ("hvac repair", "local"),
    ("commercial roofing contractor", "local"),
    ("24/7 locksmith service", "local"),
    ("water damage restoration", "local"),
    ("electrician contractor", "local"),
    ("solar panel installer", "local"),
    ("tree removal service", "local"),
    ("garage door repair", "local"),
    ("pest control company", "local"),
    ("towing service", "local"),
    ("foundation repair contractor", "local"),
    ("concrete paving contractor", "local"),
    ("asphalt paving contractor", "local"),
    ("fence contractor", "local"),
    ("gutter installation contractor", "local"),

    # --- 2. High-Ticket Health, Medical & Aesthetic Clinics ---
    ("cosmetic dentist", "local"),
    ("dental implant specialist", "local"),
    ("med spa", "local"),
    ("plastic surgery clinic", "local"),
    ("dermatology clinic", "local"),
    ("orthodontist clinic", "local"),
    ("chiropractor clinic", "local"),
    ("physical therapy clinic", "local"),
    ("hair transplant clinic", "local"),
    ("anti aging wellness clinic", "local"),

    # --- 3. Legal, Financial & Corporate Professional Services ---
    ("personal injury lawyer", "local"),
    ("car accident attorney", "local"),
    ("criminal defense lawyer", "local"),
    ("divorce attorney", "local"),
    ("estate planning lawyer", "local"),
    ("immigration attorney", "local"),
    ("cpa accounting firm", "local"),
    ("wealth management advisor", "local"),
    ("commercial real estate broker", "local"),
    ("mortgage broker", "local"),

    # --- 4. High-End Home & Commercial Luxury Services ---
    ("luxury custom home builder", "local"),
    ("architectural design firm", "local"),
    ("interior design studio", "local"),
    ("swimming pool contractor", "local"),
    ("landscape architecture firm", "local"),
    ("kitchen remodeling contractor", "local"),
    ("bathroom renovation contractor", "local"),

    # --- 5. B2B Marketing, Digital & Tech Agencies (Video Clips & AI) ---
    ("seo agency", "digital"),
    ("web design agency", "digital"),
    ("digital marketing agency", "digital"),
    ("performance marketing agency", "digital"),
    ("branding agency", "digital"),
    ("software development agency", "digital"),
    ("mobile app development agency", "digital"),
    ("ecommerce marketing agency", "digital"),
    ("pr agency", "digital"),
    ("b2b lead generation agency", "digital"),

    # --- 6. Startups, SaaS & Content Creators (Video Repurposing) ---
    ("b2b saas company", "digital"),
    ("ai startup", "ai_tech"),
    ("fintech startup", "ai_tech"),
    ("business podcast host", "creator"),
    ("tech podcast host", "creator"),
    ("finance youtube creator", "creator"),
    ("real estate investor podcast", "creator"),
]

class RotationManager:
    """
    Autonomous Keyword-First Rotation Engine.
    Enforces Rule: 1 Keyword sweeps ALL countries before advancing to the next keyword.
    Continuously loops infinitely through all niches.
    """

    def __init__(self, db_path: Optional[str] = None):
        init_db()
        self.initialize_queue()

    def initialize_queue(self, keywords: Optional[List[Tuple[str, str]]] = None, countries: Optional[List[str]] = None):
        """Populates the campaign queue, preserving existing progress."""
        kw_list = keywords or DEFAULT_KEYWORDS
        ctry_list = countries or DEFAULT_COUNTRIES

        with get_connection() as conn:
            cursor = conn.cursor()
            for kw, b_type in kw_list:
                for ctry in ctry_list:
                    cursor.execute("""
                        INSERT OR IGNORE INTO campaign_state (keyword, country, business_type, status, leads_scraped, leads_contacted)
                        VALUES (?, ?, ?, 'queued', 0, 0)
                    """, (kw, ctry, b_type))
            conn.commit()

    def get_current_slot(self) -> Optional[Dict[str, Any]]:
        """
        Pulls the next active keyword + country slot in rotation.
        If all slots ever finish, it automatically resets the queue for an infinite fresh sweep!
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Find the first keyword that still has uncompleted countries
            cursor.execute("""
                SELECT keyword, business_type
                FROM campaign_state
                WHERE status IN ('in_progress', 'queued')
                ORDER BY id ASC
                LIMIT 1
            """)
            row = cursor.fetchone()

            # 2. If queue completed, automatically reset all slots back to 'queued' for continuous infinite running
            if not row:
                logger.info("[CYCLE COMPLETE] All 60+ keywords across 49 countries completed! Resetting queue for fresh infinite rotation...")
                cursor.execute("UPDATE campaign_state SET status = 'queued'")
                conn.commit()

                cursor.execute("""
                    SELECT keyword, business_type
                    FROM campaign_state
                    WHERE status IN ('in_progress', 'queued')
                    ORDER BY id ASC
                    LIMIT 1
                """)
                row = cursor.fetchone()

            if not row:
                return None

            active_keyword = row["keyword"]

            # 3. Find the first pending country for this active keyword
            cursor.execute("""
                SELECT id, keyword, country, business_type, status, leads_scraped, leads_contacted
                FROM campaign_state
                WHERE keyword = ? AND status IN ('in_progress', 'queued')
                ORDER BY id ASC
                LIMIT 1
            """, (active_keyword,))
            
            slot = cursor.fetchone()
            if slot:
                return dict(slot)
            return None

    def mark_slot_completed(self, keyword: str, country: str):
        """Marks a (keyword, country) pair as fully scraped and completed."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE campaign_state
                SET status = 'completed', last_run_at = CURRENT_TIMESTAMP
                WHERE keyword = ? AND country = ?
            """, (keyword, country))
            conn.commit()
            logger.info(f"Completed rotation slot: [{keyword}] in [{country}]. Advancing to next country/keyword.")

    def get_rotation_summary(self) -> List[Dict[str, Any]]:
        """Returns high-level status of the entire rotation queue."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT keyword, business_type,
                       COUNT(CASE WHEN status = 'completed' THEN 1 END) as countries_completed,
                       COUNT(*) as total_countries,
                       SUM(leads_scraped) as total_scraped,
                       SUM(leads_contacted) as total_contacted
                FROM campaign_state
                GROUP BY keyword, business_type
                ORDER BY MIN(id) ASC
            """)
            return [dict(r) for r in cursor.fetchall()]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    mgr = RotationManager()
    current = mgr.get_current_slot()
    print("\n" + "="*60)
    print(" AUTONOMOUS KEYWORD-FIRST ROTATION STATUS")
    print("="*60)
    if current:
        print(f">> CURRENT ACTIVE ROTATION SLOT:")
        print(f"   * Keyword:       {current['keyword'].upper()}")
        print(f"   * Country:       {current['country']}")
        print(f"   * Business Type: {current['business_type']}")
        print(f"   * Status:        {current['status']}")
    print("="*60 + "\n")
