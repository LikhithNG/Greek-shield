import schedule
import time
from datetime import datetime
from robust_pipeline import OptionsPipeline

def run_pipeline():
    print(f"\n[{datetime.now()}] Running scheduled pipeline...")
    pipeline = OptionsPipeline()
    pipeline.run_daily_collection(['AAPL'])
    print(f"[{datetime.now()}] Pipeline complete!")

# Schedule for 6:30 PM daily
schedule.every().day.at("18:30").do(run_pipeline)

print("📅 Scheduler started!")
print("Will run daily at 6:30 PM")
print("Keep this terminal open (minimize it)")
print("Press Ctrl+C to stop\n")

while True:
    schedule.run_pending()
    time.sleep(60)  # Check every minute