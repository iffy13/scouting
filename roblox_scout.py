#!/usr/bin/env python3
"""Roblox scout.

Finds small and new Roblox creators who need animation, trailers, thumbnails or video editing, and sends them to
your Telegram. It NEVER contacts anyone by itself.

Two lead sources:

  1. POSTS   People asking for help right now: "[HIRING] animator", "need a trailer for my game", "my game has
             0 players", "looking for a video editor for my Roblox channel". Searched on the Roblox DevForum,
             Reddit (r/robloxgamedev, r/ROBLOXStudio, r/RobloxDevelopers, r/NewTubers), X, itch.io, RoHire,
             Roblox Talent Hub and Upwork. Each lead comes with a draft reply you post yourself.

  2. EMAILS  Small Roblox YouTube channels (default 300 to 30,000 subscribers) that uploaded recently and put a
             business email in their channel description. With YOUTUBE_API_KEY it uses the YouTube Data API
             (exact subscriber counts and last upload). Without it, it searches YouTube pages through Serper.
             These are the leads for the email automation.

Safety: business emails only (the ones creators publish for business), and anything that looks like a child's
channel (states an age under 16, mentions parents running it) is skipped.

Needs: SERPER_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (the same secrets the other scouts use).
Optional: YOUTUBE_API_KEY (better email leads), ANTHROPIC_API_KEY (smarter scoring and drafts),
          DB_PASSPHRASE (the email leads file is saved encrypted for download).
Standard library only.

Run:  python roblox_scout.py                 both sources
      python roblox_scout.py --posts         posts only
      python roblox_scout.py --emails        email leads only
      python roblox_scout.py --dry           print, send nothing to Telegram, save nothing
      python roblox_scout.py --selftest      check scoring and parsing, no network
"""
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SERPER_KEY = os.getenv("SERPER_API_KEY", "")
YOUTUBE_KEY = os.getenv("YOUTUBE_API_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("ROBLOX_SCOUT_MODEL", "claude-haiku-5-5")
WINDOW = os.getenv("ROBLOX_SCOUT_WINDOW", "w")              # Serper time filter: d = day, w = week, m = month
MAX_POST_QUERIES = int(os.getenv("ROBLOX_SCOUT_MAX_QUERIES", "30"))
MAX_POST_ALERTS = int(os.getenv("ROBLOX_SCOUT_MAX_ALERTS", "10"))
MIN_SCORE = int(os.getenv("ROBLOX_SCOUT_MIN_SCORE", "5"))
YT_MIN_SUBS = int(os.getenv("YT_MIN_SUBS", "300"))
YT_MAX_SUBS = int(os.getenv("YT_MAX_SUBS", "30000"))
YT_MAX_QUERIES = int(os.getenv("YT_MAX_QUERIES", "10"))       # YouTube API: each search costs 100 of 10,000 daily units
YT_SERPER_QUERIES = int(os.getenv("YT_SERPER_QUERIES", "8"))  # fallback searches when there is no YouTube key
YT_RECENT_DAYS = int(os.getenv("YT_RECENT_DAYS", "21"))
STATE_DIR = os.getenv("ROBLOX_SCOUT_STATE", "roblox_scout_state")
ARGS = set(sys.argv[1:])
DRY = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes") or "--dry" in ARGS

# =========================================================================== source 1: posts
# (search, lead type it usually finds). Add your own with ROBLOX_SCOUT_EXTRA, one per line as: TYPE|search
POST_QUERIES = [
    # Subreddits where BUYERS must tag their post [Hiring] or [Paid]: almost no sellers in these results
    ('site:reddit.com/r/forhire "[hiring]" roblox', "ANIM"),
    ('site:reddit.com/r/gameDevClassifieds "[paid]" OR "[hiring]" roblox', "ANIM"),
    ('site:reddit.com/r/HungryArtists "[hiring]" roblox', "THUMB"),
    ('site:reddit.com/r/hireanartist "[hiring]" roblox', "THUMB"),
    ('site:reddit.com/r/forhire "[hiring]" "video editor" roblox OR youtube gaming', "YTER"),
    ('site:devforum.roblox.com intitle:hiring animator OR animations', "ANIM"),
    ('site:devforum.roblox.com intitle:hiring trailer OR cinematic OR thumbnail OR icon', "VIDEO"),
    # Roblox DevForum, Find and Hire Talent: small teams paying for work right now
    ('site:devforum.roblox.com hiring animator', "ANIM"),
    ('site:devforum.roblox.com "looking for" animator OR animations paid OR commission OR robux', "ANIM"),
    ('site:devforum.roblox.com hiring trailer OR "game trailer" OR cinematic OR "showcase video"', "VIDEO"),
    ('site:devforum.roblox.com hiring thumbnail OR "game icon" OR "thumbnails"', "THUMB"),
    ('site:devforum.roblox.com "my game" "no players" OR "0 players" OR "nobody plays" OR "get players"', "LAUNCH"),
    # Reddit: solo devs and small creators
    ('site:reddit.com/r/robloxgamedev "looking for" OR hiring OR need animator OR animations', "ANIM"),
    ('site:reddit.com/r/robloxgamedev trailer OR thumbnail OR "promo video" "my game"', "VIDEO"),
    ('site:reddit.com/r/robloxgamedev "no players" OR "0 players" OR "how do i get players" OR "nobody plays"', "LAUNCH"),
    ('site:reddit.com/r/ROBLOXStudio "looking for" OR hiring OR need animator OR animation', "ANIM"),
    ('site:reddit.com/r/RobloxDevelopers hiring OR "looking for" animator OR trailer OR thumbnail', "ANIM"),
    ('site:reddit.com/r/roblox "looking for" animator OR "video editor" OR "thumbnail artist"', "ANIM"),
    ('site:reddit.com/r/NewTubers roblox editor OR thumbnail OR "editing"', "YTER"),
    ('site:reddit.com/r/SmallYoutubers roblox editor OR thumbnail OR "need help"', "YTER"),
    # X / Twitter
    ('site:x.com roblox "looking for" animator OR "need an animator" OR "hiring an animator"', "ANIM"),
    ('site:x.com roblox "looking for" "video editor" OR "thumbnail artist" OR "thumbnail designer"', "YTER"),
    ('site:x.com "#RobloxDev" "looking for" OR hiring animator OR trailer OR thumbnail', "ANIM"),
    ('site:x.com roblox "need a trailer" OR "game trailer" OR "looking for someone to make"', "VIDEO"),
    # Job boards
    ('site:rohire.dev animator OR animation OR trailer', "ANIM"),
    ('site:create.roblox.com/talent animator OR animation OR trailer OR thumbnail', "ANIM"),
    ('site:talent.roblox.com animator OR animation OR trailer', "ANIM"),
    ('site:itch.io roblox animator OR animation OR trailer "looking for" OR "help wanted"', "ANIM"),
    ('site:upwork.com/freelance-jobs roblox animation OR animator OR trailer OR "video editor"', "ANIM"),
    ('site:fiverr.com/requests OR site:freelancer.com/projects roblox animation OR animator OR trailer', "ANIM"),
]

ROBLOX_HOSTS = ("devforum.roblox.com", "rohire.dev", "create.roblox.com", "talent.roblox.com")
ROBLOX_SUBS = ("/r/robloxgamedev", "/r/roblox", "/r/robloxdevelopers")
NEED = [(r"\banimat(or|ors|ion|ions|e)\b", 3), (r"\btrailer\b", 3), (r"\bcinematic", 2), (r"\bcutscene", 2),
        (r"\bthumbnails?\b", 2), (r"\bgame icon", 2), (r"\bvideo editor\b", 3), (r"\bediting\b", 1),
        (r"\beditor\b", 1), (r"\bshowcase video", 2), (r"\bpromo(tional)? video", 2), (r"\bemotes?\b", 2),
        (r"\bvfx\b", 1), (r"\bmoon animator\b", 2), (r"\bblender\b", 1),
        (r"no players|0 players|zero players|nobody plays|no one plays|get (more )?players|player count", 3)]
# A post is only a lead when its author is BUYING. One of these must be present.
BUYER = [r"\[\s*(hiring|paid|recruiting|task)\s*\]", r"^\s*hiring\b", r"\bhiring (an?|some|for|\d|experienced|skilled)",
         r"\bis hiring\b", r"\bwe(?:'re| are) hiring\b", r"\bnow hiring\b",
         r"\blooking for (an?|some|someone|somebody|\d+|experienced|skilled|talented|good|reliable)\b(?! (work|job|clients?|commissions?|customers|buyers|projects?|gigs?))",
         r"\bneed(s|ed|ing)? (an?|someone|somebody|some(one)? to|help (with|making))\b", r"\bwho can (make|animate|edit|do|create)\b",
         r"\b(will|willing to|can|i'?ll) pay\b", r"\bpaying (in )?(\$|usd|robux|\d)", r"\bbudget\b", r"\bseeking (an?|experienced)\b",
         r"\brecruiting\b", r"\bpay(ment)? (is|of|will be|per)\b", r"\bper animation\b"]
# Any sign that the author is SELLING removes the post. These are other freelancers, not buyers.
SELLER = [r"\bfor hire\b", r"\[\s*(fh|for hire|offering|selling|available)\s*\]", r"\bhire me\b",
          r"\bcommissions? (are )?(open|available)\b", r"\b(open|available) for (commissions?|work|hire|projects?|orders)\b",
          r"\b(accepting|taking) (commissions?|orders|clients|requests|work)\b",
          r"\blooking for (work|a job|jobs|clients?|commissions?|customers|buyers|projects?|gigs?|opportunities)\b",
          r"\bi(?:'?m| am) an? [\w\s\-]{0,30}(animator|editor|designer|artist|modell?er|builder|scripter|developer|freelancer)\b",
          r"\b(i|we) (make|create|do|offer|provide|sell|design|edit|animate) [\w\s]{0,20}(for (you|your)|animations|trailers|thumbnails|icons|edits|gfx)\b",
          r"\b(my|our) (portfolio|services|prices|pricing|rates|work|showcase|commissions)\b",
          r"\bstarting (at|from)\b", r"\bprices? (start|from|list)\b", r"\bslots?\b( open| left| available)?", r"\bcheap\b",
          r"\bdm (me )?(for|to order|if you)\b", r"\bcontact me\b", r"\bcheck out my\b", r"\bfiverr\.com/(?!requests)",
          r"\bgfx (artist|designer|commissions)\b", r"^\s*\[?\s*(portfolio|showcase|services|commissions)\b",
          r"\b(animation|animator|editing|thumbnail|gfx|trailer|cinematic|ugc|modeling|building) (portfolio|services|commissions)\b",
          r"\[\s*(closed|filled)\s*\]", r"\b(closed|filled)\b\s*[\]\)|:\-]", r"^\s*(closed|filled)\b",
          r"\btutorial\b", r"\bhow to (animate|make an? (animation|trailer|thumbnail))\b", r"\btop \d+\b", r"\bfree download\b"]
UNPAID = [r"\bunpaid\b", r"\bvolunteer", r"\bpercentage only\b", r"% of (the )?(revenue|profit|earnings)",
          r"\brevenue share\b", r"\bprofit share\b", r"\bfor free\b", r"\bno pay\b", r"\bexposure\b"]
DOMAIN_BONUS = {"devforum.roblox.com": 2, "rohire.dev": 2, "create.roblox.com": 2, "talent.roblox.com": 2,
                "reddit.com": 1, "x.com": 0, "twitter.com": 0, "itch.io": 0, "upwork.com": 1}


def _hits(patterns, text):
    return sum(1 for p in patterns if re.search(p, text, re.I))


def norm_url(url):
    u = urllib.parse.urlsplit(url.strip())
    host = u.netloc.lower().replace("www.", "").replace("old.reddit.com", "reddit.com").replace("twitter.com", "x.com")
    return f"{host}{u.path.rstrip('/')}"


def host_of(url):
    return urllib.parse.urlsplit(url).netloc.lower().replace("www.", "").replace("old.", "")


def age_hours(date_text):
    """Hours since the post, from Serper's date text ("2 hours ago", "Nov 8, 2026"), or None when unknown."""
    t = (date_text or "").strip().lower()
    if not t:
        return None
    m = re.search(r"(\d+)\s*(minute|hour|day|week|month)s?\s+ago", t)
    if m:
        return int(m.group(1)) * {"minute": 1 / 60, "hour": 1, "day": 24, "week": 168, "month": 720}[m.group(2)]
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y"):
        try:
            d = datetime.strptime(date_text.strip(), fmt).replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - d).total_seconds() / 3600)
        except ValueError:
            continue
    return None


def recency_bonus(date_text):
    h = age_hours(date_text)
    if h is None:
        return 0
    return 3 if h <= 24 else (2 if h <= 72 else (1 if h <= 168 else -2))


def age_text(date_text):
    h = age_hours(date_text)
    if h is None:
        return ""
    if h < 1:
        return "posted under an hour ago"
    if h < 48:
        return f"posted about {int(h)} hour{'s' if int(h) != 1 else ''} ago"
    return f"posted about {int(h // 24)} days ago"


def classify(text, hint):
    t = text.lower()
    if re.search(r"no players|0 players|zero players|nobody plays|no one plays|get (more )?players|player count", t):
        return "LAUNCH"
    if re.search(r"youtube|channel|video editor|subscribers|\byt\b", t):
        return "YTER"
    if re.search(r"trailer|cinematic|cutscene|showcase video|promo(tional)? video", t):
        return "VIDEO"
    if re.search(r"thumbnail|game icon", t):
        return "THUMB"
    if re.search(r"animat|emote", t):
        return "ANIM"
    return hint


def is_roblox(item):
    link = item.get("link", "").lower()
    text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
    return "roblox" in text or any(h in link for h in ROBLOX_HOSTS) or any(s in link for s in ROBLOX_SUBS)


BOILERPLATE = re.compile(r"\s*[-|:]\s*(find and hire talent|collaboration|developer forum|roblox|reddit|itch\.io|"
                         r"r/\w+|x|twitter|community|help wanted or offered)\b.*$", re.I)
NO_PLAYERS = r"no players|0 players|zero players|nobody plays|no one plays|get (more )?players|no visits|0 visits|player count"


def clean_text(item):
    """Title without the site name ("... - Find and Hire Talent - Developer Forum") plus the snippet."""
    title = BOILERPLATE.sub("", item.get("title", ""))
    return f"{title} {item.get('snippet', '')}", title


def is_seller(item):
    text, title = clean_text(item)
    return _hits(SELLER, text) > 0 or _hits(SELLER, title) > 0


def rule_score(item, hint):
    """Returns (score, type) or (0, None) when the result is not a BUYER lead."""
    text, _ = clean_text(item)
    if not is_roblox(item) or is_seller(item):
        return 0, None
    need = min(6, sum(w for p, w in NEED if re.search(p, text, re.I)))
    struggling = bool(re.search(NO_PLAYERS, text, re.I)) and bool(re.search(r"\bmy (first |new |own )?(roblox )?(game|experience)\b", text, re.I))
    buyer = _hits(BUYER, text)
    if need == 0 or (buyer == 0 and not struggling):
        return 0, None
    score = need + min(6, 3 * buyer) + (3 if struggling else 0) + recency_bonus(item.get("date", ""))
    score += DOMAIN_BONUS.get(host_of(item.get("link", "")), 0)
    if _hits(UNPAID, text):
        score -= 4
    return score, classify(text, hint)


TEMPLATES = {
    "ANIM": ("Hey, I make Roblox animations (R6 and R15, combat, idles, emotes, cutscenes). I can send a few "
             "samples that match your game's style. How many animations do you need and what rig are you using?"),
    "VIDEO": ("Hey, I make Roblox game trailers and cinematics, the short kind that work for the game page, "
              "TikTok and YouTube Shorts. If you send me the game link I can tell you what shots I would use "
              "and send a couple of past examples."),
    "THUMB": ("Hey, I do Roblox thumbnails and game icons. A better icon is usually the cheapest way to get more "
              "clicks from the discover page. Send the game link and I will tell you what I would change."),
    "LAUNCH": ("Most new games get stuck there because the icon and thumbnail do not get clicks, so the algorithm "
               "never tests the game with more players. A short trailer for Shorts and TikTok plus a stronger "
               "icon usually helps more than ads at the start. What is the game link? Happy to give honest feedback."),
    "YTER": ("Hey, I edit Roblox videos and make thumbnails and animated intros for smaller channels. If you "
             "share your channel I can do one thumbnail or a short edit as a sample so you can see if it fits."),
}
LABEL = {"ANIM": "Needs animations", "VIDEO": "Needs a trailer or cinematic", "THUMB": "Needs thumbnails or icon",
         "LAUNCH": "Game launched, no players yet", "YTER": "Roblox YouTuber needs editing"}

SYSTEM_PROMPT = """You help Samuel, a freelancer who sells Roblox animations, game trailers and cinematics,
thumbnails and game icons, and video editing for Roblox YouTubers. You judge a public post found by search.
Reply with JSON only, no other text, with these keys:
fit: 0 to 10, how likely the poster would pay Samuel for this. The poster must be a BUYER. Score 0 for anyone
selling or advertising their own services (animators, editors, GFX or thumbnail artists, portfolios, commissions open),
and 0 to 2 for closed or filled jobs, tutorials, unpaid or profit share only requests, and anyone who looks under 16.
type: one of ANIM, VIDEO, THUMB, LAUNCH, YTER, SKIP
who: solo dev, small team, studio, youtuber or other
budget: the budget or pay if stated, else empty
summary: at most 20 words on what they need
reply: 2 to 4 short sentences Samuel could post or DM. Specific to their post, casual, no hype, no links, no
dashes of any kind, never suggest a call. Ask one useful question (rig, number of animations, game link)."""


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
    text = re.sub(r"\s*(?:—|–|--|\s-\s)\s*", ", ", text)
    return re.sub(r"(?<=\w)-(?=\w)", " ", text).strip()


# =========================================================================== source 2: YouTube email leads
YT_TOPICS = [
    "roblox story", "roblox funny moments", "roblox brookhaven", "roblox obby",
    "roblox horror", "roblox devlog", "making a roblox game", "roblox but", "roblox tycoon",
    "roblox blox fruits", "roblox shorts", "roblox studio tutorial", "roblox edit",
]
YT_SERPER = [
    'site:youtube.com roblox "@gmail.com" "business"',
    'site:youtube.com roblox "business inquiries" "@gmail.com"',
    'site:youtube.com roblox devlog "@gmail.com" OR "@outlook.com"',
    'site:youtube.com roblox "for business" "@gmail.com" subscribers',
    'site:youtube.com roblox story "@gmail.com"',
    'site:youtube.com "roblox" "contact" "@gmail.com" OR "@hotmail.com" OR "@outlook.com"',
    'site:youtube.com roblox "sponsorships" OR "collabs" "@gmail.com"',
    'site:youtube.com roblox obby OR tycoon "@gmail.com"',
    'site:youtube.com roblox horror "@gmail.com"',
]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+(?:@|\s?\[at\]\s?|\s?\(at\)\s?)[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
BAD_EMAIL = re.compile(r"noreply|no-reply|example\.|@youtube|@google|@roblox|support@|privacy@|abuse@|\.png$|\.jpg$", re.I)
# Signs a channel is run by a child. These are skipped: no email, no outreach.
CHILD = [r"\bi(?:'?m| am) (?:[5-9]|1[0-5])\b", r"\b(?:[5-9]|1[0-5]) ?(?:years? old|yo|y/o)\b",
         r"\bmy (?:mom|mum|dad|mother|father|parents?) (?:runs|manages|helps|uploads)",
         r"\bparent(?:s|al)? (?:email|managed|supervised)", r"\bkid(?:s)? channel\b", r"\bi(?:'?m| am) a kid\b",
         r"\bage (?:[5-9]|1[0-5])\b", r"\bgrade [1-9]\b"]
SUBS_RE = re.compile(r"([\d.,]+)\s*([KkMm])?\s+subscribers")


# Channels that SELL editing, thumbnails, GFX or animation are competitors, not buyers
SELLER_CHANNEL = [r"\bcommissions?\b", r"\bfor hire\b", r"\bhire me\b", r"\bportfolio\b", r"\bfiverr\b", r"\bupwork\b",
                  r"\b(thumbnail|gfx|graphic|logo|icon) (designer|artist|maker|design)\b", r"\bgfx\b",
                  r"\b(video )?editor for\b", r"\bediting services\b", r"\bmy services\b", r"\bprices?\b", r"\brates\b",
                  r"\border(s|ing)?\b", r"\bdm (me )?for\b", r"\bi (make|do|edit|design|create) (thumbnails|edits|videos|animations|intros|logos) for\b",
                  r"\bfreelanc", r"\bclients?\b", r"\bstudio services\b", r"\banimator for hire\b"]


def is_seller_channel(text):
    return _hits(SELLER_CHANNEL, text or "") > 0


def find_emails(text):
    out = []
    for raw in EMAIL_RE.findall(text or ""):
        e = re.sub(r"\s?[\[\(]at[\]\)]\s?", "@", raw).strip(".,;:()[]<>").lower()
        if "@" in e and not BAD_EMAIL.search(e) and e not in out:
            out.append(e)
    return out


def looks_like_child(text):
    return _hits(CHILD, text or "") > 0


def parse_subs(text):
    m = SUBS_RE.search(text or "")
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    mult = {"k": 1_000, "m": 1_000_000}.get((m.group(2) or "").lower(), 1)
    return int(n * mult)


def angle_for(text):
    t = (text or "").lower()
    if re.search(r"devlog|making a (roblox )?game|my game|studio|developer|\bdev\b", t):
        return "Game dev: offer a trailer, animations or an icon for their game"
    if re.search(r"animat|story|stories|cartoon|skit", t):
        return "Story/animation channel: offer animation help or faster turnaround"
    if re.search(r"shorts|tiktok", t):
        return "Shorts creator: offer short edits and thumbnails"
    return "Gameplay channel: offer editing, thumbnails or an animated intro"


def yt_get(path, params):
    params = dict(params, key=YOUTUBE_KEY)
    url = f"https://www.googleapis.com/youtube/v3/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=40) as r:
        return json.load(r)


def youtube_api_leads(seen):
    after = (datetime.now(timezone.utc) - timedelta(days=YT_RECENT_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    channels, last_upload = [], {}
    topics = list(YT_TOPICS)
    day = datetime.now(timezone.utc).timetuple().tm_yday
    topics = topics[day % len(topics):] + topics[:day % len(topics)]  # rotate so every topic gets used
    for q in topics[:YT_MAX_QUERIES]:
        try:
            data = yt_get("search", {"part": "snippet", "q": q, "type": "video", "order": "date",
                                     "publishedAfter": after, "maxResults": 50, "relevanceLanguage": "en"})
        except urllib.error.HTTPError as e:
            print(f"YouTube search failed (HTTP {e.code}) for {q}: {e.read()[:200]!r}")
            if e.code in (400, 403):
                break
            continue
        for it in data.get("items", []):
            cid = it["snippet"]["channelId"]
            if f"yt:{cid}" in seen:
                continue
            if cid not in channels:
                channels.append(cid)
            last_upload.setdefault(cid, it["snippet"].get("publishedAt", ""))
    print(f"YouTube: {len(channels)} new channels to check")
    leads, checked = [], []
    for i in range(0, len(channels), 50):
        batch = channels[i:i + 50]
        try:
            data = yt_get("channels", {"part": "snippet,statistics", "id": ",".join(batch), "maxResults": 50})
        except urllib.error.HTTPError as e:
            print(f"YouTube channels failed (HTTP {e.code})")
            break
        for ch in data.get("items", []):
            cid, sn, st = ch["id"], ch["snippet"], ch.get("statistics", {})
            checked.append(f"yt:{cid}")
            subs = int(st.get("subscriberCount", 0) or 0)
            desc = sn.get("description", "")
            if not (YT_MIN_SUBS <= subs <= YT_MAX_SUBS) or int(st.get("videoCount", 0) or 0) < 5:
                continue
            if looks_like_child(desc) or sn.get("madeForKids") or is_seller_channel(sn.get("title", "") + " " + desc):
                continue
            emails = find_emails(desc)
            if not emails:
                continue
            leads.append({
                "source": "youtube_api", "channel": sn.get("title", ""), "channel_id": cid,
                "url": f"https://www.youtube.com/channel/{cid}", "email": emails[0], "other_emails": emails[1:],
                "subscribers": subs, "videos": int(st.get("videoCount", 0) or 0),
                "country": sn.get("country", ""), "last_upload": last_upload.get(cid, "")[:10],
                "angle": angle_for(sn.get("title", "") + " " + desc), "key": f"yt:{cid}",
            })
    return leads, checked


def youtube_serper_leads(seen):
    leads, checked = [], []
    day = datetime.now(timezone.utc).timetuple().tm_yday
    queries = YT_SERPER[day % len(YT_SERPER):] + YT_SERPER[:day % len(YT_SERPER)]
    for q in queries[:YT_SERPER_QUERIES]:
        try:
            results = serper(q, window="m")
        except Exception as e:
            print(f"search failed ({e}): {q}")
            if isinstance(e, urllib.error.HTTPError):
                break
            continue
        for item in results:
            link = item.get("link", "")
            m = re.search(r"youtube\.com/(@[\w.\-]+|channel/[\w\-]+|c/[\w.\-]+|user/[\w.\-]+)", link)
            if not m:
                continue
            handle = m.group(1)
            key = f"yt:{handle.lower()}"
            text = f"{item.get('title', '')} {item.get('snippet', '')}"
            checked.append(key)
            if key in seen or "roblox" not in text.lower() or looks_like_child(text) or is_seller_channel(text):
                continue
            emails = find_emails(text)
            subs = parse_subs(text)
            if not emails or (subs is not None and not (YT_MIN_SUBS <= subs <= YT_MAX_SUBS)):
                continue
            leads.append({
                "source": "youtube_search", "channel": re.sub(r"\s*-\s*YouTube\s*$", "", item.get("title", "")),
                "channel_id": handle, "url": f"https://www.youtube.com/{handle}", "email": emails[0],
                "other_emails": emails[1:], "subscribers": subs if subs is not None else "",
                "videos": "", "country": "", "last_upload": "", "angle": angle_for(text), "key": key,
            })
    return leads, checked


# =========================================================================== shared plumbing
def serper(query, window=None):
    body = json.dumps({"q": query, "num": 10, "tbs": f"qdr:{window or WINDOW}"}).encode()
    req = urllib.request.Request("https://google.serper.dev/search", data=body, method="POST",
                                 headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r).get("organic", [])


def load_json(name, default):
    try:
        with open(os.path.join(STATE_DIR, name)) as f:
            return json.load(f)
    except Exception:
        return default


def save_json(name, data):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(os.path.join(STATE_DIR, name), "w") as f:
        json.dump(data, f, indent=1)


def prune(seen, days=180):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return {k: v for k, v in seen.items() if v >= cutoff}


def telegram(text):
    if DRY or not (TG_TOKEN and TG_CHAT):
        print(("(dry run) " if DRY else "(no Telegram secrets) ") + "message:\n" + text + "\n")
        return
    time.sleep(0.6)
    data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": text[:3900], "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data, timeout=30)
    except Exception as e:
        print(f"telegram failed: {e}")


def format_post(n, lead):
    when = age_text(lead.get("date", ""))
    extra = ", ".join(x for x in (f"by a {lead['who']}" if lead.get("who") else "",
                                  f"budget {lead['budget']}" if lead.get("budget") else "", when) if x)
    return (f"Roblox lead {n}: {LABEL.get(lead['type'], lead['type'])}\n"
            f"Fit {lead['fit']}/10 on {host_of(lead['link'])}" + (f", {extra}" if extra else "") + "\n\n"
            f"{lead.get('summary') or lead.get('title', '')}\n{lead['link']}\n\n"
            f"Draft reply:\n{lead['reply']}")


def format_emails(leads, total):
    lines = [f"Roblox email leads: {len(leads)} new small creator channels (sellers filtered out) with a business email ({total} saved in total)."]
    for i, l in enumerate(leads, 1):
        subs = f"{l['subscribers']:,} subs" if isinstance(l["subscribers"], int) else "subs unknown"
        up = f", last upload {l['last_upload']}" if l.get("last_upload") else ""
        lines.append(f"\n{i}. {l['channel']} ({subs}{up})\n{l['email']}\n{l['url']}\n{l['angle']}")
    return "\n".join(lines)


# =========================================================================== runs
def run_posts(seen):
    queries = list(POST_QUERIES)
    for line in os.getenv("ROBLOX_SCOUT_EXTRA", "").splitlines():
        if "|" in line:
            kind, q = line.split("|", 1)
            queries.append((q.strip(), kind.strip().upper()))
    found, titles, stopped = {}, set(), None
    for q, hint in queries[:MAX_POST_QUERIES]:
        try:
            results = serper(q)
        except urllib.error.HTTPError as e:
            stopped = f"Roblox scout stopped: search returned HTTP {e.code}. Check the Serper credits and key."
            break
        except Exception as e:
            print(f"search failed ({e}): {q}")
            continue
        for item in results:
            key = norm_url(item.get("link", ""))
            title_key = re.sub(r"\W+", "", (item.get("title", "") + item.get("snippet", "")[:80]).lower())
            if not key or key in seen or key in found or title_key in titles:
                continue
            score, kind = rule_score(item, hint)
            if score >= MIN_SCORE:
                titles.add(title_key)
                found[key] = dict(item, score=score, type=kind, key=key)
    ranked = sorted(found.values(), key=lambda x: -x["score"])
    print(f"posts: {len(ranked)} candidates after rules")
    leads = []
    for item in ranked[:MAX_POST_ALERTS * 3]:
        judged = ai_judge(item)
        if judged:
            if judged.get("type") == "SKIP" or judged["fit"] < 5:
                continue
            kind = judged["type"] if judged.get("type") in TEMPLATES else item["type"]
            lead = dict(item, type=kind, fit=judged["fit"], who=judged.get("who", ""), budget=judged.get("budget", ""),
                        summary=judged.get("summary", ""), reply=judged.get("reply") or TEMPLATES[kind])
        else:
            lead = dict(item, fit=min(10, item["score"]), who="", budget="", summary="", reply=TEMPLATES[item["type"]])
        leads.append(lead)
        if len(leads) >= MAX_POST_ALERTS:
            break
    leads.sort(key=lambda x: (age_hours(x.get("date", "")) or 999, -x["fit"]))
    return leads, [i["key"] for i in ranked], stopped


def run_emails(seen):
    if YOUTUBE_KEY:
        leads, checked = youtube_api_leads(seen)
        if not leads and SERPER_KEY:
            more, more_checked = youtube_serper_leads(seen)
            leads, checked = leads + more, checked + more_checked
    else:
        leads, checked = youtube_serper_leads(seen)
    unique, emails = [], set()
    for l in leads:
        if l["email"] not in emails:
            emails.add(l["email"])
            unique.append(l)
    return unique, checked


def save_email_leads(new):
    """All email leads ever found, in roblox_scout_state/ (cached, never committed) plus an encrypted copy."""
    allp = load_json("email_leads.json", [])
    known = {l["email"] for l in allp}
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for l in new:
        if l["email"] not in known:
            allp.append(dict(l, found=stamp, status="new"))
    save_json("email_leads.json", allp)
    fields = ["found", "status", "channel", "email", "other_emails", "subscribers", "videos", "country",
              "last_upload", "angle", "url", "source"]
    path = os.path.join(STATE_DIR, "roblox_email_leads.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for l in allp:
            w.writerow(dict(l, other_emails=" ".join(l.get("other_emails", []))))
    return len(allp)


def main():
    if not SERPER_KEY and not YOUTUBE_KEY:
        sys.exit("SERPER_API_KEY is missing (and no YOUTUBE_API_KEY either)")
    do_posts = "--emails" not in ARGS
    do_emails = "--posts" not in ARGS
    seen = prune(load_json("seen.json", {}))
    now = datetime.now(timezone.utc).isoformat()
    posts, email_leads, stopped, total = [], [], None, len(load_json("email_leads.json", []))

    if do_posts and SERPER_KEY:
        posts, checked, stopped = run_posts(seen)
        if posts:
            telegram(f"Roblox scout: {len(posts)} new BUYER{'S' if len(posts) != 1 else ''} (people hiring or needing help, "
                     "sellers filtered out), newest first. Reply on the post or DM them.")
            for i, lead in enumerate(posts, 1):
                telegram(format_post(i, lead))
        if not DRY:
            for k in checked:
                seen[k] = now
    if do_emails and not stopped:
        email_leads, checked = run_emails(seen)
        if not DRY:
            for k in checked:
                seen[k] = now
            total = save_email_leads(email_leads)
        if email_leads:
            telegram(format_emails(email_leads, total))

    src = "YouTube API" if YOUTUBE_KEY else "Serper search (add YOUTUBE_API_KEY for more and better email leads)"
    summary = (f"Roblox scout finished.\nPost leads: {len(posts)}\nNew email leads: {len(email_leads)} "
               f"(total saved: {total})\nEmail source: {src}")
    if stopped:
        summary += f"\n\n{stopped}"
    telegram(summary)
    if not DRY:
        save_json("seen.json", seen)
        with open("roblox_leads_today.json", "w") as f:  # posts are public pages, safe to keep as an artifact
            json.dump(posts, f, indent=2)


def selftest():
    def item(title, snippet, link, date="1 day ago"):
        return {"title": title, "snippet": snippet, "link": link, "date": date}
    good = [
        (item("[HIRING] Animator for anime fighting game", "Looking for an animator, paying 1500 robux per animation",
              "https://devforum.roblox.com/t/hiring-animator/123"), "ANIM"),
        (item("My roblox game has 0 players, how do I get players?", "Released my first game last week, need help",
              "https://www.reddit.com/r/robloxgamedev/comments/abc/x/"), "LAUNCH"),
        (item("Need a trailer for my Roblox game", "Looking for someone to make a game trailer, budget $50",
              "https://x.com/somedev/status/1"), "VIDEO"),
        (item("Looking for a video editor for my roblox channel", "Small youtuber, need help editing, paying per video",
              "https://www.reddit.com/r/NewTubers/comments/def/y/"), "YTER"),
    ]
    bad = [
        item("Roblox Animator Portfolio - Find and Hire Talent - Developer Forum",
             "Hi, I'm a roblox animator with 3 years of experience, looking for work. Paid commissions, DM me.",
             "https://devforum.roblox.com/t/animator-portfolio/5"),
        item("Roblox trailers and cinematics, cheap", "I make cinematic trailers for your roblox game, starting at $20",
             "https://x.com/seller/status/2"),
        item("Thumbnail and icon commissions", "Roblox GFX artist, need a thumbnail? Slots open, check out my work",
             "https://www.reddit.com/r/roblox/comments/s/y/"),
        item("[FH] Roblox video editor", "Looking for clients who need a video editor for roblox videos, paid",
             "https://www.reddit.com/r/forhire/comments/z/"),
        item("Need an animator? Hire me", "Roblox animator, open for commissions", "https://devforum.roblox.com/t/x/6"),
        item("[FOR HIRE] Roblox animator, commissions open", "My portfolio, looking for work, paid",
             "https://devforum.roblox.com/t/for-hire/1"),
        item("[CLOSED] Hiring animator", "looking for an animator, paid robux", "https://devforum.roblox.com/t/c/2"),
        item("How to animate in Roblox Studio tutorial", "learn animation", "https://youtube.com/watch?v=1"),
        item("Looking for an animator", "need an animator for my game paid", "https://reddit.com/r/Minecraft/x"),
    ]
    ok = True
    for it, want in good:
        s, k = rule_score(it, "ANIM")
        print(f"good  score={s:2} type={k} want={want}  {it['title']}")
        ok &= s >= MIN_SCORE and k == want
    for it in bad:
        s, k = rule_score(it, "ANIM")
        print(f"bad   score={s:2} type={k}  {it['title']}")
        ok &= s < MIN_SCORE
    assert find_emails("Business: cool.dev [at] gmail.com or noreply@youtube.com") == ["cool.dev@gmail.com"]
    assert find_emails("contact me: Ben.Edits@Outlook.com.") == ["ben.edits@outlook.com"]
    assert looks_like_child("hi im 12 and i play roblox") and looks_like_child("My mom runs this channel")
    assert not looks_like_child("I post roblox videos 3 times a week. Business: a@gmail.com")
    assert parse_subs("Roblox stuff. 12.4K subscribers. 230 videos") == 12400
    assert parse_subs("1,250 subscribers") == 1250
    assert is_seller_channel("Roblox thumbnail designer, DM for prices. Business: x@gmail.com")
    assert not is_seller_channel("I upload roblox obby videos every week! Business: x@gmail.com")
    ok &= rule_score(item("[Hiring] Roblox animator", "Need 10 combat animations, budget $100",
                          "https://www.reddit.com/r/forhire/comments/q/"), "ANIM")[0] >= MIN_SCORE
    assert "Game dev" in angle_for("Roblox devlog: making a roblox game")
    assert clean_reply("Hey - I can help—fast") == "Hey, I can help, fast"
    print("selftest", "passed" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    selftest() if "--selftest" in ARGS else main()
