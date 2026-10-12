import asyncio
import logging
from db import init_db, get_connection
from scrapers.osm import OSMScraper
from scrapers.trustpilot import TrustpilotScraper
from enricher.crawler import WebsiteCrawler
from verifier.email_verifier import EmailVerifier
from offers.rule_engine import OfferRuleEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("test_pipeline")

async def test_run():
    print("=" * 60)
    print(" UNIVERSAL LEAD OUTREACH ENGINE — LIVE PIPELINE TEST")
    print("=" * 60)
    
    init_db()
    
    # 1. Test Local Business Discovery (OSM)
    print("\n[Step 1] Discovering Local Businesses (Keyword: 'plumber', Country: 'US')...")
    osm = OSMScraper()
    local_leads = await osm.search(keyword="plumber", country="US", limit=5)
    print(f"-> Found {len(local_leads)} local businesses.")
    for lead in local_leads[:3]:
        print(f"   • {lead['name']} | City: {lead.get('city')} | Website: {lead.get('website')}")

    # 2. Test Digital / SaaS Business Discovery (Trustpilot)
    print("\n[Step 2] Discovering Digital Businesses (Keyword: 'digital marketing', Country: 'US')...")
    trustpilot = TrustpilotScraper()
    digital_leads = await trustpilot.search(keyword="digital marketing", country="US", limit=5)
    print(f"-> Found {len(digital_leads)} digital businesses.")
    for lead in digital_leads[:3]:
        print(f"   • {lead['name']} | Website: {lead.get('website')} | Rating: {lead.get('rating')} ({lead.get('reviews_count')} reviews)")

    # 3. Test Enrichment & Crawler
    print("\n[Step 3] Testing Email Crawler on discovered leads...")
    crawler = WebsiteCrawler(timeout=10)
    sample_site = next((l["website"] for l in local_leads + digital_leads if l.get("website")), "https://example.com")
    print(f"-> Crawling sample site: {sample_site}")
    crawl_result = await crawler.crawl_site(sample_site)
    print(f"-> Emails found: {crawl_result.get('emails')}")
    print(f"-> Signals: {crawl_result.get('signals')}")

    # 4. Test Verification Engine
    print("\n[Step 4] Testing Multi-Stage Email Verifier...")
    verifier = EmailVerifier()
    test_emails = ["contact@google.com", "fake_nonexistent_user_12345@google.com", "invalid-syntax@", "test@mailinator.com"]
    for email in test_emails:
        res = await verifier.verify(email)
        print(f"   • {email} -> Verdict: [{res['verdict'].upper()}] (Deliverable: {res['is_deliverable']}, Reason: {res['reason']})")

    # 5. Test Offer & Copy Personalization Engine
    print("\n[Step 5] Testing Dynamic Offer Matching & Copy Generation...")
    sample_business = {
        "name": "Apex Plumbing Services",
        "keyword": "plumber",
        "country": "US",
        "city": "Austin",
        "rating": 4.9,
        "reviews_count": 87,
        "website": "https://apexplumbingexample.com"
    }
    
    # Simulate signals with no booking chat
    matched_offer = OfferRuleEngine.determine_offer(sample_business, {"has_booking_chat": False, "has_youtube": False})
    print(f"-> Matched Offer for {sample_business['name']}: {matched_offer.upper()}")
    
    subject_d1, body_d1 = OfferRuleEngine.get_email_copy(matched_offer, stage=1, business=sample_business, first_name="Dave")
    print("\n--- [Day 1 Email Preview] ---")
    print(f"Subject: {subject_d1}")
    print(body_d1)
    
    subject_d3, body_d3 = OfferRuleEngine.get_email_copy(matched_offer, stage=2, business=sample_business, first_name="Dave", mockup_link="https://demo.ai-voice.io/apex")
    print("\n--- [Day 3 Follow-Up 1 Preview (Deliver Goods)] ---")
    print(f"Subject: {subject_d3}")
    print(body_d3)

    print("\n" + "=" * 60)
    print(" PIPELINE TEST COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_run())
