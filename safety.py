"""
Small shared rules used by sending and logging.

1. Private logs. On GitHub Actions the run logs of a public repository can be read by anyone, so lead email
   addresses and reply text are masked there. On your own PC or server everything is printed in full.

2. Business hours. Each run only emails countries where it is a working day and between 08:00 and 17:00
   local time, so nobody gets a sales email at 3am or on their weekend.
"""
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional

IN_CI = bool(os.getenv("GITHUB_ACTIONS"))


def mask_email(email: Optional[str]) -> str:
    """'jane@acme.com' -> 'j***@a***.com' on GitHub Actions, unchanged elsewhere."""
    e = (email or "").strip()
    if not IN_CI or "@" not in e:
        return e
    user, host = e.split("@", 1)
    return f"{user[:1]}***@{host[:1]}***.{host.rsplit('.', 1)[-1]}"


def mask_text(text: Optional[str]) -> str:
    """Reply text and email bodies: hidden on GitHub Actions, unchanged elsewhere."""
    if not IN_CI:
        return text or ""
    return f"[{len(text or '')} characters hidden in public logs]"


def mask_emails_in(text: Optional[str]) -> str:
    """Masks every email address inside a longer line (for error messages)."""
    if not IN_CI:
        return text or ""
    return re.sub(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", lambda m: mask_email(m.group(0)), text or "")


# country: (UTC offset in hours, standard time; working days, Monday = 0)
MON_FRI = (0, 1, 2, 3, 4)
SUN_THU = (6, 0, 1, 2, 3)
COUNTRY_CLOCK = {
    "US": (-5, MON_FRI), "CA": (-5, MON_FRI), "AU": (10, MON_FRI), "NZ": (12, MON_FRI),
    "UK": (0, MON_FRI), "IE": (0, MON_FRI), "ZA": (2, MON_FRI),
    "AE": (4, MON_FRI),  # the UAE moved to a Monday to Friday week in 2022
    "OM": (4, SUN_THU), "SA": (3, SUN_THU), "QA": (3, SUN_THU), "KW": (3, SUN_THU), "BH": (3, SUN_THU),
    "SG": (8, MON_FRI), "MY": (8, MON_FRI), "HK": (8, MON_FRI), "PH": (8, MON_FRI), "IN": (5.5, MON_FRI),
    "NG": (1, MON_FRI), "GH": (0, MON_FRI), "KE": (3, MON_FRI),
}
OPEN_FROM = int(os.getenv("SEND_LOCAL_START", "8"))
OPEN_UNTIL = int(os.getenv("SEND_LOCAL_END", "17"))


def is_open(country: str, now_utc: Optional[datetime] = None) -> bool:
    """True when it is a working day and business hours in that country."""
    offset, days = COUNTRY_CLOCK.get((country or "").upper(), (0, MON_FRI))
    now_utc = now_utc or datetime.now(timezone.utc)
    local = now_utc + timedelta(hours=offset)
    return local.weekday() in days and OPEN_FROM <= local.hour < OPEN_UNTIL


def open_countries(countries: Iterable[str], now_utc: Optional[datetime] = None) -> List[str]:
    return [c for c in countries if is_open(c, now_utc)]
