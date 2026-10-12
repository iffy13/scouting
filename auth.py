import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

def main():
    creds_file = "credentials.json"
    token_file = "token.json"

    if not os.path.exists(creds_file):
        print(f"Error: {creds_file} not found.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
    # Using port=0 lets Google select the standard dynamic localhost loopback
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    with open(token_file, "w") as token:
        token.write(creds.to_json())

    print("\n" + "="*60)
    print("SUCCESS: token.json created! Authentication complete.")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
