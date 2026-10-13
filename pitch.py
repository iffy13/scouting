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
REC_HOOKS = {
    "ads": [
        "I noticed {name} runs online ads. When one of those paid calls rings out because everyone is busy, that "
        "customer usually just calls the next company on the list.",
        "{name} is paying for ads, which means paying for phone calls. Every one that goes unanswered is money spent "
        "on a customer who books with someone else.",
    ],
    "calls_only": [
        "Your site sends every new customer to the phone, with no booking form or chat. So every call that rings out "
        "is a job that probably goes to a competitor.",
        "On your website the phone is the only way in. That works until you're with a customer and the next one hears "
        "voicemail and hangs up.",
    ],
    "busy": [
        "With the number of reviews {name} has, the phone must ring a lot, including while you're out on jobs or "
        "with a customer.",
    ],
}
REC_NICHE_HOOKS = {
    "trades": [
        "Most people with an urgent problem call the first company they find. If nobody picks up, they call the next "
        "one within a minute.",
        "When you're up a ladder or under a sink, you can't answer the phone, but that's exactly when new customers "
        "call.",
    ],
    "restoration": [
        "When water is coming through a ceiling at 10pm, people keep calling until someone answers. The first company "
        "to pick up usually gets the job.",
    ],
    "dental": [
        "When a new patient calls and gets voicemail, most don't leave a message. They book with the next practice "
        "instead.",
        "The front desk can't answer the phone while checking in a patient, and new patients rarely call back.",
    ],
    "legal": [
        "Most people looking for a lawyer call two or three firms, and the first one that answers usually gets the "
        "case.",
        "A potential client who reaches voicemail on their first call rarely tries again. They call the next firm.",
    ],
    "default": [
        "Most customers who reach voicemail don't leave a message. They just call someone else.",
        "Missed calls are the most expensive thing most small businesses never measure: each one can be a customer "
        "who went elsewhere.",
    ],
}
REC_OFFERS = [
    "I set up AI receptionists that answer every call in your business name, day or night, take the details and "
    "text you a summary, so no caller slips through the cracks.",
    "I build AI phone assistants that pick up when you can't, collect the caller's details and what they need, and "
    "send them to you within a minute.",
    "I set up an AI receptionist that answers after hours and whenever the team is busy, so every caller talks to "
    "someone instead of a voicemail.",
]
REC_CLOSERS = [
    "How are you handling calls you can't pick up right now?",
    "Would you be open to a quick chat about it?",
    "Want me to send a short recording of how it sounds?",
    "Is this something you'd want covered?",
]
REC_SUBJECTS = {
    "default": ["missed calls at {name}", "calls that go to voicemail", "the calls you can't pick up",
                "after-hours calls at {name}", "who answers when you're busy?"],
    "dental": ["new patient calls at {name}", "calls during busy hours", "new patients who reach voicemail",
               "missed calls at {name}"],
    "legal": ["first calls from new clients", "missed enquiries at {name}", "when a new client calls",
              "calls that go to voicemail"],
}

# --------------------------------------------------------------------------- whatsapp
WA_HOOKS = {
    "wa_link": [
        "Your website sends customers straight to WhatsApp. That works well until several people message at once and "
        "it's all landing on one phone.",
        "I saw the WhatsApp button on your site. When those chats sit on one person's phone, replies slow down on busy "
        "days and after hours, and that's when customers move on.",
    ],
    "ads": [
        "{name} is paying for ads, and a lot of that traffic turns into WhatsApp messages. Every hour a message waits, "
        "the chance of a sale drops.",
    ],
    "commerce_no_chat": [
        "Customers can buy or book on your site, but there's no quick way to get an instant answer to a simple "
        "question, and that's where many of them drop off.",
    ],
    "wa_mention": [
        "I saw {name} takes enquiries on WhatsApp. When messages wait hours for a reply, many customers simply go with "
        "whoever answers first.",
    ],
}
WA_GENERIC_HOOKS = [
    "Many customers would rather send a WhatsApp than call, and they expect a reply in minutes. Slow answers quietly "
    "lose sales.",
    "A customer who messages on WhatsApp and waits hours for an answer has usually bought somewhere else by the time "
    "someone replies.",
]
WA_OFFERS = [
    "I set up the official WhatsApp Business API: your whole team answers from one number, and common questions like "
    "prices, hours and bookings get an instant automatic reply, day or night.",
    "With the official WhatsApp Business API, chats go to one shared team inbox, routine questions are answered "
    "automatically, and nothing gets lost on someone's personal phone. I set this up for businesses like yours.",
]
WA_CLOSERS = [
    "How are you handling WhatsApp messages at the moment?",
    "Would you be open to a quick chat about it?",
    "Is this worth a short conversation?",
    "Who answers your WhatsApp messages after hours right now?",
]
WA_SUBJECTS = {
    "default": ["WhatsApp messages at {name}", "slow WhatsApp replies", "answering WhatsApp faster",
                "WhatsApp after hours"],
    "wa_link": ["the WhatsApp button on your site", "WhatsApp chats at {name}", "slow WhatsApp replies",
                "WhatsApp after hours"],
}

# --------------------------------------------------------------------------- 3D renders
R3_HOOKS = {
    "prebuild": [
        "I saw {name} has projects that aren't built yet. Clients and buyers commit much faster when they can see the "
        "finished space instead of imagining it from a plan.",
        "Selling or getting sign-off on a project that only exists on paper is hard, and that's where many deals stall.",
    ],
    "renders": [
        "I saw you already use visuals in your presentations. When your usual renderer is booked up or slow, a second "
        "option keeps projects moving.",
    ],
    "portfolio": [
        "Your finished projects look great, but for the next one the client has to say yes before there's anything to "
        "photograph.",
    ],
}
R3_NICHE_HOOKS = {
    "interior": ["Most clients struggle to picture a room from a mood board or a floor plan, and that doubt slows "
                 "down sign-off."],
    "architect": ["Many clients can't really read drawings, so they hesitate, or ask for changes late when changes "
                  "cost the most."],
    "builder": ["Homeowners find it hard to commit to a build they can't picture, so decisions drag on."],
    "remodel": ["Homeowners find it hard to say yes to a kitchen or bathroom they can't picture, so decisions drag "
                "on."],
    "developer": ["Off-plan buyers hesitate when all they have is a floor plan and a promise."],
    "landscape": ["Clients rarely picture a garden or pool design from a sketch, so it's hard for them to say yes."],
    "default": ["Clients find it hard to say yes to a space they can't picture, so decisions drag on."],
}
R3_OFFERS = [
    "I make realistic 3D renders of interiors and exteriors from plans, sketches or photos, so your clients can see "
    "the finished result before work starts.",
    "I create realistic 3D renders from your plans or sketches, so clients see exactly what they're getting and "
    "decide faster.",
]
R3_CLOSERS = [
    "Do you have a project coming up where that would help?",
    "Would you be open to a quick chat about an upcoming project?",
    "Want me to send a few examples of my work?",
    "How do you show clients a design before it's built today?",
]
R3_SUBJECTS = {
    "default": ["helping clients picture the finished space", "visuals before it's built", "3D renders for {name}",
                "getting faster sign-off from clients"],
    "developer": ["selling projects before they're built", "visuals for off-plan buyers", "3D renders for {name}"],
    "prebuild": ["your upcoming projects", "visuals before it's built", "3D renders for {name}"],
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
                        if not ev and re.search(r"\bI (noticed|saw)\b", b):
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
