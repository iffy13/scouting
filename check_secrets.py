"""
Run this BEFORE you push to GitHub. It looks at every file git would upload and warns you if any
contains a password, token or key. It never prints the secret itself, only the file and line number.

  python check_secrets.py
"""
import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_NAMES = (".env", "credentials.json", "token.json", "mailbox_map.json", "smtp_accounts.json")
PATTERNS = {
    "Google refresh token": re.compile(r'"refresh_token"\s*:\s*"'),
    "Google client secret": re.compile(r"GOCSPX-[A-Za-z0-9_-]{10,}"),
    "client_secret field": re.compile(r'"client_secret"\s*:\s*"'),
    "Telegram bot token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "private key": re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
}
SKIP = {"check_secrets.py"}


def files_git_would_upload():
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"], capture_output=True, text=True
    )
    if out.returncode != 0:
        sys.exit("Run this inside the project folder, after git init.")
    return [Path(p) for p in out.stdout.splitlines() if p.strip()]


def main():
    problems = []
    for p in files_git_would_upload():
        if p.name in FORBIDDEN_NAMES or p.suffix == ".db" or "accounts" in p.parts:
            problems.append(f"{p}: this file must never be uploaded")
            continue
        if p.name in SKIP or not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for label, pat in PATTERNS.items():
                if pat.search(line):
                    problems.append(f"{p} line {i}: looks like a {label}")
    if problems:
        print("\nSTOP. Do not push yet:\n")
        print("\n".join(problems))
        print("\nFix these first, usually by adding the file to .gitignore, then run this again.")
        sys.exit(1)
    print("\nAll clear. No passwords, tokens or keys found in the files git would upload.")


if __name__ == "__main__":
    main()
