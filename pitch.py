"""
First emails built around the lead's PAIN, not our features.

Every email = hook (the problem, in one or two sentences) + outcome (what changes for them) + one easy question.

The hook uses what the scout actually found on that business's site (evidence_json): runs ads, sends people to
WhatsApp, has no booking or chat, lists projects that are not built yet, and so on. When nothing specific was found,
a niche pain line is used instead, worded as a general truth, never as something we "noticed". Nothing here claims
past clients, numbers, results or free work: no promises that have to be delivered.

Run   python pitch.py   for the self test and sample emails.
"""
import random
import re
from typing import List, Optional, Tuple

from messages_variants import UNUSABLE_NAME, greeting, name_is_usable

# --------------------------------------------------------------------------- what the scout found
FLAG_WORDS = {
    "wa_link": "whatsapp click to chat",
    "wa_mention": "mentions whatsapp",
    "no_chat": "no live chat",
    "commerce": "sells or books online",
    "ads": "ad tracking",
    "ads2": "pays for traffic",
    "calls_only": "no chat or online booking",
    "busy": "busy business by review",
    "prebuild": "upcoming, proposed or under construction",
    "renders": "already talks about renders",
    "portfolio": "shows projects",
}


def flags(evidence_text: str) -> set:
    low = (evidence_text or "").lower()
    found = {k for k, w in FLAG_WORDS.items() if w in low}
    if "ads2" in found:
        found.add("ads")
    return found


# --------------------------------------------------------------------------- receptionist
# Style rules (what top cold emailers do): under ~75 words, one idea per short paragraph, the reader's problem first,
# the outcome not the tech, and one low-effort question at the end (interest, not a meeting).
REC_HOOKS = {
    "ads": [
        "Saw that {name} runs online ads. Who answers the phone when those turn into calls?",
        "{name} is paying for ads, so I wondered who picks up when someone calls.",
    ],
    "calls_only": [
        "Your website sends new customers to the phone. Who answers when everyone is busy?",
        "On your site the phone is the only way in. What happens to the calls nobody can pick up?",
    ],
    "busy": [
        "Looks like the phone must ring a lot at {name}. Who picks up when everyone is busy?",
    ],
}
REC_NICHE_HOOKS = {
    "trades": [
        "Quick question: who answers the phone when you are on a job?",
        "When you are busy on a job, what happens to the calls that come in?",
    ],
    "restoration": [
        "Quick question: who answers when an urgent call comes in at night?",
    ],
    "dental": [
        "Quick question: who answers new patient calls when the front desk is busy?",
        "What happens to a new patient's call over lunch or after closing?",
    ],
    "legal": [
        "Quick question: who answers a new enquiry when everyone is with a client?",
    ],
    "default": [
        "Quick question: who answers the phone when everyone is busy?",
    ],
}
REC_OFFERS = [
    "I set up an AI assistant that answers those calls, takes the caller's details and sends them to you.",
    "I build a phone assistant that picks up when your team cannot and texts you who called and why.",
]
REC_CLOSERS = [
    "Would a short sample call be useful?",
    "Happy to show how it would work for {name} if useful.",
    "Would that be useful?",
]
REC_SUBJECTS = {
    "default": ["missed calls at {name}", "quick question", "your phones"],
    "dental": ["new patient calls", "quick question", "your phones"],
    "legal": ["new client calls", "quick question", "your phones"],
}

# --------------------------------------------------------------------------- whatsapp
# Same shape as a short note from a person: one question, one plain sentence about what you do, one soft ask.
# No feature lists, no "official API" wording, no selling lines. That is what keeps it in the Primary tab.
WA_HOOKS = {
    "wa_link": [
        "Saw the WhatsApp button on your site. Who answers those chats when the team is busy?",
        "Your site sends people to WhatsApp. Who answers when several chats come in at once?",
    ],
    "ads": [
        "{name} runs ads, so I wondered who answers the WhatsApp chats that come from them.",
    ],
    "commerce_no_chat": [
        "People can buy or book on your site. Who answers when they have a quick question?",
    ],
    "wa_mention": [
        "Saw that {name} takes enquiries on WhatsApp. Who answers them when the team is busy or closed?",
    ],
}
WA_GENERIC_HOOKS = [
    "Quick question: who answers your WhatsApp messages when the team is busy or closed?",
    "Quick question: what happens to a WhatsApp message that arrives at night?",
]
WA_OFFERS = [
    "I set up WhatsApp for businesses so a team shares one number and common questions get answered automatically.",
    "I help businesses set up WhatsApp so the whole team answers from one number and routine questions get an automatic reply.",
]
WA_CLOSERS = [
    "Happy to show how it would work for {name} if useful.",
    "Would that be useful?",
    "Is that something you would want to look at?",
]
WA_SUBJECTS = {
    "default": ["whatsapp chats", "quick question", "whatsapp at {name}"],
    "wa_link": ["your whatsapp chats", "the whatsapp button", "quick question"],
}

# --------------------------------------------------------------------------- 3D renders
R3_HOOKS = {
    "prebuild": [
        "Saw that {name} has projects that are not built yet. Do clients find it hard to picture the finished space?",
    ],
    "renders": [
        "Saw you already use visuals in your presentations. Is there room for a second person on renders when your usual artist is booked?",
    ],
    "portfolio": [
        "Your finished projects look good. Do you have anything to show clients before the next one is built?",
    ],
}
R3_NICHE_HOOKS = {
    "interior": ["Quick question: do your clients find it hard to picture a room from a mood board?"],
    "architect": ["Quick question: do clients struggle to read your drawings?"],
    "builder": ["Quick question: do homeowners find it hard to picture a build before it starts?"],
    "remodel": ["Quick question: do homeowners find it hard to picture a new kitchen or bathroom?"],
    "developer": ["Quick question: do off plan buyers hesitate when all they have is a floor plan?"],
    "landscape": ["Quick question: do clients find it hard to picture a garden from a sketch?"],
    "default": ["Quick question: do your clients find it hard to picture the finished space?"],
}
R3_OFFERS = [
    "I make 3D renders of interiors and exteriors from plans or sketches, so clients can see the result before work starts.",
    "I turn plans and sketches into 3D renders, so clients see the finished space before work starts.",
]
R3_CLOSERS = [
    "Happy to share a couple of examples if useful.",
    "Do you have a project coming up where that would help?",
    "Would that be useful?",
]
R3_SUBJECTS = {
    "default": ["renders for {name}", "quick question", "visuals before it is built"],
    "developer": ["off plan visuals", "quick question", "renders for {name}"],
    "prebuild": ["your upcoming projects", "quick question", "renders for {name}"],
}


# --------------------------------------------------------------------------- building
def _rnd(seed: str, slot: str) -> random.Random:
    return random.Random(f"pitch:{seed}:{slot}")


def _pick(pool: List[str], seed: str, slot: str, usable_name: bool) -> str:
    if not usable_name:
        pool = [p for p in pool if "{name}" not in p] or pool
    return _rnd(seed, slot).choice(pool)


def _hook(service: str, f: set, niche: str, seed: str, ok: bool) -> str:
    if service == "receptionist":
        order = [k for k in ("ads", "calls_only", "busy") if k in f]
        pool = [h for k in order[:1] for h in REC_HOOKS[k]]  # the strongest signal only
        generic = REC_NICHE_HOOKS.get(niche, REC_NICHE_HOOKS["default"])
    elif service == "whatsapp_api":
        order = []
        if "wa_link" in f:
            order.append("wa_link")
        if "ads" in f:
            order.append("ads")
        if "commerce" in f and "no_chat" in f:
            order.append("commerce_no_chat")
        if "wa_mention" in f and "wa_link" not in f:
            order.append("wa_mention")
        pool = [h for k in order[:1] for h in WA_HOOKS[k]]  # the strongest signal only
        generic = WA_GENERIC_HOOKS
    else:
        order = [k for k in ("prebuild", "renders", "portfolio") if k in f]
        pool = [h for k in order[:1] for h in R3_HOOKS[k]]
        generic = R3_NICHE_HOOKS.get(niche, R3_NICHE_HOOKS["default"])
    usable = [h for h in pool if ok or "{name}" not in h]
    return _rnd(seed, "hook").choice(usable or generic) if (usable or generic) else ""


def build(service: str, niche: str, name: str, owner_name: Optional[str], country: Optional[str],
          evidence_text: str, seed: str) -> Tuple[str, str]:
    """(subject, body without footer). niche: receptionist trades/restoration/dental/legal/default,
    render_3d interior/architect/builder/remodel/developer/landscape/default, whatsapp anything."""
    ok = name_is_usable(name)
    shown = name if ok else UNUSABLE_NAME
    f = flags(evidence_text)
    if service == "receptionist":
        subjects = REC_SUBJECTS.get(niche, REC_SUBJECTS["default"])
        offers, closers = REC_OFFERS, REC_CLOSERS
    elif service == "whatsapp_api":
        subjects = WA_SUBJECTS["wa_link" if "wa_link" in f else "default"]
        offers, closers = WA_OFFERS, WA_CLOSERS
    else:
        subjects = R3_SUBJECTS["prebuild" if "prebuild" in f else ("developer" if niche == "developer" else "default")]
        offers, closers = R3_OFFERS, R3_CLOSERS
    subject = _pick(subjects, seed, "subject", ok).format(name=shown)
    hook = _hook(service, f, niche, seed, ok)
    parts = [hook, _pick(offers, seed, "offer", ok), _pick(closers, seed, "closer", ok)]
    body = "\n\n".join(p.format(name=shown) for p in parts if p)
    hello = greeting(owner_name, country)
    if hello == "Hello,":
        hello = "Hi,"  # "Hi Larry team," reads like a mail merge; a plain "Hi," reads like a person
    return subject, f"{hello}\n\n{body}"


# --------------------------------------------------------------------------- self test
def _self_test() -> int:
    problems, n = [], 0
    ev_sets = ["", "uses a WhatsApp click to chat link | no live chat or bot on the site | runs ad tracking",
               "mentions WhatsApp on the site | sells or books online, so there are customer messages",
               "phone is the main contact route | no chat or online booking, calls are the only way in | pays for traffic",
               "busy business by review count", "shows projects on the site | mentions upcoming, proposed or under construction work",
               "already talks about renders or visualisation"]
    combos = [("receptionist", k) for k in ("trades", "restoration", "dental", "legal", "default")]
    combos += [("whatsapp_api", "x")]
    combos += [("render_3d", k) for k in ("interior", "architect", "builder", "remodel", "developer", "landscape", "default")]
    for svc, niche in combos:
        for nm in ("Bright Smile Dental", UNUSABLE_NAME):
            for own, c in ((None, "AE"), ("Sam Carter", "US")):
                for ev in ev_sets:
                    for i in range(15):
                        s, b = build(svc, niche, nm, own, c, ev, f"{svc}{niche}{i}.com")
                        n += 1
                        words = len(b.split())
                        if re.search(r"[{}]", s + b):
                            problems.append(f"unfilled slot: {s} / {b[:60]}")
                        if words > 95:
                            problems.append(f"{svc} too long ({words} words)")
                        if "!" in s + b:
                            problems.append("exclamation mark")
                        if not ev and re.search(r"\b(I noticed|I saw|Saw that|Saw the|Saw you)\b", b):
                            problems.append(f"claims an observation without evidence: {b[:80]}")
    print(f"rendered {n} emails, {len(problems)} problems")
    for p in problems[:10]:
        print("  -", p)
    return len(problems)


if __name__ == "__main__":
    bad = _self_test()
    footer = "\n\nSamuel\nIffy Studios · <postal address>\nNot relevant? Reply \"stop\" and I won't email you again."
    samples = [
        ("receptionist", "trades", "Bright Plumbing", "Sam Carter", "US", "phone is the main contact route | pays for traffic, missed calls cost real money"),
        ("receptionist", "dental", "Bright Smile Dental", None, "AU", ""),
        ("whatsapp_api", "x", "Glow Med Spa", None, "AE", "uses a WhatsApp click to chat link (manual WhatsApp today) | no live chat"),
        ("whatsapp_api", "x", "Al Noor Furniture", None, "SA", ""),
        ("render_3d", "developer", "Palm Villas", None, "AE", "mentions upcoming, proposed or under construction work"),
        ("render_3d", "interior", "Studio Nine", "Emma Lee", "US", ""),
    ]
    for svc, niche, nm, own, c, ev in samples:
        s, b = build(svc, niche, nm, own, c, ev, nm.lower().replace(" ", "") + ".com")
        print("=" * 64, f"\n[{svc} / {niche} / evidence: {'yes' if ev else 'none'}]\nSubject: {s}\n\n{b}{footer}\n")
    raise SystemExit(1 if bad else 0)
