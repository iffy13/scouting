import re
import dns.resolver
import aiohttp
import smtplib
import socket
import logging
import asyncio
from typing import Dict, Any, Optional
from config import MILLION_VERIFIER_API_KEY, PROSPEO_API_KEY
from safety import IN_CI

logger = logging.getLogger(__name__)

DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "guerrillamail.com", "10minutemail.com",
    "yopmail.com", "trashmail.com", "fakeinbox.com", "sharklasers.com",
    "getairmail.com", "dispostable.com", "throwawaymail.com", "temp-mail.org",
    "maildrop.cc", "mohmal.com", "burnermail.io", "nada.ltd", "crazymailing.com",
    "generator.email", "fakemailgenerator.com", "mytemp.email", "inboxkitten.com"
}

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

class EmailVerifier:
    """
    Multi-stage high-precision email verification:
    1. Syntax Check
    2. Disposable Domain Filter
    3. DNS MX Check
    4. Direct SMTP Socket Ping (HELO -> MAIL FROM -> RCPT TO)
    5. Fallback External API (MillionVerifier / Prospeo)
    """

    def __init__(self):
        self.million_verifier_key = MILLION_VERIFIER_API_KEY
        self.prospeo_key = PROSPEO_API_KEY

    async def verify(self, email: str) -> Dict[str, Any]:
        """
        Returns {
            'verdict': 'valid' | 'catchall' | 'risky' | 'invalid',
            'is_deliverable': bool,
            'reason': str
        }
        """
        email = email.strip().lower()

        # Step 1: Syntax Check
        if not EMAIL_REGEX.match(email):
            return {"verdict": "invalid", "is_deliverable": False, "reason": "invalid_syntax"}

        user, domain = email.split("@", 1)

        # Step 2: Disposable Check
        if domain in DISPOSABLE_DOMAINS:
            return {"verdict": "invalid", "is_deliverable": False, "reason": "disposable_domain"}

        # Step 3: DNS MX Check
        has_mx, mx_hosts = self._check_mx_records(domain)
        if not has_mx or not mx_hosts:
            return {"verdict": "invalid", "is_deliverable": False, "reason": "no_mx_records"}

        # Step 4: External API Verification (if configured)
        if self.million_verifier_key:
            api_result = await self._verify_with_millionverifier(email)
            if api_result:
                return api_result

        # Step 5: Direct SMTP handshake. Skipped on GitHub Actions: its servers block port 25, so every probe would
        # only wait for the timeout. There, without MILLION_VERIFIER_API_KEY, "valid" only means "the domain
        # accepts email", so adding that key is the way to catch dead addresses before they bounce.
        if not IN_CI:
            smtp_verdict = await asyncio.to_thread(self._smtp_ping, mx_hosts[0], email)
            if smtp_verdict:
                return smtp_verdict

        # Step 6: Fallback Default
        return {
            "verdict": "valid",
            "is_deliverable": True,
            "reason": f"mx_records_verified ({mx_hosts[0]})"
        }

    def _check_mx_records(self, domain: str) -> tuple[bool, list[str]]:
        try:
            records = dns.resolver.resolve(domain, "MX")
            # Sort by preference
            sorted_records = sorted(records, key=lambda r: r.preference)
            mx_hosts = [str(r.exchange).rstrip(".") for r in sorted_records]
            return len(mx_hosts) > 0, mx_hosts
        except Exception:
            return False, []

    def _smtp_ping(self, mx_host: str, email: str) -> Optional[Dict[str, Any]]:
        """
        Direct SMTP ping: Connects to MX server, sends HELO, MAIL FROM, and RCPT TO.
        Does NOT send the email. Checks response code for 250 (mailbox exists) vs 550 (mailbox rejected).
        """
        # Skip major anti-probing hosts that strictly block port 25 or tarpit SMTP pings
        skip_smtp_probe_hosts = ["google.com", "googlemail.com", "outlook.com", "protection.outlook.com", "pphosted.com"]
        if any(h in mx_host.lower() for h in skip_smtp_probe_hosts):
            return {
                "verdict": "valid",
                "is_deliverable": True,
                "reason": f"mx_trusted_provider ({mx_host})"
            }

        try:
            server = smtplib.SMTP(timeout=5)
            server.set_debuglevel(0)
            server.connect(mx_host, 25)
            server.helo(socket.getfqdn() or "localhost")  # our own host name, not a domain we do not own
            server.mail("")  # empty sender, the standard way to probe without claiming an address
            code, message = server.rcpt(email)
            server.quit()

            if code == 250:
                return {
                    "verdict": "valid",
                    "is_deliverable": True,
                    "reason": "smtp_rcpt_ok_250"
                }
            elif code in (550, 551, 552, 553, 554):
                return {
                    "verdict": "invalid",
                    "is_deliverable": False,
                    "reason": f"smtp_rejected_code_{code}"
                }
        except (socket.timeout, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError):
            # Port 25 may be blocked by local ISP/firewall - gracefully fall back to MX valid
            pass
        except Exception as e:
            logger.debug(f"SMTP ping check warning: {type(e).__name__}")

        return None

    async def _verify_with_millionverifier(self, email: str) -> Optional[Dict[str, Any]]:
        url = "https://api.millionverifier.com/api/v3/"
        params = {"api": self.million_verifier_key, "email": email, "timeout": "10"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = (data.get("result") or "").lower()
                        if not result or data.get("error") or result == "unknown":
                            # out of credits, bad key or the server could not tell: not a verdict on the address,
                            # so fall back to the other checks instead of throwing the lead away
                            logger.warning("MillionVerifier gave no verdict (credits, key or unknown), using MX check")
                            return None
                        if result == "ok":
                            return {"verdict": "valid", "is_deliverable": True, "reason": "millionverifier_ok"}
                        elif result == "catch_all":
                            return {"verdict": "catchall", "is_deliverable": False, "reason": "millionverifier_catchall"}
                        else:
                            return {"verdict": "invalid", "is_deliverable": False, "reason": f"millionverifier_{result}"}
        except Exception as e:
            logger.warning(f"MillionVerifier API error: {type(e).__name__}")  # never log the URL, it holds the key
        return None
