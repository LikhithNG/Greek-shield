#!/usr/bin/env python3
"""
Fetch options data from Yahoo Finance and save to S3
"""

import os
from dotenv import load_dotenv
import boto3
import yfinance as yf
import pandas as pd
from datetime import datetime, date
import json
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)

def safe_int(value, default=0):
    """Safely convert to int, handling NaN"""
    if pd.isna(value):
        return default
    try:
        return int(value)
    except:
        return default

def safe_float(value, default=0.0):
    """Safely convert to float, handling NaN"""
    if pd.isna(value):
        return default
    try:
        return float(value)
    except:
        return default

def fetch_options_data(ticker='AAPL'):
    """Fetch from Yahoo Finance"""
    
    logging.info(f"📊 Fetching {ticker} from Yahoo Finance...")
    
    stock = yf.Ticker(ticker)
    
    # Get current price
    hist = stock.history(period='1d')
    underlying_price = hist['Close'].iloc[-1]
    logging.info(f"   Current price: ${underlying_price:.2f}")
    
    # Get options
    expiries = stock.options[:3]
    logging.info(f"   Processing {len(expiries)} expiration dates")
    
    all_options = []
    
    for expiry in expiries:
        logging.info(f"   Processing {expiry}...")
        opt_chain = stock.option_chain(expiry)
        
        for opt_type, data in [('CALL', opt_chain.calls), ('PUT', opt_chain.puts)]:
            if not data.empty:
                for _, row in data.iterrows():
                    exp_date = pd.to_datetime(expiry).date()
                    
                    all_options.append({
                        'ticker': ticker,
                        'collection_date': str(date.today()),
                        'collection_timestamp': datetime.now().isoformat(),
                        'underlying_price': safe_float(underlying_price),
                        'contract_symbol': str(row.get('contractSymbol', '')),
                        'expiration_date': str(expiry),
                        'strike_price': safe_float(row.get('strike', 0)),
                        'option_type': opt_type,
                        'last_price': safe_float(row.get('lastPrice', 0)),
                        'bid': safe_float(row.get('bid', 0)),
                        'ask': safe_float(row.get('ask', 0)),
                        'volume': safe_int(row.get('volume', 0)),
                        'open_interest': safe_int(row.get('openInterest', 0)),
                        'implied_volatility': safe_float(row.get('impliedVolatility', 0)),
                        'days_to_expiry': int((exp_date - date.today()).days)
                    })
    
    logging.info(f"✅ Collected {len(all_options)} option contracts")
    return all_options

def upload_to_s3(data, ticker='AAPL'):
    """Upload to S3"""
    
    logging.info(f"📤 Uploading to S3...")
    
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION')
    )
    
    bucket = os.getenv('S3_BUCKET_NAME')
    today = date.today()
    folder = f"options-data/{ticker}/{today.year}/{today.month:02d}/{today.day:02d}"
    
    # Upload JSON
    json_key = f"{folder}/options_{ticker}_{today}.json"
    s3.put_object(
        Bucket=bucket,
        Key=json_key,
        Body=json.dumps(data, indent=2),
        ContentType='application/json'
    )
    logging.info(f"   ✅ JSON uploaded: {json_key}")
    
    # Upload CSV
    csv_key = f"{folder}/options_{ticker}_{today}.csv"
    df = pd.DataFrame(data)
    s3.put_object(
        Bucket=bucket,
        Key=csv_key,
        Body=df.to_csv(index=False),
        ContentType='text/csv'
    )
    logging.info(f"   ✅ CSV uploaded: {csv_key}")
    
    return json_key, csv_key

def main():
    print("="*60)
    print("YAHOO FINANCE → S3 PIPELINE")
    print("="*60)
    
    ticker = os.getenv('TICKER', 'AAPL')
    
    # Fetch data
    options_data = fetch_options_data(ticker)
    
    if not options_data:
        print("❌ No data collected")
        return
    
    # Upload to S3
    json_key, csv_key = upload_to_s3(options_data, ticker)
    
    print("\n" + "="*60)
    print("✅ PIPELINE COMPLETED!")
    print("="*60)
    print(f"Collected: {len(options_data)} contracts")
    print(f"S3 Bucket: {os.getenv('S3_BUCKET_NAME')}")
    print(f"JSON: {json_key}")
    print(f"CSV: {csv_key}")
    print("\n🔍 Check your S3 bucket to see the organized data!")
    print("="*60)

if __name__ == "__main__":
    main()