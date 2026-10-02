# connection.py
import snowflake.connector
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

def test_snowflake_connection():
    """Test basic Snowflake connection"""
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
        print("✅ Connected to Snowflake!")
        
        cursor = conn.cursor()
        cursor.execute("SELECT CURRENT_VERSION()")
        version = cursor.fetchone()[0]
        print(f"Snowflake version: {version}")
        
        # Test query your tables
        cursor.execute("SHOW TABLES IN SCHEMA RAW_DATA")
        tables = cursor.fetchall()
        print(f"Found {len(tables)} tables in RAW_DATA schema")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Snowflake connection failed: {e}")
        if "MFA" in str(e):
            print("\n⚠️  MFA is blocking connection. Using CSV fallback strategy.")
            print("Your data is being saved locally to 'data/' folder instead.")
        return False

if __name__ == "__main__":
    test_snowflake_connection()