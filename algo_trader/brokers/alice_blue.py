"""
Alice Blue Broker Integration
API Documentation: https://ant.aliceblueonline.com/
"""
import requests
import hashlib
import json
from typing import Dict, List, Optional
from urllib.parse import urlencode
from datetime import datetime
from loguru import logger

from .base import BaseBroker, BrokerOrder


class AliceBlueBroker(BaseBroker):
    """
    Alice Blue ANT API Integration
    Updated for v2 API
    """

    BASE_URL = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api"
    AUTH_URL = "https://ant.aliceblueonline.com"
    SESSION_URL = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api/customer/getUserDetails"

    def __init__(self, api_key: str, api_secret: str, user_id: str = None,
                 redirect_uri: str = "http://127.0.0.1:5000/callback"):
        super().__init__(api_key, api_secret)
        self.broker_name = "alice_blue"
        self.user_id = user_id
        self.redirect_uri = redirect_uri
        self.session_id = None

    def get_login_url(self) -> str:
        """Get Alice Blue OAuth login URL"""
        # New format: https://ant.aliceblueonline.com/?appcode=YOUR_API_KEY
        return f"{self.AUTH_URL}/?appcode={self.api_key}"

    def authenticate(self, access_token: str = None, session_id: str = None, **kwargs) -> bool:
        """Authenticate using existing access token or session"""
        if access_token:
            self.access_token = access_token
            self.is_authenticated = True
            return True
        if session_id:
            self.session_id = session_id
            self.is_authenticated = True
            return True
        return False

    def generate_session(self, auth_code: str) -> bool:
        """Generate session using authorization code"""
        try:
            # Alice Blue uses SHA-256 hash for authentication
            checksum = hashlib.sha256(
                (self.user_id + self.api_key + auth_code).encode()
            ).hexdigest()

            payload = {
                'userId': self.user_id,
                'userData': auth_code,
                'source': 'API',
                'checkSum': checksum
            }

            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            response = requests.post(
                f"{self.BASE_URL}/customer/getUserDetails",
                json=payload,
                headers=headers
            )
            data = response.json()

            if response.status_code == 200 and data.get('stat') == 'Ok':
                self.session_id = data.get('sessionId')
                self.access_token = data.get('sessionId')
                self.is_authenticated = True
                logger.info("Alice Blue authentication successful")
                return True
            else:
                logger.error(f"Alice Blue auth failed: {data}")
                return False

        except Exception as e:
            logger.error(f"Alice Blue auth error: {e}")
            return False

    def _get_headers(self) -> Dict:
        """Get headers for authenticated requests"""
        return {
            'Authorization': f'Bearer {self.user_id} {self.session_id}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make authenticated API request"""
        if not self.is_authenticated:
            return {'success': False, 'message': 'Not authenticated'}

        url = f"{self.BASE_URL}{endpoint}"
        self._log_request(endpoint, method)

        try:
            if method == "GET":
                response = requests.get(url, headers=self._get_headers(), params=data)
            elif method == "POST":
                response = requests.post(url, headers=self._get_headers(), json=data)
            else:
                return {'success': False, 'message': f'Unknown method: {method}'}

            result = response.json()

            if response.status_code == 200:
                if result.get('stat') == 'Ok' or result.get('status') == 'success':
                    result['success'] = True
                else:
                    result['success'] = False
                return result
            else:
                return self._handle_error(result, endpoint)

        except Exception as e:
            logger.error(f"Alice Blue API error: {e}")
            return {'success': False, 'message': str(e)}

    def _get_exchange_code(self, exchange: str) -> str:
        """Get Alice Blue exchange code"""
        exchange_map = {
            'NSE': 'NSE',
            'BSE': 'BSE',
            'NFO': 'NFO',
            'MCX': 'MCX',
            'CDS': 'CDS'
        }
        return exchange_map.get(exchange, 'NSE')

    def place_order(self, order) -> Dict:
        """Place an order on Alice Blue"""
        # Handle both BrokerOrder and Order objects
        if hasattr(order, 'symbol'):
            symbol = order.symbol
            exchange = order.exchange.value if hasattr(order.exchange, 'value') else order.exchange
            transaction_type = order.transaction_type.value if hasattr(order.transaction_type, 'value') else order.transaction_type
            order_type = order.order_type.value if hasattr(order.order_type, 'value') else order.order_type
            quantity = order.quantity
            price = order.price
            trigger_price = getattr(order, 'trigger_price', None)
            product = getattr(order, 'product', 'CNC')
        else:
            return {'success': False, 'message': 'Invalid order format'}

        # Map order types
        order_type_map = {
            'MARKET': 'MKT',
            'LIMIT': 'L',
            'SL': 'SL',
            'SL-M': 'SL-M'
        }

        # Map product types
        product_map = {
            'CNC': 'CNC',
            'MIS': 'MIS',
            'NRML': 'NRML'
        }

        # Map transaction type
        trans_map = {
            'BUY': 'B',
            'SELL': 'S'
        }

        payload = {
            'exchange': self._get_exchange_code(exchange),
            'order_type': order_type_map.get(order_type, 'MKT'),
            'instrument_token': self._get_instrument_token(symbol, exchange),
            'quantity': quantity,
            'disclosed_quantity': 0,
            'price': price or 0,
            'trigger_price': trigger_price or 0,
            'validity': 'DAY',
            'product': product_map.get(product, 'CNC'),
            'trading_symbol': symbol,
            'transaction_type': trans_map.get(transaction_type, 'B'),
            'order_tag': 'AlgoTrader'
        }

        result = self._make_request("POST", "/placeOrder/executePlaceOrder", payload)

        if result.get('success') and result.get('NOrdNo'):
            return {
                'success': True,
                'order_id': result['NOrdNo'],
                'message': 'Order placed successfully'
            }
        return result

    def _get_instrument_token(self, symbol: str, exchange: str) -> int:
        """Get instrument token for a symbol (placeholder - needs master data)"""
        # In production, this should look up from master contract file
        # For now, return placeholder
        return 0

    def modify_order(self, order_id: str, quantity: int = None, price: float = None,
                    order_type: str = None, trigger_price: float = None) -> Dict:
        """Modify an existing order"""
        payload = {
            'nestOrderNumber': order_id,
            'exch': 'NSE'
        }

        if quantity:
            payload['qty'] = quantity
        if price:
            payload['prc'] = price
        if order_type:
            payload['prctyp'] = order_type
        if trigger_price:
            payload['trgprc'] = trigger_price

        return self._make_request("POST", "/placeOrder/modifyOrder", payload)

    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        payload = {
            'nestOrderNumber': order_id,
            'exch': 'NSE'
        }

        result = self._make_request("POST", "/placeOrder/cancelOrder", payload)
        if result.get('success'):
            return {'success': True, 'message': 'Order cancelled'}
        return result

    def get_order_status(self, order_id: str) -> Dict:
        """Get status of a specific order"""
        orders = self.get_orders()
        for order in orders:
            if order.get('Nstordno') == order_id:
                return order
        return {}

    def get_orders(self) -> List[Dict]:
        """Get all orders for the day"""
        result = self._make_request("GET", "/placeOrder/fetchOrderBook")
        if result.get('success'):
            return result.get('data', []) or result.get('orderBook', [])
        return []

    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        result = self._make_request("GET", "/positionAndHoldings/positionBook")
        if result.get('success'):
            return result.get('data', []) or result.get('positionBook', [])
        return []

    def get_holdings(self) -> List[Dict]:
        """Get holdings"""
        result = self._make_request("GET", "/positionAndHoldings/holdings")
        if result.get('success'):
            return result.get('data', []) or result.get('holdingValue', [])
        return []

    def get_funds(self) -> Dict:
        """Get available funds"""
        result = self._make_request("GET", "/limits/getRmsLimits")
        if result.get('success'):
            return result
        return {}

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Dict:
        """Get current quote for a symbol"""
        payload = {
            'exchange': self._get_exchange_code(exchange),
            'token': self._get_instrument_token(symbol, exchange)
        }
        result = self._make_request("POST", "/marketWatch/fetchLTPData", payload)
        if result.get('success'):
            return result
        return {}

    def get_historical_data(self, symbol: str, exchange: str = "NSE",
                           interval: str = "day", from_date: str = None,
                           to_date: str = None) -> List[Dict]:
        """
        Get historical OHLCV data
        Note: Alice Blue has limited historical data API
        """
        # Alice Blue's historical data API requires specific subscription
        # This is a placeholder implementation
        payload = {
            'exchange': self._get_exchange_code(exchange),
            'token': self._get_instrument_token(symbol, exchange),
            'resolution': interval,
            'from': from_date,
            'to': to_date
        }

        result = self._make_request("POST", "/chart/history", payload)

        if result.get('success') and result.get('data'):
            candles = result['data']
            formatted = []
            for c in candles:
                formatted.append({
                    'timestamp': c.get('time'),
                    'open': c.get('open'),
                    'high': c.get('high'),
                    'low': c.get('low'),
                    'close': c.get('close'),
                    'volume': c.get('volume')
                })
            return formatted
        return []

    def get_profile(self) -> Dict:
        """Get user profile"""
        result = self._make_request("GET", "/customer/accountDetails")
        if result.get('success'):
            return result
        return {}

    def download_master_contract(self, exchange: str = "NSE") -> List[Dict]:
        """Download master contract file for symbol lookup"""
        try:
            url = f"https://v2api.aliceblueonline.com/restpy/static/{exchange.upper()}_symbols.json"
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Failed to download master contract: {e}")
        return []

    def get_option_ltp(self, symbol: str, strike: int, opt_type: str, expiry: str = None) -> float:
        """
        Get LTP for an option contract from AliceBlue
        symbol: NIFTY, BANKNIFTY, SENSEX, etc.
        strike: Strike price (e.g., 25200)
        opt_type: CE or PE
        """
        try:
            # Determine exchange
            if symbol.upper() in ['SENSEX', 'BANKEX']:
                exchange = 'BFO'  # BSE F&O
            else:
                exchange = 'NFO'  # NSE F&O

            # Build trading symbol
            # AliceBlue format: NIFTY24FEB25200CE
            from datetime import datetime, timedelta

            # Get nearest expiry (weekly for NIFTY/BANKNIFTY, monthly for others)
            now = datetime.now()

            # Find next Thursday for weekly expiry
            days_until_thursday = (3 - now.weekday()) % 7
            if days_until_thursday == 0 and now.hour >= 15:
                days_until_thursday = 7
            next_expiry = now + timedelta(days=days_until_thursday)

            # Format expiry
            expiry_str = next_expiry.strftime('%d%b%y').upper()  # e.g., 06FEB26

            # Build trading symbol
            trading_symbol = f"{symbol.upper()}{expiry_str}{int(strike)}{opt_type.upper()}"

            # Get market data
            payload = {
                'exchange': exchange,
                'tradingSymbol': trading_symbol
            }

            result = self._make_request("POST", "/marketWatch/fetchData/scripDetails", payload)

            if result.get('success') and result.get('data'):
                ltp = result['data'].get('ltp', 0)
                if ltp and float(ltp) > 0:
                    return float(ltp)

            # Try with month format (for monthly expiry)
            expiry_month = now.strftime('%b%y').upper()  # e.g., FEB26
            trading_symbol2 = f"{symbol.upper()}{expiry_month}{int(strike)}{opt_type.upper()}"

            payload['tradingSymbol'] = trading_symbol2
            result = self._make_request("POST", "/marketWatch/fetchData/scripDetails", payload)

            if result.get('success') and result.get('data'):
                ltp = result['data'].get('ltp', 0)
                if ltp and float(ltp) > 0:
                    return float(ltp)

            logger.debug(f"Could not fetch option LTP for {symbol} {strike} {opt_type}")
            return 0

        except Exception as e:
            logger.error(f"Error fetching option LTP from AliceBlue: {e}")
            return 0

    def get_ltp(self, symbol: str, exchange: str = "NSE") -> float:
        """Get LTP for any instrument"""
        try:
            payload = {
                'exchange': exchange,
                'tradingSymbol': symbol
            }
            result = self._make_request("POST", "/marketWatch/fetchData/scripDetails", payload)

            if result.get('success') and result.get('data'):
                return float(result['data'].get('ltp', 0))
            return 0
        except Exception as e:
            logger.error(f"Error getting LTP: {e}")
            return 0
