#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import snowflake.connector

load_dotenv()

print("Testing Snowflake Trial Account Connection...")
print(f"Account: {os.getenv('SNOWFLAKE_ACCOUNT')}")
print(f"User: {os.getenv('SNOWFLAKE_USER')}")

try:
    conn = snowflake.connector.connect(
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA'),
        role=os.getenv('SNOWFLAKE_ROLE')
    )
    
    print("✅ Connected successfully!")
    
    cursor = conn.cursor()
    cursor.execute("SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE()")
    user, role, warehouse = cursor.fetchone()
    print(f"✅ User: {user}")
    print(f"✅ Role: {role}")
    print(f"✅ Warehouse: {warehouse}")
    
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print(f"✅ Found {len(tables)} tables:")
    for table in tables:
        print(f"   - {table[1]}")
    
    cursor.close()
    conn.close()
    print("\n🎉 CONNECTION TEST PASSED!")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")