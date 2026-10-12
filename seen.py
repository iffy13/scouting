"""
One place that answers: have we already looked at this business, or already emailed this address?
Checks every service, plus the history of your older system. Used by the scout and by send_paced.py.
"""
import sqlite3


def norm(domain: str) -> str:
    d = (domain or "").lower().strip()
    return d[4:] if d.startswith("www.") else d


def known_domain(conn, domain: str) -> bool:
    """True if this website was already scouted for ANY service, or already emailed by the older system."""
    d = norm(domain)
    if conn.execute("SELECT 1 FROM scout_leads WHERE domain IN (?, ?) LIMIT 1", (d, "www." + d)).fetchone():
        return True
    try:
        old = conn.execute(
            """SELECT 1 FROM businesses b
               JOIN emails e ON e.business_id = b.id
               JOIN sequences s ON s.email_id = e.id
               WHERE b.domain IN (?, ?) AND s.last_sent_at IS NOT NULL LIMIT 1""",
            (d, "www." + d),
        ).fetchone()
    except sqlite3.Error:
        old = None
    return bool(old)


def already_emailed(conn, email: str) -> bool:
    """True if this address was already emailed by any service or by the older system."""
    e = (email or "").lower().strip()
    if not e:
        return False
    if conn.execute(
        "SELECT 1 FROM scout_leads WHERE sent_at IS NOT NULL AND LOWER(emails_json) LIKE ? LIMIT 1", (f'%"{e}"%',)
    ).fetchone():
        return True
    try:
        old = conn.execute(
            """SELECT 1 FROM emails e JOIN sequences s ON s.email_id = e.id
               WHERE LOWER(e.email) = ? AND s.last_sent_at IS NOT NULL LIMIT 1""",
            (e,),
        ).fetchone()
    except sqlite3.Error:
        old = None
    return bool(old)
