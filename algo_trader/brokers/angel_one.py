"""
Angel One (SmartAPI) Broker Integration
"""
import requests
import hashlib
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger

try:
    import pyotp
    PYOTP_AVAILABLE = True
except ImportError:
    PYOTP_AVAILABLE = False
    pyotp = None

from algo_trader.brokers.base import BaseBroker, BrokerOrder


class AngelOneBroker(BaseBroker):
    """
    Angel One SmartAPI Integration

    Requires:
    - API Key from SmartAPI developer portal
    - Client ID (User ID)
    - Password
    - TOTP Secret (for 2FA)

    API Docs: https://smartapi.angelbroking.com/docs
    """

    BASE_URL = "https://apiconnect.angelbroking.com"
    LOGIN_URL = "https://smartapi.angelbroking.com/publisher-login"

    EXCHANGE_MAP = {
        "NSE": "NSE",
        "BSE": "BSE",
        "NFO": "NFO",
        "MCX": "MCX",
        "CDS": "CDS",
    }

    PRODUCT_MAP = {
        "CNC": "DELIVERY",
        "MIS": "INTRADAY",
        "NRML": "CARRYFORWARD",
        "MARGIN": "MARGIN",
    }

    ORDER_TYPE_MAP = {
        "MARKET": "MARKET",
        "LIMIT": "LIMIT",
        "SL": "STOPLOSS_LIMIT",
        "SL-M": "STOPLOSS_MARKET",
    }

    def __init__(self, api_key: str, api_secret: str = "", **kwargs):
        super().__init__(api_key, api_secret, **kwargs)
        self.broker_name = "angelone"
        self.client_id = kwargs.get('client_id', '')
        self.password = kwargs.get('password', '')
        self.totp_secret = kwargs.get('totp_secret', '')
        self.refresh_token = None
        self.feed_token = None
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": api_key
        })

    def _get_headers(self) -> Dict:
        """Get headers for authenticated requests"""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": self.api_key
        }
        return headers

    def get_login_url(self) -> str:
        """Get SmartAPI login URL"""
        return self.LOGIN_URL

    def authenticate(self, **kwargs) -> bool:
        """
        Authenticate with Angel One using credentials
        """
        client_id = kwargs.get('client_id', self.client_id)
        password = kwargs.get('password', self.password)
        totp_secret = kwargs.get('totp_secret', self.totp_secret)

        if not client_id or not password:
            logger.error("Angel One: Client ID and password required")
            return False

        try:
            url = f"{self.BASE_URL}/rest/auth/angelbroking/user/v1/loginByPassword"

            # Generate TOTP if secret is provided
            totp = ""
            if totp_secret:
                totp = pyotp.TOTP(totp_secret).now()

            data = {
                "clientcode": client_id,
                "password": password,
                "totp": totp
            }

            response = self._session.post(url, json=data)
            result = response.json()

            if result.get('status') and result.get('data'):
                self.access_token = result['data'].get('jwtToken')
                self.refresh_token = result['data'].get('refreshToken')
                self.feed_token = result['data'].get('feedToken')
                self.client_id = client_id
                self.is_authenticated = True
                logger.info(f"Angel One authenticated for client: {client_id}")
                return True
            else:
                logger.error(f"Angel One authentication failed: {result.get('message')}")
                return False

        except Exception as e:
            logger.error(f"Angel One authentication error: {e}")
            return False

    def generate_session(self, auth_code: str) -> bool:
        """
        Not typically used for Angel One - use authenticate() instead
        """
        return self.authenticate()

    def place_order(self, order: BrokerOrder) -> Dict:
        """Place an order through SmartAPI"""
        try:
            url = f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/placeOrder"

            exchange = self.EXCHANGE_MAP.get(order.exchange, order.exchange)
            product = self.PRODUCT_MAP.get(order.product, "DELIVERY")
            order_type = self.ORDER_TYPE_MAP.get(order.order_type, "MARKET")

            # Get symbol token
            symbol_token = self._get_symbol_token(order.symbol, exchange)

            data = {
                "variety": "NORMAL",
                "tradingsymbol": order.symbol,
                "symboltoken": symbol_token,
                "transactiontype": order.transaction_type,
                "exchange": exchange,
                "ordertype": order_type,
                "producttype": product,
                "duration": "DAY",
                "quantity": str(order.quantity),
            }

            if order.price and order_type in ["LIMIT", "STOPLOSS_LIMIT"]:
                data["price"] = str(order.price)
            else:
                data["price"] = "0"

            if order.trigger_price and order_type in ["STOPLOSS_LIMIT", "STOPLOSS_MARKET"]:
                data["triggerprice"] = str(order.trigger_price)
            else:
                data["triggerprice"] = "0"

            self._log_request(url, "POST")
            response = self._session.post(url, json=data, headers=self._get_headers())
            result = response.json()

            if result.get('status') and result.get('data'):
                order_id = result['data'].get('orderid')
                logger.info(f"Angel One order placed: {order_id}")
                return {
                    'success': True,
                    'order_id': order_id,
                    'broker_order_id': order_id,
                    'message': 'Order placed successfully'
                }
            else:
                return self._handle_error(result, "place_order")

        except Exception as e:
            logger.error(f"Angel One place_order error: {e}")
            return {'success': False, 'message': str(e)}

    def modify_order(self, order_id: str, **kwargs) -> Dict:
        """Modify an existing order"""
        try:
            url = f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/modifyOrder"

            data = {
                "variety": "NORMAL",
                "orderid": order_id,
            }

            if 'quantity' in kwargs:
                data['quantity'] = str(kwargs['quantity'])
            if 'price' in kwargs:
                data['price'] = str(kwargs['price'])
            if 'trigger_price' in kwargs:
                data['triggerprice'] = str(kwargs['trigger_price'])
            if 'order_type' in kwargs:
                data['ordertype'] = self.ORDER_TYPE_MAP.get(kwargs['order_type'], kwargs['order_type'])

            response = self._session.post(url, json=data, headers=self._get_headers())
            result = response.json()

            if result.get('status'):
                return {'success': True, 'message': 'Order modified successfully'}
            else:
                return self._handle_error(result, "modify_order")

        except Exception as e:
            logger.error(f"Angel One modify_order error: {e}")
            return {'success': False, 'message': str(e)}

    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        try:
            url = f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/cancelOrder"

            data = {
                "variety": "NORMAL",
                "orderid": order_id
            }

            response = self._session.post(url, json=data, headers=self._get_headers())
            result = response.json()

            if result.get('status'):
                logger.info(f"Angel One order cancelled: {order_id}")
                return {'success': True, 'message': 'Order cancelled successfully'}
            else:
                return self._handle_error(result, "cancel_order")

        except Exception as e:
            logger.error(f"Angel One cancel_order error: {e}")
            return {'success': False, 'message': str(e)}

    def get_order_status(self, order_id: str) -> Dict:
        """Get status of a specific order"""
        orders = self.get_orders()
        for order in orders:
            if order.get('orderid') == order_id:
                return order
        return {}

    def get_orders(self) -> List[Dict]:
        """Get all orders for the day"""
        try:
            url = f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/getOrderBook"

            response = self._session.get(url, headers=self._get_headers())
            result = response.json()

            if result.get('status') and result.get('data'):
                return result.get('data', [])
            return []

        except Exception as e:
            logger.error(f"Angel One get_orders error: {e}")
            return []

    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        try:
            url = f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/getPosition"

            response = self._session.get(url, headers=self._get_headers())
            result = response.json()

            if result.get('status') and result.get('data'):
                return result.get('data', [])
            return []

        except Exception as e:
            logger.error(f"Angel One get_positions error: {e}")
            return []

    def get_holdings(self) -> List[Dict]:
        """Get holdings (delivery stocks)"""
        try:
            url = f"{self.BASE_URL}/rest/secure/angelbroking/portfolio/v1/getHolding"

            response = self._session.get(url, headers=self._get_headers())
            result = response.json()

            if result.get('status') and result.get('data'):
                return result.get('data', [])
            return []

        except Exception as e:
            logger.error(f"Angel One get_holdings error: {e}")
            return []

    def get_funds(self) -> Dict:
        """Get available funds/margins"""
        try:
            url = f"{self.BASE_URL}/rest/secure/angelbroking/user/v1/getRMS"

            response = self._session.get(url, headers=self._get_headers())
            result = response.json()

            if result.get('status') and result.get('data'):
                data = result['data']
                return {
                    'available_cash': float(data.get('availablecash', 0)),
                    'available_margin': float(data.get('availableintradaypayin', 0)),
                    'used_margin': float(data.get('utiliseddebits', 0)),
                    'total_balance': float(data.get('net', 0))
                }
            return {}

        except Exception as e:
            logger.error(f"Angel One get_funds error: {e}")
            return {}

    def get_quote(self, symbol: str, exchange: str) -> Dict:
        """Get current quote for a symbol"""
        try:
            url = f"{self.BASE_URL}/rest/secure/angelbroking/market/v1/quote"

            exchange_mapped = self.EXCHANGE_MAP.get(exchange, exchange)
            symbol_token = self._get_symbol_token(symbol, exchange_mapped)

            data = {
                "mode": "FULL",
                "exchangeTokens": {
                    exchange_mapped: [symbol_token]
                }
            }

            response = self._session.post(url, json=data, headers=self._get_headers())
            result = response.json()

            if result.get('status') and result.get('data'):
                fetched = result['data'].get('fetched', [])
                if fetched:
                    quote = fetched[0]
                    return {
                        'symbol': symbol,
                        'exchange': exchange,
                        'ltp': float(quote.get('ltp', 0)),
                        'open': float(quote.get('open', 0)),
                        'high': float(quote.get('high', 0)),
                        'low': float(quote.get('low', 0)),
                        'close': float(quote.get('close', 0)),
                        'volume': int(quote.get('tradeVolume', 0)),
                        'change': float(quote.get('netChange', 0)),
                        'change_percent': float(quote.get('percentChange', 0)),
                    }
            return {}

        except Exception as e:
            logger.error(f"Angel One get_quote error: {e}")
            return {}

    def get_historical_data(self, symbol: str, exchange: str,
                           interval: str, from_date: str, to_date: str) -> List[Dict]:
        """
        Get historical OHLCV data
        """
        try:
            url = f"{self.BASE_URL}/rest/secure/angelbroking/historical/v1/getCandleData"

            # Map interval to Angel One format
            interval_map = {
                "1minute": "ONE_MINUTE",
                "5minute": "FIVE_MINUTE",
                "15minute": "FIFTEEN_MINUTE",
                "30minute": "THIRTY_MINUTE",
                "60minute": "ONE_HOUR",
                "day": "ONE_DAY",
            }
            angel_interval = interval_map.get(interval, "ONE_DAY")

            exchange_mapped = self.EXCHANGE_MAP.get(exchange, exchange)
            symbol_token = self._get_symbol_token(symbol, exchange_mapped)

            data = {
                "exchange": exchange_mapped,
                "symboltoken": symbol_token,
                "interval": angel_interval,
                "fromdate": from_date + " 09:15",
                "todate": to_date + " 15:30"
            }

            response = self._session.post(url, json=data, headers=self._get_headers())
            result = response.json()

            if result.get('status') and result.get('data'):
                candles = result['data']
                return [
                    {
                        'timestamp': c[0],
                        'open': float(c[1]),
                        'high': float(c[2]),
                        'low': float(c[3]),
                        'close': float(c[4]),
                        'volume': int(c[5])
                    }
                    for c in candles
                ]
            return []

        except Exception as e:
            logger.error(f"Angel One get_historical_data error: {e}")
            return []

    def _get_symbol_token(self, symbol: str, exchange: str) -> str:
        """Get symbol token for a trading symbol"""
        # This would typically query a master contract file
        # For now, return a placeholder - in production, maintain a symbol-token map
        try:
            url = f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/searchScrip"
            data = {
                "exchange": exchange,
                "searchscrip": symbol
            }

            response = self._session.post(url, json=data, headers=self._get_headers())
            result = response.json()

            if result.get('status') and result.get('data'):
                for item in result['data']:
                    if item.get('tradingsymbol') == symbol:
                        return item.get('symboltoken', '')
            return ""

        except Exception as e:
            logger.error(f"Error getting symbol token: {e}")
            return ""

    def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token"""
        try:
            if not self.refresh_token:
                logger.error("No refresh token available")
                return False

            url = f"{self.BASE_URL}/rest/auth/angelbroking/jwt/v1/generateTokens"
            data = {
                "refreshToken": self.refresh_token
            }

            response = self._session.post(url, json=data, headers=self._get_headers())
            result = response.json()

            if result.get('status') and result.get('data'):
                self.access_token = result['data'].get('jwtToken')
                self.refresh_token = result['data'].get('refreshToken')
                self.feed_token = result['data'].get('feedToken')
                logger.info("Angel One token refreshed")
                return True
            return False

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False

    def logout(self) -> bool:
        """Logout and invalidate tokens"""
        try:
            url = f"{self.BASE_URL}/rest/secure/angelbroking/user/v1/logout"
            data = {"clientcode": self.client_id}

            response = self._session.post(url, json=data, headers=self._get_headers())
            result = response.json()

            if result.get('status'):
                self.access_token = None
                self.refresh_token = None
                self.is_authenticated = False
                logger.info("Angel One logged out")
                return True
            return False

        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False
