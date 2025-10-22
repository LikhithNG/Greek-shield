#!/usr/bin/env python3
"""
Automated Daily Options Data Pipeline - School Account Version
Fetches from Yahoo Finance → Loads to RISK_MONITOR.OPTIONS
"""

import os
from dotenv import load_dotenv
import snowflake.connector
import yfinance as yf
import pandas as pd
from datetime import datetime, date
import uuid
import logging

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log'),
        logging.StreamHandler()
    ]
)

def get_snowflake_connection():
    """Connect to Snowflake using school account"""
    return snowflake.connector.connect(
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA'),
        role=os.getenv('SNOWFLAKE_ROLE')
    )

def fetch_and_load_options(ticker='AAPL'):
    """Fetch options and load to Snowflake"""
    
    logging.info("="*60)
    logging.info(f"Starting pipeline for {ticker} at {datetime.now()}")
    logging.info("="*60)
    
    try:
        # Fetch from Yahoo Finance
        logging.info(f"Fetching {ticker} from Yahoo Finance...")
        stock = yf.Ticker(ticker)
        
        hist = stock.history(period='1d')
        if hist.empty:
            logging.error("No stock data")
            return False
        
        underlying_price = hist['Close'].iloc[-1]
        logging.info(f"Current price: ${underlying_price:.2f}")
        
        # Get options
        expiries = stock.options[:3]
        logging.info(f"Processing {len(expiries)} expiration dates")
        
        all_options = []
        snapshot_id = str(uuid.uuid4())
        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for expiry in expiries:
            logging.info(f"  Processing {expiry}...")
            opt_chain = stock.option_chain(expiry)
            
            for opt_type, data in [('CALL', opt_chain.calls), ('PUT', opt_chain.puts)]:
                if not data.empty:
                    for _, row in data.iterrows():
                        exp_date = pd.to_datetime(expiry).date()
                        days_to_exp = (exp_date - date.today()).days
                        
                        all_options.append({
                            'snapshot_id': snapshot_id,
                            'collection_timestamp': timestamp_str,
                            'ticker': ticker,
                            'underlying_price': underlying_price,
                            'contract_symbol': row.get('contractSymbol', ''),
                            'expiration_date': expiry,
                            'strike_price': row['strike'],
                            'option_type': opt_type,
                            'last_price': row.get('lastPrice', 0),
                            'bid': row.get('bid', 0),
                            'ask': row.get('ask', 0),
                            'volume': row.get('volume', 0),
                            'open_interest': row.get('openInterest', 0),
                            'implied_volatility': row.get('impliedVolatility', 0),
                            'days_to_expiry': days_to_exp
                        })
        
        logging.info(f"Collected {len(all_options)} contracts")
        
        # Backup
        os.makedirs('data', exist_ok=True)
        backup_file = f"data/backup_{ticker}_{date.today()}.csv"
        pd.DataFrame(all_options).to_csv(backup_file, index=False)
        logging.info(f"Backup: {backup_file}")
        
        # Load to Snowflake
        logging.info("Connecting to Snowflake (school account)...")
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        logging.info("Connected!")
        
        logging.info(f"Loading to RISK_MONITOR.OPTIONS.OPTIONS_SNAPSHOT...")
        loaded = 0
        
        for option in all_options:
            try:
                cursor.execute("""
                    INSERT INTO OPTIONS_SNAPSHOT 
                    (snapshot_id, collection_timestamp, ticker, underlying_price, 
                     contract_symbol, expiration_date, strike_price, option_type,
                     last_price, bid, ask, volume, open_interest, 
                     implied_volatility, days_to_expiry)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    option['snapshot_id'],
                    option['collection_timestamp'],
                    option['ticker'],
                    float(option['underlying_price']),
                    option['contract_symbol'],
                    option['expiration_date'],
                    float(option['strike_price']),
                    option['option_type'],
                    float(option['last_price']),
                    float(option['bid']),
                    float(option['ask']),
                    int(option['volume']),
                    int(option['open_interest']),
                    float(option['implied_volatility']),
                    int(option['days_to_expiry'])
                ))
                loaded += 1
            except Exception as e:
                logging.error(f"Error: {e}")
                continue
        
        conn.commit()
        logging.info(f"✅ Loaded {loaded} rows")
        
        cursor.execute("SELECT COUNT(*) FROM OPTIONS_SNAPSHOT")
        total = cursor.fetchone()[0]
        logging.info(f"✅ Total: {total} rows")
        
        cursor.close()
        conn.close()
        
        logging.info("="*60)
        logging.info("✅ Pipeline completed!")
        logging.info("="*60)
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = fetch_and_load_options('AAPL')
    exit(0 if success else 1)