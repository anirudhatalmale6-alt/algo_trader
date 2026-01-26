"""
Base Broker class - Abstract interface for all broker integrations
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class ProductType(Enum):
    CNC = "CNC"  # Cash and Carry (Delivery)
    MIS = "MIS"  # Margin Intraday Square-off
    NRML = "NRML"  # Normal (F&O overnight)


@dataclass
class BrokerOrder:
    """Standard order format across brokers"""
    symbol: str
    exchange: str
    transaction_type: str  # BUY/SELL
    order_type: str  # MARKET/LIMIT/SL/SL-M
    quantity: int
    price: float = None
    trigger_price: float = None
    product: str = "CNC"
    validity: str = "DAY"


class BaseBroker(ABC):
    """
    Abstract base class for broker integrations
    All broker implementations must inherit from this
    """

    def __init__(self, api_key: str, api_secret: str, **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = None
        self.is_authenticated = False
        self.broker_name = "base"

    @abstractmethod
    def authenticate(self, **kwargs) -> bool:
        """
        Authenticate with the broker API
        Returns True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_login_url(self) -> str:
        """
        Get the OAuth login URL for user authentication
        """
        pass

    @abstractmethod
    def generate_session(self, auth_code: str) -> bool:
        """
        Generate session/access token using authorization code
        """
        pass

    @abstractmethod
    def place_order(self, order: BrokerOrder) -> Dict:
        """
        Place an order
        Returns: {'success': bool, 'order_id': str, 'message': str}
        """
        pass

    @abstractmethod
    def modify_order(self, order_id: str, **kwargs) -> Dict:
        """
        Modify an existing order
        Returns: {'success': bool, 'message': str}
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel an order
        Returns: {'success': bool, 'message': str}
        """
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict:
        """
        Get status of a specific order
        """
        pass

    @abstractmethod
    def get_orders(self) -> List[Dict]:
        """
        Get all orders for the day
        """
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict]:
        """
        Get current positions
        """
        pass

    @abstractmethod
    def get_holdings(self) -> List[Dict]:
        """
        Get holdings (delivery stocks)
        """
        pass

    @abstractmethod
    def get_funds(self) -> Dict:
        """
        Get available funds/margins
        """
        pass

    @abstractmethod
    def get_quote(self, symbol: str, exchange: str) -> Dict:
        """
        Get current quote for a symbol
        """
        pass

    @abstractmethod
    def get_historical_data(self, symbol: str, exchange: str,
                           interval: str, from_date: str, to_date: str) -> List[Dict]:
        """
        Get historical OHLCV data
        interval: 1minute, 5minute, 15minute, 30minute, 60minute, day
        """
        pass

    def _log_request(self, endpoint: str, method: str = "GET"):
        """Log API request for debugging"""
        logger.debug(f"{self.broker_name} API: {method} {endpoint}")

    def _handle_error(self, response: Dict, context: str = "") -> Dict:
        """Handle API error response"""
        error_msg = response.get('message', 'Unknown error')
        logger.error(f"{self.broker_name} {context}: {error_msg}")
        return {'success': False, 'message': error_msg}

    def is_market_open(self) -> bool:
        """Check if market is open (basic implementation)"""
        from datetime import datetime
        import pytz

        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)

        # Market hours: 9:15 AM to 3:30 PM, Monday to Friday
        if now.weekday() >= 5:  # Weekend
            return False

        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

        return market_open <= now <= market_close
