import sys
import time
import logging

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from verifier.deliverability_tester import DeliverabilityTester
from sender.gmail_client import MultiGmailService
from config import DISABLED_INBOXES, AUTHOR_INBOXES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("deliverability_test")

def run_deliverability_audit():
    print("\n" + "="*80)
    print("   INBOX PLACEMENT AUDIT & AUTO-WARMUP (PEER-TO-PEER GMAIL MONITORING)")
    print("="*80)
    print("This tool sends a realistic test email from each active sending inbox to a peer seed")
    print("account, inspects folder placement, and automatically rescues any message from Spam")
    print("with a 2-way verified reply to warm up your inbox reputation with Google.\n")

    tester = DeliverabilityTester()
    b2b_service = MultiGmailService(mode="b2b")
    author_service = MultiGmailService(mode="author")

    active_b2b = b2b_service.get_all_accounts()
    active_author = author_service.get_all_accounts()
    all_active = active_b2b + active_author

    if not all_active:
        print("[-] No active sending inboxes found.")
        return

    print(f"[*] Found {len(all_active)} Active Sending Inboxes to Test:")
    for a in all_active:
        pool_type = "Author" if a["email"].lower() in [x.lower() for x in AUTHOR_INBOXES] else "B2B"
        print(f"    - {a['email']} ({pool_type})")
    
    seed_pool = tester.get_seed_receivers()
    print(f"\n[*] Rotating Seed Receiver Pool ({len(seed_pool)} inboxes):")
    for s in seed_pool:
        print(f"    - {s}")

    print("\n" + "-"*80)
    print("STARTING AUDIT, PLACEMENT DETECTION & AUTO-WARMUP RESCUE...")
    print("-"*80)

    results = []
    for idx, acc in enumerate(all_active, 1):
        sender_email = acc["email"]
        service = acc["service"]
        receiver_email = tester.get_next_seed_receiver(sender_email)

        print(f"\n[{idx}/{len(all_active)}] Testing & Warming: {sender_email} -> {receiver_email}...")
        res = tester.run_live_seed_test(sender_email=sender_email, gmail_service=service)
        if res:
            results.append(res)
        else:
            results.append({
                "sender": sender_email,
                "receiver": receiver_email,
                "placement": {"label": "[SEND ERROR]", "status": "error"}
            })

    # Summary Report
    print("\n" + "="*80)
    print("                     DELIVERABILITY PLACEMENT REPORT")
    print("="*80)
    print(f"{'SENDER INBOX':<30} {'RECEIVER SEED':<30} {'PLACEMENT RESULT'}")
    print("-"*80)

    primary_count = 0
    for r in results:
        sender = r["sender"]
        receiver = r.get("receiver", "N/A")
        label = r.get("placement", {}).get("label", "UNKNOWN")
        status = r.get("placement", {}).get("status", "")
        if status in ("inbox", "delivered", "rescued"):
            primary_count += 1
        print(f"{sender:<30} {receiver:<30} {label}")

    print("="*80)
    health_pct = (primary_count / max(1, len(results))) * 100
    print(f"Deliverability & Warmup Score: {health_pct:.1f}% ({primary_count}/{len(results)} Delivered/Rescued)")
    print("Note: Any spam placements were automatically unspammed, starred, and replied to")
    print("      to continuously boost your Google sender domain and IP trust score.")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_deliverability_audit()
