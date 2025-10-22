"""
Options Data Pipeline - Local Version (No Snowflake Required)
Saves data to CSV files for development and testing
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm
import logging
import os
from typing import Dict, List, Optional
import time
import warnings
warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
RISK_FREE_RATE = 0.045  # Current T-bill rate
DATA_DIR = 'data'  # Directory to store CSV files

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs('logs', exist_ok=True)

class BlackScholesGreeks:
    """Calculate Options Greeks using Black-Scholes model"""
    
    def __init__(self, risk_free_rate: float = 0.045):
        self.r = risk_free_rate
    
    def calculate_d1_d2(self, S: float, K: float, T: float, sigma: float) -> tuple:
        """Calculate d1 and d2 for Black-Scholes"""
        try:
            if T <= 0 or sigma <= 0:
                return 0, 0
            d1 = (np.log(S/K) + (self.r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
            d2 = d1 - sigma*np.sqrt(T)
            return d1, d2
        except:
            return 0, 0
    
    def calculate_all_greeks(self, S: float, K: float, T: float, sigma: float, 
                           option_type: str = 'CALL') -> Dict[str, float]:
        """Calculate all Greeks for an option"""
        
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}
        
        try:
            d1, d2 = self.calculate_d1_d2(S, K, T, sigma)
            
            # Delta
            if option_type.upper() == 'CALL':
                delta = norm.cdf(d1)
                theta = ((-S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) 
                        - self.r * K * np.exp(-self.r * T) * norm.cdf(d2)) / 365
                rho = K * T * np.exp(-self.r * T) * norm.cdf(d2) / 100
            else:  # PUT
                delta = norm.cdf(d1) - 1
                theta = ((-S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) 
                        + self.r * K * np.exp(-self.r * T) * norm.cdf(-d2)) / 365
                rho = -K * T * np.exp(-self.r * T) * norm.cdf(-d2) / 100
            
            # Same for both
            gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
            vega = S * norm.pdf(d1) * np.sqrt(T) / 100
            
            return {
                'delta': round(delta, 4),
                'gamma': round(gamma, 4),
                'theta': round(theta, 4),
                'vega': round(vega, 4),
                'rho': round(rho, 4)
            }
        except Exception as e:
            logger.error(f"Error calculating Greeks: {e}")
            return {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}

class OptionsDataFetcher:
    """Fetch options data from Yahoo Finance"""
    
    def __init__(self):
        self.calculator = BlackScholesGreeks(RISK_FREE_RATE)
        self.max_retries = 3
    
    def fetch_with_retry(self, ticker: str) -> Optional[yf.Ticker]:
        """Fetch ticker with retry logic"""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Fetching {ticker} data (attempt {attempt + 1})...")
                stock = yf.Ticker(ticker)
                
                # Test if we can get data
                hist = stock.history(period='1d')
                if not hist.empty:
                    return stock
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)  # Wait before retry
                    
        return None
    
    def fetch_stock_data(self, ticker: str) -> Optional[Dict]:
        """Fetch current stock data"""
        stock = self.fetch_with_retry(ticker)
        if not stock:
            return None
            
        try:
            hist = stock.history(period='5d')
            if hist.empty:
                return None
                
            current_price = hist['Close'].iloc[-1]
            
            # Calculate historical volatility
            returns = hist['Close'].pct_change().dropna()
            historical_vol = returns.std() * np.sqrt(252) if len(returns) > 0 else 0.25
            
            return {
                'ticker': ticker,
                'current_price': float(current_price),
                'historical_volatility': float(historical_vol),
                'last_update': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error fetching stock data: {e}")
            return None
    
    def fetch_options_chain(self, ticker: str, max_expiries: int = 2) -> pd.DataFrame:
        """Fetch and process options chain data"""
        
        stock = self.fetch_with_retry(ticker)
        if not stock:
            logger.error(f"Failed to fetch {ticker}")
            return pd.DataFrame()
        
        stock_data = self.fetch_stock_data(ticker)
        if not stock_data:
            logger.error(f"No stock data for {ticker}")
            return pd.DataFrame()
            
        current_price = stock_data['current_price']
        logger.info(f"{ticker} current price: ${current_price:.2f}")
        
        try:
            # Get expiration dates
            expirations = stock.options
            if not expirations:
                logger.error(f"No options data for {ticker}")
                return pd.DataFrame()
            
            logger.info(f"Found {len(expirations)} expiration dates")
            selected_expiries = expirations[:max_expiries]
            logger.info(f"Processing {selected_expiries}")
            
            all_options = []
            
            for expiry_str in selected_expiries:
                expiry_date = pd.to_datetime(expiry_str)
                days_to_exp = (expiry_date - datetime.now()).days
                
                if days_to_exp <= 0:
                    continue
                    
                T = days_to_exp / 365.0
                
                # Get options chain
                opt_chain = stock.option_chain(expiry_str)
                
                # Process CALLS
                for _, opt in opt_chain.calls.iterrows():
                    option_data = self._process_contract(
                        opt, ticker, current_price, expiry_date,
                        days_to_exp, T, 'CALL'
                    )
                    if option_data:
                        all_options.append(option_data)
                
                # Process PUTS  
                for _, opt in opt_chain.puts.iterrows():
                    option_data = self._process_contract(
                        opt, ticker, current_price, expiry_date,
                        days_to_exp, T, 'PUT'
                    )
                    if option_data:
                        all_options.append(option_data)
            
            df = pd.DataFrame(all_options)
            logger.info(f"Successfully fetched {len(df)} contracts")
            return df
            
        except Exception as e:
            logger.error(f"Error in options chain fetch: {e}")
            return pd.DataFrame()
    
    def _process_contract(self, opt: pd.Series, ticker: str, stock_price: float,
                         expiry_date: datetime, days_to_exp: int, T: float,
                         option_type: str) -> Optional[Dict]:
        """Process single option contract"""
        try:
            # Get option price
            if pd.notna(opt.get('lastPrice', 0)) and opt['lastPrice'] > 0:
                option_price = float(opt['lastPrice'])
            elif pd.notna(opt.get('bid', 0)) and pd.notna(opt.get('ask', 0)):
                option_price = float((opt['bid'] + opt['ask']) / 2)
            else:
                option_price = 0
            
            # Get IV
            iv = float(opt.get('impliedVolatility', 0.25))
            if iv <= 0:
                iv = 0.25
            
            # Calculate Greeks
            greeks = self.calculator.calculate_all_greeks(
                S=stock_price,
                K=float(opt['strike']),
                T=T,
                sigma=iv,
                option_type=option_type
            )
            
            # Calculate moneyness
            moneyness = stock_price / opt['strike']
            
            # Calculate intrinsic value
            if option_type == 'CALL':
                intrinsic_value = max(0, stock_price - opt['strike'])
            else:
                intrinsic_value = max(0, opt['strike'] - stock_price)
            
            time_value = max(0, option_price - intrinsic_value)
            
            return {
                'timestamp': datetime.now(),
                'ticker': ticker,
                'underlying_price': stock_price,
                'expiration_date': expiry_date.strftime('%Y-%m-%d'),
                'days_to_expiration': days_to_exp,
                'strike_price': float(opt['strike']),
                'option_type': option_type,
                'last_price': option_price,
                'bid': float(opt.get('bid', 0)),
                'ask': float(opt.get('ask', 0)),
                'volume': int(opt.get('volume', 0)) if pd.notna(opt.get('volume')) else 0,
                'open_interest': int(opt.get('openInterest', 0)) if pd.notna(opt.get('openInterest')) else 0,
                'implied_volatility': iv,
                'delta': greeks['delta'],
                'gamma': greeks['gamma'],
                'theta': greeks['theta'],
                'vega': greeks['vega'],
                'rho': greeks['rho'],
                'moneyness': round(moneyness, 4),
                'intrinsic_value': round(intrinsic_value, 2),
                'time_value': round(time_value, 2)
            }
        except Exception as e:
            logger.warning(f"Error processing contract: {e}")
            return None

class LocalDataManager:
    """Manage data storage in CSV files"""
    
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
    
    def save_options_data(self, df: pd.DataFrame, ticker: str) -> str:
        """Save options data to CSV"""
        if df.empty:
            logger.warning("No data to save")
            return ""
            
        # Create filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.data_dir}/{ticker}_options_{timestamp}.csv"
        
        # Save to CSV
        df.to_csv(filename, index=False)
        logger.info(f"Saved {len(df)} records to {filename}")
        
        # Also save as 'latest' for easy access
        latest_file = f"{self.data_dir}/{ticker}_options_latest.csv"
        df.to_csv(latest_file, index=False)
        
        return filename
    
    def load_latest_data(self, ticker: str) -> pd.DataFrame:
        """Load the latest options data for a ticker"""
        latest_file = f"{self.data_dir}/{ticker}_options_latest.csv"
        
        if os.path.exists(latest_file):
            df = pd.read_csv(latest_file)
            # Convert timestamp back to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            logger.info(f"Loaded {len(df)} records from {latest_file}")
            return df
        else:
            logger.warning(f"No data file found for {ticker}")
            return pd.DataFrame()
    
    def get_all_snapshots(self, ticker: str) -> List[str]:
        """Get list of all snapshot files for a ticker"""
        files = []
        for file in os.listdir(self.data_dir):
            if file.startswith(f"{ticker}_options_") and file.endswith('.csv'):
                files.append(file)
        return sorted(files)

def analyze_options_data(df: pd.DataFrame) -> None:
    """Analyze and print insights from options data"""
    
    if df.empty:
        return
    
    print("\n" + "="*60)
    print("OPTIONS DATA ANALYSIS")
    print("="*60)
    
    # Basic statistics
    print(f"\nTotal contracts: {len(df)}")
    print(f"Expiration dates: {df['expiration_date'].nunique()}")
    print(f"Strike prices: {df['strike_price'].nunique()}")
    
    # High risk contracts (theta decay)
    high_theta = df[df['theta'] < -0.50]
    if not high_theta.empty:
        print(f"\n⚠️  HIGH THETA DECAY ({len(high_theta)} contracts):")
        for _, row in high_theta.nlargest(5, 'theta').iterrows():
            daily_loss = abs(row['theta'] * 100)
            print(f"  {row['option_type']} ${row['strike_price']:.0f} exp:{row['expiration_date']}: "
                  f"Theta={row['theta']:.3f} (${daily_loss:.0f}/day loss)")
    
    # High delta contracts
    high_delta = df[abs(df['delta']) > 0.80]
    if not high_delta.empty:
        print(f"\n📊 HIGH DELTA ({len(high_delta)} contracts):")
        for _, row in high_delta.head(3).iterrows():
            print(f"  {row['option_type']} ${row['strike_price']:.0f}: Delta={row['delta']:.3f}")
    
    # Most active contracts
    active = df.nlargest(5, 'volume')
    if not active.empty:
        print(f"\n📈 MOST ACTIVE CONTRACTS:")
        for _, row in active.iterrows():
            print(f"  {row['option_type']} ${row['strike_price']:.0f}: Volume={row['volume']:,}")
    
    # Summary by expiration
    print(f"\n📅 BY EXPIRATION:")
    summary = df.groupby('expiration_date').agg({
        'option_type': 'count',
        'volume': 'sum',
        'theta': 'mean'
    }).rename(columns={'option_type': 'contracts'})
    print(summary)

def main():
    """Main execution function"""
    
    print("\n" + "🎯"*20)
    print("OPTIONS DATA PIPELINE - LOCAL VERSION")
    print("🎯"*20)
    
    # Initialize components
    fetcher = OptionsDataFetcher()
    manager = LocalDataManager()
    
    # Ticker to process
    ticker = 'AAPL'
    
    print(f"\nProcessing {ticker}...")
    print("-"*40)
    
    # Fetch options data
    options_df = fetcher.fetch_options_chain(ticker, max_expiries=2)
    
    if not options_df.empty:
        # Save to CSV
        filename = manager.save_options_data(options_df, ticker)
        
        # Analyze the data
        analyze_options_data(options_df)
        
        print(f"\n✅ SUCCESS! Data saved to: {filename}")
        print(f"📁 Check the 'data' folder for CSV files")
        
        # Return the dataframe for use by other scripts
        return options_df
    else:
        print(f"\n❌ Failed to fetch options data")
        return pd.DataFrame()

if __name__ == "__main__":
    df = main()
    
    if not df.empty:
        print("\n💡 Next steps:")
        print("1. Run agents.py to generate risk alerts")
        print("2. Run dashboard.py to view in Streamlit")
        print("3. Check 'data' folder for saved CSV files")