#!/usr/bin/env python3
"""
Scheduler that runs the pipeline at 6:30 PM daily
"""

import schedule
import time
import subprocess
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

def run_pipeline():
    """Run the automated pipeline"""
    logging.info(f"Triggering pipeline at {datetime.now()}")
    try:
        result = subprocess.run(
            ['python', 'automated_daily_pipeline.py'],
            capture_output=True,
            text=True
        )
        logging.info(f"Pipeline output: {result.stdout}")
        if result.returncode != 0:
            logging.error(f"Pipeline failed: {result.stderr}")
    except Exception as e:
        logging.error(f"Error running pipeline: {e}")

# Schedule for 6:30 PM every day
schedule.every().day.at("18:30").do(run_pipeline)

print("Scheduler started. Pipeline will run at 6:30 PM daily.")
print("Press Ctrl+C to stop.")

while True:
    schedule.run_pending()
    time.sleep(60)  # Check every minute