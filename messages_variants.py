"""
Wording pools for first emails and follow ups. Pure functions, no imports from the rest of the tool.

Why this file exists: the old copy was one body per service, so 30 emails a day from one Gmail inbox shared
about 98% of their words. Mailbox providers cluster near identical mail, so each email now picks, from the
business domain, one subject, one body and one follow up out of separate pools. The same lead always gets the
same pick (stable between preview and send), and different leads read differently.

Rules the wording follows:
  no claim that the sender has done this for others, no invented numbers, no claim about the lead's business that
  was not found on its site, no assumption that the lead has voicemail or WhatsApp unless the scraper saw it,
  nothing that reads wrongly when the name is unusable ("your business"), one small question as the only ask.

Duties the wording creates (both must exist before the first send):
  1. a short sample call recording the sender can send when someone replies "demo"
  2. a one page outline of the WhatsApp setup, with the price, for replies that ask for the outline

Run   python messages_variants.py   to render every variant and run the self test.
"""
import random
import re
from typing import Dict, List, Optional, Tuple

UNUSABLE_NAME = "your business"

# Markets where a first name is the normal way to greet a stranger. Elsewhere a plain "Hello," is safer than
# guessing which part of a name is the given name.
GIVEN_NAME_FIRST = {"US", "CA", "AU", "NZ", "UK", "IE"}
ROLE_WORDS = {"admin", "info", "sales", "team", "manager", "owner", "office", "support", "contact", "hello", "mail",
              "enquiries", "inquiries", "reception", "booking", "bookings", "service", "services"}
HONORIFICS = {"dr", "mr", "mrs", "ms", "miss", "prof", "eng", "sheikh", "capt", "sir"}


def greeting(owner_name: Optional[str], country: Optional[str]) -> str:
    """'Hi Sam,' only when the name is a plain given name in a market that uses them first. Otherwise 'Hello,'."""
    if not owner_name or (country or "").upper() not in GIVEN_NAME_FIRST:
        return "Hello,"
    parts = [p for p in re.split(r"\s+", owner_name.strip()) if p]
    if parts and parts[0].strip(".").lower() in HONORIFICS:
        return "Hello,"  # "Dr Khan" -> we cannot tell a given name from a surname
    if len(parts) < 2:
        return "Hello,"
    first = parts[0]
    if not re.fullmatch(r"[A-Za-z][A-Za-z'’-]{1,24}", first) or first.lower() in ROLE_WORDS or first.isupper():
        return "Hello,"
    return f"Hi {first.capitalize()},"


# ---------------------------------------------------------------- subjects
# Short, descriptive, honest about being a sales note. Only some carry the business name; when the name is
# unusable the name free ones are used.
SUBJECTS: Dict[str, List[str]] = {
    "receptionist": [
        "calls when you're on a job", "who answers the phone at {name}?", "AI phone answering for {name}",
        "when the phone rings mid-job", "phone calls outside office hours",
    ],
    "receptionist_dental": [
        "new patient calls at {name}", "phones during lunch at {name}", "when the front desk is busy",
        "AI phone answering for {name}", "calls after the office closes",
    ],
    "receptionist_legal": [
        "new client calls at {name}", "first calls from new clients", "who answers the phone at {name}?",
        "AI phone answering for {name}", "after-hours calls at {name}",
    ],
    "whatsapp_api": [
        "WhatsApp at {name}", "WhatsApp messages after hours", "one WhatsApp inbox for the team",
        "{name} on WhatsApp", "official WhatsApp Business API for {name}",
    ],
    "whatsapp_seen": [
        "the WhatsApp link on your website", "WhatsApp chats at {name}", "who answers your WhatsApp chat?",
        "sharing the WhatsApp chat inbox", "about the chat link on your site",
    ],
}

# ---------------------------------------------------------------- who is answering the phone (receptionist)
WHO_LINES: Dict[str, List[str]] = {
    "trades": [
        "When you're on a job and the phone rings, who picks up?",
        "What happens to calls that come in while the crew is out on jobs?",
        "If a new customer calls while you're with another one, who answers?",
    ],
    "restoration": [
        "When an urgent call comes in at night, who answers?",
        "If a call comes in while the crew is out on a job, who picks up?",
        "Who answers when someone calls about an urgent problem at 10pm?",
    ],
    "dental": [
        "When the front desk is with a patient and the phone rings, who picks up?",
        "What happens to a new patient's call over lunch or after closing?",
        "If the front desk is tied up, who answers the phone?",
    ],
    "legal": [
        "When you're with a client and a new enquiry calls, who picks up?",
        "What happens to a first call from a potential client when nobody is free to answer?",
        "If a new enquiry comes in after hours, who answers?",
    ],
    "default": [
        "When the phone rings and everyone is busy, who picks up?",
        "What happens to calls that come in when nobody is free to answer?",
        "If a new customer calls while the team is tied up, who answers?",
    ],
}

# ---------------------------------------------------------------- bodies (greeting and footer are added outside)
# A body is three independent pieces: an opener, an offer sentence and a closing ask. Each piece stands alone, so any
# opener can pair with any offer and any closer. That gives 60+ different emails per service from a handful of
# hand written lines, with a different structure each time, not word swaps.
# Slots: {name} {noun} {trade}. Every piece reads correctly with name = "your business".
RECEPTIONIST_OPENERS = [
    "What happens when a call to {name} reaches voicemail?",
    "When a caller can't reach anyone at {name}, do they usually leave a message?",
]  # plus three niche lines from WHO_LINES, chosen in build_first
RECEPTIONIST_OFFERS = [
    "I set up an AI phone assistant that picks up when you can't. It takes the caller's name, number and what they "
    "need, then sends you a short summary.",
    "I offer an AI phone assistant for {trade}. It answers calls that would otherwise go to voicemail, collects the "
    "caller's name, number and reason for calling, and sends you the details.",
    "I'm a one-person studio and I set up AI phone assistants that answer calls you can't get to, note who called "
    "and why, and send you the details.",
    "I set up an AI phone assistant that answers, notes who called and why, and sends you the details.",
]
RECEPTIONIST_CLOSERS = [
    "If you'd like to hear a sample call, reply \"demo\" and I'll send a short recording.",
    "Would hearing a sample call be useful? Reply \"demo\" and I'll send one.",
    "Want me to send a sample call so you can hear it?",
    "Is that something you'd want covered, or is the phone already handled?",
]

WHATSAPP_OPENERS = [
    "When someone messages {name} on WhatsApp at night, what happens to that message?",
    "Does one person at {name} handle WhatsApp messages, or does a team share them?",
    "Is WhatsApp a busy channel for {name}?",
    "Quick question about WhatsApp at {name}.",
]
WHATSAPP_OFFERS = [
    "I can set up the official WhatsApp Business API for {noun}: automatic replies to common questions, and one "
    "shared inbox the whole team answers from.",
    "With the official WhatsApp Business API, a team shares one inbox and routine questions, like opening hours or "
    "prices, get an automatic reply. I set that up for {noun}.",
    "The free WhatsApp Business app only lets a few devices share one number. The official API has no such limit "
    "and can connect to your booking system or CRM. I set it up for {noun}.",
    "I set up the official WhatsApp Business API for {noun}, so several people answer from one shared inbox and "
    "routine questions get an automatic reply.",
]
WHATSAPP_CLOSERS = [
    "Would a short outline of how that would work be useful?",
    "Should I send a short outline?",
    "If it's relevant, I can send a short outline of how it works and what it costs.",
    "Worth a quick look?",
]

SEEN_OPENERS = [
    "I noticed your website has a WhatsApp chat link. When someone taps it, does the message go to one person's "
    "phone or to a team?",
    "Your website sends people to WhatsApp, so it's clearly a channel for {name}. Do those chats land on one phone, "
    "or does a team share them?",
    "Does a team share the chats that come in through the WhatsApp link on your website, or does one phone catch "
    "everything?",
]
SEEN_OFFERS = [
    "I set up the official WhatsApp Business API, so several people can answer from one shared inbox and routine "
    "questions get an automatic reply.",
    "The official WhatsApp Business API gives a shared inbox and automatic replies for routine questions. I can set "
    "that up for you.",
    "The official WhatsApp Business API lets a whole team answer from one number, with automatic replies for "
    "routine questions. I set that up.",
]
SEEN_CLOSERS = [
    "Should I send a short outline?",
    "I can send a short outline of how it works.",
    "Worth a quick look?",
]

# The one follow up. Written to stand alone (it never refers to a detail of the first email), so any follow up
# can pair with any first email. No opt out sentence in the body, the footer already carries it.
FOLLOWUPS = {
    "receptionist": [
        "Following up on my note about calls at {name}. If it would help to hear what a call sounds like, reply "
        "\"demo\" and I'll send a short recording.",
        "I wanted to close the loop on my note about phone calls. If the phone is already covered, ignore this. If "
        "not, I'm happy to send a sample call.",
        "One last note from me on phone answering. Reply \"demo\" if you'd like a short sample call, otherwise I'll "
        "leave it there.",
    ],
    "whatsapp_api": [
        "Following up on my note about WhatsApp at {name}. Is it mostly one person answering from a single phone, or "
        "does a team already share it?",
        "I wanted to close the loop on my WhatsApp note. If a short outline of how a shared inbox would work would "
        "help, reply \"outline\" and I'll send it.",
        "One last note from me on WhatsApp. Reply \"outline\" if you'd like the short version of how it would work, "
        "otherwise I'll leave it there.",
    ],
}


def name_is_usable(name: str) -> bool:
    return bool(name) and name.strip().lower() != UNUSABLE_NAME


def _rnd(seed: str, slot: str) -> random.Random:
    return random.Random(f"{seed}:{slot}")


def _noun(noun: Optional[str]) -> str:
    return noun if noun else "businesses"


def build_first(service_id: str, niche_key: str, noun: str, trade: str, name: str, owner_name: Optional[str],
                country: Optional[str], seen: bool, seed: str) -> Tuple[str, str]:
    """Returns (subject, body) WITHOUT the footer. `seed` should be the lead's domain."""
    ok = name_is_usable(name)
    shown = name if ok else UNUSABLE_NAME
    if service_id == "receptionist":
        pool = SUBJECTS.get(f"receptionist_{niche_key}", SUBJECTS["receptionist"])
    else:
        pool = SUBJECTS["whatsapp_seen" if seen else "whatsapp_api"]
    if not ok:
        pool = [s for s in pool if "{name}" not in s] or pool
    subject = _rnd(seed, "subject").choice(pool).format(name=shown)

    if service_id == "receptionist":
        openers = WHO_LINES.get(niche_key, WHO_LINES["default"]) + RECEPTIONIST_OPENERS
        parts = (_rnd(seed, "opener").choice(openers), _rnd(seed, "offer").choice(RECEPTIONIST_OFFERS),
                 _rnd(seed, "closer").choice(RECEPTIONIST_CLOSERS))
    elif seen:
        parts = (_rnd(seed, "opener").choice(SEEN_OPENERS), _rnd(seed, "offer").choice(SEEN_OFFERS),
                 _rnd(seed, "closer").choice(SEEN_CLOSERS))
    else:
        parts = (_rnd(seed, "opener").choice(WHATSAPP_OPENERS), _rnd(seed, "offer").choice(WHATSAPP_OFFERS),
                 _rnd(seed, "closer").choice(WHATSAPP_CLOSERS))
    body = "\n\n".join(p.format(name=shown, noun=_noun(noun), trade=trade or "local businesses") for p in parts)
    return subject, f"{greeting(owner_name, country)}\n\n{body}"


def build_followup(service_id: str, name: str, owner_name: Optional[str], country: Optional[str], seed: str,
                   first_subject: str) -> Tuple[str, str]:
    """Returns ('Re: ' + the subject that was actually sent, body) WITHOUT the footer."""
    shown = name if name_is_usable(name) else UNUSABLE_NAME
    text = _rnd(seed, "followup").choice(FOLLOWUPS[service_id]).format(name=shown)
    return "Re: " + first_subject, f"{greeting(owner_name, country)}\n\n{text}"


# ---------------------------------------------------------------- self test and preview
def _self_test() -> int:
    problems = []
    names = ["Response Plumbing", UNUSABLE_NAME]
    owners = [(None, "AE"), ("Sam Carter", "US"), ("Dr Khan", "US"), ("Abdul Rahman Al Falasi", "AE"), ("INFO", "US")]
    combos = [("receptionist", k, "local businesses") for k in ["trades", "restoration", "dental", "legal", "default"]]
    combos += [("whatsapp_api", "x", n) for n in ["online stores", "clinics", "salons", "businesses"]]
    count = 0
    for service, key, noun in combos:
        for nm in names:
            for own, ctry in owners:
                for seen in ([False] if service == "receptionist" else [False, True]):
                    for i in range(40):
                        seed = f"{service}-{key}-{i}.example"
                        subj, body = build_first(service, key, noun, "home service companies", nm, own, ctry, seen, seed)
                        fs, fb = build_followup(service, nm, own, ctry, seed, subj)
                        count += 1
                        for label, text in (("subject", subj), ("body", body), ("follow up", fb)):
                            if re.search(r"[{}]", text):
                                problems.append(f"unrendered slot in {label}: {text[:80]!r}")
                            if "  " in text.replace("\n", " ").strip() and "   " in text:
                                problems.append(f"double spaces in {label}")
                            if "your business's" in text.lower() or "hi there" in text.lower():
                                problems.append(f"awkward text in {label}: {text[:80]!r}")
                        words = len(body.split())
                        if words > 75:
                            problems.append(f"body too long ({words} words): {body[:60]!r}")
                        if "!" in subj + body + fb or any(w.isupper() and len(w) > 3 and w not in ("WHATSAPP",) for w in (subj + " " + body).split()):
                            if "API" not in subj + body and "CRM" not in body:
                                problems.append(f"shouting or exclamation: {body[:60]!r}")
                        if nm == UNUSABLE_NAME and "{name}" in subj:
                            problems.append("name slot in subject for unusable name")
    # spread over a day of 30 sends: distinct bodies and how alike they are (4 word sequence overlap)
    def grams(t):
        w = re.findall(r"[a-z']+", t.lower())
        return {tuple(w[i:i + 4]) for i in range(len(w) - 3)}
    for service, key, noun in (("receptionist", "trades", "x"), ("whatsapp_api", "x", "clinics")):
        bodies, subjects = [], set()
        for i in range(300):
            sj, b = build_first(service, key, noun, "home service companies", "Acme", None, "US", False, f"d{i}.com")
            bodies.append(b.split("\n\n", 1)[1]); subjects.add(sj)
        day = bodies[:30]
        sims = []
        for a in range(len(day)):
            for b2 in range(a + 1, len(day)):
                ga, gb = grams(day[a]), grams(day[b2])
                sims.append(len(ga & gb) / max(1, len(ga | gb)))
        print(f"{service}: {len(set(bodies))} distinct bodies and {len(subjects)} subjects over 300 leads; "
              f"avg overlap between two sends on the same day {sum(sims)/len(sims):.2f}, worst {max(sims):.2f}")
    print(f"rendered {count} combinations, {len(problems)} problems")
    for p in problems[:15]:
        print("  -", p)
    return len(problems)


if __name__ == "__main__":
    bad = _self_test()
    footer = "\nSamuel Gansallo\nIffy Studios · <your postal address>\nNot relevant? Reply \"stop\" and I won't email you again."
    for service, key, noun, own, ctry, seen in (("receptionist", "dental", "clinics", "Sam Carter", "US", False),
                                                  ("whatsapp_api", "x", "clinics", None, "AE", False),
                                                  ("whatsapp_api", "x", "businesses", None, "AE", True)):
        s, b = build_first(service, key, noun, "dental practices", "Bright Smile Dental", own, ctry, seen, "brightsmile.com")
        fs, fb = build_followup(service, "Bright Smile Dental", own, ctry, "brightsmile.com", s)
        print("=" * 60, f"\n[{service}{' / seen' if seen else ''}] Subject: {s}\n\n{b}{footer}\n\n--- follow up ---\nSubject: {fs}\n\n{fb}{footer}\n")
    raise SystemExit(1 if bad else 0)
