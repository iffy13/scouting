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

def add_new_gmail_account():
    creds_file = "credentials.json"
    if not os.path.exists(creds_file):
        print("Error: credentials.json not found.")
        return

    print("\n" + "="*60)
    print(" CONNECT NEW GMAIL INBOX TO OUTREACH POOL")
    print("="*60)
    print("1. Ensure this email is added under 'Test Users' in Google Cloud Console.")
    print("2. A browser window will open for you to sign in and click 'Allow'.\n")

    flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    # Fetch connected profile to identify the email address
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    email_address = profile.get("emailAddress", "unknown_account")

    # Save isolated token for this account
    token_filename = ACCOUNTS_DIR / f"{email_address}.json"
    with open(token_filename, "w") as f:
        f.write(creds.to_json())

    # Also maintain primary token.json if first account
    if not os.path.exists("token.json"):
        with open("token.json", "w") as f:
            f.write(creds.to_json())

    print("\n" + "="*60)
    print(f" SUCCESS: Account [{email_address}] is connected & active!")
    print(f" Saved to: {token_filename}")
    print("="*60 + "\n")

def list_connected_accounts():
    accounts = list(ACCOUNTS_DIR.glob("*.json"))
    print("\n--- Currently Connected Gmail Accounts ---")
    if not accounts:
        if os.path.exists("token.json"):
            print(" • 1 Primary Account (token.json active)")
        else:
            print(" • No accounts connected yet.")
        return
    for idx, acc in enumerate(accounts, 1):
        print(f" {idx}. {acc.stem}")
    print(f"Total sending capacity: {len(accounts) * 50} emails/day (at 50/day each)\n")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        list_connected_accounts()
    else:
        add_new_gmail_account()
