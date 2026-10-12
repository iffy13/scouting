"""
Niche specific first messages.

Each business gets a message written for its own line of work, with several honest
wording variants. The variant is picked from the business domain, so the same lead
always shows the same message in preview and in send, and different leads read differently.

Rules the copy follows:
  no fake replies or fake history, no invented numbers or results, no claims about the
  business that were not found on its site, always a plain way to say no (added by footer).

See every niche and variant:   python messages.py
"""
import json
import random
import sys
from typing import Any, Dict, Optional, Tuple

# niche key: (words to match in the search keyword, how to name them, what is true for them, what we offer them)
WHATSAPP_NICHES = {
    "ecommerce": (
        ["ecommerce", "store", "shop"],
        "online stores",
        [
            "Online shoppers usually ask about stock, delivery and orders before they buy, and those chats are easy to lose when they sit on one phone.",
            "Order status and product questions arrive all day for most online stores, and answering each one by hand takes time.",
        ],
        [
            "I set up the official WhatsApp Business Platform with Meta verification, so order updates and common questions are answered automatically and the rest go to your team.",
            "I connect your store to the official WhatsApp Cloud API, with Meta business verification, for order updates, abandoned cart reminders and a shared team inbox.",
        ],
    ),
    "clinic": (
        ["dental", "med spa", "clinic", "dentist", "medical"],
        "clinics",
        [
            "Patients like to confirm, move or ask about appointments on WhatsApp, and missed messages often turn into missed bookings.",
            "Appointment questions and reminders take up a lot of front desk time in a busy clinic.",
        ],
        [
            "I set up the official WhatsApp Business Platform with Meta business verification, so booking requests, reminders and common questions are handled in one shared inbox.",
            "I connect your clinic to the official WhatsApp Cloud API, with the verified green tick, for appointment reminders and faster replies.",
        ],
    ),
    "beauty": (
        ["beauty", "salons", "spa"],
        "salon",
        [
            "Clients tend to book and rebook by message, and a reply that comes an hour late can mean the slot goes elsewhere.",
            "Most salon bookings start as a quick message, and keeping up with them between appointments is hard.",
        ],
        [
            "I set up the official WhatsApp Business Platform with Meta verification, so booking messages and reminders are handled quickly and nothing is missed.",
            "I connect your salon to the official WhatsApp Cloud API, so reminders go out automatically and your team shares one inbox.",
        ],
    ),
    "realestate": (
        ["real estate", "property", "agency"],
        "agencies",
        [
            "Property enquiries come in at all hours, and the agent who replies first usually wins the viewing.",
            "Buyers and renters often message several agencies at once, so response speed matters a lot.",
        ],
        [
            "I set up the official WhatsApp Business Platform with Meta verification, so new enquiries get an instant first reply and are passed to the right agent.",
            "I connect your agency to the official WhatsApp Cloud API, with lead capture and a shared inbox, so no enquiry sits unanswered.",
        ],
    ),
    "travel": (
        ["travel", "tour"],
        "travel businesses",
        [
            "Travellers ask many questions before they book, and they usually message more than one agency.",
            "Quotes, itineraries and booking changes mostly happen over chat in travel, which gets hard to manage from one phone.",
        ],
        [
            "I set up the official WhatsApp Business Platform with Meta verification, so enquiries, quotes and booking updates are handled in one place.",
            "I connect your business to the official WhatsApp Cloud API so common questions get instant answers and your team handles the rest.",
        ],
    ),
    "school": (
        ["schools", "academy", "language", "education", "college"],
        "school",
        [
            "Parents and students ask about fees, schedules and enrolment all through the day, often outside office hours.",
            "Admissions questions repeat a lot, and answering each one by hand takes staff time.",
        ],
        [
            "I set up the official WhatsApp Business Platform with Meta verification, so common admissions questions are answered instantly and the rest reach your staff.",
            "I connect your school to the official WhatsApp Cloud API for enquiries, reminders and announcements in one shared inbox.",
        ],
    ),
    "auto": (
        ["car", "dealerships", "auto", "motor"],
        "dealership",
        [
            "Buyers message about availability and prices and expect a quick answer, and slow replies send them to the next dealer.",
            "Test drive requests and price questions come in at all hours.",
        ],
        [
            "I set up the official WhatsApp Business Platform with Meta verification, so enquiries get an instant reply and reach the right salesperson.",
            "I connect your dealership to the official WhatsApp Cloud API, with a shared inbox and automatic first replies.",
        ],
    ),
    "fitness": (
        ["fitness", "gym", "studios", "yoga"],
        "studio",
        [
            "Members ask about classes, trials and memberships by message, and a fast reply often decides whether they join.",
            "Class bookings and reminders create a steady stream of messages for a small team.",
        ],
        [
            "I set up the official WhatsApp Business Platform with Meta verification, so trial requests, class reminders and common questions run smoothly.",
            "I connect your studio to the official WhatsApp Cloud API so replies are fast and your team shares one inbox.",
        ],
    ),
    "furniture": (
        ["furniture", "home", "interior"],
        "furniture stores",
        [
            "Customers often send photos and ask about sizes, finishes and delivery before they order.",
            "Delivery questions and order updates take up a lot of time in a furniture business.",
        ],
        [
            "I set up the official WhatsApp Business Platform with Meta verification, so product questions and delivery updates are handled in one shared inbox.",
            "I connect your store to the official WhatsApp Cloud API for order updates and faster replies.",
        ],
    ),
    "food": (
        ["restaurants", "delivery", "food", "cafe"],
        "restaurant",
        [
            "Orders and table requests arrive in bursts, and a missed message is a missed order.",
            "Customers often ask about menus, opening hours and delivery times just before they order.",
        ],
        [
            "I set up the official WhatsApp Business Platform with Meta verification, so order questions and updates are answered automatically.",
            "I connect your restaurant to the official WhatsApp Cloud API so common questions get instant replies and your team handles the orders.",
        ],
    ),
}

RECEPTIONIST_NICHES = {
    "trades": (
        ["plumber", "hvac", "electrician", "garage door", "contractor", "repair"],
        "trades businesses",
        [
            "When you are on a job and cannot pick up, the caller usually rings the next company on the list.",
            "Most people calling a trade business need help now, and they rarely leave a voicemail.",
        ],
        [
            "I build AI phone assistants that answer every call, take the customer's details and the problem, and book the job into your calendar.",
            "I set up an AI receptionist that picks up straight away, sorts urgent jobs from routine ones and sends you the details.",
        ],
    ),
    "restoration": (
        ["restoration", "water damage", "pest"],
        "emergency services",
        [
            "Emergency callers call several companies and book the first one that answers.",
            "A call that arrives at night or in the middle of a job is the one most likely to be lost.",
        ],
        [
            "I build AI phone assistants that answer every call at any hour, take the details and tell you straight away when a job is urgent.",
            "I set up an AI receptionist that answers instantly, collects the address and the problem and sends it to your phone.",
        ],
    ),
    "dental": (
        ["dentist", "dental", "cosmetic"],
        "dental practices",
        [
            "The front desk is often busy with patients when new patient calls come in.",
            "Calls that arrive at lunch or after closing time often go to voicemail, and new patients rarely call back.",
        ],
        [
            "I build AI phone assistants that answer calls when the desk is busy or closed, take the patient's details and book the appointment.",
            "I set up an AI receptionist that handles new patient calls and common questions and passes the rest to your team.",
        ],
    ),
    "legal": (
        ["lawyer", "attorney", "legal", "law"],
        "law firms",
        [
            "People looking for a lawyer often call several firms, and they usually go with the one that answers first.",
            "New client calls that reach voicemail are often lost for good.",
        ],
        [
            "I build AI phone assistants that answer every call, ask the right first questions and send you a summary, so you can call the serious ones back quickly.",
            "I set up an AI receptionist that answers at any hour, gathers the details of the enquiry and books a consultation.",
        ],
    ),
}

COUNTRY_NAMES = {
    "AE": "the UAE", "SA": "Saudi Arabia", "QA": "Qatar", "KW": "Kuwait", "BH": "Bahrain", "OM": "Oman",
    "ES": "Spain", "IT": "Italy", "PT": "Portugal", "NL": "the Netherlands", "DE": "Germany",
    "UK": "the United Kingdom", "SG": "Singapore", "MY": "Malaysia", "US": "the United States",
    "CA": "Canada", "AU": "Australia", "NZ": "New Zealand", "IE": "Ireland",
}

GREETINGS = ["Hi {who},", "Hello {who},", "Good day {who},"]
OPENERS = [
    "I came across {name} while looking at {noun} in {place}.",
    "I found {name} while researching {noun} in {place}.",
    "{name} came up when I was looking at {noun} in {place}.",
]
CTAS = {
    "whatsapp_api": [
        "If that is something you are thinking about, I can send a short outline of how it works and what it costs.",
        "If it would help, I can send a short outline of how the setup works.",
        "Would a short outline of how it works and what it costs be useful?",
    ],
    "receptionist": [
        "Would a short recorded example of how it sounds for a business like yours be useful?",
        "If it would help, I can send a short recording of how it handles a call.",
        "If that is something you are thinking about, I can send a short example.",
    ],
}
SUBJECTS = {
    "whatsapp_api": ["WhatsApp for {name}", "Customer messages at {name}", "A question about {name}"],
    "receptionist": ["Calls to {name}", "Missed calls at {name}", "A question about {name}"],
}
PACKS = {"whatsapp_api": WHATSAPP_NICHES, "receptionist": RECEPTIONIST_NICHES}


def _pick_niche(service_id: str, keyword: str):
    kw = (keyword or "").lower()
    pack = PACKS[service_id]
    for key, (needles, noun, situ, offer) in pack.items():
        if any(n in kw for n in needles):
            return key, noun, situ, offer
    key = next(iter(pack))
    needles, noun, situ, offer = pack[key]
    return key, noun, situ, offer


def compose(service_id: str, lead: Dict[str, Any], footer_text: str) -> Optional[Tuple[str, str]]:
    if service_id not in PACKS:
        return None
    rnd = random.Random(f"{service_id}:{lead.get('domain') or lead.get('name')}")
    name = lead["name"]
    owner = lead.get("owner_name")
    who = owner if owner else f"{name} team"
    city = lead.get("city")
    code = (lead.get("country") or "").upper()
    place = city if city and city.lower() != "general" else COUNTRY_NAMES.get(code, "your area")
    key, noun, situ, offer = _pick_niche(service_id, lead.get("keyword", ""))
    evidence = " ".join(json.loads(lead.get("evidence_json") or "[]")).lower()

    parts = [
        rnd.choice(GREETINGS).format(who=who),
        rnd.choice(OPENERS).format(name=name, noun=noun, place=place),
    ]
    if service_id == "whatsapp_api" and "whatsapp click" in evidence:
        parts.append("I noticed customers can already message you on WhatsApp from your website.")
    parts += [rnd.choice(situ), rnd.choice(offer), rnd.choice(CTAS[service_id])]
    subject = rnd.choice(SUBJECTS[service_id]).format(name=name)
    return subject, "\n\n".join(parts) + footer_text


if __name__ == "__main__":
    sample_footer = "\n\nYour Name\nYour Business\nYour address\n\nIf you would rather not hear from me, just reply \"no\" and I will not contact you again."
    for sid, pack in PACKS.items():
        for key, (needles, noun, _s, _o) in pack.items():
            for i in range(2):
                lead = {"name": f"Sample {noun.title()} {i + 1}", "domain": f"sample{key}{i}.com", "city": "General", "country": "AE" if sid == "whatsapp_api" else "US", "keyword": needles[0], "evidence_json": "[]"}
                subj, body = compose(sid, lead, sample_footer)
                print("=" * 70, f"\n[{sid} / {key}]  Subject: {subj}\n\n{body}\n")
