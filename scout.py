"""
Scouting runner. Finds and scores prospects per service. It NEVER sends email.

Examples:
  python scout.py --list
  python scout.py --service whatsapp_api --max 60
  python scout.py --service whatsapp_api --countries AE,UK --keywords "dental clinic,med spa" --max 30
  python scout.py --service whatsapp_api --export-only
"""
import argparse
import asyncio
from seen import known_domain
import random
from lead_filter import clean_emails, service_junk_reason
import csv
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import aiohttp

from config import BASE_DIR, DEFAULT_HEADERS
from db import get_connection, init_db
from enricher.researcher import DeepBusinessResearcher
from offers.cleaner import clean_business_name, is_valid_prospect_domain
from scout_signals import SCORERS, SCOUT_UA, inspect_site
from scrapers.direct_web import DirectWebScraper
from scrapers.multi_platform import MultiPlatformScraper
from scrapers.serper import SerperScraper, SerperUnavailable
from services import SERVICES, get_service, validate_mailbox_map

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scout")

EXPORT_DIR = BASE_DIR / "exports"

# Countries where unsolicited email to businesses is restricted or needs care.
# Scouting is fine everywhere, this only flags how to approach the lead afterwards.
CAREFUL_REGIONS = {
    "DE", "AT", "FR", "BE", "LU", "NL", "ES", "IT", "PT", "DK", "FI", "SE", "NO", "IE", "PL", "CZ",
    "RO", "GR", "UK", "CH", "EE", "LT", "LV", "SK", "SI", "HU", "HR", "CY", "MT", "IS", "LI", "MC",
    "ZA",  # South Africa: POPIA section 69 needs consent for electronic direct marketing, businesses included
}


def init_scout_tables():
    init_db()
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scout_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id TEXT NOT NULL,
                name TEXT NOT NULL,
                domain TEXT NOT NULL,
                website TEXT,
                country TEXT,
                city TEXT,
                keyword TEXT,
                phone TEXT,
                emails_json TEXT,
                owner_name TEXT,
                score INTEGER DEFAULT 0,
                evidence_json TEXT,
                approach_note TEXT,
                status TEXT DEFAULT 'new',   -- new, shortlisted, approved, skipped, contacted, replied, won, lost
                sent_at TIMESTAMP,
                sender_inbox TEXT,
                gmail_thread_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(service_id, domain)
            )
        """)
        for col in ("sent_at TIMESTAMP", "sender_inbox TEXT", "gmail_thread_id TEXT",
                    "last_reply_id TEXT", "reply_snippet TEXT", "replied_at TIMESTAMP", "sent_subject TEXT",
                    "followup_sent_at TIMESTAMP", "skip_reason TEXT", "send_attempts INTEGER DEFAULT 0", "sent_to TEXT", "sent_body TEXT", "followup_body TEXT"):
            try:
                conn.execute(f"ALTER TABLE scout_leads ADD COLUMN {col}")
            except Exception:
                pass
        conn.commit()


def approach_note(country: str, emails: List[str], has_form: bool) -> str:
    if country in CAREFUL_REGIONS:
        return "Regulated region: use contact form or LinkedIn first, or a role address with a clear opt out. Check local rules."
    if emails:
        return "Email allowed with real sender identity, postal address and a working opt out line."
    return "Use contact form or phone route." if has_form else "No public contact route found."


SEARCH_URL = "https://html.duckduckgo.com/html/"
EMPTY_STREAK_LIMIT = 6  # stop after this many searches in a row bring back nothing at all


async def search_engine_check() -> str:
    """Returns "" when the search engine answers with results, otherwise a short reason.
    The scrapers hide their errors, so without this a blocked engine looks like "0 new businesses"."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    reason = ""
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession(headers=headers) as s:
                async with s.post(SEARCH_URL, data={"q": "dental clinic Dubai official site"},
                                  timeout=aiohttp.ClientTimeout(total=15)) as r:
                    html = await r.text()
                    if r.status == 200 and "result__a" in html:
                        return ""
                    reason = f"search engine answered HTTP {r.status} with no results"
        except asyncio.TimeoutError:
            reason = "search engine did not answer within 15s"
        except Exception as e:
            reason = f"search engine error: {type(e).__name__}"
        await asyncio.sleep(5 * (attempt + 1))
    return reason


def _blocked_note(service_id: str, reason: str, tell: bool = True):
    msg = (f"Scouting skipped for {service_id}: {reason}. DuckDuckGo blocks most cloud servers, "
           f"including GitHub Actions, so scouting needs your PC or a search API.")
    logger.warning(msg)
    if not tell:
        return
    try:
        import tg
        tg.send(f"<b>Scouting blocked: {tg.esc(service_id)}</b>\n{tg.esc(msg)}")
    except Exception:
        pass


def _serper_note_due() -> bool:
    """True at most once a day, so an exhausted Serper key does not message you every 2 hours."""
    with get_connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS scout_state (key TEXT PRIMARY KEY, value TEXT)")
        row = conn.execute("SELECT value FROM scout_state WHERE key='serper_note'").fetchone()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if row and row[0] == today:
            return False
        conn.execute("INSERT OR REPLACE INTO scout_state (key, value) VALUES ('serper_note', ?)", (today,))
        conn.commit()
    return True


def use_serper() -> bool:
    """Serper is used when SERPER_API_KEY is set, unless SCOUT_SOURCE=web forces the free web search."""
    return bool(os.getenv("SERPER_API_KEY")) and os.getenv("SCOUT_SOURCE", "").lower() != "web"


async def scout_service(service_id: str, countries: List[str], keywords: List[str], max_new: int) -> Dict[str, Any]:
    """Returns {"added": n, "blocked": reason}. blocked is "" when the search source worked."""
    svc = get_service(service_id)
    if svc.engine != "scout":
        logger.info(f"{svc.id} is handled by {svc.engine}, nothing to scout here.")
        return {"added": 0, "blocked": ""}
    scorer = SCORERS[svc.id]
    countries = countries or svc.countries
    keywords = keywords or svc.keywords

    init_scout_tables()
    backlog_max = int(os.getenv("SCOUT_BACKLOG_MAX") or 40)
    with get_connection() as conn:
        backlog = conn.execute(
            "SELECT COUNT(*) FROM scout_leads WHERE service_id=? AND status='approved' AND sent_at IS NULL", (svc.id,)
        ).fetchone()[0]
    if backlog >= backlog_max:
        logger.info(f"Skipping scouting for {svc.id}: {backlog} approved leads are still waiting to be sent "
                    f"(limit {backlog_max}), no search credits used.")
        return {"added": 0, "blocked": ""}
    serper = SerperScraper() if use_serper() else None
    serper_max = int(os.getenv("SERPER_MAX_QUERIES") or 16)
    if serper:
        logger.info(f"Search source: Serper API (up to {serper_max} queries)")
    else:
        reason = await search_engine_check()
        if reason:
            _blocked_note(svc.id, reason)
            return {"added": 0, "blocked": reason}
        logger.info("Search source: DuckDuckGo web search")
    blocked = ""
    direct = DirectWebScraper()
    platforms = MultiPlatformScraper()
    researcher = DeepBusinessResearcher(timeout=10)
    sem = asyncio.Semaphore(5)
    headers = dict(DEFAULT_HEADERS)
    headers["User-Agent"] = SCOUT_UA
    added = 0
    empty_streak = 0

    async with aiohttp.ClientSession(headers=headers, connector=aiohttp.TCPConnector(limit=10)) as session:
        # Shuffled every run, so repeat runs search a different slice instead of the same first queries.
        pairs = [(k, c) for k in keywords for c in countries]
        random.shuffle(pairs)
        for kw, ctry in pairs:
            if added >= max_new:
                break
            logger.info(f"Scouting [{kw}] in [{ctry}] for {svc.id}")
            leads: List[Dict[str, Any]] = []
            if serper:
                if serper.queries >= serper_max:
                    break
                try:
                    leads = await serper.search(kw, ctry, limit=10)
                except SerperUnavailable as e:
                    blocked = f"{e}. The free credits are probably used up"
                    _blocked_note(svc.id, blocked, tell=_serper_note_due())
                    break
            else:
                await asyncio.sleep(random.uniform(4, 8))
                res = await asyncio.gather(
                    direct.search(keyword=kw, country=ctry, city="General", limit=8),
                    platforms.search_all_approved_platforms(keyword=kw, country=ctry, city="General", per_platform_limit=2),
                    return_exceptions=True,
                )
                for r in res:
                    if isinstance(r, list):
                        leads.extend(r)
            empty_streak = 0 if leads else empty_streak + 1
            if empty_streak >= EMPTY_STREAK_LIMIT:
                blocked = f"{empty_streak} searches in a row returned nothing"
                _blocked_note(svc.id, blocked)
                break

            seen = set()
            for lead in leads:
                if added >= max_new:
                    break
                domain, website = lead.get("domain"), lead.get("website")
                if not domain or not website or domain in seen or not is_valid_prospect_domain(domain, website) or service_junk_reason(svc.id, lead.get("name"), domain, website):
                    continue
                seen.add(domain)

                with get_connection() as conn:
                    if known_domain(conn, domain):
                        continue

                sig = await inspect_site(session, website, sem)
                if sig is None:
                    logger.info(f"robots.txt disallows {domain}, skipped")
                    continue
                try:
                    contact = await researcher.research_business(website)
                except Exception:
                    contact = {}
                contact["phone"] = lead.get("phone")
                emails = clean_emails(contact.get("emails", []), domain)[:3]

                score, evidence = scorer(sig, lead, contact)
                status = "shortlisted" if score >= svc.min_score else "skipped"
                name = clean_business_name(lead["name"], domain)
                with get_connection() as conn:
                    conn.execute(
                        """INSERT OR IGNORE INTO scout_leads
                           (service_id, name, domain, website, country, city, keyword, phone,
                            emails_json, owner_name, score, evidence_json, approach_note, status)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (svc.id, name, domain, website, ctry, lead.get("city"), kw, lead.get("phone"),
                         json.dumps(emails), contact.get("founder_name"), score, json.dumps(evidence),
                         approach_note(ctry, emails, sig["has_contact_form"]), status),
                    )
                    conn.commit()
                added += 1
                logger.info(f"  {name} ({domain}) score {score} -> {status}")
            if added >= max_new or blocked or (serper and serper.queries >= serper_max):
                break
    logger.info(f"Scouted {added} new businesses for {svc.id}")
    try:
        import tg
        with get_connection() as conn:
            short = conn.execute(
                "SELECT COUNT(*) FROM scout_leads WHERE service_id=? AND status='shortlisted'", (svc.id,)
            ).fetchone()[0]
        tg.send(
            f"<b>Scouting finished: {tg.esc(svc.id)}</b>\n"
            f"New businesses found this run: {added}\n"
            f"Shortlisted (approved automatically on the next step): {short}"
        )
    except Exception as e:
        logger.debug(f"Telegram note skipped: {e}")
    return {"added": added, "blocked": blocked}


def export_shortlist(service_id: str) -> str:
    init_scout_tables()
    EXPORT_DIR.mkdir(exist_ok=True)
    path = EXPORT_DIR / f"{service_id}_shortlist_{datetime.now():%Y%m%d_%H%M}.csv"
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM scout_leads WHERE service_id=? AND status='shortlisted' ORDER BY score DESC", (service_id,)
        ).fetchall()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["score", "name", "website", "country", "city", "owner", "phone", "emails", "why it fits", "how to approach"])
        for r in rows:
            w.writerow([
                r["score"], r["name"], r["website"], r["country"], r["city"], r["owner_name"], r["phone"],
                ", ".join(json.loads(r["emails_json"] or "[]")),
                " | ".join(json.loads(r["evidence_json"] or "[]")),
                r["approach_note"],
            ])
    logger.info(f"Exported {len(rows)} shortlisted leads to {path}")
    return str(path)


def main():
    ap = argparse.ArgumentParser(description="Scouting runner (no sending)")
    ap.add_argument("--list", action="store_true", help="Show services and mailbox assignments")
    ap.add_argument("--service", choices=list(SERVICES))
    ap.add_argument("--countries", default="")
    ap.add_argument("--keywords", default="")
    ap.add_argument("--max", type=int, default=50, help="Max new businesses to scout this run")
    ap.add_argument("--export-only", action="store_true")
    a = ap.parse_args()

    if a.list or not a.service:
        for sid in SERVICES:
            s = get_service(sid)
            print(f"{sid:14} engine={s.engine:14} mailbox={s.mailbox or 'NOT SET'}  {s.label}")
        for p in validate_mailbox_map():
            print("WARNING:", p)
        return

    if not a.export_only:
        asyncio.run(scout_service(
            a.service,
            [c.strip().upper() for c in a.countries.split(",") if c.strip()],
            [k.strip() for k in a.keywords.split(",") if k.strip()],
            a.max,
        ))
    export_shortlist(a.service)


if __name__ == "__main__":
    main()
