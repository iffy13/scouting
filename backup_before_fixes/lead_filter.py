"""
Keeps articles, directories, marketplaces, giant brands and government sites out of your leads.
Only real, individual businesses should be shortlisted.

  python lead_filter.py clean     re-checks leads already in your database that were not emailed yet
                                  and marks the junk ones as skipped
"""
import re
import sys
from typing import Optional

GIANTS = (
    "amazon.", "noon.com", "ubereats", "glovo", "deliveroo", "talabat", "careem", "jumia", "alibaba", "aliexpress",
    "ebay.", "shopify.com", "wix.com", "etsy.com", "walmart.", "temu.", "shein.", "zalando", "booking.com",
    "airbnb", "expedia", "justeat", "foodpanda", "doordash", "grubhub", "menuintegrado", "olx.", "dubizzle",
    "wikipedia", "forbes.", "medium.com", "pinterest", "f6s.com", "crunchbase", "apple.com", "google.",
)
PUBLISHER_WORDS = (
    "tips", "diary", "planner", "handbook", "tools", "guide", "blog", "news", "magazine", "leads", "wmtips",
    "review", "ranking", "directory", "compare", "listing", "yellowpages", "business-list",
)
TITLE_PATTERNS = [
    r"^\d+\+?\s.*\b(apps|websites|companies|sites|platforms|stores|shops|agencies|ways|things|tips|services|restaurants|clinics|brands|tools|places|delivery|market)\b",
    r"\b(top|best)\s+\d*\s*\w*",                    # "Top 10", "Best ..."
    r"\blist of\b", r"\bguide\b", r"\bhow to\b", r"\bvs\.?\b", r"\breviews?\b", r"\branking",
    r"\b(apps|websites|companies|sites|platforms|stores|shops|agencies)\s+(in|for|near)\b",
    r"\bmarket share\b", r"\bdirectory\b", r"\bonline shopping\b", r"\bin (the )?(uae|dubai|italy|portugal|spain|germany|uk)\s*(&|and|\(|for|\d{4})",
]
GOV_EDU = (".gov", ".gob.", ".edu", ".ac.", "u.ae", ".mil")


def junk_reason(name: Optional[str], domain: Optional[str], website: Optional[str] = None) -> Optional[str]:
    """Returns a short reason when this is not an individual business, otherwise None."""
    d = (domain or "").lower().replace("www.", "")
    n = (name or "").strip().lower()
    if any(g in d for g in GIANTS):
        return "big brand or marketplace"
    if any(d.endswith(g) or g in d for g in GOV_EDU):
        return "government or school site"
    host_first = d.split(".")[0] if d else ""
    if any(w in host_first or w in d for w in PUBLISHER_WORDS):
        return "article, blog or directory site"
    for pat in TITLE_PATTERNS:
        if re.search(pat, n):
            return "looks like a list or article"
    if len(n) < 3:
        return "no clear business name"
    return None


def clean_existing():
    from db import get_connection
    from scout import init_scout_tables

    init_scout_tables()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, domain, website, status FROM scout_leads WHERE status IN ('new','shortlisted','approved')"
        ).fetchall()
        removed = 0
        for r in rows:
            why = junk_reason(r["name"], r["domain"], r["website"])
            if why:
                conn.execute("UPDATE scout_leads SET status='skipped' WHERE id=?", (r["id"],))
                print(f"skipped #{r['id']} {r['name']} ({r['domain']}): {why}")
                removed += 1
        conn.commit()
    print(f"\nChecked {len(rows)} leads, marked {removed} as skipped, {len(rows) - removed} kept.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean_existing()
    else:
        print(__doc__)
