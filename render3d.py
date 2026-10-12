"""
3D rendering service for interior and exterior design buyers: what to scout, how to score a lead, what to write.
Pure functions. The only import from the rest of the tool is messages_variants (greeting, name_is_usable).

Who buys: businesses that sell a building, a room or a garden before it exists, and have to show a client what
it will look like. That is architects, interior designers, home builders and remodelers, property developers,
landscape designers and fit out teams.

What the wording promises: 3D renders of interiors and exteriors made from plans, sketches or photos, and a
set of samples on request. It does NOT promise a turnaround time, a price, a count of past projects or any
result, because none of those are on file. Add them only when they are true and provable.

Duty the wording creates before the first send: a few sample renders (images or a one page PDF) ready to send when
someone replies "samples", plus a price or "from" price for replies that ask for a quote.

Run   python render3d.py   to run the self test and print three full example emails.
"""
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from messages_variants import greeting, name_is_usable, UNUSABLE_NAME

SERVICE_ID = "render_3d"
LABEL = "3D rendering for interior and exterior design"
DESCRIPTION = ("3D renders of interiors and exteriors from plans, sketches or photos, for the people who have to show "
               "a client or a buyer a space that is not built yet.")
MIN_SCORE = 40

# Markets that are scouted AND emailed. Markets in CAREFUL_REGIONS (UK, IE, EU) are not in this list on purpose:
# the existing rule keeps them out of auto approval, so scouting them would only burn search credits.
COUNTRIES = ["US", "CA", "AU", "NZ", "AE", "SA", "QA", "KW", "BH", "OM", "SG", "MY"]  # ZA removed: POPIA needs consent

# keyword -> niche key. Keywords are what gets searched, the niche decides the subject and wording.
KEYWORD_NICHE: Dict[str, str] = {
    "interior design studio": "interior",
    "interior designer": "interior",
    "commercial interior design firm": "interior",
    "residential architect": "architect",
    "architecture firm": "architect",
    "custom home builder": "builder",
    "luxury home builder": "builder",
    "design build firm": "builder",
    "interior fit out company": "builder",
    "home renovation company": "remodel",
    "kitchen remodeling company": "remodel",
    "bathroom remodeling company": "remodel",
    "property developer": "developer",
    "real estate developer": "developer",
    "villa developer": "developer",
    "landscape design company": "landscape",
    "pool builder": "landscape",
    "outdoor living designer": "landscape",
}
KEYWORDS: List[str] = list(KEYWORD_NICHE)

TRADE_PHRASE: Dict[str, str] = {
    "architect": "architecture practices",
    "interior": "interior design studios",
    "builder": "home builders and fit out teams",
    "remodel": "remodeling companies",
    "developer": "property developers",
    "landscape": "landscape designers",
    "default": "design and building firms",
}

_NICHE_WORDS = [
    ("architect", r"architect"),
    ("interior", r"interior|decor|design studio|designer"),
    ("landscape", r"landscape|garden|pool|outdoor"),
    ("developer", r"develop|properties|property|estates|real ?estate|homes? for sale|villas?"),
    ("remodel", r"remodel|renovat|kitchen|bath"),
    ("builder", r"build|construct|contractor|fit ?out|joinery"),
]


def detect_niche(keyword: Optional[str], name: Optional[str], domain: Optional[str]) -> str:
    """The scouting keyword is the most reliable signal. Falls back to words in the name or domain."""
    kw = (keyword or "").strip().lower()
    if kw in KEYWORD_NICHE:
        return KEYWORD_NICHE[kw]
    text = f"{name or ''} {domain or ''}".lower()
    for key, pat in _NICHE_WORDS:
        if re.search(pat, text):
            return key
    return "default"


# ---------------------------------------------------------------- who NOT to email
# Other render studios sell the same thing, software makers and marketplaces are not buyers, and very large firms
# have in house visual teams. Used on top of lead_filter.junk_reason.
_SELLER_WORDS = re.compile(r"render|visuali[sz]|archviz|\bcgi\b|3d ?(studio|design|model|print|scan)|virtual tour", re.I)
_NOT_BUYER_DOMAINS = (
    "houzz.", "archdaily", "dezeen", "architizer", "behance", "dribbble", "artstation", "sketchup", "trimble",
    "autodesk", "lumion", "enscape", "chaos.", "vray", "twinmotion", "unrealengine", "fiverr", "upwork",
    "freelancer.", "99designs", "ikea.", "wayfair", "homedepot", "lowes.", "hgtv", "zillow", "realtor.com",
    "rightmove", "propertyfinder", "bayut", "archinect", "designboom", "canva.", "freepik", "shutterstock",
    "gensler", "som.com", "hok.com", "perkinswill", "aecom", "arup.com", "fosterandpartners", "zaha-hadid",
    # national volume home builders: in house design and marketing teams
    "drhorton", "lennar", "pulte", "nvrinc", "ryanhomes", "tollbrothers", "kbhome", "meritagehomes", "taylormorrison",
    "centurycommunities", "mihomes", "clayton", "schumacherhomes", "metricon", "simonds", "porterdavis", "henley.com.au",
)


def render3d_junk_reason(name: Optional[str], domain: Optional[str]) -> Optional[str]:
    d = (domain or "").lower().replace("www.", "")
    n = (name or "").lower()
    if any(x in d for x in _NOT_BUYER_DOMAINS):
        return "software, marketplace, directory or very large firm"
    if _SELLER_WORDS.search(n) or _SELLER_WORDS.search(d.split(".")[0] if d else ""):
        return "sells 3D visuals itself"
    return None


# ---------------------------------------------------------------- site signals and score
_PORTFOLIO = re.compile(r"portfolio|our work|projects|gallery|case stud|recent work", re.I)
_RENDER_WORDS = re.compile(r"3d render|renderings?\b|visuali[sz]ations?|walk-?through|\bcgi\b|artist'?s? impression", re.I)
_PRE_BUILD = re.compile(
    r"off[- ]plan|pre[- ]?construction|pre[- ]?sales?|coming soon|under construction|new developments?|master ?plan|"
    r"proposed|concept design|design proposal|planning (permission|approval|application)|upcoming projects?", re.I)


def analyse_html_render3d(pages: Dict[str, str]) -> Dict[str, Any]:
    """Pure function. Merge the result into the signals from scout_signals.analyse_html (sig.update(...))."""
    joined = "\n".join(pages.values())
    title = re.search(r"<title[^>]*>(.*?)</title>", joined, re.I | re.S)
    title_text = re.sub(r"\s+", " ", title.group(1)).strip() if title else ""
    return {
        "has_portfolio": bool(_PORTFOLIO.search(joined)),
        "mentions_renders": bool(_RENDER_WORDS.search(joined)),
        "pre_build_cues": bool(_PRE_BUILD.search(joined)),
        "title_is_seller": bool(_SELLER_WORDS.search(title_text)),
    }


def score_render3d(sig: Dict[str, Any], lead: Dict[str, Any], contact: Dict[str, Any]) -> Tuple[int, List[str]]:
    """Same signature as scout_signals.score_receptionist. `sig` must include analyse_html_render3d output."""
    ev: List[str] = []
    if not sig.get("reachable"):
        return 0, ["site not reachable"]
    if sig.get("title_is_seller"):
        return 0, ["site presents itself as a 3D visualisation studio, skip"]
    score = 10
    if sig.get("has_portfolio"):
        score += 20
        ev.append("shows projects on the site, so visuals matter to its clients")
    if sig.get("pre_build_cues"):
        score += 20
        ev.append("mentions upcoming, proposed or under construction work, which needs visuals before it exists")
    if sig.get("mentions_renders"):
        score += 10
        ev.append("already talks about renders or visualisation")
    if sig.get("runs_ads"):
        score += 10
        ev.append("runs ad tracking, so it spends on marketing")
    if (lead.get("reviews_count") or 0) >= 10:
        score += 10
        ev.append(f"{lead.get('reviews_count')} reviews, steady client flow")
    if contact.get("emails") or contact.get("phone") or sig.get("has_contact_form"):
        score += 10
        ev.append("has a public business contact route")
    return min(score, 100), ev


# ---------------------------------------------------------------- subjects
# Short, descriptive, honest about being a sales note. When the business name is unusable only the name free
# ones are used.
SUBJECTS: Dict[str, List[str]] = {
    "architect": [
        "3D views for design proposals", "renders from your drawings", "3D renders for {name}",
        "showing clients the finished design", "interior and exterior renders",
    ],
    "interior": [
        "3D views of your room concepts", "interior renders for client presentations", "3D renders for {name}",
        "showing clients the finished space", "visuals for {poss} projects",
    ],
    "builder": [
        "showing clients the finished build", "3D renders before the build starts", "3D renders for {name}",
        "visuals for {poss} projects", "interior and exterior renders",
    ],
    "remodel": [
        "kitchen and bath renders for clients", "showing clients the finished remodel", "3D renders for {name}",
        "visuals for {poss} projects", "3D views before the work starts",
    ],
    "developer": [
        "visuals for projects not yet built", "3D visuals before the build is finished", "3D renders for {name}",
        "visuals for {poss} projects", "interior and exterior renders",
    ],
    "landscape": [
        "outdoor renders for your clients", "3D views of garden designs", "3D renders for {name}",
        "showing clients the finished space", "visuals for {poss} projects",
    ],
    "default": [
        "3D renders for {name}", "visuals for your next project", "interior and exterior renders",
        "showing clients the finished space", "3D renders from your plans",
    ],
}

# ---------------------------------------------------------------- bodies (greeting and footer are added outside)
# A body is an opener, an offer sentence and a closing ask. Each piece stands alone, so any opener pairs with any
# offer and any closer. Slots: {name} {trade}. Every piece reads correctly with name = "your business".
NICHE_OPENERS: Dict[str, List[str]] = {
    "architect": [
        "When you present a design to a client, is it drawings only, or do you also show 3D views?",
        "How do your clients picture a design before it's built: drawings, models, or 3D views?",
        "For a project that's still on paper, how do clients get a feel for the finished building?",
    ],
    "interior": [
        "When you present a room concept, do clients see a mood board, or a 3D view of the finished space?",
        "How do your clients picture a finished interior before the work begins?",
        "Do your clients ask to see the space before they commit to a design?",
    ],
    "builder": [
        "When a client is choosing between layouts or finishes, how do they picture the result?",
        "How do your clients see the finished home before the build starts?",
        "Before a build starts, what do clients have to go on: plans, or images of the finished result?",
    ],
    "remodel": [
        "How do your clients picture a new kitchen or bathroom before the work starts?",
        "When a client is choosing finishes, how do they see the finished room?",
        "Do your clients ask to see the finished space before they sign off on a remodel?",
    ],
    "developer": [
        "For a project that isn't built yet, what do buyers see: floor plans, or finished visuals?",
        "How do you show buyers a project that is still on plan?",
        "While a development is under construction, what do your marketing materials show?",
    ],
    "landscape": [
        "How do your clients picture a garden or outdoor space before it's built?",
        "When you present a landscape design, do clients see plans, or a 3D view of the finished space?",
        "Do your clients ask to see the outdoor space before they approve a design?",
    ],
    "default": [
        "When you present a project to a client, how do they picture the finished result?",
        "Do your clients ever ask to see the finished space before the work starts?",
        "How do your clients see a project before it's built?",
    ],
}
GENERIC_OPENERS = [
    "Does {name} use 3D visuals when presenting projects to clients?",
    "Quick question about project visuals at {name}.",
    "Do you outsource 3D visuals for client projects, or is it done in house?",
    "Do you ever need visuals for a project that is still at the drawing stage?",
    "When a project is still at the drawing stage, how does a client get a sense of the result?",
    "Do clients ever ask you for a picture of the finished space before work starts?",
]
OFFERS = [
    "I make 3D renders of interiors and exteriors from plans, sketches or photos, so clients can see the finished "
    "space before anything is built.",
    "I create realistic 3D renders for {trade}: interior and exterior views built from your plans or sketches.",
    "I do 3D interior and exterior renders for {trade}. You send plans, sketches or reference photos, and I turn "
    "them into images your clients can react to.",
    "I make 3D renders for {trade}, so a client can see a finished interior or exterior before work begins.",
    "I'm a 3D artist and I make interior and exterior renders for {trade}, from plans, sketches or photos.",
    "For {trade} I produce 3D renders of rooms, buildings and outdoor spaces from drawings or reference photos.",
    "I make 3D renders from plans, sketches or reference photos: interior and exterior views your clients can look "
    "at before anything is built.",
]
CLOSERS = [
    "If you'd like to see some of my work, reply \"samples\" and I'll send a few examples.",
    "Would a few samples be useful? Reply \"samples\" and I'll send some.",
    "Is that something you'd want help with on an upcoming project?",
    "Want me to send a few samples?",
    "If a project is coming up, I can quote from the plans.",
    "I can send a few samples if that would help. Just reply \"samples\".",
    "Is there a project coming up where visuals would help?",
]

# One follow up, written to stand alone so any follow up pairs with any first email. No opt out sentence in the
# body, the footer already carries it.
FOLLOWUPS = [
    "Following up on my note about 3D renders for {name}. If a project needs visuals, reply \"samples\" and I'll send "
    "a few examples.",
    "I wanted to close the loop on my note about 3D renders. If visuals are already covered, ignore this. If not, "
    "I'm happy to send some samples.",
    "One last note from me on 3D visuals. Reply \"samples\" if you'd like to see some examples, otherwise I'll leave "
    "it there.",
]


def _rnd(seed: str, slot: str) -> random.Random:
    return random.Random(f"{seed}:{slot}")


def build_first(niche_key: str, name: str, owner_name: Optional[str], country: Optional[str],
                seed: str) -> Tuple[str, str]:
    """Returns (subject, body) WITHOUT the footer. `seed` should be the lead's domain, so the same lead always
    gets the same email between preview and send."""
    key = niche_key if niche_key in SUBJECTS else "default"
    ok = name_is_usable(name)
    shown = name if ok else UNUSABLE_NAME
    pool = SUBJECTS[key]
    if not ok:
        pool = [s for s in pool if "{name}" not in s and "{poss}" not in s] or pool
    poss = shown + ("'" if shown.endswith("s") else "'s")  # "BuildLabs' projects", not "BuildLabs's"
    subject = _rnd(seed, "subject").choice(pool).format(name=shown, poss=poss)
    trade = TRADE_PHRASE.get(key, TRADE_PHRASE["default"])
    openers = NICHE_OPENERS[key] + GENERIC_OPENERS
    if not ok:
        openers = [o for o in openers if "{name}" not in o]
    parts = (_rnd(seed, "opener").choice(openers), _rnd(seed, "offer").choice(OFFERS),
             _rnd(seed, "closer").choice(CLOSERS))
    body = "\n\n".join(p.format(name=shown, trade=trade) for p in parts)
    return subject, f"{greeting(owner_name, country)}\n\n{body}"


def build_followup(name: str, owner_name: Optional[str], country: Optional[str], seed: str,
                   first_subject: str) -> Tuple[str, str]:
    """Returns ('Re: ' + the subject that was actually sent, body) WITHOUT the footer."""
    ok = name_is_usable(name)
    shown = name if ok else UNUSABLE_NAME
    pool = FOLLOWUPS if ok else ([f for f in FOLLOWUPS if "{name}" not in f] or FOLLOWUPS)
    text = _rnd(seed, "followup").choice(pool).format(name=shown)
    return "Re: " + first_subject, f"{greeting(owner_name, country)}\n\n{text}"


# ---------------------------------------------------------------- self test and preview
def _self_test() -> int:
    problems: List[str] = []
    names = ["Harbor Interiors", "BuildLabs", UNUSABLE_NAME]
    owners = [(None, "AE"), ("Sam Carter", "US"), ("Dr Khan", "US"), ("Abdul Rahman Al Falasi", "AE"), ("INFO", "US")]
    count = 0
    for key in list(SUBJECTS):
        for nm in names:
            for own, ctry in owners:
                for i in range(40):
                    seed = f"{key}-{i}.example"
                    subj, body = build_first(key, nm, own, ctry, seed)
                    fs, fb = build_followup(nm, own, ctry, seed, subj)
                    count += 1
                    for label, text in (("subject", subj), ("body", body), ("follow up", fb)):
                        if re.search(r"[{}]", text):
                            problems.append(f"unrendered slot in {label}: {text[:80]!r}")
                        if "your business's" in text.lower() or "hi there" in text.lower() or "s's " in text:
                            problems.append(f"awkward text in {label}: {text[:80]!r}")
                        if "!" in text or "free" in text.lower() or "guarantee" in text.lower():
                            problems.append(f"spammy word in {label}: {text[:80]!r}")
                    if len(body.split()) > 75:
                        problems.append(f"body too long ({len(body.split())} words): {body[:60]!r}")
                    if nm == UNUSABLE_NAME and ("{name}" in subj or "{poss}" in subj):
                        problems.append("name slot in subject for unusable name")
                    if nm == UNUSABLE_NAME and "your business" in (subj + body + fb).lower():
                        problems.append(f"'your business' still shown: {body[:80]!r}")
    # niche detection and filters
    checks = [
        (detect_niche("architecture firm", "X", "x.com"), "architect"),
        (detect_niche(None, "Palm Landscape & Pools", "palm.com"), "landscape"),
        (detect_niche(None, "Acme Building Co", "acme.com"), "builder"),
        (detect_niche(None, "Zed", "zed.com"), "default"),
    ]
    for got, want in checks:
        if got != want:
            problems.append(f"detect_niche gave {got}, wanted {want}")
    for nm, dm, want in (("Pixel Render Studio", "pixelrender.com", True), ("Houzz", "houzz.com", True),
                         ("Harbor Interiors", "harborinteriors.com", False), ("Arch Visualisation", "av.com", True)):
        if bool(render3d_junk_reason(nm, dm)) != want:
            problems.append(f"junk filter wrong for {nm}")
    sig = {"reachable": True, "runs_ads": False, "has_contact_form": True}
    sig.update(analyse_html_render3d({"": "<title>Harbor Interiors</title> Our work: new development coming soon"}))
    sc, _ = score_render3d(sig, {}, {})
    if sc < MIN_SCORE:
        problems.append(f"portfolio + pre build + contact scored only {sc}")
    sig2 = {"reachable": True}
    sig2.update(analyse_html_render3d({"": "<title>Best 3D Rendering Studio</title> 3D renders"}))
    if score_render3d(sig2, {}, {})[0] != 0:
        problems.append("render studio site was not skipped")

    def grams(t: str) -> set:
        w = re.findall(r"[a-z']+", t.lower())
        return {tuple(w[i:i + 4]) for i in range(len(w) - 3)}
    for key in ("interior", "developer"):
        bodies, subjects = [], set()
        for i in range(300):
            sj, b = build_first(key, "Acme", None, "US", f"d{i}.com")
            bodies.append(b.split("\n\n", 1)[1])
            subjects.add(sj)
        day = bodies[:30]
        sims = [len(grams(day[a]) & grams(day[b])) / max(1, len(grams(day[a]) | grams(day[b])))
                for a in range(len(day)) for b in range(a + 1, len(day))]
        print(f"{key}: {len(set(bodies))} distinct bodies and {len(subjects)} subjects over 300 leads; "
              f"avg overlap on one day {sum(sims) / len(sims):.2f}, worst {max(sims):.2f}")
    print(f"rendered {count} combinations, {len(problems)} problems")
    for p in problems[:15]:
        print("  -", p)
    return len(problems)


if __name__ == "__main__":
    bad = _self_test()
    footer = "\n\nSender Name\nBusiness Name · <postal address>\nNot relevant? Reply \"stop\" and I won't email you again."
    for key, nm, own, ctry, seed in (("interior", "Harbor Interiors", "Sam Carter", "US", "harborinteriors.com"),
                                      ("developer", "Skyline Developments", None, "AE", "skylinedev.ae"),
                                      ("remodel", UNUSABLE_NAME, None, "AU", "kitchenco.com.au")):
        s, b = build_first(key, nm, own, ctry, seed)
        fs, fb = build_followup(nm, own, ctry, seed, s)
        print("=" * 60, f"\n[{key}] Subject: {s}\n\n{b}{footer}\n\n--- follow up ---\nSubject: {fs}\n\n{fb}{footer}\n")
    raise SystemExit(1 if bad else 0)
