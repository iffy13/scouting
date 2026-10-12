"""
Helps you fill the GitHub secrets without opening any file.
It copies one secret at a time to your clipboard. You paste it into GitHub, press Enter here,
and it copies the next one. Nothing is printed on screen.

  python secrets_helper.py
"""
import json
import secrets
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values


def ensure_db_passphrase() -> str:
    """DB_PASSPHRASE locks the database saved on GitHub. Made once and kept in your .env, because without it the
    saved database cannot be opened again. Never change it after the first run."""
    env = dotenv_values(".env")
    value = (env.get("DB_PASSPHRASE") or "").strip()
    if not value:
        value = secrets.token_urlsafe(32)
        with open(".env", "a", encoding="utf-8") as f:
            f.write(f"\nDB_PASSPHRASE={value}\n")
        print("Made a new DB_PASSPHRASE and saved it in .env. Keep a copy somewhere safe.")
    return value


def collect():
    items = [("DB_PASSPHRASE", ensure_db_passphrase())]
    env = dotenv_values(".env")
    mapping = json.loads(Path("mailbox_map.json").read_text("utf-8"))
    # The third mailbox moved from book_trailer to render_3d. An old map is upgraded here so GitHub gets the new key.
    if "render_3d" not in mapping and mapping.get("book_trailer"):
        mapping["render_3d"] = mapping.pop("book_trailer")
        Path("mailbox_map.json").write_text(json.dumps(mapping, indent=2), "utf-8")
        print("mailbox_map.json: renamed book_trailer to render_3d (the third mailbox now sends 3D rendering emails).")
    items.append(("MAILBOX_MAP_JSON", json.dumps(mapping)))
    for sid, secret in (("whatsapp_api", "ACCOUNT_WHATSAPP_JSON"), ("receptionist", "ACCOUNT_RECEPTIONIST_JSON"), ("render_3d", "ACCOUNT_BOOKS_JSON")):
        mb = (mapping.get(sid) or "").strip().lower()
        f = Path("accounts") / f"{mb}.json"
        if mb and f.exists():
            items.append((secret, json.dumps(json.loads(f.read_text("utf-8")))))
        else:
            print(f"Skipping {secret}: no connected token for {sid}. Run: python outreach.py connect --service {sid}")
    for name in ("BUSINESS_NAME", "POSTAL_ADDRESS", "SENDER_NAME", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        v = (env.get(name) or "").strip()
        if v:
            items.append((name, v))
        else:
            print(f"Skipping {name}: not set in .env")
    return items


def copy(text: str):
    subprocess.run(["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"], input=text, text=True, check=True)


def main():
    items = collect()
    print(f"\n{len(items)} secrets to add. In GitHub open your repo, Settings, Secrets and variables, Actions, New repository secret.\n")
    for i, (name, value) in enumerate(items, 1):
        copy(value)
        print(f"{i} of {len(items)}: the value for  {name}  is on your clipboard.")
        print("   Type the name exactly, paste the value, click Add secret.")
        input("   Press Enter for the next one... ")
    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ' '"])
    print("\nDone. Your clipboard has been cleared.")


if __name__ == "__main__":
    main()
