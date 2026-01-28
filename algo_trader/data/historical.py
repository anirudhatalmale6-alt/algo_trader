"""
Historical Data Manager
Fetches and caches historical OHLCV data from brokers and Yahoo Finance
"""
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path
import json
from loguru import logger


# Yahoo Finance symbol mapping for Indian stocks
NSE_SUFFIX = ".NS"
BSE_SUFFIX = ".BO"
INDEX_SYMBOLS = {
    'NIFTY': '^NSEI', 'NIFTY50': '^NSEI',
    'BANKNIFTY': '^NSEBANK', 'SENSEX': '^BSESN',
}


class HistoricalDataManager:
    """
    Manages historical data fetching and caching
    """

    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".algo_trader" / "data_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.brokers = {}

    def register_broker(self, name: str, broker_instance):
        """Register a broker for data fetching"""
        self.brokers[name] = broker_instance
        logger.info(f"Registered broker '{name}' for historical data")

    def get_historical_data(self, symbol: str, exchange: str = "NSE",
                           interval: str = "day", days: int = 365,
                           broker: str = None) -> Optional[pd.DataFrame]:
        """
        Get historical OHLCV data

        Args:
            symbol: Stock symbol (e.g., RELIANCE, NIFTY)
            exchange: Exchange (NSE, BSE, NFO)
            interval: Candle interval (1minute, 5minute, 15minute, 30minute, 60minute, day)
            days: Number of days of data to fetch
            broker: Broker to use for fetching (uses first available if not specified)

        Returns:
            DataFrame with columns: open, high, low, close, volume, datetime
        """
        # Try cache first
        cached_data = self._load_from_cache(symbol, exchange, interval, days)
        if cached_data is not None:
            logger.info(f"Loaded {symbol} data from cache")
            return cached_data

        # Fetch from broker
        broker_name = broker or (list(self.brokers.keys())[0] if self.brokers else None)

        if not broker_name or broker_name not in self.brokers:
            logger.warning("No broker available for historical data")
            return self._get_sample_data(symbol, days)

        try:
            broker_instance = self.brokers[broker_name]
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            candles = broker_instance.get_historical_data(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                from_date=start_date,
                to_date=end_date
            )

            if candles:
                df = pd.DataFrame(candles)
                df['datetime'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('datetime')
                df = df[['open', 'high', 'low', 'close', 'volume']]

                # Cache the data
                self._save_to_cache(df, symbol, exchange, interval)

                return df

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")

        # Return sample data as fallback
        return self._get_sample_data(symbol, days)

    def _get_cache_key(self, symbol: str, exchange: str, interval: str) -> str:
        """Generate cache key"""
        return f"{exchange}_{symbol}_{interval}"

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path"""
        return self.cache_dir / f"{cache_key}.parquet"

    def _load_from_cache(self, symbol: str, exchange: str, interval: str, days: int) -> Optional[pd.DataFrame]:
        """Load data from cache if valid"""
        cache_key = self._get_cache_key(symbol, exchange, interval)
        cache_path = self._get_cache_path(cache_key)
        meta_path = self.cache_dir / f"{cache_key}_meta.json"

        if not cache_path.exists() or not meta_path.exists():
            return None

        try:
            # Check cache validity
            with open(meta_path, 'r') as f:
                meta = json.load(f)

            cached_date = datetime.fromisoformat(meta.get('cached_at', '2000-01-01'))
            cache_age = (datetime.now() - cached_date).total_seconds() / 3600  # hours

            # Cache valid for 24 hours for daily data, 1 hour for intraday
            max_age = 24 if interval == 'day' else 1

            if cache_age > max_age:
                return None

            # Load data
            df = pd.read_parquet(cache_path)
            return df

        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return None

    def _save_to_cache(self, df: pd.DataFrame, symbol: str, exchange: str, interval: str):
        """Save data to cache"""
        try:
            cache_key = self._get_cache_key(symbol, exchange, interval)
            cache_path = self._get_cache_path(cache_key)
            meta_path = self.cache_dir / f"{cache_key}_meta.json"

            # Save data
            df.to_parquet(cache_path)

            # Save metadata
            meta = {
                'symbol': symbol,
                'exchange': exchange,
                'interval': interval,
                'cached_at': datetime.now().isoformat(),
                'rows': len(df)
            }
            with open(meta_path, 'w') as f:
                json.dump(meta, f)

            logger.info(f"Cached {len(df)} rows for {symbol}")

        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def _get_sample_data(self, symbol: str, days: int) -> pd.DataFrame:
        """Generate sample data for testing when no broker is available"""
        import numpy as np

        logger.info(f"Generating sample data for {symbol} ({days} days)")

        dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq='D')

        # Generate realistic-looking price data
        np.random.seed(hash(symbol) % 2**32)  # Consistent data for same symbol

        # Start price based on symbol
        if 'NIFTY' in symbol.upper():
            base_price = 18000
        elif 'BANK' in symbol.upper():
            base_price = 42000
        else:
            base_price = 1000 + (hash(symbol) % 4000)

        # Generate returns
        returns = np.random.randn(days) * 0.015  # 1.5% daily volatility
        prices = base_price * np.exp(np.cumsum(returns))

        # Generate OHLCV
        df = pd.DataFrame({
            'open': prices * (1 + np.random.randn(days) * 0.005),
            'high': prices * (1 + np.abs(np.random.randn(days) * 0.01)),
            'low': prices * (1 - np.abs(np.random.randn(days) * 0.01)),
            'close': prices,
            'volume': np.random.randint(100000, 10000000, days)
        }, index=dates)

        # Ensure high >= close, open and low <= close, open
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)

        return df

    def clear_cache(self, symbol: str = None, exchange: str = None):
        """Clear cached data"""
        if symbol and exchange:
            # Clear specific symbol
            for interval in ['1minute', '5minute', '15minute', '30minute', '60minute', 'day']:
                cache_key = self._get_cache_key(symbol, exchange, interval)
                cache_path = self._get_cache_path(cache_key)
                meta_path = self.cache_dir / f"{cache_key}_meta.json"

                if cache_path.exists():
                    cache_path.unlink()
                if meta_path.exists():
                    meta_path.unlink()

            logger.info(f"Cleared cache for {exchange}:{symbol}")
        else:
            # Clear all cache
            for file in self.cache_dir.glob("*"):
                file.unlink()
            logger.info("Cleared all data cache")

    def fetch_yahoo_data(self, symbol: str, start_date: datetime, end_date: datetime,
                         interval: str = "1d") -> Optional[pd.DataFrame]:
        """
        Fetch historical data from Yahoo Finance (free, no broker needed)

        Args:
            symbol: Stock symbol (e.g., 'RELIANCE', 'NIFTY', 'TCS')
            start_date: Start date
            end_date: End date
            interval: Candle interval - 1m, 5m, 15m, 30m, 1h, 1d, 1wk

        Returns:
            DataFrame with columns: datetime, open, high, low, close, volume
        """
        # Convert to Yahoo symbol
        symbol_upper = symbol.upper().strip()
        if symbol_upper in INDEX_SYMBOLS:
            yahoo_symbol = INDEX_SYMBOLS[symbol_upper]
        elif not (symbol_upper.endswith('.NS') or symbol_upper.endswith('.BO') or symbol_upper.startswith('^')):
            yahoo_symbol = f"{symbol_upper}{NSE_SUFFIX}"
        else:
            yahoo_symbol = symbol_upper

        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        params = {
            'period1': start_ts,
            'period2': end_ts,
            'interval': interval,
            'events': 'history'
        }

        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            if 'chart' not in data or 'result' not in data['chart']:
                logger.error(f"Invalid response from Yahoo Finance for {symbol}")
                return None

            result = data['chart']['result'][0]

            if 'timestamp' not in result:
                logger.error(f"No data available for {symbol}")
                return None

            timestamps = result['timestamp']
            quotes = result['indicators']['quote'][0]

            df = pd.DataFrame({
                'datetime': pd.to_datetime(timestamps, unit='s'),
                'open': quotes.get('open', []),
                'high': quotes.get('high', []),
                'low': quotes.get('low', []),
                'close': quotes.get('close', []),
                'volume': quotes.get('volume', [])
            })

            df = df.dropna()
            df = df.sort_values('datetime').reset_index(drop=True)

            logger.info(f"Fetched {len(df)} candles for {symbol} from Yahoo Finance")
            return df

        except Exception as e:
            logger.error(f"Error fetching Yahoo data: {e}")
            return None

    def get_data_for_backtest(self, symbol: str, days: int = 365,
                              interval: str = "1d") -> pd.DataFrame:
        """
        Get data suitable for backtesting - tries Yahoo first, then sample data

        Args:
            symbol: Stock symbol
            days: Number of days of history
            interval: Candle interval (1d, 1h, etc.)

        Returns:
            DataFrame with datetime, open, high, low, close, volume
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Try Yahoo Finance first
        df = self.fetch_yahoo_data(symbol, start_date, end_date, interval)

        if df is not None and len(df) > 0:
            return df

        # Fall back to sample data
        logger.warning(f"Using sample data for {symbol}")
        sample_df = self._get_sample_data(symbol, days)
        sample_df = sample_df.reset_index()
        sample_df = sample_df.rename(columns={'index': 'datetime'})
        return sample_df

    @staticmethod
    def get_available_symbols() -> List[str]:
        """Get list of commonly used NSE symbols"""
        return [
            # Indices
            "NIFTY", "BANKNIFTY",
            # Large Cap
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
            "HINDUNILVR", "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK",
            "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "TITAN",
            "SUNPHARMA", "ULTRACEMCO", "WIPRO", "HCLTECH", "BAJFINANCE",
            "ADANIPORTS", "POWERGRID", "NTPC", "TATASTEEL", "ONGC",
        ]
