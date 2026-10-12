"""
Sends one plain test email from each service mailbox to an address you control.
Touches nothing else. Usage:  python test_mail.py you@gmail.com
"""
import sys

import tg
from services import SERVICES, load_mailbox_map


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python test_mail.py you@gmail.com")
    to = sys.argv[1].replace(" ", "").strip().lower()
    if "@" not in to or "." not in to.split("@")[-1]:
        sys.exit(f"'{to}' does not look like an email address.")

    from sender.gmail_client import MultiGmailService

    pool = MultiGmailService(mode="all")
    mapping = load_mailbox_map()
    results = []
    print(f"\nSending one test from each service mailbox to {to}\n")
    for sid in SERVICES:
        mb = mapping.get(sid)
        box = next((e for e in pool.accounts if e.lower() == mb), None) if mb else None
        if not box:
            print(f"{sid:14} {mb or 'NOT ASSIGNED'}  not connected, skipped. Run: python outreach.py connect --service {sid}")
            results.append((sid, mb, False))
            continue
        res = pool.send_email(
            to_email=to,
            subject=f"Test from the {sid} mailbox",
            body_text=(
                f"This is a test message from the {sid} mailbox ({box}).\n\n"
                "If you can read this, sending works for this service."
            ),
            from_account_email=box,
            strict_sender=True,
        )
        ok = bool(res)
        print(f"{sid:14} {box}  {'SENT' if ok else 'FAILED (' + str(pool.last_failure) + ')'}")
        results.append((sid, box, ok))

    done = sum(1 for _, _, ok in results if ok)
    print(f"\n{done} of {len(results)} test emails sent. Check the inbox and the Spam folder of {to}.")
    tg.send(
        "<b>Test emails</b>\n"
        + "\n".join(f"{tg.esc(sid)}: {'sent' if ok else 'failed'} ({tg.esc(mb)})" for sid, mb, ok in results)
    )


if __name__ == "__main__":
    main()
