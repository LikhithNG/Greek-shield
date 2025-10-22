#!/usr/bin/env python3
"""
Daily runner for options data collection
Run this manually or schedule with cron/Task Scheduler
"""

from robust_pipeline import OptionsPipeline
import sys
from datetime import datetime

def main():
    print(f"\n{'='*60}")
    print(f"Running Daily Options Data Collection")
    print(f"Time: {datetime.now()}")
    print(f"{'='*60}\n")
    
    # Initialize pipeline
    pipeline = OptionsPipeline()
    
    # Define tickers to collect
    tickers = ['AAPL']  # Add more later: ['AAPL', 'TSLA', 'SPY']
    
    # Run collection
    results = pipeline.run_daily_collection(tickers)
    
    # Report results
    success_count = sum(1 for df in results.values() if not df.empty)
    
    print(f"\n{'='*60}")
    print(f"Collection Complete")
    print(f"Success: {success_count}/{len(tickers)} tickers")
    print(f"{'='*60}")
    
    return 0 if success_count > 0 else 1

if __name__ == "__main__":
    sys.exit(main())