"""
Keeps articles, directories, marketplaces, giant brands and government sites out of your leads.
Only real, individual businesses should be shortlisted.

  python lead_filter.py clean     re-checks leads already in your database that were not emailed yet,
                                  marks the junk ones as skipped and removes junk emails, putting the
                                  business's own address first
"""
import json
import re
import sys
from typing import Iterable, List, Optional

GIANTS = (
    "amazon.", "noon.com", "ubereats", "glovo", "deliveroo", "talabat", "careem", "jumia", "alibaba", "aliexpress",
    "ebay.", "shopify.com", "wix.com", "etsy.com", "walmart.", "temu.", "shein.", "zalando", "booking.com",
    "airbnb", "expedia", "justeat", "foodpanda", "doordash", "grubhub", "menuintegrado", "olx.", "dubizzle",
    "wikipedia", "forbes.", "medium.com", "pinterest", "f6s.com", "crunchbase", "apple.com", "google.",
    "lazada.", "shopee.", "zalora.", "ubuy.", "statista.", "mordorintelligence", "centrepointstores", "extra.com",
    "xcite.com", "rotorooter", "mrrooter", "mdec.my", "houzz.", "archdaily", "dezeen", "behance.", "dribbble",
    "propertyfinder", "bayut", "zillow", "realtor.com", "realestate.com.au", "domain.com.au", "99acres", "magicbricks",
    "property24", "privateproperty", "propertypro", "archello", "homify", "carrefour", "ikea.", "jarir.com", "sharafdg", "luluhypermarket",
)
# Businesses that sell websites or shop software. They show up for "ecommerce store" but they are vendors, not buyers.
VENDOR_PATTERNS = [
    r"\bwebsite (development|design|builder)\b", r"\bweb (design|development)\b", r"\becommerce (solutions?|platform|website)\b",
    r"\bdigital (marketing )?agency\b", r"\bhosting\b", r"\bshopping cart software\b",
]
PUBLISHER_WORDS = (
    "tips", "diary", "planner", "handbook", "tools", "guide", "blog", "news", "magazine", "leads", "wmtips",
    "review", "ranking", "directory", "compare", "listing", "yellowpages", "business-list",
)
TITLE_PATTERNS = [
    r"^\d+\+?\s.*\b(apps|websites|companies|sites|platforms|stores|shops|agencies|ways|things|tips|services|restaurants|clinics|brands|tools|places|delivery|market)\b",
    r"\b(top|best)\s+\d*\s*\w*",                    # "Top 10", "Best ..."
    r"\blist of\b", r"\bguide\b", r"\bhow to\b", r"\bvs\.?\b", r"\breviews?\b", r"\branking",
    r"\b(apps|websites|companies|sites|platforms|stores|shops|agencies)\s+(in|for|near)\b",
    r"\bmarket share\b", r"\bdirectory\b",
    # trade bodies and lists of members, not a business that buys
    r"\bassociations?\b", r"\bfederation\b", r"\bcouncil\b", r"\bchamber of commerce\b", r"\bguild\b",
    r"\bby (province|state|city|region|territory)\b", r"\bnear me\b", r"\bonline shopping\b", r"\bin (the )?(uae|dubai|italy|portugal|spain|germany|uk)\s*(&|and|\(|for|\d{4})",
]
GOV_EDU = (".gov", ".gob.", ".edu", ".ac.", "u.ae", ".mil")
# Page titles that are not a business name (offers/cleaner.py swaps them for the domain name)
BAD_NAMES = {"home", "homepage", "home page", "welcome", "index", "contact", "contact us", "about", "about us", "untitled", "page not found", "official website", "official site"}
PLACES = (
    "australia", "oman", "bahrain", "uae", "united arab emirates", "dubai", "abu dhabi", "saudi arabia", "riyadh", "jeddah",
    "qatar", "doha", "kuwait", "singapore", "malaysia", "kuala lumpur", "united states", "usa", "canada", "new zealand",
    "ireland", "united kingdom", "uk", "london", "italy", "spain", "portugal", "germany", "netherlands",
    "mexico", "méxico", "cdmx", "brasil", "brazil", "colombia", "bogotá", "argentina", "chile", "são paulo",
)
LIST_NAME_PATTERNS = [
    r"^\d+\+?\s+\w+",                                                  # "10 Electricians ...", "25 best ..."
    r"\b(companies|dealerships|electricians|plumbers|clinics|salons|agencies|contractors)\b.*\bin\s+(the\s+)?(" + "|".join(PLACES) + r")\b",
    # Spanish and Portuguese lists and directories: "Las 10 mejores clínicas...", "Melhores imobiliárias em..."
    r"\b(mejores|melhores|directorio|diretório|guía de|guia de|ranking)\b",
    r"^(las|los|as|os)\s+\d+\b",
]
# URL paths that belong to lists, directories and location landing pages, not a business home page
LIST_URL_PATTERNS = [
    r"/listicles?/", r"/top-\d*", r"/best-", r"/top-agencies/", r"/directory/", r"/companies/", r"/list-of-",
    r"-in-(" + "|".join(p.replace(" ", "-") for p in PLACES) + r")(/|$|-)", r"/\d+-[a-z]+-in-",
    r"/mejores-", r"/melhores-", r"/directorio/", r"/diretorio/",
]
FREE_MAIL = ("gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "yahoo.com", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com")
# Font and theme credits that sit in page code, not real contacts
CREDIT_EMAILS = ("impallari", "rfuenzalida", "sorkin", "typemade", "huertatipografica", "cyreal", "example.com", "domain.com", "sentry")
EMAIL_SHAPE = re.compile(r"^[a-z0-9][a-z0-9._%+-]*@(?:[a-z0-9-]+\.)+[a-z]{2,24}$")


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
    for pat in TITLE_PATTERNS + LIST_NAME_PATTERNS:
        if re.search(pat, n):
            return "looks like a list or article"
    for pat in VENDOR_PATTERNS:
        if re.search(pat, n):
            return "sells websites or software, not a buyer"
    path = (website or "").lower().split("://", 1)[-1]
    path = path[path.find("/"):] if "/" in path else ""
    for pat in LIST_URL_PATTERNS:
        if re.search(pat, path):
            return "list, directory or location page, not a business home page"
    if len(n) < 3:
        return "no clear business name"
    return None


def service_junk_reason(service_id: str, name: Optional[str], domain: Optional[str], website: Optional[str] = None) -> Optional[str]:
    """junk_reason plus the extra rules of one service (render_3d also skips render studios and software)."""
    why = junk_reason(name, domain, website)
    if service_id == "lead_gen":
        # agencies and web designers are BUYERS of lead lists, so the "sells websites" rule does not apply here
        if why and why != "sells websites or software, not a buyer":
            return why
        import leadgen
        return leadgen.leadgen_junk_reason(name, domain)
    if why or service_id != "render_3d":
        return why
    import render3d
    return render3d.render3d_junk_reason(name, domain)


def _root(domain: str) -> str:
    d = (domain or "").lower().replace("www.", "").strip(".")
    parts = d.split(".")
    # keep the last 3 labels for two-part country suffixes like .com.au, .co.uk, .com.om
    if len(parts) >= 3 and parts[-2] in ("com", "co", "org", "net", "gov", "edu", "ac"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def clean_emails(emails: Iterable[str], domain: Optional[str]) -> List[str]:
    """Drops parse junk (leaflet@1.9.4, wght@, bootstrap@5.3.2), government addresses and font credits.
    Orders what is left: same domain as the website first, then free mail found on the site, then the rest,
    because the send step uses the first email."""
    site = _root(domain or "")
    ranked = []
    for e in emails or []:
        e = (e or "").strip().lower().strip(".,;:")
        if not EMAIL_SHAPE.match(e) or any(c in e for c in CREDIT_EMAILS):
            continue
        host = e.split("@", 1)[1]
        if any(g in host for g in GOV_EDU):
            continue
        rank = 0 if site and _root(host) == site else 1 if host in FREE_MAIL else 2
        if e not in [x for _, x in ranked]:
            ranked.append((rank, e))
    return [e for _, e in sorted(ranked, key=lambda t: t[0])]


def clean_existing():
    from db import get_connection
    from scout import init_scout_tables

    init_scout_tables()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, service_id, name, domain, website, status, emails_json FROM scout_leads WHERE status IN ('new','shortlisted','approved')"
        ).fetchall()
        removed = fixed = 0
        for r in rows:
            why = service_junk_reason(r["service_id"], r["name"], r["domain"], r["website"])
            if why:
                conn.execute("UPDATE scout_leads SET status='skipped' WHERE id=?", (r["id"],))
                print(f"skipped #{r['id']} {r['name']} ({r['domain']}): {why}")
                removed += 1
                continue
            old = json.loads(r["emails_json"] or "[]")
            new = clean_emails(old, r["domain"])
            if new != old:
                conn.execute("UPDATE scout_leads SET emails_json=? WHERE id=?", (json.dumps(new), r["id"]))
                print(f"emails #{r['id']} {r['name']}: {', '.join(old)} -> {', '.join(new) or '(none left)'}")
                fixed += 1
        conn.commit()
    print(f"\nChecked {len(rows)} leads, marked {removed} as skipped, cleaned emails on {fixed}, {len(rows) - removed} kept.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean_existing()
    else:
        print(__doc__)
