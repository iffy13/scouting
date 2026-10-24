"""
Lead lists service: verified lists of prospects (business, website, checked email, owner name when found) for
businesses that live on a steady flow of new clients. What to scout, how strictly to score, what to write.

Who buys (and what list they get):
  agencies, coaches, consultants, B2B service firms  -> businesses that match their ideal client
  high-ticket home services (roofing, solar, HVAC...) -> property managers, realtors, builders, facility managers
                                                        (the referral partners who send repeat jobs)
  clinics and med spas                                -> local employers, gyms and wellness businesses
                                                        (partnerships and corporate plans)
Only business contacts are ever offered: published business addresses, never lists of private people.

STRICT on purpose. A lead is only emailed when the site shows it is actively trying to win clients right now:
it pays for ads, is hiring for sales, or says it is growing (new location, expanding, now open). On top of that
it must sell through enquiries (consultation, quote, book a call) or have a contact route. Businesses that say
they are fully booked or not taking new clients, and lead gen / data sellers, are skipped.

Duty the wording creates: when someone replies, send a real sample of 10 leads for their area. The scout itself
can build it: python scout.py --service <their kind of client> ... or by hand.

Run   python leadgen.py   for the self test and three example emails.
"""
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from messages_variants import greeting, name_is_usable, UNUSABLE_NAME

SERVICE_ID = "lead_gen"
LABEL = "Verified lead lists"
DESCRIPTION = ("Verified lists of prospects (business, website, checked email, owner name when found) for agencies, "
               "coaches, B2B firms, high-ticket home services and clinics that depend on new clients.")
MIN_SCORE = 55

# Everywhere the send step is allowed to email. EU/EEA, UK, Switzerland and South Africa are left out: the
# careful-regions rule never emails them, so scouting there would only burn search credits.
COUNTRIES = ["US", "CA", "AU", "NZ", "AE", "SA", "QA", "KW", "BH", "OM", "SG", "MY", "HK", "PH", "IN",
             "NG", "GH", "KE"]

# keyword -> niche. Keywords already used by the other services are left out (one business, one service).
KEYWORD_NICHE: Dict[str, str] = {
    "marketing agency": "agency",
    "digital marketing agency": "agency",
    "seo agency": "agency",
    "web design agency": "agency",
    "branding agency": "agency",
    "social media marketing agency": "agency",
    "business coach": "coach",
    "executive coach": "coach",
    "sales training company": "coach",
    "management consultant": "coach",
    "managed it services": "b2b",
    "it support company": "b2b",
    "accounting firm": "b2b",
    "bookkeeping services": "b2b",
    "commercial cleaning company": "b2b",
    "staffing agency": "b2b",
    "recruitment agency": "b2b",
    "commercial insurance broker": "b2b",
    "roofing company": "home",
    "solar installer": "home",
    "hvac company": "home",
    "commercial roofing contractor": "home",
    "window replacement company": "home",
    "dental implant clinic": "clinic",
    "cosmetic surgery clinic": "clinic",
    "physiotherapy clinic": "clinic",
    "chiropractor": "clinic",
    "aesthetics clinic": "clinic",
}
KEYWORDS: List[str] = list(KEYWORD_NICHE)

TRADE: Dict[str, str] = {
    "agency": "agencies", "coach": "coaches and consultants", "b2b": "B2B service firms",
    "home": "home service companies", "clinic": "clinics", "default": "service businesses",
}
# what the list would contain, written to follow "lists of"
LIST_OF: Dict[str, str] = {
    "agency": "businesses that match your ideal client",
    "coach": "business owners who match your ideal client",
    "b2b": "local businesses in the size and industry you serve",
    "home": "property managers, real estate agents, builders and facility managers in your area",
    "clinic": "local employers, gyms and wellness businesses near you",
    "default": "businesses that match your ideal client",
}

_NICHE_WORDS = [
    ("agency", r"agency|marketing|seo|digital|media|creative|branding"),
    ("coach", r"coach|consult|mentor|training"),
    ("clinic", r"clinic|dental|dentist|medical|aesthetic|physio|chiro|cosmetic|spa"),
    ("home", r"roof|solar|hvac|heating|cooling|window|exterior"),
    ("b2b", r"\bit\b|tech|account|bookkeep|cleaning|staffing|recruit|insurance"),
]


def detect_niche(keyword: Optional[str], name: Optional[str], domain: Optional[str]) -> str:
    kw = (keyword or "").strip().lower()
    if kw in KEYWORD_NICHE:
        return KEYWORD_NICHE[kw]
    text = f"{name or ''} {domain or ''}".lower()
    for key, pat in _NICHE_WORDS:
        if re.search(pat, text):
            return key
    return "default"


# ---------------------------------------------------------------- who NOT to email
# Competitors (lead gen, appointment setting, data sellers) and big chains / franchises.
_COMPETITOR = re.compile(r"lead ?gen|leads?\b|appointment ?sett|prospecting|outbound|\bdata\b|database|"
                         r"list ?build|demand ?gen|cold ?email|sdr", re.I)
_NOT_BUYER_DOMAINS = (
    "zoominfo", "apollo.io", "lusha", "seamless.ai", "uplead", "hunter.io", "clearbit", "leadiq", "cognism",
    "upwork", "fiverr", "freelancer.", "clutch.co", "sortlist", "designrush", "goodfirms", "upcity", "expertise.com",
    "wpp.com", "publicis", "omnicom", "dentsu", "ogilvy", "accenture", "deloitte", "pwc.", "kpmg", "ey.com",
    "roberthalf", "adecco", "randstad", "manpower", "aspendental", "smiledirect", "clearchoice", "sunrun",
    "tesla.com", "vivint", "carrier.com", "trane.com", "lennox", "searshomeservices", "servpro", "servicemaster",
)


def leadgen_junk_reason(name: Optional[str], domain: Optional[str]) -> Optional[str]:
    d = (domain or "").lower().replace("www.", "")
    n = (name or "").lower()
    if any(x in d for x in _NOT_BUYER_DOMAINS):
        return "big chain, platform or data seller"
    if _COMPETITOR.search(n) or _COMPETITOR.search(d.split(".")[0] if d else ""):
        return "sells leads or outreach itself"
    return None


# ---------------------------------------------------------------- site signals and score
_ENQUIRY = re.compile(
    r"free consultation|book (a|your) (call|consultation|demo|strategy)|schedule (a|your) (call|consultation)|"
    r"discovery call|strategy (call|session)|get (a|your) (free )?(quote|estimate|proposal)|request (a )?(quote|"
    r"estimate|proposal|consultation)|free (estimate|assessment|audit)|talk to (an|our) (expert|team)", re.I)
_HIRING_SALES = re.compile(
    r"(hiring|careers?|join our team|open (positions|roles)|we.?re looking for).{0,200}?"
    r"(sales|business development|account (executive|manager)|\bsdr\b|\bbdr\b|appointment setter|growth)", re.I | re.S)
_GROWTH = re.compile(r"now open|grand opening|new location|opening soon|we.?re (growing|expanding)|"
                     r"expanding (to|into)|recently opened|just opened|second location", re.I)
_B2B_CLIENTS = re.compile(r"case stud|our clients|clients we.?ve worked|trusted by|businesses we|b2b|for businesses", re.I)
_NO_NEED = re.compile(r"fully booked|not (currently )?(accepting|taking) new (clients|patients|customers|projects)|"
                      r"wait ?list|waiting list|booked (out|up) (until|through)", re.I)


def _text(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def analyse_html_leadgen(pages: Dict[str, str]) -> Dict[str, Any]:
    """Pure function. Merged into the signals from scout_signals.analyse_html."""
    text = _text("\n".join(pages.values()))
    title = re.search(r"<title[^>]*>(.*?)</title>", "\n".join(pages.values()), re.I | re.S)
    title_text = re.sub(r"\s+", " ", title.group(1)).strip() if title else ""
    return {
        "lg_enquiry": bool(_ENQUIRY.search(text)),
        "lg_hiring_sales": bool(_HIRING_SALES.search(text)),
        "lg_growth": bool(_GROWTH.search(text)),
        "lg_b2b": bool(_B2B_CLIENTS.search(text)),
        "lg_no_need": bool(_NO_NEED.search(text)),
        "lg_title_competitor": bool(re.search(r"lead ?gen|appointment ?sett|b2b data|lead lists?", title_text, re.I)),
    }


def score_leadgen(sig: Dict[str, Any], lead: Dict[str, Any], contact: Dict[str, Any]) -> Tuple[int, List[str]]:
    """Strict: without a sign of actively chasing growth (ads, hiring for sales, expanding) the lead stays below
    MIN_SCORE, so it is never emailed."""
    ev: List[str] = []
    if not sig.get("reachable"):
        return 0, ["site not reachable"]
    if sig.get("lg_title_competitor"):
        return 0, ["sells lead generation itself, skip"]
    if sig.get("lg_no_need"):
        return 0, ["says it is fully booked or not taking new clients, skip"]
    score = 10
    strong = False
    if sig.get("runs_ads"):
        score += 15
        strong = True
        ev.append("pays for ads to win clients")
    if sig.get("lg_hiring_sales"):
        score += 20
        strong = True
        ev.append("is hiring for sales or growth")
    if sig.get("lg_growth"):
        score += 15
        strong = True
        ev.append("says it is growing or opening a new location")
    if sig.get("lg_enquiry"):
        score += 20
        ev.append("sells through consultations or quotes, so every new lead counts")
    if sig.get("lg_b2b"):
        score += 10
        ev.append("works with business clients")
    if contact.get("emails") or contact.get("phone") or sig.get("has_contact_form"):
        score += 10
        ev.append("has a public business contact route")
    if not strong:
        score = min(score, MIN_SCORE - 5)
        ev.append("no sign it is actively chasing new clients right now (no ads, sales hiring or expansion)")
    return min(score, 100), ev


# ---------------------------------------------------------------- wording
SUBJECTS: Dict[str, List[str]] = {
    "agency": ["new clients for {name}", "a list of your ideal clients", "10 sample leads for {name}",
               "where your next clients come from", "quick question about new clients"],
    "coach": ["new clients for {name}", "a list of your ideal clients", "10 sample leads for you",
              "quick question about new clients", "finding your next clients"],
    "b2b": ["new clients for {name}", "a list of local businesses for you", "10 sample leads for {name}",
            "quick question about new clients", "where your next clients come from"],
    "home": ["repeat work for {name}", "property managers in your area", "10 sample leads for {name}",
             "more repeat jobs", "quick question about referrals"],
    "clinic": ["new patients for {name}", "local partners for {name}", "10 sample leads for you",
               "quick question about new patients", "corporate partners near you"],
    "default": ["new clients for {name}", "10 sample leads for you", "quick question about new clients",
                "where your next clients come from"],
}
OPENERS: Dict[str, List[str]] = {
    "agency": [
        "For a lot of agencies, new clients come in waves: referrals one month, nothing the next.",
        "When referrals slow down, where do new clients for {name} come from?",
        "How much of your week goes into finding new clients instead of doing client work?",
    ],
    "coach": [
        "Most coaches are great at the work and short on time to find the next client.",
        "When referrals slow down, where do new clients for {name} come from?",
        "How much of your week goes into finding new clients?",
    ],
    "b2b": [
        "Most firms like {name} grow on referrals, which are hard to plan around.",
        "When referrals slow down, where do new clients for {name} come from?",
        "How do you find new business clients today, beyond referrals?",
    ],
    "home": [
        "One good property manager can send a company like yours more jobs in a year than a month of ads.",
        "Do property managers and realtors already send {name} repeat work?",
        "Most of the steady work in your trade comes from a few referral partners, not one-off ads.",
    ],
    "clinic": [
        "The clinics that grow fastest near you usually partner with local employers and gyms.",
        "Have you looked at corporate plans or partnerships with local businesses for {name}?",
        "Most new patients still come from word of mouth, which is hard to plan around.",
    ],
    "default": [
        "When referrals slow down, where do new clients for {name} come from?",
        "How do you find new clients today, beyond referrals?",
    ],
}
OFFERS = [
    "I build verified lead lists: {list}, each with a checked email address, their website and, where I can find "
    "it, the owner's name.",
    "I put together lists of {list}, with emails checked so your outreach doesn't bounce.",
    "I research and verify {list}, so you start your outreach with real contacts instead of a blank page.",
    "I make lead lists for {trade}: {list}, with verified emails and websites, ready for your outreach.",
]
CLOSERS = [
    "Would a sample of 10 for your area be useful, so you can judge the quality?",
    "Want me to put together 10 sample leads for you to look at?",
    "If I sent you 10 sample leads, would you take a look?",
    "Who is your ideal client? I can send 10 sample leads that match.",
]
FOLLOWUPS = [
    "Just bumping this up. Happy to send 10 sample leads for {name} so you can see the quality first.",
    "Quick follow up: would a sample list of 10 leads be useful, or should I close the loop?",
    "One last note from me. If you already have enough leads, no worries and I won't follow up again.",
]


def _rnd(seed: str, slot: str) -> random.Random:
    return random.Random(f"{seed}:{slot}")


def build_first(niche_key: str, name: str, owner_name: Optional[str], country: Optional[str],
                seed: str) -> Tuple[str, str]:
    """(subject, body) WITHOUT the footer. The same lead always gets the same email (seeded by its domain)."""
    key = niche_key if niche_key in SUBJECTS else "default"
    ok = name_is_usable(name)
    shown = name if ok else UNUSABLE_NAME
    subjects = SUBJECTS[key] if ok else ([s for s in SUBJECTS[key] if "{name}" not in s] or SUBJECTS[key])
    openers = OPENERS.get(key, OPENERS["default"])
    if not ok:
        openers = [o for o in openers if "{name}" not in o] or OPENERS["default"][1:]
    subject = _rnd(seed, "subject").choice(subjects).format(name=shown)
    closers = CLOSERS if key in ("agency", "coach", "b2b", "default") else [c for c in CLOSERS if "ideal client" not in c]
    parts = (_rnd(seed, "opener").choice(openers), _rnd(seed, "offer").choice(OFFERS),
             _rnd(seed, "closer").choice(closers))
    body = "\n\n".join(p.format(name=shown, trade=TRADE.get(key, TRADE["default"]),
                                list=LIST_OF.get(key, LIST_OF["default"])) for p in parts)
    return subject, f"{greeting(owner_name, country)}\n\n{body}"


def build_followup(name: str, owner_name: Optional[str], country: Optional[str], seed: str,
                   first_subject: str) -> Tuple[str, str]:
    ok = name_is_usable(name)
    pool = FOLLOWUPS if ok else ([f for f in FOLLOWUPS if "{name}" not in f] or FOLLOWUPS)
    text = _rnd(seed, "followup").choice(pool).format(name=name if ok else UNUSABLE_NAME)
    return "Re: " + first_subject, f"{greeting(owner_name, country)}\n\n{text}"


# ---------------------------------------------------------------- self test and preview
def _self_test() -> int:
    problems: List[str] = []
    for key in list(SUBJECTS):
        for nm in ("Harbor Digital", "Peak Roofing Co", UNUSABLE_NAME):
            for own, ctry in ((None, "US"), ("Sam Carter", "US"), ("INFO", "NG")):
                for i in range(40):
                    seed = f"{key}-{i}.example"
                    s, b = build_first(key, nm, own, ctry, seed)
                    fs, fb = build_followup(nm, own, ctry, seed, s)
                    for label, t in (("subject", s), ("body", b), ("follow up", fb)):
                        if re.search(r"[{}]", t):
                            problems.append(f"unrendered slot in {label}: {t[:80]!r}")
                        if "!" in t or re.search(r"\bfree\b|guarantee", t, re.I) or "http" in t:
                            problems.append(f"spammy text in {label}: {t[:80]!r}")
                        if nm == UNUSABLE_NAME and UNUSABLE_NAME in t.lower():
                            problems.append(f"'your business' shown in {label}: {t[:80]!r}")
                    if len(b.split()) > 80:
                        problems.append(f"body too long ({len(b.split())} words)")
    for nm, dm, want in (("Acme Lead Gen", "acmeleadgen.com", True), ("ZoomInfo", "zoominfo.com", True),
                         ("Harbor Digital", "harbordigital.com", False), ("Peak Roofing", "peakroofing.com", False)):
        if bool(leadgen_junk_reason(nm, dm)) != want:
            problems.append(f"junk filter wrong for {nm}")
    base = {"reachable": True, "has_contact_form": True}
    s1 = dict(base, runs_ads=True, **analyse_html_leadgen({"": "Book a free consultation today. Our clients include"}))
    s2 = dict(base, runs_ads=False, **analyse_html_leadgen({"": "Get a quote. Call us."}))
    s3 = dict(base, runs_ads=True, **analyse_html_leadgen({"": "Sorry, we are not accepting new clients"}))
    s4 = dict(base, runs_ads=False, **analyse_html_leadgen({"": "Careers: we're hiring an Account Executive. Request a quote"}))
    if score_leadgen(s1, {}, {})[0] < MIN_SCORE:
        problems.append("ads + consultation scored too low")
    if score_leadgen(s2, {}, {})[0] >= MIN_SCORE:
        problems.append("no growth signal still passed")
    if score_leadgen(s3, {}, {})[0] != 0:
        problems.append("not accepting new clients was not skipped")
    if score_leadgen(s4, {}, {})[0] < MIN_SCORE:
        problems.append("hiring sales + quote scored too low")
    print(f"{len(problems)} problems")
    for p in problems[:15]:
        print("  -", p)
    return len(problems)


if __name__ == "__main__":
    bad = _self_test()
    footer = "\n\nSender Name\nBusiness Name · <postal address>\nNot relevant? Reply \"stop\" and I won't email you again."
    for key, nm, own, ctry, seed in (("agency", "Harbor Digital", "Sam Carter", "US", "harbordigital.com"),
                                      ("home", "Peak Roofing Co", None, "AU", "peakroofing.com.au"),
                                      ("clinic", UNUSABLE_NAME, None, "AE", "smileclinic.ae")):
        s, b = build_first(key, nm, own, ctry, seed)
        fs, fb = build_followup(nm, own, ctry, seed, s)
        print("=" * 60, f"\n[{key}] Subject: {s}\n\n{b}{footer}\n\n--- follow up ---\nSubject: {fs}\n\n{fb}{footer}\n")
    raise SystemExit(1 if bad else 0)
