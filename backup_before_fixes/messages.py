"""
Niche specific first messages, premium and professional tone.

Each business gets a message written for its own line of work, with several wording variants.
The variant is picked from the business domain, so the same lead always shows the same message in
preview and in send, and different leads read differently.

Rules the copy follows:
  no fake replies or fake history, no invented numbers or results, no claims about the business
  that were not found on its site, and a plain way to say no (added by the footer).

See every niche and variant:   python messages.py
"""
import json
import random
from typing import Any, Dict, Optional, Tuple

WHATSAPP_NICHES = {
    "ecommerce": (
        ["ecommerce", "store", "shop"],
        "online stores",
        [
            "In online retail, the speed and quality of the first reply often decides whether a customer completes the purchase.",
            "Order updates, delivery questions and product enquiries reach online stores around the clock, and customers expect immediate, professional answers.",
        ],
        [
            "I implement the official WhatsApp Business Platform with full Meta business verification, including automated order updates, abandoned cart recovery and a shared inbox for your team.",
            "I set up the official WhatsApp Cloud API for your store, verified with Meta, so order updates and common questions are handled instantly while your team focuses on the conversations that matter.",
        ],
    ),
    "clinic": (
        ["dental", "med spa", "clinic", "dentist", "medical"],
        "clinics",
        [
            "In a clinic, how quickly and courteously a patient is answered shapes their first impression of the practice.",
            "Appointment requests, reminders and follow up questions reach clinics throughout the day, and each one is an opportunity to serve a patient well.",
        ],
        [
            "I implement the official WhatsApp Business Platform with Meta business verification, giving your clinic automated reminders, instant answers to common questions and a shared inbox for your front desk.",
            "I set up your clinic on the official WhatsApp Cloud API, with a verified business profile, so appointments are confirmed and managed in one organised place.",
        ],
    ),
    "beauty": (
        ["beauty", "salon", "spa"],
        "salons",
        [
            "For a salon, a booking is often won or lost by how quickly the first message is answered.",
            "Clients increasingly book and rebook by message, and they expect an immediate, polished reply.",
        ],
        [
            "I implement the official WhatsApp Business Platform with Meta verification, so booking requests and reminders are handled promptly and every client feels looked after.",
            "I set up the official WhatsApp Cloud API for your salon, with automated reminders and one shared inbox for your team.",
        ],
    ),
    "realestate": (
        ["real estate", "property", "agency"],
        "agencies",
        [
            "In real estate, the agency that responds first to an enquiry usually secures the viewing.",
            "Property enquiries arrive at all hours, and prospective clients often contact several agencies at once.",
        ],
        [
            "I implement the official WhatsApp Business Platform with Meta verification, giving every enquiry an instant, professional first response and routing it to the right agent.",
            "I set up the official WhatsApp Cloud API for your agency, with lead capture and a shared inbox, so no enquiry goes unanswered.",
        ],
    ),
    "travel": (
        ["travel", "tour"],
        "travel businesses",
        [
            "Travellers ask detailed questions before committing, and the agency that answers with clarity and speed earns the booking.",
            "Quotes, itineraries and booking changes largely happen over chat in the travel industry.",
        ],
        [
            "I implement the official WhatsApp Business Platform with Meta verification, so enquiries, quotations and booking updates are managed in one organised place.",
            "I set up the official WhatsApp Cloud API for your business, so common questions receive instant answers and your team can focus on the bookings.",
        ],
    ),
    "school": (
        ["school", "academy", "language", "education", "college"],
        "schools",
        [
            "Parents and students ask about fees, schedules and enrolment throughout the day, often outside office hours.",
            "A prompt and courteous reply to an admissions enquiry reflects the standard of the institution itself.",
        ],
        [
            "I implement the official WhatsApp Business Platform with Meta verification, so common admissions questions are answered instantly and the rest reach the right member of staff.",
            "I set up the official WhatsApp Cloud API for your school, covering enquiries, reminders and announcements in one shared inbox.",
        ],
    ),
    "auto": (
        ["car", "dealership", "auto", "motor"],
        "dealerships",
        [
            "Buyers expect an immediate answer on availability and pricing, and a delayed reply often sends them to another dealer.",
            "Test drive requests and price enquiries arrive at all hours and deserve a prompt, professional response.",
        ],
        [
            "I implement the official WhatsApp Business Platform with Meta verification, so every enquiry receives an instant reply and reaches the right salesperson.",
            "I set up the official WhatsApp Cloud API for your dealership, with a shared inbox and automated first responses.",
        ],
    ),
    "fitness": (
        ["fitness", "gym", "studio", "yoga"],
        "studios",
        [
            "In fitness, a fast and welcoming reply to a trial request often decides whether a visitor becomes a member.",
            "Class bookings, reminders and membership questions create a steady stream of messages for a small team.",
        ],
        [
            "I implement the official WhatsApp Business Platform with Meta verification, so trial requests, class reminders and common questions are handled smoothly.",
            "I set up the official WhatsApp Cloud API for your studio, so replies are immediate and your team shares one organised inbox.",
        ],
    ),
    "furniture": (
        ["furniture", "home", "interior"],
        "furniture stores",
        [
            "Customers often send photos and ask about sizes, finishes and delivery before they order, and they value a knowledgeable, prompt reply.",
            "Delivery questions and order updates take considerable time in a furniture business.",
        ],
        [
            "I implement the official WhatsApp Business Platform with Meta verification, so product questions and delivery updates are managed in one shared inbox.",
            "I set up the official WhatsApp Cloud API for your store, for order updates and faster, more consistent replies.",
        ],
    ),
    "food": (
        ["restaurant", "delivery", "food", "cafe"],
        "restaurants",
        [
            "Orders and table requests arrive in bursts, and a missed message is a missed order.",
            "Guests ask about menus, opening hours and delivery times just before they order, and expect an instant answer.",
        ],
        [
            "I implement the official WhatsApp Business Platform with Meta verification, so order questions and updates are answered automatically and accurately.",
            "I set up the official WhatsApp Cloud API for your restaurant, so common questions receive instant replies while your team focuses on the orders.",
        ],
    ),
}

RECEPTIONIST_NICHES = {
    "trades": (
        ["plumber", "hvac", "electrician", "garage door", "contractor", "repair"],
        "trades businesses",
        [
            "When you are on a job and unable to answer, the caller usually moves on to the next company on the list.",
            "People calling a trade business typically need help urgently, and few of them leave a voicemail.",
        ],
        [
            "I build AI phone assistants that answer every call professionally, record the customer's details and the nature of the problem, and book the job directly into your calendar.",
            "I set up an AI receptionist that answers immediately, distinguishes urgent jobs from routine ones, and sends you a clear summary of each call.",
        ],
    ),
    "restoration": (
        ["restoration", "water damage", "pest"],
        "emergency services",
        [
            "Emergency callers contact several companies and book the first one that answers.",
            "A call that arrives at night or in the middle of a job is the one most at risk of being lost.",
        ],
        [
            "I build AI phone assistants that answer every call at any hour, record the details and alert you immediately when a job is urgent.",
            "I set up an AI receptionist that answers instantly, records the address and the nature of the emergency, and sends it straight to your phone.",
        ],
    ),
    "dental": (
        ["dentist", "dental", "cosmetic"],
        "dental practices",
        [
            "While the front desk attends to patients, new patient calls can go unanswered, and those callers rarely try again.",
            "Calls that arrive during lunch or after closing often reach voicemail, and prospective patients seldom call back.",
        ],
        [
            "I build AI phone assistants that answer calls when the desk is busy or closed, record the patient's details and book the appointment.",
            "I set up an AI receptionist that handles new patient calls and common questions with courtesy and passes anything else to your team.",
        ],
    ),
    "legal": (
        ["lawyer", "attorney", "legal", "law"],
        "law firms",
        [
            "People seeking legal help usually contact several firms and instruct the one that responds first.",
            "A new client call that reaches voicemail is very often lost for good.",
        ],
        [
            "I build AI phone assistants that answer every call, ask the right first questions and send you a concise summary, so you can return the important calls promptly.",
            "I set up an AI receptionist that answers at any hour, records the details of each enquiry and books a consultation.",
        ],
    ),
}

COUNTRY_NAMES = {
    "AE": "the UAE", "SA": "Saudi Arabia", "QA": "Qatar", "KW": "Kuwait", "BH": "Bahrain", "OM": "Oman",
    "ES": "Spain", "IT": "Italy", "PT": "Portugal", "NL": "the Netherlands", "DE": "Germany",
    "UK": "the United Kingdom", "SG": "Singapore", "MY": "Malaysia", "US": "the United States",
    "CA": "Canada", "AU": "Australia", "NZ": "New Zealand", "IE": "Ireland",
}

GREETINGS = ["Dear {who},", "Good day {who},", "Hello {who},"]
PURPOSE = {
    "whatsapp_api": "strengthen their customer communication",
    "receptionist": "strengthen their call handling",
}
INTROS = [
    "I am reaching out to {name} because I work with {noun} in {place} to {purpose}.",
    "{name} came to my attention while I was researching {noun} in {place}. I work with them to {purpose}.",
    "I work with {noun} in {place} to {purpose}, and I wanted to introduce myself to {name}.",
]
CTAS = {
    "whatsapp_api": [
        "If this is a priority for {name}, I would be glad to send a concise outline of the approach, the timeline and the cost.",
        "I would welcome the opportunity to share a brief outline of how this would work for {name}, including timeline and cost.",
        "Should this be of interest, I will gladly prepare a short outline tailored to {name}.",
    ],
    "receptionist": [
        "If this is of interest, I would be glad to send a short recording that demonstrates how the assistant handles a call for a business like {name}.",
        "I would welcome the opportunity to share a brief demonstration recording tailored to {name}.",
        "Should this be of interest, I will gladly send a short recorded example.",
    ],
}
SUBJECTS = {
    "whatsapp_api": ["WhatsApp Business Platform for {name}", "Customer messaging at {name}", "An introduction regarding {name}"],
    "receptionist": ["Call handling at {name}", "Never missing a call at {name}", "An introduction regarding {name}"],
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
        rnd.choice(INTROS).format(name=name, noun=noun, place=place, purpose=PURPOSE[service_id]),
    ]
    if service_id == "whatsapp_api" and "whatsapp click" in evidence:
        parts.append(f"I noticed that {name} already invites customers to message on WhatsApp, which is an excellent foundation to build on.")
    parts += [rnd.choice(situ), rnd.choice(offer), rnd.choice(CTAS[service_id]).format(name=name), "Kind regards,"]
    subject = rnd.choice(SUBJECTS[service_id]).format(name=name)
    return subject, "\n\n".join(parts[:-1]) + "\n\n" + parts[-1] + "\n" + footer_text.lstrip("\n")


if __name__ == "__main__":
    sample_footer = "\n\nYour Name\nYour Business\nYour address\n\nIf you would rather not hear from me, just reply \"no\" and I will not contact you again."
    for sid, pack in PACKS.items():
        for key, (needles, noun, _s, _o) in pack.items():
            lead = {"name": f"Sample {key.title()}", "domain": f"sample{key}.com", "city": "General",
                    "country": "AE" if sid == "whatsapp_api" else "US", "keyword": needles[0], "evidence_json": "[]"}
            subj, body = compose(sid, lead, sample_footer)
            print("=" * 70, f"\n[{sid} / {key}]  Subject: {subj}\n\n{body}\n")
