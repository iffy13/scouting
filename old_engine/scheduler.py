import time
import subprocess
import sys
import os
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scheduler.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_HOUR = 9   # 9:00 AM
TARGET_MINUTE = 0

def run_daily_outreach_job():
    logger.info("=" * 60)
    logger.info(f"STARTING SCHEDULED OUTREACH RUN at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    try:
        cmd = [sys.executable, "main.py", "--action", "full"]
        process = subprocess.Popen(
            cmd,
            cwd=WORK_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        for line in iter(process.stdout.readline, ''):
            if line:
                logger.info(line.strip())
        process.stdout.close()
        process.wait()
        logger.info(f"Scheduled outreach completed with exit code: {process.returncode}")
    except Exception as e:
        logger.error(f"Error during scheduled outreach execution: {e}")

def main():
    print("=" * 60)
    print(" AUTONOMOUS OUTREACH 24/7 BACKGROUND SCHEDULER")
    print("=" * 60)
    print(f"Scheduled to run automatically every day at {TARGET_HOUR:02d}:{TARGET_MINUTE:02d} AM.")
    print("Leave this window open in the background (or minimize it).")
    print("Press Ctrl+C to stop.\n")

    last_run_day = None

    while True:
        now = datetime.now()
        current_day = now.date()

        # Check if it's 9:00 AM or later and hasn't run today yet
        if now.hour == TARGET_HOUR and now.minute >= TARGET_MINUTE and last_run_day != current_day:
            last_run_day = current_day
            run_daily_outreach_job()
        
        # Calculate time until next check
        time.sleep(30)

if __name__ == "__main__":
    main()
