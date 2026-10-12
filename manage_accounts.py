import os
import json
import logging
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

ACCOUNTS_DIR = Path("accounts")
ACCOUNTS_DIR.mkdir(exist_ok=True)

def list_accounts():
    files = sorted(list(ACCOUNTS_DIR.glob("*.json")))
    print("\n" + "="*60)
    print(f" CONNECTED GMAIL ACCOUNTS ({len(files)} Active)")
    print("="*60)
    if not files:
        print("  (No accounts connected currently)")
    else:
        for idx, f in enumerate(files, 1):
            print(f"  [{idx}] {f.stem}")
    print(f"\n  Total Daily Sending Capacity: {len(files) * 50} emails/day")
    print("="*60 + "\n")
    return files

def add_account():
    creds_file = "credentials.json"
    if not os.path.exists(creds_file):
        print("Error: credentials.json not found in project folder.")
        return

    print("\n" + "="*60)
    print(" CONNECT A NEW GMAIL ACCOUNT")
    print("="*60)
    print("1. Make sure this Gmail is added under 'Test Users' in your Google Cloud Console.")
    print("2. A browser window will open for you to log in and authorize.")
    print("="*60 + "\n")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email_address = profile.get("emailAddress", "unknown_account")

        token_filename = ACCOUNTS_DIR / f"{email_address}.json"
        with open(token_filename, "w") as f:
            f.write(creds.to_json())

        # Update root token.json as fallback
        with open("token.json", "w") as f:
            f.write(creds.to_json())

        print(f"\n[SUCCESS] Account [{email_address}] successfully added to rotation!")
    except Exception as e:
        print(f"\n[ERROR] Failed to add account: {e}")

def remove_account():
    files = list_accounts()
    if not files:
        return

    choice = input("Enter the number of the account you want to REMOVE (or 0 to cancel): ").strip()
    if not choice.isdigit():
        print("Invalid choice.")
        return
    idx = int(choice)
    if idx == 0:
        return
    if 1 <= idx <= len(files):
        target_file = files[idx - 1]
        email_name = target_file.stem
        confirm = input(f"Are you sure you want to remove [{email_name}]? (y/n): ").strip().lower()
        if confirm == "y":
            target_file.unlink(missing_ok=True)
            # Also clean root token.json if matching
            if os.path.exists("token.json"):
                try:
                    with open("token.json", "r") as tf:
                        data = json.load(tf)
                        # Remove if needed
                except Exception:
                    pass
            print(f"\n[SUCCESS] Account [{email_name}] removed.")
    else:
        print("Invalid number.")

def menu():
    while True:
        print("\n" + "="*60)
        print("          GMAIL INBOX MANAGER")
        print("="*60)
        print(" 1. List connected Gmail accounts")
        print(" 2. Add a new Gmail account")
        print(" 3. Remove an existing Gmail account")
        print(" 4. Exit")
        print("="*60)
        choice = input("Select an option (1-4): ").strip()
        if choice == "1":
            list_accounts()
        elif choice == "2":
            add_account()
        elif choice == "3":
            remove_account()
        elif choice == "4":
            print("Exiting.")
            break
        else:
            print("Invalid option.")

if __name__ == "__main__":
    menu()
