import yfinance as yf
import time
import requests
from datetime import datetime

print("Testing Yahoo Finance connection fixes...")

# Method 1: Direct test with session
print("\n1. Testing with fresh session...")
session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

try:
    aapl = yf.Ticker('AAPL', session=session)
    info = aapl.info
    if 'currentPrice' in info:
        print(f"✅ Success! AAPL price: ${info['currentPrice']}")
    else:
        hist = aapl.history(period='1d')
        if not hist.empty:
            print(f"✅ Success! AAPL price: ${hist['Close'].iloc[-1]:.2f}")
except Exception as e:
    print(f"❌ Failed: {e}")

# Method 2: Try with download function
print("\n2. Testing with yf.download...")
try:
    data = yf.download('AAPL', period='5d', progress=False)
    if not data.empty:
        price = data['Close'].iloc[-1]
        print(f"✅ Success! AAPL price: ${price:.2f}")
        print(f"   Data shape: {data.shape}")
except Exception as e:
    print(f"❌ Failed: {e}")

# Method 3: Test options
print("\n3. Testing options data...")
try:
    aapl = yf.Ticker('AAPL')
    opts = aapl.options
    if opts:
        print(f"✅ Found {len(opts)} expiration dates")
        print(f"   Next 3: {opts[:3]}")
except Exception as e:
    print(f"❌ Failed: {e}")