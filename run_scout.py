"""
Runs the scout for every service one after the other, then sends you a Telegram summary.
Nobody is scouted twice, even across services. Nothing is emailed.

  python run_scout.py                  both services, 100 businesses each
  python run_scout.py --max 60         both services, 60 each
  python run_scout.py --only receptionist
You can press Ctrl+C at any time. Leads found so far are saved.
"""
import argparse
import subprocess
import sys

import tg

JOBS = {
    "whatsapp_api": ["--countries", "AE,SA,QA,KW,BH,OM,SG,MY"],
    "receptionist": ["--countries", "US,CA,AU,NZ"],
    "render_3d": ["--countries", "US,CA,AU,NZ,AE,SA,QA,KW,BH,OM,SG,MY,ZA"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=100)
    ap.add_argument("--only", choices=list(JOBS))
    a = ap.parse_args()
    todo = [a.only] if a.only else list(JOBS)
    try:
        for sid in todo:
            print(f"\n=== Scouting {sid}, up to {a.max} businesses ===\n")
            subprocess.run([sys.executable, "scout.py", "--service", sid, "--max", str(a.max)] + JOBS[sid])
    except KeyboardInterrupt:
        print("\nStopped by you. Leads found so far are saved.")
    print("\n=== Summary ===")
    subprocess.run([sys.executable, "outreach.py", "report"])
    tg.send("<b>Scouting run finished</b>\nServices: " + tg.esc(", ".join(todo)) + "\nRun: python outreach.py report")


if __name__ == "__main__":
    main()
