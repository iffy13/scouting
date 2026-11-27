#!/usr/bin/env python3
"""Roblox outreach: emails the leads found by roblox_scout.py, from one of your connected mailboxes.

What it does each run:
  1. Checks the threads of everyone already emailed. A reply stops all further email to that person and is sent to
     your Telegram. A bounce marks the address dead.
  2. Sends ONE follow up, in the same thread, to people who did not answer the first email after FOLLOWUP_DAYS.
  3. Sends first emails to new leads, up to the daily cap, with a random 4 to 9 minute gap between emails.
  4. Tells you on Telegram what was sent.

Deliverability rules built in (they are why it is plain and short on purpose):
  plain text only, no links, no images, no tracking, no attachments, no sales words, 50 to 110 words, a real
  question at the end, a different subject and wording for every lead, a low daily volume, human gaps, one follow up
  at most, and a plain opt out sentence. Nobody is emailed twice from the start.

Needs: the mailbox secrets the old autopilot used (MAILBOX_MAP_JSON plus ACCOUNT_*_JSON tokens and/or
SMTP_ACCOUNTS_JSON), SENDER_NAME, TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
Optional: ROBLOX_MAILBOX (which address sends; default the 3D rendering mailbox), ROBLOX_DAILY_CAP (default 50),
ROBLOX_PER_RUN (default 10), POSTAL_ADDRESS (added under the opt out line, needed for US commercial email law).

Run:  python roblox_outreach.py             normal run
      python roblox_outreach.py --dry       show what would be sent, send nothing, save nothing
      python roblox_outreach.py --preview N print N sample emails from the saved leads (no sending)
      python roblox_outreach.py --selftest  check the email writer, no network
"""
import hashlib
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone

STATE_DIR = os.getenv("ROBLOX_SCOUT_STATE", "roblox_scout_state")
SENDER_NAME = os.getenv("SENDER_NAME", "").strip() or "Samuel"
FIRST_NAME = SENDER_NAME.split()[0]
POSTAL_ADDRESS = os.getenv("POSTAL_ADDRESS", "").strip()
DAILY_CAP = int(os.getenv("ROBLOX_DAILY_CAP", "50") or 50)
PER_RUN = int(os.getenv("ROBLOX_PER_RUN", "10") or 10)
MIN_GAP = float(os.getenv("ROBLOX_MIN_GAP", "3") or 3)
MAX_GAP = float(os.getenv("ROBLOX_MAX_GAP", "7") or 7)
FOLLOWUP_DAYS = int(os.getenv("ROBLOX_FOLLOWUP_DAYS", "4") or 4)
MC_SHARE = float(os.getenv("MINECRAFT_SHARE", "0.5") or 0.5)
BOUNCE_LIMIT = float(os.getenv("ROBLOX_BOUNCE_LIMIT", "0.08") or 0.08)
PAUSED = os.getenv("ROBLOX_OUTREACH_PAUSED", "").lower() in ("1", "true", "yes")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
ARGS = sys.argv[1:]
DRY = "--dry" in ARGS or os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")

# =========================================================================== the writer
GENERIC_NAMES = re.compile(r"^(home|homepage|contact( us)?|about( us)?|welcome|index|untitled|official site|"
                           r"linktree|beacons|carrd|roblox|games?|studio|press kit|presskit)$", re.I)


def clean_name(lead):
    name = (lead.get("channel") or "").strip()
    name = re.split(r"\s+[|\-–—:]\s+", name)[0].strip(" .,'\"")
    name = re.sub(r"\s*(\(@[\w.]+\)|on (linktree|beacons|carrd)|\| linktree|- youtube)$", "", name, flags=re.I).strip()
    name = re.sub(r"^@", "", name)
    if not name or GENERIC_NAMES.match(name) or len(name) > 40 or len(name) < 2:
        host = (lead.get("channel_id") or "").lower()
        host = re.sub(r"^(www\.|@)", "", host).split("/")[-1]
        root = host.split(".")[0] if "." in host else host
        name = root.replace("-", " ").replace("_", " ").title() if root and len(root) > 2 else ""
    return name


def niche_of(lead):
    return lead.get("niche") or "roblox"


def kind_of(lead):
    src = lead.get("source", "")
    if src.startswith("youtube"):
        return "YT"
    return {"web_studio": "STUDIO", "web_agency": "AGENCY", "web_ugc": "UGC", "web_edu": "EDU",
            "web_server": "SERVER"}.get(src, "CREATOR")


# Each list is a pool. Every lead gets its own pick from each pool, so the emails differ in subject, opening,
# middle, question and sign off. Wording is plain and honest: only things that are true for every lead.
SUBJECTS = {
    "STUDIO": ["{name}", "question about {name}", "animations at {name}", "who does your animations?",
               "{name} trailer", "quick question", "for the {name} team", "next update at {name}"],
    "AGENCY": ["roblox animation help", "quick question", "extra hands on roblox projects?", "{name}",
               "animator for {name} projects", "question for the {name} team", "roblox trailers"],
    "UGC": ["{name} items", "showcase clips for {name}?", "quick one", "question about {name}", "{name}",
            "item promos"],
    "EDU": ["{name}", "question about {name}", "videos for {name}", "quick question", "roblox class promo"],
    "YT": ["{name}", "your videos", "quick question", "editing for {name}?", "{name} thumbnails",
           "question about your channel", "hey {name}"],
    "CREATOR": ["{name}", "quick question", "your roblox stuff", "question for {name}", "hey {name}"],
}
SUBJECTS["SERVER"] = ["{name}", "{name} trailer", "question about {name}", "trailer for {name}?", "quick question",
                      "for the {name} team", "new players for {name}"]
GREETINGS = {
    "STUDIO": ["Hi {name} team,", "Hey {name} team,", "Hi there,", "Hello {name} team,"],
    "AGENCY": ["Hi {name} team,", "Hi there,", "Hey {name} team,", "Hello,"],
    "UGC": ["Hey {name},", "Hi {name},", "Hi there,", "Hey,"],
    "EDU": ["Hi {name} team,", "Hello,", "Hi there,"],
    "YT": ["Hey {name},", "Hi {name},", "Yo {name},", "Hey,"],
    "CREATOR": ["Hey {name},", "Hi {name},", "Hey,", "Hi there,"],
}
GREETINGS["SERVER"] = ["Hi {name} team,", "Hey {name} team,", "Hi there,", "Hey,"]
CONTEXT = {
    "STUDIO": ["I came across {name} while looking for small studios building on Roblox.",
               "I found {name} while going through Roblox studios that are still growing.",
               "Ran into {name} while looking at teams making Roblox games.",
               "I was looking at independent Roblox studios this week and {name} came up."],
    "AGENCY": ["I saw that {name} works on Roblox projects for brands.",
               "I came across {name} while looking at teams that build Roblox experiences for clients.",
               "Found {name} while looking into who builds branded Roblox games."],
    "UGC": ["I came across {name} while looking at Roblox UGC creators.",
            "Ran into {name} while looking at who is making Roblox items right now.",
            "I found {name} while going through Roblox UGC shops."],
    "EDU": ["I came across {name} while looking at Roblox coding classes.",
            "I found {name} while looking into places that teach kids to build on Roblox.",
            "Ran into {name} while looking at Roblox game design courses."],
    "YT": ["I came across your channel while looking at smaller Roblox creators.",
           "Found your channel while looking through Roblox creators who upload regularly.",
           "Your channel came up while I was looking at Roblox YouTubers who are growing.",
           "I ran into your channel while looking for Roblox creators to work with."],
    "CREATOR": ["I came across your page while looking at Roblox creators.",
                "Found you while looking through Roblox creators online.",
                "Your page came up while I was looking for Roblox creators to work with."],
}
CONTEXT["SERVER"] = ["I came across {name} while looking at Minecraft servers that are still growing.",
                     "Found {name} while going through smaller Minecraft networks.",
                     "Ran into {name} while looking at Minecraft servers this week."]
WHO_I_AM = {
    "STUDIO": ["I make Roblox animations, mostly combat, idles, emotes and cutscenes, plus short game trailers.",
               "I animate for Roblox games (R6 and R15) and cut trailers for game pages and Shorts.",
               "I do Roblox animation work and short trailers, the kind used on the game page and TikTok."],
    "AGENCY": ["I'm a Roblox animator and I also cut trailers, so I usually work as extra hands when a team is busy.",
               "I do Roblox animation and trailer editing, and I often help teams that are short on time.",
               "I make Roblox animations and short promo videos, mostly as outside help for teams."],
    "UGC": ["I make short showcase clips and thumbnails for Roblox items, the kind that work on TikTok and the item page.",
            "I do Roblox animation and short item showcase videos.",
            "I make Roblox item thumbnails and short animated showcases."],
    "EDU": ["I make Roblox animations and short promo videos.",
            "I do Roblox animation and short videos, the kind used to show what students build.",
            "I make short animated Roblox clips and promo videos."],
    "YT": ["I edit Roblox videos and make thumbnails and short animated intros.",
           "I do editing and thumbnails for Roblox channels, plus some Roblox animation.",
           "I edit Roblox videos and make thumbnails, mostly for channels around your size."],
    "CREATOR": ["I edit Roblox videos and make thumbnails and short animations.",
                "I do Roblox animation, editing and thumbnails.",
                "I make Roblox animations and edit videos."],
}
WHO_I_AM["SERVER"] = ["I make Minecraft server trailers and short promo clips, the kind that work on server lists, TikTok and Shorts.",
                      "I do Minecraft cinematics and server trailers, plus thumbnails and banners for listings.",
                      "I edit Minecraft trailers and make short animated promos for servers."]
QUESTION = {
    "STUDIO": ["Are you doing animations in house right now, or is that something you'd hand off?",
               "Do you have a trailer for your current game yet, or is that still on the list?",
               "Who handles animations on your side at the moment?",
               "Is there anything animation wise slowing down your next update?",
               "Would it help to have someone on call for animations when you need them?"],
    "AGENCY": ["Do you ever bring in outside animators when projects stack up?",
               "Is animation something you keep in house, or do you sometimes hand it off?",
               "Who usually cuts the trailers for your Roblox projects?",
               "Would it be useful to have an animator you can call on for busy weeks?"],
    "UGC": ["How are you promoting new items at the moment?",
            "Do you make your own showcase clips, or is that something you'd hand off?",
            "Would short showcase clips be useful for your next drop?"],
    "EDU": ["Do you have videos showing what students make, or is that something you'd want?",
            "How do you usually show parents what the class looks like?",
            "Would short animated clips be useful for promoting your next session?"],
    "YT": ["Are you editing everything yourself right now?",
           "Do you make your own thumbnails, or is that something you'd hand off?",
           "What takes you the longest when you put a video together?",
           "Would it help to get some time back on editing?"],
    "CREATOR": ["Are you doing all your editing yourself?",
                "What takes you the longest at the moment, editing or thumbnails?",
                "Would it help to have someone handle the editing side?"],
}
QUESTION["SERVER"] = ["Do you have a trailer for the server yet, or is that still on the list?",
                      "How are you getting new players at the moment?",
                      "Who handles your trailers and promo videos right now?",
                      "Would a short trailer help for your next season or update?"]
SAMPLE = ["If it's useful I can send a couple of examples.", "Happy to send a few examples if you want to see my work.",
          "I can send some examples if that helps.", "Can share a few samples if you're curious.", ""]
SIGNOFF = ["Thanks,", "Cheers,", "Best,", "Thanks for reading,", "All the best,", "Talk soon,", ""]
OPT_OUT = ["If this isn't relevant, just let me know and I won't email again.",
           "If it's not for you, just say so and I won't follow up.",
           "Not relevant? Just reply no and I'll leave it there.",
           "If you'd rather not hear from me, a quick reply is enough and I won't write again."]

FOLLOW_UPS = [
    "Hey, just bringing this back up in case it got buried. {question}",
    "Quick follow up on my note from last week. {question} No worries if the timing isn't right.",
    "Following up once in case this slipped past. {question}",
    "Just checking this reached you. {question} If not, no problem at all.",
]
FU_SIGN = ["Thanks,", "Cheers,", "Best,", ""]


def _rng(lead, salt=""):
    seed = hashlib.sha256((lead.get("email", "") + salt).encode()).hexdigest()
    return random.Random(int(seed[:12], 16))


def _fill(text, name):
    if not name:
        text = (text.replace("Hi {name} team,", "Hi there,").replace("Hey {name} team,", "Hey there,")
                .replace("Hello {name} team,", "Hello,").replace("Hey {name},", "Hey,").replace("Hi {name},", "Hi,")
                .replace("Yo {name},", "Hey,").replace("hey {name}", "quick question")
                .replace("{name} team", "your team").replace("{name}", "your team"))
    return text.replace("{name}", name)


MC_SWAPS = [("(R6 and R15)", "(Blender rigs)"), ("R6 and R15", "Blender"), ("Roblox UGC creators", "Minecraft creators"),
            ("Roblox UGC shops", "Minecraft marketplace creators"), ("Roblox items", "Minecraft maps and packs"),
            ("teams making Roblox games", "teams making Minecraft maps and servers"),
            ("Roblox studios", "Minecraft studios"), ("Roblox", "Minecraft"), ("roblox", "minecraft"),
            ("game pages", "server lists"), ("the game page", "the listing")]


def for_niche(text, lead):
    if niche_of(lead) != "minecraft":
        return text
    for a, b in MC_SWAPS:
        text = text.replace(a, b)
    return text


def compose(lead):
    """(subject, body) for the first email. Same lead always gets the same email, different leads differ."""
    kind, name = kind_of(lead), clean_name(lead)
    r = _rng(lead)
    subject = _fill(r.choice(SUBJECTS[kind]), name)
    if not name and subject in ("", "your team"):
        subject = "quick question"
    if not (name and subject.startswith(name)):  # never change the case of a name
        subject = subject[0].lower() + subject[1:] if r.random() < 0.6 else subject[0].upper() + subject[1:]
    question = r.choice(QUESTION[kind])
    lines = [_fill(r.choice(GREETINGS[kind]), name), ""]
    para = [_fill(r.choice(CONTEXT[kind]), name), r.choice(WHO_I_AM[kind])]
    if r.random() < 0.5:
        lines += [" ".join(para), "", question]
    else:
        lines += [para[0], "", para[1] + " " + question]
    sample = r.choice(SAMPLE)
    if sample:
        lines[-1] += " " + sample
    sign = r.choice(SIGNOFF)
    lines += ["", (sign + "\n" + FIRST_NAME) if sign else FIRST_NAME]
    lines += ["", r.choice(OPT_OUT)]
    if POSTAL_ADDRESS:
        lines.append(POSTAL_ADDRESS)
    return for_niche(subject, lead), for_niche("\n".join(lines), lead)


def compose_followup(lead):
    kind = kind_of(lead)
    r = _rng(lead, "followup")
    question = r.choice(QUESTION[kind])
    body = r.choice(FOLLOW_UPS).format(question=question)
    sign = r.choice(FU_SIGN)
    text = body + "\n\n" + ((sign + "\n" + FIRST_NAME) if sign else FIRST_NAME)
    text += "\n\n" + r.choice(OPT_OUT) + (("\n" + POSTAL_ADDRESS) if POSTAL_ADDRESS else "")
    subj = lead.get("sent_subject") or "quick question"
    return ("Re: " + subj) if not subj.lower().startswith("re:") else subj, for_niche(text, lead)


SPAM_WORDS = re.compile(r"\b(free|guarantee[d]?|discount|offer|deal|limited time|act now|click|buy|cheap|"
                        r"\$\d|100%|risk[- ]free|winner|urgent)\b|!!|https?://|www\.", re.I)


def lint(subject, body):
    """Problems that would make an email look like bulk mail. Empty list = fine."""
    probs = []
    words = len(re.findall(r"\w+", body))
    if SPAM_WORDS.search(subject + " " + body):
        probs.append("spam word or link")
    if not 25 <= words <= 140:
        probs.append(f"{words} words")
    if (subject.isupper() and len(subject.split()) > 2) or len(subject) > 60:
        probs.append("subject")
    return probs


# =========================================================================== state, telegram
def load_leads():
    try:
        with open(os.path.join(STATE_DIR, "email_leads.json")) as f:
            return json.load(f)
    except Exception:
        return []


def save_leads(leads):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = os.path.join(STATE_DIR, "email_leads.json.tmp")
    with open(tmp, "w") as f:
        json.dump(leads, f, indent=1)
    os.replace(tmp, os.path.join(STATE_DIR, "email_leads.json"))


def telegram(text):
    if DRY or not (TG_TOKEN and TG_CHAT):
        print("(telegram) " + text + "\n")
        return
    import urllib.parse
    import urllib.request
    time.sleep(0.6)
    data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": text[:3900], "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data, timeout=30)
    except Exception as e:
        print(f"telegram failed: {e}")


def now():
    return datetime.now(timezone.utc)


def mask(e):
    u, _, d = (e or "").partition("@")
    return (u[:2] + "***@" + d) if d else "***"


# =========================================================================== mailbox
def pick_mailbox(svc):
    accounts = [a["email"] for a in svc.get_all_accounts()]
    wanted = os.getenv("ROBLOX_MAILBOX", "").strip().lower()
    if not wanted:
        try:
            from services import load_mailbox_map
            wanted = (load_mailbox_map().get("render_3d") or "").lower()
        except Exception:
            wanted = ""
    for a in accounts:
        if a.lower() == wanted:
            return a
    return accounts[0] if accounts and not wanted else None


def thread_status(svc, mailbox, lead):
    """'replied', 'bounced' or '' for a lead already emailed. Replies come back with their text."""
    acc = svc.accounts.get(mailbox)
    if not acc or not lead.get("thread_id"):
        return "", ""
    try:
        if acc.get("type") == "smtp":
            from sender import smtp_mailbox
            got = smtp_mailbox.latest_inbound(acc["cfg"], mailbox, lead.get("message_id") or lead["thread_id"],
                                              [lead["email"]])
            if not got:
                return "", ""
            frm = got["from"].lower()
            if "mailer-daemon" in frm or "postmaster" in frm:
                return "bounced", ""
            return "replied", got["text"]
        th = acc["service"].users().threads().get(userId="me", id=lead["thread_id"], format="full").execute()
        for m in th.get("messages", [])[1:]:
            headers = {h["name"].lower(): h["value"] for h in m.get("payload", {}).get("headers", [])}
            frm = headers.get("from", "").lower()
            if mailbox.lower() in frm:
                continue
            if "mailer-daemon" in frm or "postmaster" in frm:
                return "bounced", ""
            return "replied", m.get("snippet", "")
    except Exception as e:
        print(f"thread check failed for {mask(lead['email'])}: {type(e).__name__}")
    return "", ""


def sent_today(leads):
    today = now().date().isoformat()
    return sum(1 for l in leads if (l.get("sent_at") or "")[:10] == today) + \
        sum(1 for l in leads if (l.get("followup_at") or "")[:10] == today)


# =========================================================================== domain check
def domain_report(mailbox):
    """SPF, DKIM and DMARC for the sending domain. These decide whether Gmail trusts the mail at all."""
    domain = mailbox.split("@", 1)[1].lower()
    if domain in ("gmail.com", "googlemail.com"):
        return domain, True, "Sending from a Gmail address: Google signs it, nothing to set up."
    try:
        import dns.resolver
    except ImportError:
        return domain, True, "dnspython missing, domain not checked"

    def txt(name):
        try:
            return [b"".join(r.strings).decode("utf-8", "ignore") for r in dns.resolver.resolve(name, "TXT", lifetime=10)]
        except Exception:
            return []
    spf = [t for t in txt(domain) if t.lower().startswith("v=spf1")]
    dmarc = [t for t in txt("_dmarc." + domain) if t.lower().startswith("v=dmarc1")]
    dkim_sel = [sel for sel in ("default", "mail", "dkim", "selector1", "selector2", "google", "k1", "s1", "zoho", "x")
                if any("p=" in t for t in txt(f"{sel}._domainkey.{domain}"))]
    ok = bool(spf) and bool(dmarc) and bool(dkim_sel)
    lines = [f"Domain check for {domain}:",
             f"SPF: {'OK  ' + spf[0][:120] if spf else 'MISSING'}",
             f"DKIM: {'OK (selector ' + ', '.join(dkim_sel) + ')' if dkim_sel else 'NOT FOUND on common selectors'}",
             f"DMARC: {'OK  ' + dmarc[0][:120] if dmarc else 'MISSING'}"]
    if not ok:
        lines.append("Gmail sends mail without these to spam far more often. In your hosting panel (cPanel: "
                     "Email Deliverability, click Repair) turn on SPF and DKIM, and add a TXT record named _dmarc "
                     "with the value  v=DMARC1; p=none; rua=mailto:" + mailbox)
    return domain, ok, "\n".join(lines)


# =========================================================================== run
def run():
    leads = load_leads()
    if PAUSED:
        print("ROBLOX_OUTREACH_PAUSED is true, nothing sent.")
        return
    if not leads:
        telegram("Roblox outreach: no email leads saved yet. The scout runs first, then emails start.")
        return
    from sender.gmail_client import MultiGmailService
    svc = MultiGmailService(mode="all")
    mailbox = pick_mailbox(svc)
    if not mailbox:
        telegram("Roblox outreach stopped: the sending mailbox is not connected. Check the mailbox secrets "
                 "(MAILBOX_MAP_JSON and the ACCOUNT_*_JSON or SMTP_ACCOUNTS_JSON tokens), or set the ROBLOX_MAILBOX "
                 "variable to a connected address. Nothing was sent.")
        return
    print(f"sending from {mask(mailbox)}")
    domain, dom_ok, dom_text = domain_report(mailbox)
    print(dom_text)
    flag = os.path.join(STATE_DIR, "domain_checked.txt")
    try:
        last = open(flag).read().strip()
    except Exception:
        last = ""
    if last != now().date().isoformat() + str(dom_ok):
        telegram(dom_text)
        if not DRY:
            os.makedirs(STATE_DIR, exist_ok=True)
            open(flag, "w").write(now().date().isoformat() + str(dom_ok))
    report = {"replied": [], "bounced": 0, "first": [], "followups": 0, "failed": 0}

    # 1. replies and bounces
    for l in leads:
        if l.get("status") in ("sent", "followed_up") and l.get("sender") == mailbox:
            st, text = thread_status(svc, mailbox, l)
            if st == "bounced":
                l["status"] = "bounced"
                report["bounced"] += 1
            elif st == "replied":
                l["status"] = "replied"
                l["replied_at"] = now().isoformat()
                report["replied"].append((l, text))
    if not DRY:
        save_leads(leads)
    for l, text in report["replied"]:
        telegram(f"REPLY from {l.get('channel') or l['email']} ({l['email']}):\n\n{(text or '').strip()[:1500]}\n\n"
                 f"Answer it from your mailbox {mailbox}. No more automatic emails go to them.")

    # re-check saved leads with the current rules (older runs kept some article pages and invalid addresses)
    from roblox_scout import usable_email, ARTICLE, ARTICLE_TITLE, BIG_COMPANY, LINK_IN_BIO
    for l in leads:
        if l.get("status", "new") != "new":
            continue
        host = (l.get("channel_id") or "") if l.get("source", "").startswith("web_") else ""
        bio = any(b in host for b in LINK_IN_BIO)
        url = l.get("url", "")
        bad = not usable_email(l["email"], "" if bio else host)
        if host and not bio:
            import urllib.parse
            bad = bad or any(b in host for b in BIG_COMPANY) or bool(ARTICLE.search(urllib.parse.urlsplit(url).path)) \
                or bool(ARTICLE_TITLE.search(l.get("channel", "")))
        if bad:
            l["status"] = "skipped"
    if not DRY:
        save_leads(leads)

    budget = max(0, min(PER_RUN, DAILY_CAP - sent_today(leads)))
    # Safety stop: a high bounce rate is what gets a domain blacklisted. Look at the last 40 first emails.
    recent = sorted((l for l in leads if l.get("sent_at")), key=lambda l: l["sent_at"])[-40:]
    bounced = sum(1 for l in recent if l.get("status") == "bounced")
    if len(recent) >= 20 and bounced / len(recent) > BOUNCE_LIMIT:
        telegram(f"Roblox outreach PAUSED: {bounced} of the last {len(recent)} emails bounced "
                 f"({bounced * 100 // len(recent)}%). Sending more would damage your domain. Tell Claude so the lead "
                 f"filter can be fixed; it restarts by itself once the rate is back under {int(BOUNCE_LIMIT * 100)}%.")
        budget = 0
    if budget == 0:
        print("daily cap reached")

    def gap():
        if not DRY:
            time.sleep(random.uniform(MIN_GAP, MAX_GAP) * 60)

    def send(l, subject, body, follow):
        res = None if DRY else svc.send_email(l["email"], subject, body, from_account_email=mailbox,
                                             thread_id=l.get("thread_id") if follow else None,
                                             in_reply_to=l.get("message_id") if follow else None)
        if DRY:
            print(f"--- would send to {l['email']}\nSubject: {subject}\n\n{body}\n")
            return True
        if not res:
            return svc.last_failure  # 'no_capacity' stops the run, 'rejected' skips this lead
        stamp = now().isoformat()
        if follow:
            l.update(status="followed_up", followup_at=stamp)
        else:
            l.update(status="sent", sent_at=stamp, sender=mailbox, sent_subject=subject,
                     thread_id=res.get("thread_id"), message_id=res.get("message_id"))
        save_leads(leads)
        return True

    # 2. follow ups first (they get the best reply rate)
    due = [l for l in leads if l.get("status") == "sent" and l.get("sender") == mailbox and
           l.get("sent_at") and now() - datetime.fromisoformat(l["sent_at"]) >= timedelta(days=FOLLOWUP_DAYS)]
    first_sent = False
    for l in due[:max(0, budget // 3)]:
        subject, body = compose_followup(l)
        if first_sent:
            gap()
        out = send(l, subject, body, True)
        first_sent = True
        if out is True:
            report["followups"] += 1
            budget -= 1
        elif out == "no_capacity":
            budget = 0
            break

    # 3. first emails to new leads
    emailed = {l["email"] for l in leads if l.get("status") not in (None, "new")}
    fresh = [l for l in leads if l.get("status", "new") == "new" and l["email"] not in emailed]
    fresh.sort(key=lambda l: (0 if l.get("source", "").startswith("youtube") else 1, l.get("found", "")))
    # Split the day between the games (MINECRAFT_SHARE, default half). When one game has no leads waiting,
    # the other one uses the free places so the daily total is still reached.
    today = now().date().isoformat()
    share = {"minecraft": MC_SHARE, "roblox": 1 - MC_SHARE}
    done = {n: sum(1 for l in leads if (l.get("sent_at") or "")[:10] == today and niche_of(l) == n) for n in share}
    queue = {n: [l for l in fresh if niche_of(l) == n] for n in share}

    def next_lead():
        open_ = [n for n in share if queue[n]]
        if not open_:
            return None
        under = [n for n in open_ if done[n] < round(DAILY_CAP * share[n])]
        pick = min(under or open_, key=lambda n: done[n] / max(share[n], 0.01))
        done[pick] += 1
        return queue[pick].pop(0)

    while budget > 0:
        l = next_lead()
        if l is None:
            break
        subject, body = compose(l)
        probs = lint(subject, body)
        if probs:
            print(f"skipped {mask(l['email'])}: {probs}")
            l["status"] = "skipped"
            continue
        if first_sent:
            gap()
        out = send(l, subject, body, False)
        first_sent = True
        if out is True:
            report["first"].append(l)
            budget -= 1
        elif out == "no_capacity":
            telegram(f"Roblox outreach paused: {mailbox} hit a sending limit. It will try again next run.")
            break
        else:
            l["status"] = "failed"
            report["failed"] += 1
            if not DRY:
                save_leads(leads)

    waiting = sum(1 for l in leads if l.get("status", "new") == "new")
    lines = [f"Outreach{' (dry run)' if DRY else ''} from {mailbox}:",
             f"First emails sent: {len(report['first'])}", f"Follow ups sent: {report['followups']}",
             f"New replies: {len(report['replied'])}", f"Bounced: {report['bounced']}",
             f"Leads waiting: {waiting} (" + ", ".join(
                 f"{sum(1 for l in leads if l.get('status', 'new') == 'new' and niche_of(l) == n)} {n.title()}"
                 for n in ("roblox", "minecraft")) + ")"]
    if report["failed"]:
        lines.append(f"Failed: {report['failed']}")
    for l in report["first"][:15]:
        lines.append(f"- [{niche_of(l).title()}] {l.get('channel') or ''} <{l['email']}>")
    telegram("\n".join(lines))


def preview(n):
    leads = load_leads() or [
        {"email": "hello@bloxforge.example", "channel": "Blox Forge Studio", "channel_id": "bloxforge.example", "source": "web_studio"},
        {"email": "biz.tom@gmail.com", "channel": "TomPlaysRoblox", "channel_id": "UCx", "source": "youtube_api"},
        {"email": "team@ugcland.example", "channel": "Home", "channel_id": "ugcland.example", "source": "web_ugc"},
        {"email": "hi@kidscode.example", "channel": "Code Camp Roblox Classes", "channel_id": "kidscode.example", "source": "web_edu"},
        {"email": "agency@brandverse.example", "channel": "Brandverse", "channel_id": "brandverse.example", "source": "web_agency"},
        {"email": "owner@craftia.example", "channel": "Craftia Network", "channel_id": "craftia.example", "source": "web_server", "niche": "minecraft"},
        {"email": "blocky.bob@gmail.com", "channel": "Blocky Bob", "channel_id": "UCy", "source": "youtube_comments", "niche": "minecraft"},
        {"email": "lia.makes@gmail.com", "channel": "Lia (@liamakes) | Linktree", "channel_id": "linktr.ee/liamakes", "source": "web_creator"},
    ]
    for l in leads[:n]:
        s, b = compose(l)
        print(f"To: {l['email']}\nSubject: {s}\n\n{b}\n{'-' * 60}")
    l = dict(leads[0], sent_subject=compose(leads[0])[0])
    s, b = compose_followup(l)
    print(f"FOLLOW UP\nSubject: {s}\n\n{b}")


def selftest():
    kinds = ["web_studio", "web_agency", "web_ugc", "web_edu", "web_creator", "youtube_api"]
    bodies, subjects = set(), set()
    for i in range(300):
        l = {"email": f"person{i}@example{i % 7}.com", "channel": f"Name{i}", "channel_id": f"name{i}.com",
             "source": kinds[i % len(kinds)]}
        s, b = compose(l)
        assert not lint(s, b), (s, b, lint(s, b))
        assert "{" not in s + b, (s, b)
        bodies.add(b.split("\n", 2)[2][:80])
        subjects.add(re.sub(r"name\d+", "", s.lower()))
        fs, fb = compose_followup(dict(l, sent_subject=s))
        assert fs.startswith("Re: ") and not lint(fs, fb), (fs, fb)
    assert len(bodies) > 150, len(bodies)
    for src in ("web_server", "youtube_api", "web_studio", "web_edu", "web_creator"):
        s_, b_ = compose({"email": f"x@{src}.com", "channel": "Craftia", "channel_id": "craftia.net", "source": src,
                          "niche": "minecraft"})
        assert "Roblox" not in s_ + b_ and "R6" not in b_ and not lint(s_, b_), (s_, b_)
        assert "Minecraft" in b_, b_
    assert compose({"email": "a@b.com", "channel": "Home", "channel_id": "", "source": "web_studio"})[1].startswith("H")
    assert clean_name({"channel": "Lia (@liamakes) | Linktree"}) == "Lia"
    assert clean_name({"channel": "Contact Us", "channel_id": "www.bloxforge.com"}) == "Bloxforge"
    print(f"selftest passed: {len(bodies)} different openings and {len(subjects)} subject shapes in 300 emails")


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)  # progress shows in the Actions log while it runs
    if "--selftest" in ARGS:
        selftest()
    elif "--preview" in ARGS:
        i = ARGS.index("--preview")
        preview(int(ARGS[i + 1]) if len(ARGS) > i + 1 and ARGS[i + 1].isdigit() else 6)
    else:
        run()
