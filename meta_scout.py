#!/usr/bin/env python3
"""Meta scout.

Finds public posts from people who have a Meta business problem right now (restricted WhatsApp account, rejected
business verification, display name refused, cannot set up the API) or who are about to need help (asking how to
start, which provider, how much it costs). Sends the best ones to your Telegram with a ready draft reply.

It NEVER sends anything to anyone. You read the lead, adjust the reply, and post it yourself.

Needs only: SERPER_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (the same secrets the old scouting used).
Optional: ANTHROPIC_API_KEY for smarter scoring and better drafts. Without it, rules and templates are used.
Standard library only, so no install step is needed.

Run:  python meta_scout.py            normal run
      python meta_scout.py --dry      print what it would send, save nothing
      python meta_scout.py --selftest check scoring and templates, no network
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SERPER_KEY = os.getenv("SERPER_API_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("META_SCOUT_MODEL", "claude-haiku-5-5")
WINDOW = os.getenv("META_SCOUT_WINDOW", "w")          # d = last day, w = last week, m = last month
MAX_QUERIES = int(os.getenv("META_SCOUT_MAX_QUERIES", "14"))
MAX_ALERTS = int(os.getenv("META_SCOUT_MAX_ALERTS", "8"))
MIN_SCORE = int(os.getenv("META_SCOUT_MIN_SCORE", "4"))
STATE_DIR = os.getenv("META_SCOUT_STATE", "meta_scout_state")
DRY = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes") or "--dry" in sys.argv

# (search, what kind of lead it usually finds). Add your own with META_SCOUT_EXTRA, one per line as: type|search
QUERIES = [
    ('site:reddit.com "whatsapp business api" restricted OR rejected OR banned OR suspended', "RESCUE"),
    ('site:reddit.com "business verification" meta rejected OR failed OR stuck', "VERIFY"),
    ('site:reddit.com whatsapp "display name" rejected OR declined', "VERIFY"),
    ('site:reddit.com "meta business" OR "business portfolio" disabled OR restricted help', "RESCUE"),
    ('site:reddit.com "whatsapp business api" "getting started" OR "worth it" OR "which provider"', "EARLY"),
    ('site:reddit.com "whatsapp business api" "looking for" OR "need someone" OR hire setup', "BUILD"),
    ('site:reddit.com whatsapp api pricing "per message" confused OR expensive OR cost', "COST"),
    ('site:reddit.com "green tick" OR "official business account" whatsapp how', "VERIFY"),
    ('site:quora.com "whatsapp business api" verification OR approval OR restricted', "VERIFY"),
    ('site:stackoverflow.com "whatsapp cloud api" "business verification" OR restricted OR "not approved"', "RESCUE"),
    ('site:github.com "WhatsApp Business" "business verification" OR "account restricted" issue', "RESCUE"),
    ('site:nairaland.com whatsapp business api OR "meta verification"', "SETUP"),
    ('"whatsapp business account" restricted "how to fix" OR appeal forum', "RESCUE"),
    ('site:reddit.com "ad account" disabled "business verification" meta', "RESCUE"),
]

# --------------------------------------------------------------------------- scoring
CORE = [
    (r"whatsapp business api", 3), (r"whatsapp api", 2), (r"cloud api", 2), (r"\bwaba\b", 3),
    (r"business verification", 3), (r"meta business", 2), (r"business portfolio", 2), (r"business manager", 2),
    (r"display name", 2), (r"green tick", 2), (r"official business account", 2), (r"whatsapp business", 1),
    (r"ad account", 1),
]
PAIN = [r"restricted", r"rejected", r"banned", r"suspended", r"disabled", r"blocked", r"flagged", r"appeal",
        r"declined", r"not approved", r"failed", r"stuck", r"can'?t", r"cannot", r"not working", r"error",
        r"locked", r"lost access", r"denied"]
BUY = [r"looking for", r"need someone", r"need help", r"\bhire\b", r"who can", r"recommend", r"any provider",
       r"how much", r"\bcost\b", r"\bprice\b", r"quote", r"freelancer", r"\bagency\b"]
EARLY = [r"how to start", r"getting started", r"worth it", r"should i", r"thinking about", r"planning to",
         r"which provider", r"alternatives", r"beginner", r"is it possible"]
JUNK = [r"top \d+", r"best .{0,30}(providers?|platforms?|tools?)", r"ultimate guide", r"step by step", r"free trial",
        r"\bwe offer\b", r"our platform", r"pricing plans", r"book a demo", r"sign up"]
VENDOR_DOMAINS = ("wati.io", "twilio.com", "360dialog.com", "gupshup.io", "interakt.shop", "respond.io",
                  "vonage.com", "kommo.com", "zendesk.com", "messagebird.com", "bird.com", "sinch.com",
                  "developers.facebook.com/docs", "facebook.com/business/help", "business.whatsapp.com",
                  "medium.com", "linkedin.com", "youtube.com")
DOMAIN_BONUS = {"reddit.com": 1, "nairaland.com": 1, "quora.com": 0, "stackoverflow.com": 0, "github.com": -1}


def _hits(patterns, text):
    return sum(1 for p in patterns if re.search(p, text, re.I))


def norm_url(url):
    u = urllib.parse.urlsplit(url.strip())
    host = u.netloc.lower().replace("www.", "").replace("old.reddit.com", "reddit.com")
    return f"{host}{u.path.rstrip('/')}"


def host_of(url):
    return urllib.parse.urlsplit(url).netloc.lower().replace("www.", "").replace("old.", "")


def recency_bonus(date_text):
    t = (date_text or "").lower()
    if re.search(r"(minute|hour)s? ago", t):
        return 2
    m = re.search(r"(\d+)\s+days? ago", t)
    if m:
        d = int(m.group(1))
        return 2 if d <= 2 else (1 if d <= 7 else 0)
    return 0


def classify(text, hint):
    t = text.lower()
    if re.search(r"restrict|banned|suspend|disabled|locked|lost access", t):
        return "RESCUE"
    if re.search(r"verif|display name|green tick|official business", t):
        return "VERIFY"
    if re.search(r"\bhire\b|need someone|looking for|freelancer|who can", t):
        return "BUILD"
    if re.search(r"how much|\bcost\b|price|pricing|per message", t):
        return "COST"
    if re.search(r"how to start|getting started|worth it|which provider|should i|beginner", t):
        return "EARLY"
    return hint


def rule_score(item, hint):
    """Returns (score, type) or (0, None) when the result is not a lead."""
    text = f"{item.get('title', '')} {item.get('snippet', '')}"
    link = item.get("link", "")
    if any(v in link for v in VENDOR_DOMAINS):
        return 0, None
    core = min(6, sum(w for p, w in CORE if re.search(p, text, re.I)))
    if core == 0:
        return 0, None
    pain = min(6, 2 * _hits(PAIN, text))
    buy = min(4, 2 * _hits(BUY, text))
    early = min(2, _hits(EARLY, text))
    if pain + buy + early == 0:
        return 0, None
    score = core + pain + buy + early + recency_bonus(item.get("date", ""))
    score += DOMAIN_BONUS.get(host_of(link), 0)
    if _hits(JUNK, text):
        score -= 5
    return score, classify(text, hint)


# --------------------------------------------------------------------------- replies (used when no AI key)
TEMPLATES = {
    "RESCUE": ("Sorry you are dealing with this, it is stressful when the account is your sales channel. The first "
               "thing to check is the exact message shown in WhatsApp Manager and the status of the business in "
               "Security Center inside Meta Business Settings, because the fix is different for a quality flag, a "
               "policy restriction and a missing verification. If you share the exact wording of the message, I can "
               "tell you which one it is and what usually works."),
    "VERIFY": ("Verification usually fails on small mismatches, for example the business name or address on the "
               "document not matching exactly what is typed in Business Settings, or a website that does not show "
               "the same details. Which document did you submit and what reason did Meta give? That tells me the "
               "likely fix."),
    "SETUP": ("The order that causes the fewest problems is a clean Business Portfolio first, then business "
              "verification, then the WhatsApp number and display name. What are you trying to connect it to, a "
              "CRM, a chatbot, or just a shared inbox?"),
    "BUILD": ("I do this kind of setup. To tell you what is involved, I need to know what you want the number to "
              "do, how many people will answer, and whether the business is already verified."),
    "COST": ("Meta charges by message type and the rates can change each quarter, so the real cost depends on "
             "your expected volume and how many template messages you send. Roughly how many conversations a month "
             "do you expect?"),
    "EARLY": ("Before choosing a provider it helps to decide what you need most, a shared team inbox, automatic "
              "replies or broadcasts, because that changes whether you need the full API at all. What kind of "
              "business is it and roughly how many chats a day?"),
}
LABEL = {"RESCUE": "Account restricted or banned", "VERIFY": "Verification or display name",
         "SETUP": "Needs setup", "BUILD": "Looking to hire", "COST": "Asking about cost",
         "EARLY": "Early stage, will need it"}

SYSTEM_PROMPT = """You help Samuel, a freelancer who sets up Meta business tools: WhatsApp Business API, Meta
Business verification, restricted account recovery, display names, Business Portfolio cleanup and template approval.
You judge a public post found by search. Reply with JSON only, no other text, with these keys:
fit: 0 to 10, how likely the poster is a business or person who would pay for this help (vendors, ads, tutorials
and developers just debugging code score 0 to 2)
type: one of RESCUE, VERIFY, SETUP, BUILD, COST, EARLY, SKIP
who: business owner, developer, agency, student, vendor or other
summary: at most 20 words on what they need
reply: 2 to 4 short sentences Samuel could post as a public comment. Help first with something specific and true.
Plain casual wording, no hype, no sales pitch, no links, no dashes of any kind, never suggest a call. If the
snippet is too thin to give real help, ask one specific question instead. Only offer more help if they share details."""


def ai_judge(item):
    if not ANTHROPIC_KEY:
        return None
    body = json.dumps({
        "model": MODEL, "max_tokens": 500, "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content":
                      f"Source: {host_of(item['link'])}\nTitle: {item.get('title', '')}\n"
                      f"Snippet: {item.get('snippet', '')}\nURL: {item['link']}"}],
    }).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
        "x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        out = json.loads(text)
        out["fit"] = int(out.get("fit", 0))
        out["reply"] = clean_reply(out.get("reply", ""))
        return out
    except Exception as e:  # any failure falls back to rules and templates
        print(f"  ai skipped: {e}")
        return None


def clean_reply(text):
    """Draft replies never contain dashes of any kind."""
    text = re.sub(r"\s*(?:\u2014|\u2013|--|\s-\s)\s*", ", ", text)
    return re.sub(r"(?<=\w)-(?=\w)", " ", text).strip()


# --------------------------------------------------------------------------- search, state, telegram
def serper(query):
    body = json.dumps({"q": query, "num": 10, "tbs": f"qdr:{WINDOW}"}).encode()
    req = urllib.request.Request("https://google.serper.dev/search", data=body, method="POST",
                                 headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r).get("organic", [])


def load_seen():
    try:
        with open(os.path.join(STATE_DIR, "seen.json")) as f:
            return json.load(f)
    except Exception:
        return {}


def save_seen(seen):
    os.makedirs(STATE_DIR, exist_ok=True)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    with open(os.path.join(STATE_DIR, "seen.json"), "w") as f:
        json.dump(seen, f)


def telegram(text):
    if not (TG_TOKEN and TG_CHAT):
        print("(no Telegram secrets, printing instead)\n" + text + "\n")
        return
    data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": text[:3900], "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data, timeout=30)
    except Exception as e:
        print(f"telegram failed: {e}")


def format_lead(n, lead):
    return (f"Lead {n}: {LABEL.get(lead['type'], lead['type'])}\n"
            f"Fit {lead['fit']}/10 on {host_of(lead['link'])}"
            + (f", posted by a {lead['who']}" if lead.get("who") else "") + "\n\n"
            f"{lead.get('summary') or lead['title']}\n{lead['link']}\n\n"
            f"Draft reply:\n{lead['reply']}")


# --------------------------------------------------------------------------- main
def main():
    queries = list(QUERIES)
    for line in os.getenv("META_SCOUT_EXTRA", "").splitlines():
        if "|" in line:
            kind, q = line.split("|", 1)
            queries.append((q.strip(), kind.strip().upper()))
    if not SERPER_KEY:
        sys.exit("SERPER_API_KEY is missing")
    seen = load_seen()
    found, titles = {}, set()
    for q, hint in queries[:MAX_QUERIES]:
        try:
            results = serper(q)
        except urllib.error.HTTPError as e:
            msg = f"Meta scout stopped: search returned HTTP {e.code}. Check the Serper credits and key."
            print(msg)
            if not DRY:
                telegram(msg)
            break
        except Exception as e:
            print(f"search failed ({e}): {q}")
            continue
        for item in results:
            key = norm_url(item.get("link", ""))
            title_key = re.sub(r"\W+", "", item.get("title", "").lower())
            if not key or key in seen or key in found or title_key in titles:
                continue
            score, kind = rule_score(item, hint)
            if score >= MIN_SCORE:
                titles.add(title_key)
                found[key] = dict(item, score=score, type=kind, key=key)
    ranked = sorted(found.values(), key=lambda x: -x["score"])
    print(f"{len(ranked)} candidates after rules")

    leads = []
    for item in ranked[:MAX_ALERTS * 2]:
        judged = ai_judge(item)
        if judged:
            if judged.get("type") == "SKIP" or judged["fit"] < 4:
                continue
            kind = judged["type"] if judged.get("type") in TEMPLATES else item["type"]
            lead = dict(item, type=kind, fit=judged["fit"], who=judged.get("who", ""),
                        summary=judged.get("summary", ""), reply=judged.get("reply") or TEMPLATES[kind])
        else:
            lead = dict(item, fit=min(10, item["score"]), who="", summary="", reply=TEMPLATES[item["type"]])
        leads.append(lead)
    leads = sorted(leads, key=lambda x: -x["fit"])[:MAX_ALERTS]

    if leads:
        telegram(f"Meta scout: {len(leads)} new lead{'s' if len(leads) != 1 else ''}, best first.")
        for i, lead in enumerate(leads, 1):
            telegram(format_lead(i, lead))
    else:
        print("no new leads")
    if not DRY:
        now = datetime.now(timezone.utc).isoformat()
        for item in ranked:
            seen[item["key"]] = now
        save_seen(seen)
        os.makedirs(STATE_DIR, exist_ok=True)
        with open("leads_today.json", "w") as f:
            json.dump(leads, f, indent=2)


def selftest():
    good = [
        ({"title": "WhatsApp Business API account restricted after verification, what now?",
          "snippet": "My WABA got restricted yesterday and Meta support is no help. Can't send messages. Need help.",
          "link": "https://www.reddit.com/r/whatsapp/comments/abc/x/", "date": "2 hours ago"}, "RESCUE"),
        ({"title": "Business verification rejected for the third time",
          "snippet": "Meta business verification keeps failing with my documents. Any agency who can fix this?",
          "link": "https://reddit.com/r/FacebookAds/comments/def/y/", "date": "1 day ago"}, "VERIFY"),
        ({"title": "Is WhatsApp Business API worth it for a small shop?",
          "snippet": "Thinking about getting started with the WhatsApp business api, which provider should I use?",
          "link": "https://reddit.com/r/smallbusiness/comments/ghi/z/", "date": "3 days ago"}, "EARLY"),
    ]
    bad = [
        {"title": "Top 10 best WhatsApp Business API providers", "snippet": "Free trial, book a demo, pricing plans.",
         "link": "https://example.com/blog"},
        {"title": "WhatsApp Business API restricted accounts guide", "snippet": "restricted rejected",
         "link": "https://www.wati.io/blog/x"},
        {"title": "Cute cat pictures", "snippet": "no relevant words at all", "link": "https://reddit.com/r/cats/x"},
    ]
    problems = 0
    for item, want in good:
        s, t = rule_score(item, "SETUP")
        ok = s >= MIN_SCORE and t == want
        problems += 0 if ok else 1
        print(("ok  " if ok else "FAIL"), s, t, "expected", want)
    for item in bad:
        s, t = rule_score(item, "SETUP")
        ok = s < MIN_SCORE
        problems += 0 if ok else 1
        print(("ok  " if ok else "FAIL"), s, t, "should be rejected:", item["title"][:40])
    for k, v in TEMPLATES.items():
        if re.search(r"[\u2014\u2013-]", v):
            problems += 1
            print("FAIL dash in template", k)
    assert clean_reply("fast \u2014 and well-known - ok -- yes") == "fast, and well known, ok, yes", clean_reply("fast \u2014 and well-known - ok -- yes")
    print(format_lead(1, dict(good[0][0], type="RESCUE", fit=9, who="business owner", summary="WABA restricted",
                              reply=TEMPLATES["RESCUE"])))
    print("selftest problems:", problems)
    return problems


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(1 if selftest() else 0)
    main()
