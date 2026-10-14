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
    host = ""
    while "." not in host:
        host = input("Mail server from 'Connect Devices' (e.g. server123.web-hosting.com): ").strip()
    smtp_port = int(input("SMTP port [465]: ").strip() or 465)
    imap_port = int(input("IMAP port [993]: ").strip() or 993)
    password = getpass.getpass("Mailbox password (hidden while you type): ")
    cfg = {"host": host, "port": smtp_port, "imap_host": host, "imap_port": imap_port, "password": password}

    print("Testing login...")
    why = smtp_mailbox.test_login(cfg, addr)
    if why and ("Timeout" in why or "timed out" in why.lower() or "10060" in why):
        print(f"{why}\nYour PC could not reach the mail server at all. Often the internet provider blocks mail ports;"
              "\nGitHub's servers usually can. If the server name is right, you can save it and test from GitHub with:"
              "\n  gh workflow run outreach.yml -f service=receptionist -f dry_run=true")
        if input("Save anyway? (y/n): ").strip().lower() != "y":
            return
    elif why:
        print(f"Not saved: {why}\nCheck the server name, ports and password in cPanel > Email Accounts > Connect Devices.")
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
