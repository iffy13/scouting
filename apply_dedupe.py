"""
Makes the scout and send_paced.py skip anyone already scouted for another service, or already emailed.
Safe to run more than once. Makes backups first (scout.py.bak2 and send_paced.py.bak).
"""
import shutil
import sys
from pathlib import Path

changed = []

p = Path("scout.py")
if p.exists():
    t = p.read_text(encoding="utf-8")
    old = 'if conn.execute("SELECT 1 FROM scout_leads WHERE service_id=? AND domain=?", (svc.id, domain)).fetchone():'
    if "known_domain" in t:
        print("scout.py already updated.")
    elif old not in t or "import asyncio\n" not in t:
        print("Could not find the spot in scout.py. Send me a screenshot of this message.")
    else:
        shutil.copy(p, "scout.py.bak2")
        t = t.replace("import asyncio\n", "import asyncio\nfrom seen import known_domain\n", 1).replace(old, "if known_domain(conn, domain):", 1)
        p.write_text(t, encoding="utf-8")
        changed.append("scout.py")

q = Path("send_paced.py")
if q.exists():
    t = q.read_text(encoding="utf-8")
    marker = "            to = emails[0].lower()\n"
    if "already_emailed" in t:
        print("send_paced.py already updated.")
    elif marker not in t:
        print("Could not find the spot in send_paced.py. Send me a screenshot of this message.")
    else:
        shutil.copy(q, "send_paced.py.bak")
        guard = (
            marker
            + "            from seen import already_emailed\n"
            + "            with get_connection() as conn:\n"
            + "                if already_emailed(conn, to):\n"
            + "                    print(f\"#{lead['id']} {to}: already emailed before. Skipped.\")\n"
            + "                    continue\n"
        )
        q.write_text(t.replace(marker, guard, 1), encoding="utf-8")
        changed.append("send_paced.py")

print("Updated: " + ", ".join(changed) if changed else "Nothing needed changing.")
