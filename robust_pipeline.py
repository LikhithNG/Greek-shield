"""
Production-Ready Options Data Pipeline
- Handles Yahoo Finance API issues gracefully
- Maintains historical data with daily appends
- Includes retry logic and fallback mechanisms
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm
import logging
import os
import json
import time
import requests
from typing import Dict, List, Optional, Tuple
import hashlib
import warnings
warnings.filterwarnings('ignore')

# ===== CONFIGURATION =====
class Config:
    DATA_DIR = 'data'
    HISTORICAL_DIR = 'data/historical'
    SNAPSHOT_DIR = 'data/snapshots'
    LOG_DIR = 'logs'
    
    # Yahoo Finance settings
    MAX_RETRIES = 5
    RETRY_DELAY = 2  # seconds
    
    # Risk-free rate
    RISK_FREE_RATE = 0.045
    
    # Data collection settings
    DEFAULT_TICKERS = ['AAPL']
    MAX_EXPIRIES = 3  # Collect 3 nearest expiries
    
    # User agent for requests
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# Create directories
for directory in [Config.DATA_DIR, Config.HISTORICAL_DIR, Config.SNAPSHOT_DIR, Config.LOG_DIR]:
    os.makedirs(directory, exist_ok=True)

# ===== LOGGING SETUP =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{Config.LOG_DIR}/pipeline_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== GREEKS CALCULATOR =====
class BlackScholesGreeks:
    """Calculate Options Greeks using Black-Scholes model"""
    
    def __init__(self, risk_free_rate: float = Config.RISK_FREE_RATE):
        self.r = risk_free_rate
    
    def calculate_all_greeks(self, S: float, K: float, T: float, 
                           sigma: float, option_type: str = 'CALL') -> Dict[str, float]:
        """Calculate all Greeks with error handling"""
        
        # Default values for edge cases
        default_greeks = {'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'rho': 0}
        
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return default_greeks
        
        try:
            # Calculate d1 and d2
            d1 = (np.log(S/K) + (self.r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
            d2 = d1 - sigma*np.sqrt(T)
            
            # Calculate Greeks based on option type
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
            
            # Same for both CALL and PUT
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
            logger.warning(f"Greeks calculation error: {e}")
            return default_greeks

# ===== YAHOO FINANCE CONNECTOR =====
class YahooFinanceConnector:
    """Robust Yahoo Finance data fetcher with retry logic"""
    
    def __init__(self):
        self.session = self._create_session()
        self.calculator = BlackScholesGreeks()
    
    def _create_session(self) -> requests.Session:
        """Create session with proper headers"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': Config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        return session
    
    def fetch_ticker_with_retry(self, ticker: str) -> Optional[yf.Ticker]:
        """Fetch ticker with multiple retry strategies"""
        
        strategies = [
            lambda: yf.Ticker(ticker, session=self.session),
            lambda: yf.Ticker(ticker),  # Try without session
            lambda: self._fetch_with_new_session(ticker)
        ]
        
        for attempt, strategy in enumerate(strategies):
            try:
                logger.info(f"Attempting to fetch {ticker} (strategy {attempt + 1})")
                stock = strategy()
                
                # Verify we can get data
                hist = stock.history(period='1d')
                if not hist.empty:
                    logger.info(f"Successfully connected to {ticker}")
                    return stock
                    
            except Exception as e:
                logger.warning(f"Strategy {attempt + 1} failed: {e}")
                time.sleep(Config.RETRY_DELAY)
        
        # Last resort: try yf.download
        try:
            logger.info(f"Trying yf.download for {ticker}")
            data = yf.download(ticker, period='5d', progress=False)
            if not data.empty:
                return yf.Ticker(ticker)
        except:
            pass
        
        logger.error(f"All strategies failed for {ticker}")
        return None
    
    def _fetch_with_new_session(self, ticker: str) -> yf.Ticker:
        """Create new session and try again"""
        self.session = self._create_session()
        return yf.Ticker(ticker, session=self.session)
    
    def get_stock_info(self, ticker: str) -> Dict:
        """Get current stock information"""
        stock = self.fetch_ticker_with_retry(ticker)
        if not stock:
            return {}
        
        try:
            # Try multiple methods to get current price
            current_price = None
            
            # Method 1: info
            try:
                info = stock.info
                current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            except:
                pass
            
            # Method 2: history
            if not current_price:
                hist = stock.history(period='5d')
                if not hist.empty:
                    current_price = float(hist['Close'].iloc[-1])
            
            if current_price:
                return {
                    'ticker': ticker,
                    'current_price': current_price,
                    'timestamp': datetime.now(),
                    'status': 'success'
                }
            
        except Exception as e:
            logger.error(f"Error getting stock info: {e}")
        
        return {'ticker': ticker, 'status': 'failed'}
    
    def fetch_options_chain(self, ticker: str) -> pd.DataFrame:
        """Fetch complete options chain with all error handling"""
        
        stock = self.fetch_ticker_with_retry(ticker)
        if not stock:
            logger.error(f"Cannot fetch options for {ticker}")
            return pd.DataFrame()
        
        stock_info = self.get_stock_info(ticker)
        if not stock_info or 'current_price' not in stock_info:
            logger.error(f"Cannot get current price for {ticker}")
            return pd.DataFrame()
        
        current_price = stock_info['current_price']
        logger.info(f"{ticker} current price: ${current_price:.2f}")
        
        try:
            # Get all available expiration dates
            expirations = stock.options
            if not expirations:
                logger.error(f"No options available for {ticker}")
                return pd.DataFrame()
            
            logger.info(f"Found {len(expirations)} expiration dates for {ticker}")
            
            # Select expiries to process
            selected_expiries = expirations[:Config.MAX_EXPIRIES]
            all_options = []
            
            for expiry_str in selected_expiries:
                logger.info(f"Processing {expiry_str} expiry...")
                
                try:
                    # Calculate days to expiration
                    expiry_date = pd.to_datetime(expiry_str)
                    days_to_exp = (expiry_date - datetime.now()).days
                    
                    if days_to_exp <= 0:
                        continue
                    
                    T = days_to_exp / 365.0
                    
                    # Get options chain for this expiry
                    opt_chain = stock.option_chain(expiry_str)
                    
                    # Process calls and puts
                    for opt_type, opt_df in [('CALL', opt_chain.calls), ('PUT', opt_chain.puts)]:
                        for _, opt in opt_df.iterrows():
                            contract_data = self._process_option_contract(
                                opt, ticker, current_price, expiry_date,
                                days_to_exp, T, opt_type
                            )
                            if contract_data:
                                all_options.append(contract_data)
                    
                except Exception as e:
                    logger.error(f"Error processing {expiry_str}: {e}")
                    continue
            
            if all_options:
                df = pd.DataFrame(all_options)
                logger.info(f"Successfully fetched {len(df)} option contracts for {ticker}")
                return df
            else:
                logger.warning(f"No options data collected for {ticker}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error fetching options chain: {e}")
            return pd.DataFrame()
    
    def _process_option_contract(self, opt: pd.Series, ticker: str, stock_price: float,
                                expiry_date: datetime, days_to_exp: int, T: float,
                                option_type: str) -> Optional[Dict]:
        """Process individual option contract"""
        try:
            # Get prices with fallbacks
            last_price = self._safe_get_float(opt, 'lastPrice', 0)
            bid = self._safe_get_float(opt, 'bid', 0)
            ask = self._safe_get_float(opt, 'ask', 0)
            
            # Calculate mid price if last price not available
            if last_price == 0 and bid > 0 and ask > 0:
                last_price = (bid + ask) / 2
            
            # Get IV with fallback
            iv = self._safe_get_float(opt, 'impliedVolatility', 0.25)
            if iv <= 0:
                iv = 0.25  # Default IV
            
            # Calculate Greeks
            strike = float(opt['strike'])
            greeks = self.calculator.calculate_all_greeks(
                S=stock_price, K=strike, T=T, sigma=iv, option_type=option_type
            )
            
            # Calculate additional metrics
            moneyness = stock_price / strike
            
            if option_type == 'CALL':
                intrinsic_value = max(0, stock_price - strike)
            else:
                intrinsic_value = max(0, strike - stock_price)
            
            time_value = max(0, last_price - intrinsic_value)
            
            return {
                'data_date': datetime.now().date(),
                'timestamp': datetime.now(),
                'ticker': ticker,
                'underlying_price': stock_price,
                'expiration_date': expiry_date.strftime('%Y-%m-%d'),
                'days_to_expiration': days_to_exp,
                'strike_price': strike,
                'option_type': option_type,
                'last_price': round(last_price, 2),
                'bid': round(bid, 2),
                'ask': round(ask, 2),
                'volume': int(self._safe_get_float(opt, 'volume', 0)),
                'open_interest': int(self._safe_get_float(opt, 'openInterest', 0)),
                'implied_volatility': round(iv, 4),
                'delta': greeks['delta'],
                'gamma': greeks['gamma'],
                'theta': greeks['theta'],
                'vega': greeks['vega'],
                'rho': greeks['rho'],
                'moneyness': round(moneyness, 4),
                'intrinsic_value': round(intrinsic_value, 2),
                'time_value': round(time_value, 2),
                # Add unique identifier for tracking
                'contract_id': self._generate_contract_id(ticker, strike, expiry_date, option_type)
            }
            
        except Exception as e:
            logger.warning(f"Error processing contract: {e}")
            return None
    
    def _safe_get_float(self, series: pd.Series, key: str, default: float) -> float:
        """Safely get float value from series"""
        try:
            val = series.get(key, default)
            if pd.isna(val) or val is None:
                return default
            return float(val)
        except:
            return default
    
    def _generate_contract_id(self, ticker: str, strike: float, expiry: datetime, opt_type: str) -> str:
        """Generate unique contract identifier"""
        id_string = f"{ticker}_{strike}_{expiry.strftime('%Y%m%d')}_{opt_type}"
        return hashlib.md5(id_string.encode()).hexdigest()[:12]

# ===== DATA MANAGER =====
class DataManager:
    """Manage data storage and historical tracking"""
    
    def __init__(self):
        self.historical_file = f"{Config.HISTORICAL_DIR}/options_historical.csv"
        self.metadata_file = f"{Config.DATA_DIR}/metadata.json"
    
    def save_daily_snapshot(self, df: pd.DataFrame, ticker: str) -> str:
        """Save daily snapshot of data"""
        if df.empty:
            logger.warning("No data to save")
            return ""
        
        # Save daily snapshot
        date_str = datetime.now().strftime('%Y%m%d')
        snapshot_file = f"{Config.SNAPSHOT_DIR}/{ticker}_snapshot_{date_str}.csv"
        df.to_csv(snapshot_file, index=False)
        logger.info(f"Saved daily snapshot: {snapshot_file}")
        
        # Also save as latest
        latest_file = f"{Config.DATA_DIR}/{ticker}_latest.csv"
        df.to_csv(latest_file, index=False)
        
        return snapshot_file
    
    def append_to_historical(self, df: pd.DataFrame) -> None:
        """Append new data to historical dataset"""
        if df.empty:
            return
        
        # Add collection date
        df['collection_date'] = datetime.now().date()
        
        if os.path.exists(self.historical_file):
            # Load existing historical data
            historical_df = pd.read_csv(self.historical_file)
            
            # Combine with new data
            combined_df = pd.concat([historical_df, df], ignore_index=True)
            
            # Remove exact duplicates based on contract_id and date
            combined_df.drop_duplicates(
                subset=['contract_id', 'data_date'],
                keep='last',
                inplace=True
            )
            
            # Save combined data
            combined_df.to_csv(self.historical_file, index=False)
            logger.info(f"Appended {len(df)} records to historical data")
        else:
            # First time - create historical file
            df.to_csv(self.historical_file, index=False)
            logger.info(f"Created historical file with {len(df)} records")
    
    def update_metadata(self, ticker: str, status: str, records: int) -> None:
        """Update metadata about data collection"""
        metadata = {}
        
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r') as f:
                metadata = json.load(f)
        
        if ticker not in metadata:
            metadata[ticker] = []
        
        metadata[ticker].append({
            'date': datetime.now().isoformat(),
            'status': status,
            'records': records
        })
        
        # Keep only last 30 days of metadata
        metadata[ticker] = metadata[ticker][-30:]
        
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def get_historical_summary(self) -> pd.DataFrame:
        """Get summary of historical data"""
        if not os.path.exists(self.historical_file):
            return pd.DataFrame()
        
        df = pd.read_csv(self.historical_file)
        
        summary = df.groupby(['ticker', 'data_date']).agg({
            'contract_id': 'count',
            'volume': 'sum',
            'open_interest': 'sum'
        }).rename(columns={'contract_id': 'contracts'})
        
        return summary

# ===== MAIN PIPELINE =====
class OptionsPipeline:
    """Main pipeline orchestrator"""
    
    def __init__(self):
        self.connector = YahooFinanceConnector()
        self.data_manager = DataManager()
    
    def run_daily_collection(self, tickers: List[str] = None) -> Dict[str, pd.DataFrame]:
        """Run daily data collection for specified tickers"""
        
        tickers = tickers or Config.DEFAULT_TICKERS
        results = {}
        
        logger.info("="*60)
        logger.info(f"Starting Daily Data Collection - {datetime.now()}")
        logger.info(f"Tickers: {tickers}")
        logger.info("="*60)
        
        for ticker in tickers:
            try:
                logger.info(f"\nProcessing {ticker}...")
                
                # Fetch options data
                options_df = self.connector.fetch_options_chain(ticker)
                
                if not options_df.empty:
                    # Save daily snapshot
                    snapshot_file = self.data_manager.save_daily_snapshot(options_df, ticker)
                    
                    # Append to historical data
                    self.data_manager.append_to_historical(options_df)
                    
                    # Update metadata
                    self.data_manager.update_metadata(ticker, 'success', len(options_df))
                    
                    # Store results
                    results[ticker] = options_df
                    
                    # Print summary
                    self._print_summary(ticker, options_df)
                else:
                    logger.warning(f"No data collected for {ticker}")
                    self.data_manager.update_metadata(ticker, 'failed', 0)
                    results[ticker] = pd.DataFrame()
                    
            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                self.data_manager.update_metadata(ticker, 'error', 0)
                results[ticker] = pd.DataFrame()
        
        logger.info("\n" + "="*60)
        logger.info("Daily collection completed")
        logger.info("="*60)
        
        return results
    
    def _print_summary(self, ticker: str, df: pd.DataFrame) -> None:
        """Print summary statistics"""
        logger.info(f"\n{ticker} Collection Summary:")
        logger.info(f"  - Total contracts: {len(df)}")
        logger.info(f"  - Expiration dates: {df['expiration_date'].nunique()}")
        logger.info(f"  - Strike prices: {df['strike_price'].nunique()}")
        logger.info(f"  - Total volume: {df['volume'].sum():,}")
        
        # Risk highlights
        high_theta = len(df[df['theta'] < -0.50])
        high_delta = len(df[abs(df['delta']) > 0.80])
        
        if high_theta > 0:
            logger.info(f"  - High theta decay: {high_theta} contracts")
        if high_delta > 0:
            logger.info(f"  - High delta: {high_delta} contracts")
    
    def get_latest_data(self, ticker: str) -> pd.DataFrame:
        """Get latest data for a ticker"""
        latest_file = f"{Config.DATA_DIR}/{ticker}_latest.csv"
        
        if os.path.exists(latest_file):
            return pd.read_csv(latest_file)
        else:
            logger.warning(f"No data found for {ticker}")
            return pd.DataFrame()
    
    def run_backfill(self, ticker: str, days_back: int = 30) -> None:
        """Backfill historical data (if needed)"""
        logger.info(f"Backfilling {days_back} days of data for {ticker}")
        # Implementation depends on Yahoo Finance limitations
        # For now, just run current day
        self.run_daily_collection([ticker])

# ===== SCHEDULER =====
def schedule_daily_run(hour: int = 18, minute: int = 30):
    """Schedule daily pipeline run"""
    import schedule
    
    def job():
        pipeline = OptionsPipeline()
        pipeline.run_daily_collection()
    
    schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(job)
    
    logger.info(f"Scheduled daily run at {hour:02d}:{minute:02d}")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# ===== MAIN EXECUTION =====
if __name__ == "__main__":
    # Create pipeline
    pipeline = OptionsPipeline()
    
    # Run collection
    results = pipeline.run_daily_collection(['AAPL'])
    
    # Show results
    for ticker, df in results.items():
        if not df.empty:
            print(f"\n✅ {ticker}: Collected {len(df)} contracts")
            print(f"📁 Data saved to:")
            print(f"   - Latest: data/{ticker}_latest.csv")
            print(f"   - Historical: data/historical/options_historical.csv")
            print(f"   - Snapshot: data/snapshots/{ticker}_snapshot_{datetime.now().strftime('%Y%m%d')}.csv")
        else:
            print(f"\n❌ {ticker}: Failed to collect data")
    
    # Show historical summary
    print("\n📊 Historical Data Summary:")
    summary = pipeline.data_manager.get_historical_summary()
    if not summary.empty:
        print(summary.tail(10))