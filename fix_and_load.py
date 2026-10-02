#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import snowflake.connector
import pandas as pd
from datetime import datetime
import uuid

load_dotenv()

# Read CSV first to see actual columns
csv_file = 'data/AAPL_latest.csv'
df = pd.read_csv(csv_file)

print("="*60)
print("CSV COLUMNS FOUND:")
print("="*60)
print(df.columns.tolist())
print("\nFirst row sample:")
print(df.head(1).to_dict('records')[0])
print("="*60)

# Add required columns
df['snapshot_id'] = str(uuid.uuid4())
df['collection_timestamp'] = datetime.now()

# Map column names (handle different possible names)
column_mapping = {
    'contractSymbol': 'contract_symbol',
    'contractsymbol': 'contract_symbol',
    'contract': 'contract_symbol'
}

# Rename if needed
for old_name, new_name in column_mapping.items():
    if old_name in df.columns:
        df[new_name] = df[old_name]

# Connect to Snowflake
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

print("\n🔌 Connecting to Snowflake...")
conn = get_connection()
cursor = conn.cursor()
print("✅ Connected!")

print(f"\n📤 Loading {len(df)} rows...")

loaded = 0
for idx, row in df.iterrows():
    try:
        # Use .get() with defaults for all fields
        cursor.execute("""
            INSERT INTO OPTIONS_SNAPSHOT 
            (snapshot_id, collection_timestamp, ticker, underlying_price, 
             contract_symbol, expiration_date, strike_price, option_type,
             last_price, bid, ask, volume, open_interest, 
             implied_volatility, days_to_expiry)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row.get('snapshot_id', str(uuid.uuid4())),
            row.get('collection_timestamp', datetime.now()),
            row.get('ticker', 'AAPL'),
            row.get('underlying_price', 0),
            row.get('contract_symbol', row.get('contractSymbol', row.get('contract', 'UNKNOWN'))),
            row.get('expiration_date', '2025-12-31'),
            row.get('strike', row.get('strike_price', 0)),
            row.get('option_type', 'call'),
            row.get('last_price', row.get('lastPrice', 0)),
            row.get('bid', 0),
            row.get('ask', 0),
            row.get('volume', 0),
            row.get('open_interest', row.get('openInterest', 0)),
            row.get('implied_volatility', row.get('impliedVolatility', 0)),
            row.get('days_to_expiry', 0)
        ))
        loaded += 1
        if loaded % 50 == 0:
            print(f"   {loaded} rows loaded...")
    except Exception as e:
        print(f"   Row {idx} error: {e}")
        continue

conn.commit()
print(f"\n✅ Successfully loaded: {loaded} rows")

# Verify
cursor.execute("SELECT COUNT(*) FROM OPTIONS_SNAPSHOT")
total = cursor.fetchone()[0]
print(f"✅ Total in Snowflake: {total} rows")

cursor.close()
conn.close()

print("\n🎉 DATA LOADED!")