"""
Plugs messages.py into outreach.py. Safe to run more than once.
Makes a backup first (outreach.py.bak) and changes only one spot.
"""
import shutil
import sys
from pathlib import Path

p = Path("outreach.py")
if not p.exists():
    sys.exit("outreach.py not found. Run this from the scouting folder.")
text = p.read_text(encoding="utf-8")
if "from messages import compose" in text:
    sys.exit("Already applied. Nothing to do.")
marker = '"""Plain, honest first message. No fake replies, no fake history."""'
if marker not in text:
    sys.exit("Could not find the spot to change in outreach.py. Send me a screenshot of the build_message function.")
shutil.copy(p, "outreach.py.bak")
hook = marker + "\n    from messages import compose\n    composed = compose(service_id, lead, footer())\n    if composed:\n        return composed"
p.write_text(text.replace(marker, hook, 1), encoding="utf-8")
print("Done. outreach.py now uses niche messages. Backup saved as outreach.py.bak")
