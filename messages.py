"""
First emails and the one follow up, per service. The wording itself lives in messages_variants.py: every lead
gets one subject, one body and one follow up picked from its domain out of separate pools, so 30 emails a day
from one inbox do not read alike. This file only works out what to say about each lead:

  the niche (dental, trades, clinics ...) from the scouting keyword, the plural noun for that niche,
  whether the site has a WhatsApp chat link, and whether the stored name is a real business name.

When the stored name is really a search result title ("Ecommerce Website", "Emergency Plumber Adelaide"),
the email says "your business" and uses a subject without a name.

Plain text, no links. Rules: no fake replies or history, no invented numbers or results, no claims about the
business that were not found on its site, and a plain way to say no (the footer, added in outreach.py).

See sample emails:   python messages.py
"""
import json
import os
from typing import Any, Dict, Optional, Tuple

from messages_variants import UNUSABLE_NAME, build_first, build_followup

# niche key: (keyword needles, plural noun used in the email)
WHATSAPP_NICHES = {
    "ecommerce": (["ecommerce", "store", "shop"], "online stores"),
    "clinic": (["dental", "med spa", "clinic", "dentist", "medical"], "clinics"),
    "beauty": (["beauty", "salon", "spa"], "salons"),
    "realestate": (["real estate", "property", "agency"], "agencies"),
    "travel": (["travel", "tour"], "travel businesses"),
    "school": (["school", "academy", "language", "education", "college"], "schools"),
    "auto": (["car", "dealership", "auto", "motor"], "dealerships"),
    "fitness": (["fitness", "gym", "studio", "yoga"], "studios"),
    "furniture": (["furniture", "home", "interior"], "furniture stores"),
    "food": (["restaurant", "delivery", "food", "cafe"], "restaurants"),
}
RECEPTIONIST_NICHES = {
    "trades": (["plumber", "hvac", "electrician", "garage door", "contractor", "repair"], "home service companies"),
    "restoration": (["restoration", "water damage", "pest"], "emergency repair companies"),
    "dental": (["dentist", "dental", "cosmetic"], "dental practices"),
    "legal": (["lawyer", "attorney", "legal", "law"], "law firms"),
}
PACKS = {"whatsapp_api": WHATSAPP_NICHES, "receptionist": RECEPTIONIST_NICHES}

GENERIC_NAME_WORDS = {
    "ecommerce", "e-commerce", "online", "store", "stores", "shop", "website", "websites", "official", "site", "services",
    "service", "solutions", "company", "companies", "best", "top", "near", "you", "me", "emergency", "repair", "repairs",
    "plumber", "plumbers", "plumbing", "hvac", "electrician", "electricians", "contractor", "contractors", "dentist",
    "dental", "clinic", "clinics", "lawyer", "lawyers", "attorney", "attorneys", "agency", "agencies", "real", "estate",
    "travel", "school", "schools", "salon", "salons", "spa", "fitness", "studio", "furniture", "restaurant", "delivery",
    "pest", "control", "garage", "door", "doors", "water", "damage", "restoration", "car", "dealership", "dealer",
    "in", "the", "and", "&", "of", "for", "your", "24/7", "24", "hour", "local", "home", "page", "logo", "find",
    "architect", "architects", "architecture", "interior", "interiors", "design", "designer", "designers", "builder",
    "builders", "custom", "luxury", "homes", "construction", "renovation", "remodeling", "kitchen", "bathroom",
    "developer", "developers", "property", "landscape", "landscaping", "pool", "outdoor", "living", "fit", "out", "firm",
}
NAME_PLACES = (
    "australia", "oman", "bahrain", "uae", "emirates", "dubai", "abu dhabi", "sharjah", "saudi", "riyadh", "jeddah",
    "qatar", "doha", "kuwait", "singapore", "malaysia", "kuala lumpur", "united states", "usa", "canada", "new zealand",
    "toronto", "vancouver", "montreal", "calgary", "sydney", "melbourne", "brisbane", "perth", "adelaide", "auckland",
    "wellington", "new york", "los angeles", "chicago", "houston", "dallas", "miami", "ireland", "dublin",
)


def display_name(name: Optional[str]) -> Optional[str]:
    """The business name, or None when the stored name is really a search result title
    ("Ecommerce Website", "Emergency Plumber Adelaide", "Toronto Plumber Near You")."""
    n = (name or "").strip()
    low = n.lower()
    if not n or len(n) > 40 or len(low.split()) > 5:
        return None
    spaced = " " + "".join(c if c.isalnum() else " " for c in low) + " "
    if any(f" {p} " in spaced for p in NAME_PLACES):
        return None
    words = [w.strip(".,:;|-()") for w in low.split()]
    if all(w in GENERIC_NAME_WORDS for w in words if w):
        return None
    return n


def _pick_niche(service_id: str, keyword: str) -> Tuple[str, str]:
    """(niche key, plural noun) for the scouting keyword. Falls back to a plain noun, never a wrong niche."""
    kw = (keyword or "").lower()
    for key, (needles, noun) in PACKS[service_id].items():
        if any(n in kw for n in needles):
            return key, noun
    return ("default", "local businesses") if service_id == "receptionist" else ("default", "businesses")


def _seed(lead: Dict[str, Any]) -> str:
    return (lead.get("domain") or lead.get("name") or "").lower()


def compose(service_id: str, lead: Dict[str, Any], footer_text: str) -> Optional[Tuple[str, str]]:
    """First email: a pain point hook built from what the scout found on the lead's site (pitch.py), what changes
    for them, and one easy question. The same lead always gets the same email (seeded by its domain)."""
    import pitch
    if service_id not in ("whatsapp_api", "receptionist", "render_3d", "lead_gen"):
        return None
    local = _local(service_id, lead)
    if local:
        return local
    name = display_name(lead.get("name")) or UNUSABLE_NAME
    if service_id == "lead_gen":
        import leadgen
        niche = leadgen.detect_niche(lead.get("keyword"), lead.get("name"), lead.get("domain"))
        subject, body = leadgen.build_first(niche, name, lead.get("owner_name"), lead.get("country"), _seed(lead))
        return subject, _team_hello(body, name) + "\n\n" + footer_text.lstrip("\n")
    evidence = " | ".join(json.loads(lead.get("evidence_json") or "[]"))
    if service_id == "render_3d":
        import render3d
        niche = render3d.detect_niche(lead.get("keyword"), lead.get("name"), lead.get("domain"))
    else:
        niche = _pick_niche(service_id, lead.get("keyword", ""))[0]
    subject, body = pitch.build(service_id, niche, name, lead.get("owner_name"), lead.get("country"), evidence, _seed(lead))
    return subject, body + "\n\n" + footer_text.lstrip("\n")


def _local_footer(lang: str, country: Optional[str] = None) -> str:
    """The signature in the reader's language (same facts as outreach.footer: name, role, business, postal address)."""
    import localize
    import outreach
    return localize.footer(lang, outreach.SENDER_NAME, outreach.SENDER_TITLE, outreach.BUSINESS_NAME,
                           outreach.POSTAL_ADDRESS if outreach.address_needed(country) else "")


def _local(service_id: str, lead: Dict[str, Any], first_subject: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """Spanish, Portuguese or Arabic email for leads in those countries (localize.py); None means use English."""
    import localize
    lang = localize.language_for(lead.get("country"), service_id)
    if lang == "en":
        return None
    name = display_name(lead.get("name"))
    owner = lead.get("owner_name")
    if first_subject is None:
        evidence = " | ".join(json.loads(lead.get("evidence_json") or "[]"))
        subject, body = localize.build_first(lang, service_id, name, evidence, _seed(lead), owner)
    else:
        subject, body = localize.build_followup(lang, service_id, name, _seed(lead), first_subject, owner)
    return subject, body + "\n\n" + _local_footer(lang, lead.get("country"))


def _team_hello(body: str, name: str) -> str:
    """Same greeting as the first email: "Hi Glow Med Spa team," instead of a bare "Hello," when the name is usable."""
    if body.startswith("Hello,") and name != UNUSABLE_NAME and len(name) <= 30:
        return f"Hi {name} team," + body[len("Hello,"):]
    return body


def compose_followup(service_id: str, lead: Dict[str, Any], footer_text: str) -> Optional[Tuple[str, str]]:
    """The one follow up, sent as a reply in the same Gmail thread. Uses the subject that was actually sent
    (sent_subject); older leads sent before that column existed get the subject recomputed."""
    first_subject = lead.get("sent_subject")
    if not first_subject:
        composed = compose(service_id, lead, footer_text)
        first_subject = composed[0] if composed else (lead.get("name") or UNUSABLE_NAME)
    local = _local(service_id, lead, first_subject)
    if local:
        return local
    name = display_name(lead.get("name")) or UNUSABLE_NAME
    if service_id == "lead_gen":
        import leadgen
        subject, body = leadgen.build_followup(name, lead.get("owner_name"), lead.get("country"), _seed(lead), first_subject)
        return subject, _team_hello(body, name) + "\n\n" + footer_text.lstrip("\n")
    if service_id == "render_3d":
        import render3d
        subject, body = render3d.build_followup(name, lead.get("owner_name"), lead.get("country"), _seed(lead), first_subject)
        return subject, _team_hello(body, name) + "\n\n" + footer_text.lstrip("\n")
    if service_id not in PACKS:
        return None
    subject, body = build_followup(service_id, name, lead.get("owner_name"), lead.get("country"),
                                   _seed(lead), first_subject)
    return subject, _team_hello(body, name) + "\n\n" + footer_text.lstrip("\n")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    sample_footer = (f"\n{os.getenv('SENDER_NAME', 'Your Name')}\n{os.getenv('BUSINESS_NAME', 'Your Business')} · "
                     f"<your postal address>\nNot relevant? Reply \"stop\" and I won't email you again.")
    for sid, pack in PACKS.items():
        for key, (needles, noun) in pack.items():
            lead = {"name": f"Sample {key.title()}", "domain": f"sample{key}.com", "city": "General",
                    "country": "AE" if sid == "whatsapp_api" else "US", "keyword": needles[0], "evidence_json": "[]"}
            subj, body = compose(sid, lead, sample_footer)
            print("=" * 70, f"\n[{sid} / {key}]  Subject: {subj}\n\n{body}\n")
            fs, fb = compose_followup(sid, lead, sample_footer)
            print(f"--- follow up ---\nSubject: {fs}\n\n{fb}\n")
