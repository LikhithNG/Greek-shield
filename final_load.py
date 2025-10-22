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
print("LOADING AAPL OPTIONS TO SNOWFLAKE")
print("="*60)

# Read CSV
csv_file = 'data/AAPL_latest.csv'
df = pd.read_csv(csv_file)
print(f"\n✅ Found {len(df)} rows in CSV")

# Add snapshot ID
snapshot_id = str(uuid.uuid4())

# Connect
conn = get_connection()
cursor = conn.cursor()
print("✅ Connected to Snowflake!")

print(f"\n📤 Loading data...")

loaded = 0
for _, row in df.iterrows():
    try:
        # Convert timestamp string to datetime
        if pd.notna(row['timestamp']):
            collection_ts = pd.to_datetime(row['timestamp'])
        else:
            collection_ts = datetime.now()
        
        cursor.execute("""
            INSERT INTO OPTIONS_SNAPSHOT 
            (snapshot_id, collection_timestamp, ticker, underlying_price, 
             contract_symbol, expiration_date, strike_price, option_type,
             last_price, bid, ask, volume, open_interest, 
             implied_volatility, days_to_expiry)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            snapshot_id,
            collection_ts,
            row['ticker'],
            float(row['underlying_price']),
            str(row['contract_id']),  # Use contract_id as contract_symbol
            str(row['expiration_date']),
            float(row['strike_price']),
            str(row['option_type']),
            float(row['last_price']),
            float(row.get('bid', 0)),
            float(row.get('ask', 0)),
            int(row.get('volume', 0)),
            int(row.get('open_interest', 0)),
            float(row.get('implied_volatility', 0)),
            int(row.get('days_to_expiration', 0))  # Use days_to_expiration
        ))
        loaded += 1
        if loaded % 50 == 0:
            print(f"   {loaded} rows loaded...")
    except Exception as e:
        print(f"   Row {loaded} error: {e}")
        continue

conn.commit()
print(f"\n✅ Successfully loaded: {loaded} rows!")

# Verify
cursor.execute("SELECT COUNT(*) FROM OPTIONS_SNAPSHOT")
total = cursor.fetchone()[0]
print(f"✅ Total in Snowflake: {total} rows")

# Show sample
print("\n📊 Sample data:")
cursor.execute("""
    SELECT ticker, strike_price, option_type, last_price, expiration_date 
    FROM OPTIONS_SNAPSHOT 
    LIMIT 5
""")
for row in cursor.fetchall():
    print(f"   {row[0]} ${row[1]} {row[2]} @ ${row[3]} exp:{row[4]}")

cursor.close()
conn.close()

print("\n🎉 DATA SUCCESSFULLY LOADED TO SNOWFLAKE!")
print("="*60)
