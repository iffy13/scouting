"""
Scouts, then approves every usable lead for you. You do not have to read anything.
Nothing is emailed here. Sending is the separate send_paced.py step.

  python run_all.py                  scout both services (100 each), then approve everything usable
  python run_all.py --max 40         scout 40 each
  python run_all.py --skip-scout     only approve what you already have

A lead is approved only when it has an email address, is not in a regulated country, and is not a
list, blog, directory or giant brand. Leads with no email are marked no_email, regulated-country leads stay shortlisted. Neither is ever emailed.
"""
import argparse
import json
import subprocess
import sys

import tg
from db import get_connection
import leadgen
import render3d
from lead_filter import service_junk_reason
from scout import CAREFUL_REGIONS, init_scout_tables

JOBS = {
    "whatsapp_api": ["--countries", "AE,SA,QA,KW,BH,OM,SG,MY,MX,BR,CO,AR,CL"],
    "receptionist": ["--countries", "US,CA,AU,NZ"],
    "render_3d": ["--countries", ",".join(render3d.COUNTRIES)],
    "lead_gen": ["--countries", ",".join(leadgen.COUNTRIES)],
}


def approve_all():
    init_scout_tables()
    lines = []
    with get_connection() as conn:
        for sid in JOBS:
            rows = conn.execute(
                "SELECT id, name, domain, website, country, emails_json FROM scout_leads WHERE service_id=? AND status='shortlisted'",
                (sid,),
            ).fetchall()
            ok = no_email = regulated = junk = 0
            for r in conn.execute(
                "SELECT id, name, domain, website FROM scout_leads WHERE service_id=? AND status='approved' AND sent_at IS NULL",
                (sid,),
            ).fetchall():
                if service_junk_reason(sid, r["name"], r["domain"], r["website"]):
                    conn.execute("UPDATE scout_leads SET status='skipped' WHERE id=?", (r["id"],))
                    junk += 1
            for r in rows:
                emails = json.loads(r["emails_json"] or "[]")
                if service_junk_reason(sid, r["name"], r["domain"], r["website"]):
                    conn.execute("UPDATE scout_leads SET status='skipped' WHERE id=?", (r["id"],))
                    junk += 1
                elif r["country"] in CAREFUL_REGIONS:
                    regulated += 1
                elif not emails:
                    # Nothing to email, so stop listing it as waiting for review. Kept for its phone/website.
                    conn.execute("UPDATE scout_leads SET status='no_email' WHERE id=?", (r["id"],))
                    no_email += 1
                else:
                    conn.execute("UPDATE scout_leads SET status='approved' WHERE id=?", (r["id"],))
                    ok += 1
            conn.commit()
            lines.append(f"{sid}: approved {ok}, no email {no_email}, regulated country {regulated}, junk removed {junk}")
    print("\n" + "\n".join(lines))
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=100)
    ap.add_argument("--skip-scout", action="store_true")
    a = ap.parse_args()
    if not a.skip_scout:
        try:
            for sid, extra in JOBS.items():
                print(f"\n=== Scouting {sid}, up to {a.max} businesses ===\n")
                subprocess.run([sys.executable, "scout.py", "--service", sid, "--max", str(a.max)] + extra)
        except KeyboardInterrupt:
            print("\nScouting stopped by you. Leads found so far are saved.")
    lines = approve_all()
    print("\nNext, to send with gaps and no questions asked:")
    for sid in JOBS:
        print(f"  python send_paced.py --service {sid} --limit 5 --auto")
    tg.send("<b>Scouting and approval finished</b>\n" + "\n".join(tg.esc(l) for l in lines))


if __name__ == "__main__":
    main()
