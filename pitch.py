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
        "Saw that {name} runs online ads. That makes every missed call a paid lead walking over to a competitor.",
        "{name} is paying for ads, which really means paying for phone calls. The ones nobody picks up usually "
        "book with whoever answers next.",
    ],
    "calls_only": [
        "Your website sends every new customer to the phone. No booking form, no chat. So when nobody can pick up, "
        "that job usually goes to whoever answers next.",
        "On your site the phone is the only way in. That works right up until you're busy and the next customer "
        "hears voicemail and hangs up.",
    ],
    "busy": [
        "With the reviews {name} has, the phone must ring a lot, often while you're out on a job.",
    ],
}
REC_NICHE_HOOKS = {
    "trades": [
        "Most people with an urgent problem call the first company they find. If nobody picks up, they ring the next "
        "one within a minute.",
        "When you're up a ladder or under a sink, you can't answer the phone. That's exactly when new customers call.",
    ],
    "restoration": [
        "When water is coming through a ceiling at 10pm, people keep calling until someone answers. The first company "
        "to pick up usually gets the job.",
    ],
    "dental": [
        "When a new patient calls and gets voicemail, most don't leave a message. They book with the next practice.",
        "The front desk can't answer the phone while checking someone in, and new patients rarely call back.",
    ],
    "legal": [
        "Most people looking for a lawyer call two or three firms. The first one that answers usually gets the case.",
    ],
    "default": [
        "Most customers who hit voicemail don't leave a message. They just call someone else.",
    ],
}
REC_OFFERS = [
    "I set up AI receptionists that answer every call in your business name, day or night, and text you the "
    "caller's details within a minute.",
    "I build AI receptionists that pick up when your team can't, take down the job, and send you a short summary "
    "straight away.",
]
REC_CLOSERS = [
    "Want me to send a 60 second sample call so you can hear it?",
    "Is this a problem for you, or is the phone already covered?",
    "Worth a quick look?",
    "How are you handling the calls you can't pick up right now?",
]
REC_SUBJECTS = {
    "default": ["missed calls at {name}", "after-hours calls", "calls you can't pick up",
                "quick question about your phones"],
    "dental": ["new patient calls at {name}", "calls during busy hours", "quick question about your phones"],
    "legal": ["first calls from new clients", "missed enquiries at {name}", "quick question about your phones"],
}

# --------------------------------------------------------------------------- whatsapp
WA_HOOKS = {
    "wa_link": [
        "Your site sends customers straight to WhatsApp. Great, until ten chats arrive at once and they all land on "
        "one person's phone.",
        "Saw the WhatsApp button on your site. On busy days and after hours, those chats wait, and that's usually "
        "when customers move on.",
    ],
    "ads": [
        "{name} is running ads, and a lot of those clicks turn into WhatsApp chats. Every hour a chat waits, the sale "
        "gets less likely.",
    ],
    "commerce_no_chat": [
        "Customers can buy or book on your site, but there's no instant answer when they have a quick question. "
        "That's where a lot of them drop off.",
    ],
    "wa_mention": [
        "Saw that {name} takes enquiries on WhatsApp. Customers there expect a reply in minutes, not hours.",
    ],
}
WA_GENERIC_HOOKS = [
    "Most customers would rather send a WhatsApp than call, and they expect a reply in minutes. Slow answers quietly "
    "lose sales.",
    "A customer who messages on WhatsApp and waits hours for an answer has usually bought elsewhere by the time "
    "someone replies.",
]
WA_OFFERS = [
    "I set up the official WhatsApp Business API: one number your whole team answers from, plus instant automatic "
    "replies to common questions like prices, hours and bookings, day or night.",
    "I set up the official WhatsApp Business API, so your team shares one inbox and routine questions get answered "
    "automatically, even at 2am.",
]
WA_CLOSERS = [
    "Who handles your WhatsApp chats right now?",
    "Worth a quick look?",
    "Is this something you've been meaning to sort out?",
]
WA_SUBJECTS = {
    "default": ["WhatsApp at {name}", "slow WhatsApp replies", "quick question about WhatsApp"],
    "wa_link": ["your WhatsApp chats", "the WhatsApp button on your site", "quick question about WhatsApp"],
}

# --------------------------------------------------------------------------- 3D renders
R3_HOOKS = {
    "prebuild": [
        "Saw that {name} has projects that aren't built yet. Buyers commit faster when they can see the finished "
        "space, not just a plan.",
        "Getting a yes on a project that only exists on paper is hard, and that's where a lot of deals stall.",
    ],
    "renders": [
        "Saw you already use visuals in your presentations. When your usual artist is booked up, a reliable second "
        "option keeps projects moving.",
    ],
    "portfolio": [
        "Your finished projects look great. The catch is that the next client has to say yes before there's anything "
        "to photograph.",
    ],
}
R3_NICHE_HOOKS = {
    "interior": ["Most clients struggle to picture a room from a mood board or a floor plan, and that doubt slows "
                 "sign-off."],
    "architect": ["A lot of clients can't really read drawings, so they hesitate, or ask for changes late when "
                  "changes cost the most."],
    "builder": ["Homeowners find it hard to commit to a build they can't picture, so decisions drag on."],
    "remodel": ["Homeowners find it hard to say yes to a kitchen or bathroom they can't picture."],
    "developer": ["Off-plan buyers hesitate when all they have is a floor plan and a promise."],
    "landscape": ["Clients rarely picture a garden or pool design from a sketch, so saying yes is hard."],
    "default": ["Clients find it hard to say yes to a space they can't picture, so decisions drag on."],
}
R3_OFFERS = [
    "I create realistic 3D renders of interiors and exteriors from your plans or sketches, so clients see exactly "
    "what they're getting and decide faster.",
    "I turn plans and sketches into realistic 3D renders, so your clients see the finished space before work starts.",
]
R3_CLOSERS = [
    "Want to see a couple of recent examples?",
    "Got a project coming up where this would help?",
    "Worth a quick look?",
]
R3_SUBJECTS = {
    "default": ["renders for {name}", "visuals before it's built", "your next client presentation"],
    "developer": ["selling projects before they're built", "visuals for off-plan buyers", "renders for {name}"],
    "prebuild": ["your upcoming projects", "visuals before it's built", "renders for {name}"],
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
    if hello == "Hello," and ok and len(shown) <= 30:
        hello = f"Hi {shown} team,"  # warmer than a bare "Hello," when we know the business but not a person
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
