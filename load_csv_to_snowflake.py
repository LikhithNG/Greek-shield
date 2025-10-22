#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import snowflake.connector
import pandas as pd
from datetime import datetime
import uuid

load_dotenv()

def get_connection():
    return snowflake.connector.connect(
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA'),
        role=os.getenv('SNOWFLAKE_ROLE')
    )

print("="*60)
print("LOADING DATA TO SNOWFLAKE")
print("="*60)

# Read CSV
csv_file = 'data/AAPL_latest.csv'
print(f"\n📂 Reading {csv_file}...")

df = pd.read_csv(csv_file)
print(f"✅ Found {len(df)} rows")

# Add IDs
df['snapshot_id'] = str(uuid.uuid4())
df['collection_timestamp'] = datetime.now()

# Connect
print(f"\n🔌 Connecting to Snowflake...")
conn = get_connection()
cursor = conn.cursor()
print("✅ Connected!")

# Check table exists
cursor.execute("SHOW TABLES LIKE 'OPTIONS_SNAPSHOT'")
if not cursor.fetchone():
    print("❌ Table doesn't exist!")
    exit()

print(f"\n📤 Loading {len(df)} rows...")

loaded = 0
for idx, row in df.iterrows():
    try:
        cursor.execute("""
            INSERT INTO OPTIONS_SNAPSHOT 
            (snapshot_id, collection_timestamp, ticker, underlying_price, 
             contract_symbol, expiration_date, strike_price, option_type,
             last_price, bid, ask, volume, open_interest, 
             implied_volatility, days_to_expiry)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            df.loc[idx, 'snapshot_id'],
            df.loc[idx, 'collection_timestamp'],
            row['ticker'],
            row['underlying_price'],
            row['contract_symbol'],
            row['expiration_date'],
            row['strike'],
            row['option_type'],
            row['last_price'],
            row.get('bid', 0),
            row.get('ask', 0),
            row.get('volume', 0),
            row.get('open_interest', 0),
            row.get('implied_volatility', 0),
            row.get('days_to_expiry', 0)
        ))
        loaded += 1
        if loaded % 50 == 0:
            print(f"   {loaded} rows...")
    except Exception as e:
        print(f"   Error on row {idx}: {e}")
        continue

conn.commit()
print(f"\n✅ Loaded {loaded} rows!")

# Verify
cursor.execute("SELECT COUNT(*) FROM OPTIONS_SNAPSHOT")
total = cursor.fetchone()[0]
print(f"✅ Total in Snowflake: {total} rows")

cursor.close()
conn.close()

print("\n🎉 DONE!")