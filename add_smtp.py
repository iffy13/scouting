"""
Connect a mailbox on your own domain (Namecheap cPanel, Zoho, ...) so the autopilot can send from it.

  python add_smtp.py

It asks for the address, the mail server and the password, tests that sending (SMTP) and reading (IMAP) both work,
saves it in smtp_accounts.json on this PC (never uploaded, it is in .gitignore) and copies every mailbox to the
SMTP_ACCOUNTS_JSON GitHub secret. Then it points the service you choose at this mailbox in mailbox_map.json and the
MAILBOX_MAP_JSON secret.

Where to find the server on Namecheap: cPanel > Email Accounts > Connect Devices next to the mailbox.
Use the "Secure SSL/TLS Settings": the server name looks like server123.web-hosting.com, SMTP port 465, IMAP 993.
"""
import getpass
import json
import shutil
import subprocess
from pathlib import Path

from sender import smtp_mailbox

FILE = smtp_mailbox.LOCAL_FILE
MAP = Path("mailbox_map.json")
SERVICES = ["whatsapp_api", "receptionist", "render_3d"]


def gh_secret(name: str, value: str) -> bool:
    if not shutil.which("gh"):
        print(f"  gh is not installed: add the secret {name} by hand in GitHub, Settings, Secrets.")
        return False
    r = subprocess.run(["gh", "secret", "set", name], input=value, text=True, capture_output=True)
    print(f"  GitHub secret {name}: {'updated' if r.returncode == 0 else 'FAILED ' + r.stderr.strip()[:120]}")
    return r.returncode == 0


def main():
    accounts = json.loads(FILE.read_text("utf-8")) if FILE.exists() else {}
    addr = ""
    while "@" not in addr:
        addr = input("Email address (type it, e.g. samuel@iffystudio.site): ").strip().lower()
    print("\nHow does this address send?")
    print("  1. Through a Gmail account ('Send mail as', e.g. Cloudflare Email Routing + Gmail)")
    print("  2. Its own mail server (Namecheap cPanel, Zoho, ...)")
    kind = input("Number [1]: ").strip() or "1"
    if kind == "1":
        login = ""
        while "@" not in login:
            login = input("The Gmail address you set it up in (e.g. you@gmail.com): ").strip().lower()
        print("Use a Google APP PASSWORD, not your normal password:")
        print("  myaccount.google.com/apppasswords  (needs 2-Step Verification on), name it 'scouting', copy the 16 letters.")
        password = getpass.getpass("App password (hidden while you type): ").replace(" ", "")
        cfg = {"host": "smtp.gmail.com", "port": 465, "imap_host": "imap.gmail.com", "imap_port": 993,
               "user": login, "password": password}
    else:
        host = ""
        while "." not in host:
            host = input("Mail server (e.g. server123.web-hosting.com or smtp.zoho.com): ").strip()
        smtp_port = int(input("SMTP port [465]: ").strip() or 465)
        imap_host = input(f"IMAP server [{host}]: ").strip() or host
        imap_port = int(input("IMAP port [993]: ").strip() or 993)
        login = input(f"Login username [{addr}]: ").strip() or addr
        password = getpass.getpass("Mailbox password (hidden while you type): ")
        cfg = {"host": host, "port": smtp_port, "imap_host": imap_host, "imap_port": imap_port, "user": login,
               "password": password}

    print("Testing login...")
    why = smtp_mailbox.test_login(cfg, addr)
    if why and ("Timeout" in why or "timed out" in why.lower() or "10060" in why):
        print(f"{why}\nYour PC could not reach the mail server at all. Often the internet provider blocks mail ports;"
              "\nGitHub's servers usually can. If the server name is right, you can save it and test from GitHub with:"
              "\n  gh workflow run outreach.yml -f service=receptionist -f dry_run=true")
        if input("Save anyway? (y/n): ").strip().lower() != "y":
            return
    elif why:
        print(f"Not saved: {why}\nCheck the server, login and password. For Gmail it must be an APP password.")
        return
    else:
        print("SMTP and IMAP both work.")
    accounts[addr] = cfg
    FILE.write_text(json.dumps(accounts, indent=2), "utf-8")
    print(f"Saved in {FILE} (this file stays on your PC).")
    gh_secret("SMTP_ACCOUNTS_JSON", json.dumps(accounts))

    print("\nWhich service should send from this mailbox?")
    for i, s in enumerate(SERVICES, 1):
        print(f"  {i}. {s}")
    print(f"  {len(SERVICES) + 1}. all three (one mailbox for everything)")
    pick = input("Number (Enter to skip): ").strip()
    chosen = []
    if pick.isdigit() and 1 <= int(pick) <= len(SERVICES):
        chosen = [SERVICES[int(pick) - 1]]
    elif pick == str(len(SERVICES) + 1):
        chosen = list(SERVICES)
    if chosen:
        mapping = json.loads(MAP.read_text("utf-8")) if MAP.exists() else {}
        mapping.pop("book_trailer", None)
        for sid in chosen:
            mapping[sid] = addr
        MAP.write_text(json.dumps(mapping, indent=2), "utf-8")
        print(f"{', '.join(chosen)} now send from {addr}.")
        gh_secret("MAILBOX_MAP_JSON", json.dumps(mapping))
    print("\nDone. Check everything with:  python outreach.py check")


if __name__ == "__main__":
    main()
