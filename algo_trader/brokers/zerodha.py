"""
Zerodha (Kite Connect) Broker Integration
"""
import hashlib
import requests
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger

from algo_trader.brokers.base import BaseBroker, BrokerOrder


class ZerodhaBroker(BaseBroker):
    """
    Zerodha Kite Connect API Integration

    Requires:
    - API Key and API Secret from Kite Connect developer console
    - User login through Kite login flow

    API Docs: https://kite.trade/docs/connect/v3/
    """

    BASE_URL = "https://api.kite.trade"
    LOGIN_URL = "https://kite.zerodha.com/connect/login"

    EXCHANGE_MAP = {
        "NSE": "NSE",
        "BSE": "BSE",
        "NFO": "NFO",
        "MCX": "MCX",
        "CDS": "CDS",
        "BFO": "BFO",
    }

    PRODUCT_MAP = {
        "CNC": "CNC",
        "MIS": "MIS",
        "NRML": "NRML",
    }

    ORDER_TYPE_MAP = {
        "MARKET": "MARKET",
        "LIMIT": "LIMIT",
        "SL": "SL",
        "SL-M": "SL-M",
    }

    def __init__(self, api_key: str, api_secret: str, **kwargs):
        super().__init__(api_key, api_secret, **kwargs)
        self.broker_name = "zerodha"
        self.user_id = kwargs.get('user_id', '')
        self._session = requests.Session()

    def _get_headers(self) -> Dict:
        """Get headers for authenticated requests"""
        return {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }

    def get_login_url(self) -> str:
        """Get Kite Connect login URL"""
        return f"{self.LOGIN_URL}?v=3&api_key={self.api_key}"

    def authenticate(self, **kwargs) -> bool:
        """
        Authenticate using existing access token
        """
        access_token = kwargs.get('access_token')
        if access_token:
            self.access_token = access_token
            # Verify token by getting profile
            try:
                profile = self._get_profile()
                if profile.get('user_id'):
                    self.user_id = profile['user_id']
                    self.is_authenticated = True
                    logger.info(f"Zerodha authenticated for user: {self.user_id}")
                    return True
            except Exception as e:
                logger.error(f"Zerodha authentication failed: {e}")

        return False

    def generate_session(self, request_token: str) -> bool:
        """
        Generate access token from request token (received after login)
        """
        try:
            # Create checksum: SHA256(api_key + request_token + api_secret)
            checksum_str = f"{self.api_key}{request_token}{self.api_secret}"
            checksum = hashlib.sha256(checksum_str.encode()).hexdigest()

            url = f"{self.BASE_URL}/session/token"
            data = {
                "api_key": self.api_key,
                "request_token": request_token,
                "checksum": checksum
            }

            response = self._session.post(url, data=data)
            result = response.json()

            if result.get('status') == 'success':
                self.access_token = result['data']['access_token']
                self.user_id = result['data']['user_id']
                self.is_authenticated = True
                logger.info(f"Zerodha session generated for user: {self.user_id}")
                return True
            else:
                logger.error(f"Zerodha session generation failed: {result.get('message')}")
                return False

        except Exception as e:
            logger.error(f"Zerodha session generation error: {e}")
            return False

    def _get_profile(self) -> Dict:
        """Get user profile"""
        url = f"{self.BASE_URL}/user/profile"
        response = self._session.get(url, headers=self._get_headers())
        result = response.json()

        if result.get('status') == 'success':
            return result.get('data', {})
        return {}

    def place_order(self, order: BrokerOrder) -> Dict:
        """Place an order through Kite Connect"""
        try:
            url = f"{self.BASE_URL}/orders/regular"

            exchange = self.EXCHANGE_MAP.get(order.exchange, order.exchange)
            product = self.PRODUCT_MAP.get(order.product, order.product)
            order_type = self.ORDER_TYPE_MAP.get(order.order_type, order.order_type)

            data = {
                "tradingsymbol": order.symbol,
                "exchange": exchange,
                "transaction_type": order.transaction_type,
                "order_type": order_type,
                "quantity": order.quantity,
                "product": product,
                "validity": order.validity,
            }

            if order.price and order_type in ["LIMIT", "SL"]:
                data["price"] = order.price

            if order.trigger_price and order_type in ["SL", "SL-M"]:
                data["trigger_price"] = order.trigger_price

            self._log_request(url, "POST")
            response = self._session.post(url, data=data, headers=self._get_headers())
            result = response.json()

            if result.get('status') == 'success':
                order_id = result['data']['order_id']
                logger.info(f"Zerodha order placed: {order_id}")
                return {
                    'success': True,
                    'order_id': order_id,
                    'broker_order_id': order_id,
                    'message': 'Order placed successfully'
                }
            else:
                return self._handle_error(result, "place_order")

        except Exception as e:
            logger.error(f"Zerodha place_order error: {e}")
            return {'success': False, 'message': str(e)}

    def modify_order(self, order_id: str, **kwargs) -> Dict:
        """Modify an existing order"""
        try:
            url = f"{self.BASE_URL}/orders/regular/{order_id}"

            data = {}
            if 'quantity' in kwargs:
                data['quantity'] = kwargs['quantity']
            if 'price' in kwargs:
                data['price'] = kwargs['price']
            if 'trigger_price' in kwargs:
                data['trigger_price'] = kwargs['trigger_price']
            if 'order_type' in kwargs:
                data['order_type'] = kwargs['order_type']

            response = self._session.put(url, data=data, headers=self._get_headers())
            result = response.json()

            if result.get('status') == 'success':
                return {'success': True, 'message': 'Order modified successfully'}
            else:
                return self._handle_error(result, "modify_order")

        except Exception as e:
            logger.error(f"Zerodha modify_order error: {e}")
            return {'success': False, 'message': str(e)}

    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        try:
            url = f"{self.BASE_URL}/orders/regular/{order_id}"

            response = self._session.delete(url, headers=self._get_headers())
            result = response.json()

            if result.get('status') == 'success':
                logger.info(f"Zerodha order cancelled: {order_id}")
                return {'success': True, 'message': 'Order cancelled successfully'}
            else:
                return self._handle_error(result, "cancel_order")

        except Exception as e:
            logger.error(f"Zerodha cancel_order error: {e}")
            return {'success': False, 'message': str(e)}

    def get_order_status(self, order_id: str) -> Dict:
        """Get status of a specific order"""
        orders = self.get_orders()
        for order in orders:
            if order.get('order_id') == order_id:
                return order
        return {}

    def get_orders(self) -> List[Dict]:
        """Get all orders for the day"""
        try:
            url = f"{self.BASE_URL}/orders"
            response = self._session.get(url, headers=self._get_headers())
            result = response.json()

            if result.get('status') == 'success':
                return result.get('data', [])
            return []

        except Exception as e:
            logger.error(f"Zerodha get_orders error: {e}")
            return []

    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        try:
            url = f"{self.BASE_URL}/portfolio/positions"
            response = self._session.get(url, headers=self._get_headers())
            result = response.json()

            if result.get('status') == 'success':
                data = result.get('data', {})
                # Combine day and net positions
                positions = data.get('day', []) + data.get('net', [])
                return positions
            return []

        except Exception as e:
            logger.error(f"Zerodha get_positions error: {e}")
            return []

    def get_holdings(self) -> List[Dict]:
        """Get holdings (delivery stocks)"""
        try:
            url = f"{self.BASE_URL}/portfolio/holdings"
            response = self._session.get(url, headers=self._get_headers())
            result = response.json()

            if result.get('status') == 'success':
                return result.get('data', [])
            return []

        except Exception as e:
            logger.error(f"Zerodha get_holdings error: {e}")
            return []

    def get_funds(self) -> Dict:
        """Get available funds/margins"""
        try:
            url = f"{self.BASE_URL}/user/margins"
            response = self._session.get(url, headers=self._get_headers())
            result = response.json()

            if result.get('status') == 'success':
                data = result.get('data', {})
                equity = data.get('equity', {})
                return {
                    'available_cash': equity.get('available', {}).get('cash', 0),
                    'available_margin': equity.get('available', {}).get('live_balance', 0),
                    'used_margin': equity.get('utilised', {}).get('debits', 0),
                    'total_balance': equity.get('net', 0)
                }
            return {}

        except Exception as e:
            logger.error(f"Zerodha get_funds error: {e}")
            return {}

    def get_quote(self, symbol: str, exchange: str) -> Dict:
        """Get current quote for a symbol"""
        try:
            instrument = f"{exchange}:{symbol}"
            url = f"{self.BASE_URL}/quote"
            params = {"i": instrument}

            response = self._session.get(url, params=params, headers=self._get_headers())
            result = response.json()

            if result.get('status') == 'success':
                data = result.get('data', {}).get(instrument, {})
                return {
                    'symbol': symbol,
                    'exchange': exchange,
                    'ltp': data.get('last_price', 0),
                    'open': data.get('ohlc', {}).get('open', 0),
                    'high': data.get('ohlc', {}).get('high', 0),
                    'low': data.get('ohlc', {}).get('low', 0),
                    'close': data.get('ohlc', {}).get('close', 0),
                    'volume': data.get('volume', 0),
                    'change': data.get('net_change', 0),
                    'change_percent': data.get('change', 0),
                }
            return {}

        except Exception as e:
            logger.error(f"Zerodha get_quote error: {e}")
            return {}

    def get_historical_data(self, symbol: str, exchange: str,
                           interval: str, from_date: str, to_date: str) -> List[Dict]:
        """
        Get historical OHLCV data

        Note: Zerodha requires instrument_token for historical data.
        This is a simplified implementation.
        """
        try:
            # Map interval to Kite format
            interval_map = {
                "1minute": "minute",
                "5minute": "5minute",
                "15minute": "15minute",
                "30minute": "30minute",
                "60minute": "60minute",
                "day": "day",
            }
            kite_interval = interval_map.get(interval, "day")

            # Get instrument token first
            instrument_token = self._get_instrument_token(symbol, exchange)
            if not instrument_token:
                logger.warning(f"Could not find instrument token for {symbol}")
                return []

            url = f"{self.BASE_URL}/instruments/historical/{instrument_token}/{kite_interval}"
            params = {
                "from": from_date,
                "to": to_date,
            }

            response = self._session.get(url, params=params, headers=self._get_headers())
            result = response.json()

            if result.get('status') == 'success':
                candles = result.get('data', {}).get('candles', [])
                return [
                    {
                        'timestamp': c[0],
                        'open': c[1],
                        'high': c[2],
                        'low': c[3],
                        'close': c[4],
                        'volume': c[5]
                    }
                    for c in candles
                ]
            return []

        except Exception as e:
            logger.error(f"Zerodha get_historical_data error: {e}")
            return []

    def _get_instrument_token(self, symbol: str, exchange: str) -> Optional[int]:
        """Get instrument token for a symbol"""
        try:
            url = f"{self.BASE_URL}/instruments/{exchange}"
            response = self._session.get(url, headers=self._get_headers())

            if response.status_code == 200:
                # Parse CSV response
                lines = response.text.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    parts = line.split(',')
                    if len(parts) > 2 and parts[2] == symbol:
                        return int(parts[0])
            return None

        except Exception as e:
            logger.error(f"Error getting instrument token: {e}")
            return None

    def get_option_chain(self, symbol: str, expiry: str = None) -> List[Dict]:
        """Get option chain for index/stock"""
        try:
            # NFO instruments for options
            url = f"{self.BASE_URL}/instruments/NFO"
            response = self._session.get(url, headers=self._get_headers())

            if response.status_code != 200:
                return []

            options = []
            lines = response.text.strip().split('\n')

            for line in lines[1:]:
                parts = line.split(',')
                if len(parts) > 10:
                    tradingsymbol = parts[2]
                    if symbol in tradingsymbol:
                        option_data = {
                            'instrument_token': parts[0],
                            'tradingsymbol': tradingsymbol,
                            'strike': float(parts[6]) if parts[6] else 0,
                            'expiry': parts[5],
                            'instrument_type': parts[9],
                        }
                        if expiry is None or parts[5] == expiry:
                            options.append(option_data)

            return options

        except Exception as e:
            logger.error(f"Zerodha get_option_chain error: {e}")
            return []
