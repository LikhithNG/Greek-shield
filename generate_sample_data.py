import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# Create data directory
os.makedirs('data', exist_ok=True)

# Generate sample AAPL options data
def generate_sample_options():
    """Generate realistic sample options data for testing"""
    
    current_price = 175.50
    
    # Two expiration dates
    expiry1 = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
    expiry2 = (datetime.now() + timedelta(days=38)).strftime('%Y-%m-%d')
    
    options_data = []
    
    # Generate strikes around current price
    strikes = np.arange(165, 186, 2.5)
    
    for expiry, days_to_exp in [(expiry1, 10), (expiry2, 38)]:
        T = days_to_exp / 365
        
        for strike in strikes:
            # Calculate realistic Greeks
            moneyness = current_price / strike
            
            # CALL
            if strike < current_price:  # ITM
                delta = 0.6 + (current_price - strike) / 100
                theta = -0.3 - (10 - days_to_exp) * 0.05
            elif strike > current_price:  # OTM
                delta = 0.4 - (strike - current_price) / 100
                theta = -0.2 - (10 - days_to_exp) * 0.03
            else:  # ATM
                delta = 0.5
                theta = -0.4
            
            delta = max(0.01, min(0.99, delta))  # Bound delta
            
            options_data.append({
                'timestamp': datetime.now(),
                'ticker': 'AAPL',
                'underlying_price': current_price,
                'expiration_date': expiry,
                'days_to_expiration': days_to_exp,
                'strike_price': strike,
                'option_type': 'CALL',
                'last_price': max(0.1, current_price - strike + 2 * np.random.random()),
                'bid': max(0.05, current_price - strike + 1.8 * np.random.random()),
                'ask': max(0.15, current_price - strike + 2.2 * np.random.random()),
                'volume': int(np.random.exponential(100)),
                'open_interest': int(np.random.exponential(500)),
                'implied_volatility': 0.2 + np.random.random() * 0.15,
                'delta': round(delta, 4),
                'gamma': round(0.01 + np.random.random() * 0.05, 4),
                'theta': round(theta - np.random.random() * 0.2, 4),
                'vega': round(0.1 + np.random.random() * 0.2, 4),
                'rho': round(0.01 + np.random.random() * 0.05, 4),
                'moneyness': round(moneyness, 4),
                'intrinsic_value': max(0, current_price - strike),
                'time_value': max(0.1, 2 * np.random.random())
            })
            
            # PUT
            put_delta = delta - 1  # Put-call parity
            
            options_data.append({
                'timestamp': datetime.now(),
                'ticker': 'AAPL',
                'underlying_price': current_price,
                'expiration_date': expiry,
                'days_to_expiration': days_to_exp,
                'strike_price': strike,
                'option_type': 'PUT',
                'last_price': max(0.1, strike - current_price + 2 * np.random.random()),
                'bid': max(0.05, strike - current_price + 1.8 * np.random.random()),
                'ask': max(0.15, strike - current_price + 2.2 * np.random.random()),
                'volume': int(np.random.exponential(80)),
                'open_interest': int(np.random.exponential(400)),
                'implied_volatility': 0.2 + np.random.random() * 0.15,
                'delta': round(put_delta, 4),
                'gamma': round(0.01 + np.random.random() * 0.05, 4),
                'theta': round(theta - np.random.random() * 0.15, 4),
                'vega': round(0.1 + np.random.random() * 0.2, 4),
                'rho': round(-0.01 - np.random.random() * 0.05, 4),
                'moneyness': round(moneyness, 4),
                'intrinsic_value': max(0, strike - current_price),
                'time_value': max(0.1, 2 * np.random.random())
            })
    
    df = pd.DataFrame(options_data)
    
    # Add some high-risk contracts for testing agents
    # High theta decay
    df.loc[df.index[:3], 'theta'] = -0.85
    # High delta
    df.loc[df.index[10:13], 'delta'] = 0.92
    
    return df

# Generate and save data
print("Generating sample AAPL options data...")
df = generate_sample_options()

# Save to CSV
filename = 'data/AAPL_options_latest.csv'
df.to_csv(filename, index=False)
print(f"✅ Saved {len(df)} sample contracts to {filename}")

# Show summary
print(f"\nSample Data Summary:")
print(f"- Contracts: {len(df)}")
print(f"- Expiries: {df['expiration_date'].nunique()}")
print(f"- High theta decay: {len(df[df['theta'] < -0.5])} contracts")
print(f"- High delta: {len(df[abs(df['delta']) > 0.8])} contracts")
print(f"\n✅ You can now proceed with building agents and dashboard using this data!")