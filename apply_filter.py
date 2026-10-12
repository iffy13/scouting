"""
Plugs lead_filter.py into scout.py and slows the searches down so the search engine stops blocking you.
Safe to run more than once. Makes a backup first (scout.py.bak).
"""
import shutil
import sys
from pathlib import Path

p = Path("scout.py")
if not p.exists():
    sys.exit("scout.py not found. Run this from the scouting folder.")
t = p.read_text(encoding="utf-8")
if "from lead_filter import junk_reason" in t:
    sys.exit("Already applied. Nothing to do.")

a = "or not is_valid_prospect_domain(domain, website):"
b = 'logger.info(f"Scouting [{kw}] in [{ctry}] for {svc.id}")'
if a not in t or b not in t or "import asyncio\n" not in t:
    sys.exit("Could not find the spots to change in scout.py. Send me a screenshot of this message.")

shutil.copy(p, "scout.py.bak")
t = t.replace("import asyncio\n", "import asyncio\nimport random\nfrom lead_filter import junk_reason\n", 1)
t = t.replace(a, 'or not is_valid_prospect_domain(domain, website) or junk_reason(lead.get("name"), domain, website):', 1)
t = t.replace(b, b + "\n                await asyncio.sleep(random.uniform(4, 8))", 1)
p.write_text(t, encoding="utf-8")
print("Done. Junk sites are now filtered and searches are slowed down. Backup saved as scout.py.bak")
