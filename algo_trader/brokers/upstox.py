"""
Upstox Broker Integration
API Documentation: https://upstox.com/developer/api-documentation/
"""
import requests
import json
import ssl
import asyncio
import threading
from typing import Dict, List, Optional, Callable
from urllib.parse import urlencode
from datetime import datetime, timedelta
from loguru import logger

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets package not installed - WebSocket features disabled")

from .base import BaseBroker, BrokerOrder


class UpstoxWebSocketManager:
    """
    WebSocket manager for real-time market data from Upstox
    """

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.websocket = None
        self.is_connected = False
        self.ltp_cache: Dict[str, float] = {}  # instrument_key -> LTP
        self._loop = None
        self._thread = None
        self._subscribed_instruments: List[str] = []
        self._callbacks: List[Callable] = []

    def get_websocket_url(self) -> Optional[str]:
        """Get authorized WebSocket URL from Upstox API"""
        try:
            url = "https://api.upstox.com/v2/feed/market-data-feed/authorize"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json'
            }
            response = requests.get(url, headers=headers)
            data = response.json()

            if response.status_code == 200 and data.get('status') == 'success':
                ws_url = data.get('data', {}).get('authorizedRedirectUri')
                logger.info(f"Got WebSocket URL: {ws_url[:50]}...")
                return ws_url
            else:
                logger.error(f"Failed to get WebSocket URL: {data}")
                return None
        except Exception as e:
            logger.error(f"Error getting WebSocket URL: {e}")
            return None

    async def _connect_and_listen(self, ws_url: str):
        """Connect to WebSocket and listen for messages"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            async with websockets.connect(ws_url, ssl=ssl_context) as websocket:
                self.websocket = websocket
                self.is_connected = True
                logger.info("Upstox WebSocket connected")

                # Subscribe to instruments if any
                if self._subscribed_instruments:
                    await self._subscribe_instruments(self._subscribed_instruments)

                # Listen for messages
                while self.is_connected:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30)
                        self._handle_message(message)
                    except asyncio.TimeoutError:
                        # Send ping to keep connection alive
                        pass
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("WebSocket connection closed")
                        self.is_connected = False
                        break

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.is_connected = False

    async def _subscribe_instruments(self, instrument_keys: List[str]):
        """Subscribe to instrument updates"""
        if not self.websocket or not self.is_connected:
            return

        data = {
            "guid": "algotrader_sub",
            "method": "sub",
            "data": {
                "mode": "ltpc",  # LTP + Close price mode
                "instrumentKeys": instrument_keys
            }
        }

        binary_data = json.dumps(data).encode('utf-8')
        await self.websocket.send(binary_data)
        logger.info(f"Subscribed to {len(instrument_keys)} instruments")

    def _handle_message(self, message):
        """Handle incoming WebSocket message"""
        try:
            # Try to decode as JSON first (some messages may not be protobuf)
            if isinstance(message, bytes):
                try:
                    data = json.loads(message.decode('utf-8'))
                except:
                    # If not JSON, try to parse as simple format
                    # Upstox may send protobuf, but we'll try JSON first
                    logger.debug(f"Received binary message, length={len(message)}")
                    return
            else:
                data = json.loads(message)

            # Extract LTP from the message
            if 'feeds' in data:
                for key, feed_data in data['feeds'].items():
                    if 'ff' in feed_data and 'ltpc' in feed_data['ff']:
                        ltpc = feed_data['ff']['ltpc']
                        ltp = ltpc.get('ltp', 0)
                        if ltp > 0:
                            self.ltp_cache[key] = ltp
                            logger.debug(f"WebSocket LTP update: {key} = {ltp}")

                            # Call registered callbacks
                            for callback in self._callbacks:
                                try:
                                    callback(key, ltp)
                                except Exception as e:
                                    logger.error(f"Callback error: {e}")

        except Exception as e:
            logger.debug(f"Message parse error: {e}")

    def start(self):
        """Start WebSocket connection in background thread"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets package not installed")
            return False

        ws_url = self.get_websocket_url()
        if not ws_url:
            return False

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._connect_and_listen(ws_url))

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

        # Wait for connection
        for _ in range(50):  # Wait up to 5 seconds
            if self.is_connected:
                return True
            import time
            time.sleep(0.1)

        return self.is_connected

    def stop(self):
        """Stop WebSocket connection"""
        self.is_connected = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def subscribe(self, instrument_keys: List[str]):
        """Subscribe to instruments"""
        self._subscribed_instruments.extend(instrument_keys)

        if self.is_connected and self._loop:
            future = asyncio.run_coroutine_threadsafe(
                self._subscribe_instruments(instrument_keys),
                self._loop
            )
            try:
                future.result(timeout=5)
            except Exception as e:
                logger.error(f"Subscribe error: {e}")

    def get_ltp(self, instrument_key: str) -> float:
        """Get cached LTP for an instrument"""
        return self.ltp_cache.get(instrument_key, 0)

    def add_callback(self, callback: Callable):
        """Add callback for LTP updates"""
        self._callbacks.append(callback)


class UpstoxBroker(BaseBroker):
    """
    Upstox API Integration
    Supports Upstox API v2
    """

    BASE_URL = "https://api.upstox.com/v2"
    AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
    TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"

    def __init__(self, api_key: str, api_secret: str, redirect_uri: str = "http://127.0.0.1:5000/callback"):
        super().__init__(api_key, api_secret)
        self.broker_name = "upstox"
        self.redirect_uri = redirect_uri
        self.ws_manager: Optional[UpstoxWebSocketManager] = None
        self._instrument_key_cache: Dict[str, str] = {}  # Cache for option instrument keys

    def get_login_url(self) -> str:
        """Get Upstox OAuth login URL"""
        params = {
            'client_id': self.api_key,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code'
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    def authenticate(self, access_token: str = None, **kwargs) -> bool:
        """Authenticate using existing access token"""
        if access_token:
            self.access_token = access_token
            self.is_authenticated = True
            # Try to start WebSocket for real-time data
            self._start_websocket()
            return True
        return False

    def _start_websocket(self):
        """Start WebSocket connection for real-time market data"""
        if not WEBSOCKETS_AVAILABLE:
            logger.warning("WebSocket not available - using REST API for LTP")
            return

        try:
            if self.ws_manager:
                self.ws_manager.stop()

            self.ws_manager = UpstoxWebSocketManager(self.access_token)
            if self.ws_manager.start():
                logger.info("Upstox WebSocket started successfully")
            else:
                logger.warning("Failed to start WebSocket - using REST API for LTP")
                self.ws_manager = None
        except Exception as e:
            logger.error(f"Error starting WebSocket: {e}")
            self.ws_manager = None

    def generate_session(self, auth_code: str) -> bool:
        """Generate access token from authorization code"""
        try:
            payload = {
                'code': auth_code,
                'client_id': self.api_key,
                'client_secret': self.api_secret,
                'redirect_uri': self.redirect_uri,
                'grant_type': 'authorization_code'
            }

            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }

            response = requests.post(self.TOKEN_URL, data=payload, headers=headers)
            data = response.json()

            if response.status_code == 200 and 'access_token' in data:
                self.access_token = data['access_token']
                self.is_authenticated = True
                logger.info("Upstox authentication successful")
                return True
            else:
                logger.error(f"Upstox auth failed: {data}")
                return False

        except Exception as e:
            logger.error(f"Upstox auth error: {e}")
            return False

    def _get_headers(self) -> Dict:
        """Get headers for authenticated requests"""
        return {
            'Authorization': f'Bearer {self.access_token}',
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
            elif method == "PUT":
                response = requests.put(url, headers=self._get_headers(), json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=self._get_headers())
            else:
                return {'success': False, 'message': f'Unknown method: {method}'}

            result = response.json()
            logger.debug(f"Upstox API response for {endpoint}: status={response.status_code}, data_keys={list(result.keys()) if isinstance(result, dict) else 'not_dict'}")

            if response.status_code == 200:
                result['success'] = True
                return result
            else:
                # Extract error message from Upstox response format
                error_msg = "Unknown error"
                if result.get('errors') and isinstance(result['errors'], list):
                    error_msg = result['errors'][0].get('message', 'Unknown error')
                elif result.get('message'):
                    error_msg = result['message']

                logger.warning(f"Upstox API non-200 response: {response.status_code} - {error_msg} - Full: {result}")
                return {'success': False, 'message': error_msg}

        except Exception as e:
            logger.error(f"Upstox API error: {e}")
            return {'success': False, 'message': str(e)}

    def _format_symbol(self, symbol: str, exchange: str) -> str:
        """Format symbol for Upstox API"""
        # Upstox uses format: NSE_EQ|INE002A01018 for equity (ISIN required)
        # NSE_FO|NIFTY23JAN19500CE for F&O

        # Try to get the correct instrument key from search API
        instrument_key = self._get_instrument_key(symbol, exchange)
        if instrument_key:
            return instrument_key

        # Fallback to basic format (may not work for all)
        exchange_map = {
            'NSE': 'NSE_EQ',
            'BSE': 'BSE_EQ',
            'NFO': 'NSE_FO',
            'MCX': 'MCX_FO'
        }
        ex = exchange_map.get(exchange, 'NSE_EQ')
        return f"{ex}|{symbol}"

    def _get_instrument_key(self, symbol: str, exchange: str) -> Optional[str]:
        """Get the correct instrument key for a symbol using search API"""
        try:
            import urllib.parse

            # Use market quote search to find the instrument
            # First try to search for the symbol
            search_url = f"/market-quote/quotes?instrument_key=NSE_EQ%7C{symbol}"
            result = self._make_request("GET", search_url)

            # If direct search fails, try searching in instruments
            if not result.get('success'):
                # Try alternative: use the instrument search endpoint
                # Upstox has an instruments master file we can download
                pass

            # Check if we have the instrument in cache
            if hasattr(self, '_instrument_cache') and symbol in self._instrument_cache:
                return self._instrument_cache[symbol]

            # Try to fetch instrument details using holdings or positions
            # as these return the correct instrument keys
            holdings_result = self._make_request("GET", "/portfolio/long-term-holdings")
            if holdings_result.get('success') and holdings_result.get('data'):
                if not hasattr(self, '_instrument_cache'):
                    self._instrument_cache = {}
                for holding in holdings_result['data']:
                    trading_symbol = holding.get('trading_symbol', '')
                    inst_key = holding.get('instrument_token', '')
                    if trading_symbol:
                        self._instrument_cache[trading_symbol] = inst_key

                if symbol in self._instrument_cache:
                    return self._instrument_cache[symbol]

            # Common NSE stocks - hardcoded ISIN mapping for popular stocks
            # This is a fallback - ideally should be fetched from API
            isin_map = {
                'RELIANCE': 'NSE_EQ|INE002A01018',
                'TCS': 'NSE_EQ|INE467B01029',
                'HDFCBANK': 'NSE_EQ|INE040A01034',
                'INFY': 'NSE_EQ|INE009A01021',
                'ICICIBANK': 'NSE_EQ|INE090A01021',
                'HDFC': 'NSE_EQ|INE001A01036',
                'SBIN': 'NSE_EQ|INE062A01020',
                'BHARTIARTL': 'NSE_EQ|INE397D01024',
                'ITC': 'NSE_EQ|INE154A01025',
                'KOTAKBANK': 'NSE_EQ|INE237A01028',
                'LT': 'NSE_EQ|INE018A01030',
                'AXISBANK': 'NSE_EQ|INE238A01034',
                'ASIANPAINT': 'NSE_EQ|INE021A01026',
                'MARUTI': 'NSE_EQ|INE585B01010',
                'BAJFINANCE': 'NSE_EQ|INE296A01024',
                'WIPRO': 'NSE_EQ|INE075A01022',
                'HCLTECH': 'NSE_EQ|INE860A01027',
                'TATASTEEL': 'NSE_EQ|INE081A01012',
                'SUNPHARMA': 'NSE_EQ|INE044A01036',
                'ULTRACEMCO': 'NSE_EQ|INE481G01011',
                'TITAN': 'NSE_EQ|INE280A01028',
                'NESTLEIND': 'NSE_EQ|INE239A01016',
                'POWERGRID': 'NSE_EQ|INE752E01010',
                'NTPC': 'NSE_EQ|INE733E01010',
                'M&M': 'NSE_EQ|INE101A01026',
                'TATAMOTORS': 'NSE_EQ|INE155A01022',
                'ONGC': 'NSE_EQ|INE213A01029',
                'JSWSTEEL': 'NSE_EQ|INE019A01038',
                'COALINDIA': 'NSE_EQ|INE522F01014',
                'ADANIENT': 'NSE_EQ|INE423A01024',
                'ADANIPORTS': 'NSE_EQ|INE742F01042',
                'BAJAJFINSV': 'NSE_EQ|INE918I01018',
                'DIVISLAB': 'NSE_EQ|INE361B01024',
                'DRREDDY': 'NSE_EQ|INE089A01023',
                'EICHERMOT': 'NSE_EQ|INE066A01013',
                'GRASIM': 'NSE_EQ|INE047A01021',
                'HINDALCO': 'NSE_EQ|INE038A01020',
                'HINDUNILVR': 'NSE_EQ|INE030A01027',
                'INDUSINDBK': 'NSE_EQ|INE095A01012',
                'TECHM': 'NSE_EQ|INE669C01036',
                'BRITANNIA': 'NSE_EQ|INE216A01022',
                'CIPLA': 'NSE_EQ|INE059A01026',
                'APOLLOHOSP': 'NSE_EQ|INE437A01024',
                'BPCL': 'NSE_EQ|INE029A01011',
                'HEROMOTOCO': 'NSE_EQ|INE158A01026',
                'TATACONSUM': 'NSE_EQ|INE192A01025',
                'UPL': 'NSE_EQ|INE628A01036',
                'SBILIFE': 'NSE_EQ|INE123W01016',
                'BSE': 'NSE_EQ|INE118H01025',
            }

            sym_upper = symbol.upper()
            if sym_upper in isin_map:
                logger.info(f"Using hardcoded ISIN for {sym_upper}: {isin_map[sym_upper]}")
                return isin_map[sym_upper]

            return None

        except Exception as e:
            logger.error(f"Error getting instrument key: {e}")
            return None

    def search_instruments(self, query: str, exchange: str = "NSE") -> List[Dict]:
        """
        Search for instruments matching the query
        Returns list of matching instruments with symbol, name, instrument_key
        """
        try:
            # Upstox doesn't have a direct search API, so we use a hardcoded list
            # In production, this should download and cache the instruments master file

            # Common NSE stocks with their details
            all_instruments = [
                {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE002A01018"},
                {"symbol": "TCS", "name": "Tata Consultancy Services", "exchange": "NSE", "instrument_key": "NSE_EQ|INE467B01029"},
                {"symbol": "HDFCBANK", "name": "HDFC Bank Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE040A01034"},
                {"symbol": "INFY", "name": "Infosys Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE009A01021"},
                {"symbol": "ICICIBANK", "name": "ICICI Bank Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE090A01021"},
                {"symbol": "SBIN", "name": "State Bank of India", "exchange": "NSE", "instrument_key": "NSE_EQ|INE062A01020"},
                {"symbol": "BHARTIARTL", "name": "Bharti Airtel Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE397D01024"},
                {"symbol": "ITC", "name": "ITC Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE154A01025"},
                {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank", "exchange": "NSE", "instrument_key": "NSE_EQ|INE237A01028"},
                {"symbol": "LT", "name": "Larsen & Toubro Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE018A01030"},
                {"symbol": "AXISBANK", "name": "Axis Bank Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE238A01034"},
                {"symbol": "ASIANPAINT", "name": "Asian Paints Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE021A01026"},
                {"symbol": "MARUTI", "name": "Maruti Suzuki India", "exchange": "NSE", "instrument_key": "NSE_EQ|INE585B01010"},
                {"symbol": "BAJFINANCE", "name": "Bajaj Finance Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE296A01024"},
                {"symbol": "WIPRO", "name": "Wipro Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE075A01022"},
                {"symbol": "HCLTECH", "name": "HCL Technologies Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE860A01027"},
                {"symbol": "TATASTEEL", "name": "Tata Steel Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE081A01012"},
                {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical", "exchange": "NSE", "instrument_key": "NSE_EQ|INE044A01036"},
                {"symbol": "ULTRACEMCO", "name": "UltraTech Cement Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE481G01011"},
                {"symbol": "TITAN", "name": "Titan Company Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE280A01028"},
                {"symbol": "NESTLEIND", "name": "Nestle India Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE239A01016"},
                {"symbol": "POWERGRID", "name": "Power Grid Corp", "exchange": "NSE", "instrument_key": "NSE_EQ|INE752E01010"},
                {"symbol": "NTPC", "name": "NTPC Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE733E01010"},
                {"symbol": "M&M", "name": "Mahindra & Mahindra", "exchange": "NSE", "instrument_key": "NSE_EQ|INE101A01026"},
                {"symbol": "TATAMOTORS", "name": "Tata Motors Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE155A01022"},
                {"symbol": "ONGC", "name": "Oil & Natural Gas Corp", "exchange": "NSE", "instrument_key": "NSE_EQ|INE213A01029"},
                {"symbol": "JSWSTEEL", "name": "JSW Steel Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE019A01038"},
                {"symbol": "COALINDIA", "name": "Coal India Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE522F01014"},
                {"symbol": "ADANIENT", "name": "Adani Enterprises", "exchange": "NSE", "instrument_key": "NSE_EQ|INE423A01024"},
                {"symbol": "ADANIPORTS", "name": "Adani Ports & SEZ", "exchange": "NSE", "instrument_key": "NSE_EQ|INE742F01042"},
                {"symbol": "BAJAJFINSV", "name": "Bajaj Finserv Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE918I01018"},
                {"symbol": "DIVISLAB", "name": "Divi's Laboratories", "exchange": "NSE", "instrument_key": "NSE_EQ|INE361B01024"},
                {"symbol": "DRREDDY", "name": "Dr. Reddy's Labs", "exchange": "NSE", "instrument_key": "NSE_EQ|INE089A01023"},
                {"symbol": "EICHERMOT", "name": "Eicher Motors Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE066A01013"},
                {"symbol": "GRASIM", "name": "Grasim Industries", "exchange": "NSE", "instrument_key": "NSE_EQ|INE047A01021"},
                {"symbol": "HINDALCO", "name": "Hindalco Industries", "exchange": "NSE", "instrument_key": "NSE_EQ|INE038A01020"},
                {"symbol": "HINDUNILVR", "name": "Hindustan Unilever", "exchange": "NSE", "instrument_key": "NSE_EQ|INE030A01027"},
                {"symbol": "INDUSINDBK", "name": "IndusInd Bank Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE095A01012"},
                {"symbol": "TECHM", "name": "Tech Mahindra Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE669C01036"},
                {"symbol": "BRITANNIA", "name": "Britannia Industries", "exchange": "NSE", "instrument_key": "NSE_EQ|INE216A01022"},
                {"symbol": "CIPLA", "name": "Cipla Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE059A01026"},
                {"symbol": "APOLLOHOSP", "name": "Apollo Hospitals", "exchange": "NSE", "instrument_key": "NSE_EQ|INE437A01024"},
                {"symbol": "BPCL", "name": "Bharat Petroleum", "exchange": "NSE", "instrument_key": "NSE_EQ|INE029A01011"},
                {"symbol": "HEROMOTOCO", "name": "Hero MotoCorp Ltd", "exchange": "NSE", "instrument_key": "NSE_EQ|INE158A01026"},
                {"symbol": "TATACONSUM", "name": "Tata Consumer Products", "exchange": "NSE", "instrument_key": "NSE_EQ|INE192A01025"},
                {"symbol": "SBILIFE", "name": "SBI Life Insurance", "exchange": "NSE", "instrument_key": "NSE_EQ|INE123W01016"},
                {"symbol": "MOUPHARM", "name": "Morepen Laboratories", "exchange": "NSE", "instrument_key": "NSE_EQ|INE083A01026"},
                {"symbol": "MOREPENLAB", "name": "Morepen Laboratories", "exchange": "NSE", "instrument_key": "NSE_EQ|INE083A01026"},
            ]

            # Filter by query (case-insensitive, match start or contains)
            query_upper = query.upper()
            results = []
            for inst in all_instruments:
                if query_upper in inst["symbol"] or query_upper in inst["name"].upper():
                    results.append({
                        "trading_symbol": inst["symbol"],
                        "symbol": inst["symbol"],
                        "name": inst["name"],
                        "exchange": inst["exchange"],
                        "instrument_key": inst["instrument_key"]
                    })

            return results[:20]  # Limit to 20 results

        except Exception as e:
            logger.error(f"Error searching instruments: {e}")
            return []

    def place_order(self, order) -> Dict:
        """Place an order on Upstox"""
        # Handle both BrokerOrder and Order objects
        if hasattr(order, 'symbol'):
            symbol = order.symbol
            exchange = order.exchange.value if hasattr(order.exchange, 'value') else order.exchange
            transaction_type = order.transaction_type.value if hasattr(order.transaction_type, 'value') else order.transaction_type
            order_type = order.order_type.value if hasattr(order.order_type, 'value') else order.order_type
            quantity = order.quantity
            price = order.price
            trigger_price = getattr(order, 'trigger_price', None)
            product = getattr(order, 'product', 'D')
        else:
            return {'success': False, 'message': 'Invalid order format'}

        # Map order types
        order_type_map = {
            'MARKET': 'MARKET',
            'LIMIT': 'LIMIT',
            'SL': 'SL',
            'SL-M': 'SL-M'
        }

        # Map product types
        product_map = {
            'CNC': 'D',  # Delivery
            'MIS': 'I',  # Intraday
            'NRML': 'D'
        }

        payload = {
            'instrument_token': self._format_symbol(symbol, exchange),
            'quantity': quantity,
            'product': product_map.get(product, 'D'),
            'validity': 'DAY',
            'price': price or 0,
            'trigger_price': trigger_price or 0,
            'order_type': order_type_map.get(order_type, 'MARKET'),
            'transaction_type': transaction_type,
            'disclosed_quantity': 0,
            'is_amo': False
        }

        logger.info(f"Upstox place_order payload: {payload}")
        result = self._make_request("POST", "/order/place", payload)
        logger.info(f"Upstox place_order result: {result}")

        if result.get('success') and result.get('data'):
            return {
                'success': True,
                'order_id': result['data'].get('order_id'),
                'message': 'Order placed successfully'
            }
        return result

    def modify_order(self, order_id: str, quantity: int = None, price: float = None,
                    order_type: str = None, trigger_price: float = None) -> Dict:
        """Modify an existing order"""
        payload = {'order_id': order_id}

        if quantity:
            payload['quantity'] = quantity
        if price:
            payload['price'] = price
        if order_type:
            payload['order_type'] = order_type
        if trigger_price:
            payload['trigger_price'] = trigger_price

        return self._make_request("PUT", "/order/modify", payload)

    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        result = self._make_request("DELETE", f"/order/cancel?order_id={order_id}")
        if result.get('success'):
            return {'success': True, 'message': 'Order cancelled'}
        return result

    def get_order_status(self, order_id: str) -> Dict:
        """Get status of a specific order"""
        result = self._make_request("GET", f"/order/details?order_id={order_id}")
        if result.get('success') and result.get('data'):
            return result['data']
        return {}

    def get_orders(self) -> List[Dict]:
        """Get all orders for the day"""
        result = self._make_request("GET", "/order/retrieve-all")
        if result.get('success') and result.get('data'):
            return result['data']
        return []

    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        result = self._make_request("GET", "/portfolio/short-term-positions")
        if result.get('success') and result.get('data'):
            return result['data']
        return []

    def get_holdings(self) -> List[Dict]:
        """Get holdings"""
        result = self._make_request("GET", "/portfolio/long-term-holdings")
        if result.get('success') and result.get('data'):
            return result['data']
        return []

    def get_funds(self) -> Dict:
        """Get available funds"""
        result = self._make_request("GET", "/user/get-funds-and-margin")
        if result.get('success') and result.get('data'):
            return result['data']
        return {}

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Dict:
        """Get current quote for a symbol"""
        instrument = self._format_symbol(symbol, exchange)
        result = self._make_request("GET", f"/market-quote/quotes?instrument_key={instrument}")
        if result.get('success') and result.get('data'):
            return result['data'].get(instrument, {})
        return {}

    def get_historical_data(self, symbol: str, exchange: str = "NSE",
                           interval: str = "day", from_date: str = None,
                           to_date: str = None) -> List[Dict]:
        """
        Get historical OHLCV data
        interval: 1minute, 5minute, 15minute, 30minute, 60minute, day, week, month
        """
        instrument = self._format_symbol(symbol, exchange)

        # Map interval
        interval_map = {
            '1minute': '1minute',
            '5minute': '5minute',
            '15minute': '15minute',
            '30minute': '30minute',
            '60minute': '60minute',
            'day': 'day',
            'week': 'week',
            'month': 'month'
        }

        params = {
            'instrument_key': instrument,
            'interval': interval_map.get(interval, 'day')
        }

        if from_date:
            params['from_date'] = from_date
        if to_date:
            params['to_date'] = to_date

        result = self._make_request("GET", "/historical-candle/intraday", params)

        if result.get('success') and result.get('data'):
            candles = result['data'].get('candles', [])
            # Format candles
            formatted = []
            for c in candles:
                formatted.append({
                    'timestamp': c[0],
                    'open': c[1],
                    'high': c[2],
                    'low': c[3],
                    'close': c[4],
                    'volume': c[5]
                })
            return formatted
        return []

    def get_profile(self) -> Dict:
        """Get user profile"""
        result = self._make_request("GET", "/user/profile")
        if result.get('success') and result.get('data'):
            return result['data']
        return {}

    def search_instruments(self, query: str, exchange: str = "NSE") -> List[Dict]:
        """Search for instruments"""
        result = self._make_request("GET", f"/market-quote/instruments?exchange={exchange}")
        if result.get('success') and result.get('data'):
            # Filter by query
            instruments = result['data']
            return [i for i in instruments if query.upper() in i.get('name', '').upper()
                    or query.upper() in i.get('trading_symbol', '').upper()]
        return []

    # ==================== GTT (Good Till Triggered) Orders ====================

    def place_gtt_order(self, symbol: str, exchange: str, transaction_type: str,
                        trigger_price: float, limit_price: float, quantity: int,
                        product: str = "CNC", order_type: str = "LIMIT") -> Dict:
        """
        Place a GTT (Good Till Triggered) order

        GTT orders remain active until triggered or cancelled.
        Useful for Stop Loss and Target orders that persist even when app is closed.

        Args:
            symbol: Stock symbol (e.g., RELIANCE)
            exchange: Exchange (NSE, BSE)
            transaction_type: BUY or SELL
            trigger_price: Price at which order gets triggered
            limit_price: Limit price for the order (use 0 for market)
            quantity: Number of shares
            product: CNC (Delivery) or MIS (Intraday)
            order_type: LIMIT or MARKET
        """
        product_map = {'CNC': 'D', 'MIS': 'I', 'NRML': 'D'}

        payload = {
            'instrument_token': self._format_symbol(symbol, exchange),
            'quantity': quantity,
            'product': product_map.get(product, 'D'),
            'transaction_type': transaction_type,
            'trigger_price': trigger_price,
            'price': limit_price,
            'order_type': order_type
        }

        result = self._make_request("POST", "/gtt/create", payload)

        if result.get('success') and result.get('data'):
            return {
                'success': True,
                'gtt_id': result['data'].get('gtt_id'),
                'message': 'GTT order placed successfully'
            }
        return result

    def place_gtt_oco(self, symbol: str, exchange: str, transaction_type: str,
                      stop_loss_trigger: float, stop_loss_price: float,
                      target_trigger: float, target_price: float,
                      quantity: int, product: str = "CNC") -> Dict:
        """
        Place a GTT OCO (One Cancels Other) order

        Places both SL and Target - whichever triggers first cancels the other.
        Perfect for bracket-style risk management.

        Args:
            symbol: Stock symbol
            exchange: Exchange
            transaction_type: BUY or SELL (opposite of your position)
            stop_loss_trigger: Price at which SL gets triggered
            stop_loss_price: Limit price for SL order
            target_trigger: Price at which target gets triggered
            target_price: Limit price for target order
            quantity: Number of shares
            product: CNC or MIS
        """
        product_map = {'CNC': 'D', 'MIS': 'I', 'NRML': 'D'}

        payload = {
            'instrument_token': self._format_symbol(symbol, exchange),
            'quantity': quantity,
            'product': product_map.get(product, 'D'),
            'transaction_type': transaction_type,
            'type': 'OCO',  # One Cancels Other
            'legs': [
                {
                    'trigger_price': stop_loss_trigger,
                    'price': stop_loss_price,
                    'order_type': 'LIMIT'
                },
                {
                    'trigger_price': target_trigger,
                    'price': target_price,
                    'order_type': 'LIMIT'
                }
            ]
        }

        result = self._make_request("POST", "/gtt/create-oco", payload)

        if result.get('success') and result.get('data'):
            return {
                'success': True,
                'gtt_id': result['data'].get('gtt_id'),
                'message': 'GTT OCO order placed successfully'
            }
        return result

    def get_gtt_orders(self) -> List[Dict]:
        """Get all active GTT orders"""
        result = self._make_request("GET", "/gtt/list")
        if result.get('success') and result.get('data'):
            return result['data']
        return []

    def get_gtt_order(self, gtt_id: str) -> Dict:
        """Get details of a specific GTT order"""
        result = self._make_request("GET", f"/gtt/details?gtt_id={gtt_id}")
        if result.get('success') and result.get('data'):
            return result['data']
        return {}

    def modify_gtt_order(self, gtt_id: str, trigger_price: float = None,
                         limit_price: float = None, quantity: int = None) -> Dict:
        """Modify an existing GTT order"""
        payload = {'gtt_id': gtt_id}

        if trigger_price:
            payload['trigger_price'] = trigger_price
        if limit_price:
            payload['price'] = limit_price
        if quantity:
            payload['quantity'] = quantity

        result = self._make_request("PUT", "/gtt/modify", payload)

        if result.get('success'):
            return {'success': True, 'message': 'GTT order modified'}
        return result

    def cancel_gtt_order(self, gtt_id: str) -> Dict:
        """Cancel a GTT order"""
        result = self._make_request("DELETE", f"/gtt/cancel?gtt_id={gtt_id}")
        if result.get('success'):
            return {'success': True, 'message': 'GTT order cancelled'}
        return result

    def get_option_ltp(self, symbol: str, strike: int, opt_type: str, expiry: str = None) -> float:
        """
        Get LTP for an option contract using Upstox API
        symbol: NIFTY, BANKNIFTY, SENSEX, MIDCPNIFTY, etc.
        strike: Strike price (e.g., 25200)
        opt_type: CE or PE
        expiry: Optional expiry date in YYYY-MM-DD format
        """
        try:
            from datetime import datetime, timedelta
            import urllib.parse

            sym_upper = symbol.upper()

            # Map symbol to Upstox instrument key format
            symbol_map = {
                'NIFTY': 'NSE_INDEX|Nifty 50',
                'BANKNIFTY': 'NSE_INDEX|Nifty Bank',
                'FINNIFTY': 'NSE_INDEX|Nifty Fin Service',
                'MIDCPNIFTY': 'NSE_INDEX|NIFTY MID SELECT',
                'SENSEX': 'BSE_INDEX|SENSEX',
                'BANKEX': 'BSE_INDEX|BANKEX',
            }

            instrument_key = symbol_map.get(sym_upper)
            if not instrument_key:
                logger.warning(f"Unknown symbol for Upstox: {sym_upper}")
                return 0

            # Check WebSocket cache first for instant real-time data
            cache_key = f"{sym_upper}_{strike}_{opt_type}"
            if cache_key in self._instrument_key_cache and self.ws_manager:
                option_inst_key = self._instrument_key_cache[cache_key]
                ws_ltp = self.ws_manager.get_ltp(option_inst_key)
                if ws_ltp > 0:
                    logger.info(f"WebSocket LTP (instant): {ws_ltp} for {sym_upper} {strike} {opt_type}")
                    return ws_ltp

            # Find expiry dates to try
            now = datetime.now()
            expiry_dates = []

            if expiry:
                expiry_dates.append(expiry)
            else:
                # Each index has a different expiry day:
                # Monday (0): MIDCPNIFTY
                # Tuesday (1): NIFTY, FINNIFTY
                # Wednesday (2): BANKNIFTY
                # Thursday (3): SENSEX, BANKEX (monthly for others)
                expiry_day_map = {
                    'NIFTY': 1,      # Tuesday
                    'BANKNIFTY': 2,  # Wednesday
                    'FINNIFTY': 1,   # Tuesday
                    'MIDCPNIFTY': 0, # Monday
                    'SENSEX': 3,     # Thursday
                    'BANKEX': 3,     # Thursday
                }
                target_day = expiry_day_map.get(sym_upper, 3)  # Default Thursday

                # Find next few expiry days for this symbol
                for weeks_ahead in range(4):
                    days_until_expiry = (target_day - now.weekday()) % 7
                    if days_until_expiry == 0 and now.hour >= 15 and weeks_ahead == 0:
                        days_until_expiry = 7
                    next_exp = now + timedelta(days=days_until_expiry + (weeks_ahead * 7))
                    expiry_dates.append(next_exp.strftime('%Y-%m-%d'))
                    logger.info(f"Calculated expiry for {sym_upper}: {next_exp.strftime('%Y-%m-%d')} ({next_exp.strftime('%A')})")

            encoded_key = urllib.parse.quote(instrument_key, safe='')

            # Method 1: Try Option Contracts API to get instrument key, then use real-time LTP API
            # This is more accurate than Option Chain API which may have delayed data
            logger.info("Trying Option Contracts + Real-time LTP API method...")
            for exp_date in expiry_dates:
                contracts_url = f"/option/contract?instrument_key={encoded_key}&expiry_date={exp_date}"
                contracts_result = self._make_request("GET", contracts_url)
                logger.info(f"Option contracts for {exp_date}: success={contracts_result.get('success')}, count={len(contracts_result.get('data', []))}")

                if contracts_result.get('success') and contracts_result.get('data'):
                    for contract in contracts_result['data']:
                        contract_strike = contract.get('strike_price', 0)
                        contract_type = contract.get('instrument_type', '')  # CE or PE

                        if (abs(float(contract_strike) - float(strike)) < 0.01 and
                            contract_type.upper() == opt_type.upper()):

                            option_instrument_key = contract.get('instrument_key', '')
                            if option_instrument_key:
                                # Cache the instrument key for future WebSocket lookups
                                cache_key = f"{sym_upper}_{strike}_{opt_type}"
                                self._instrument_key_cache[cache_key] = option_instrument_key

                                # Subscribe to WebSocket for real-time updates
                                if self.ws_manager and self.ws_manager.is_connected:
                                    self.ws_manager.subscribe([option_instrument_key])
                                    # Wait briefly for WebSocket data
                                    import time
                                    time.sleep(0.3)  # Wait 300ms for WebSocket data
                                    ws_ltp = self.ws_manager.get_ltp(option_instrument_key)
                                    if ws_ltp > 0:
                                        logger.info(f"WebSocket LTP (real-time): {ws_ltp} for {sym_upper} {strike} {opt_type}")
                                        return ws_ltp

                                # Fallback: Get LTP via REST API
                                encoded_opt_key = urllib.parse.quote(option_instrument_key, safe='')
                                ltp_url = f"/market-quote/ltp?instrument_key={encoded_opt_key}"
                                logger.info(f"Fetching LTP via REST API: {option_instrument_key}")
                                ltp_result = self._make_request("GET", ltp_url)

                                if ltp_result.get('success') and ltp_result.get('data'):
                                    # Response format: {"data": {"NSE_FO:NIFTY...": {"last_price": 123.45}}}
                                    for key, quote_data in ltp_result['data'].items():
                                        ltp = quote_data.get('last_price', 0)
                                        if ltp and float(ltp) > 0:
                                            logger.info(f"REST API LTP: {ltp} for {sym_upper} {strike} {opt_type}")
                                            return float(ltp)

            # Method 2: Fallback to Option Chain API (may have slightly delayed data)
            logger.info("Falling back to Option Chain API...")
            for exp_date in expiry_dates:
                url = f"/option/chain?instrument_key={encoded_key}&expiry_date={exp_date}"
                result = self._make_request("GET", url)

                if result.get('success') and result.get('data'):
                    chain_data = result['data']
                    logger.info(f"Upstox Option Chain: Got {len(chain_data)} strikes for expiry {exp_date}")

                    for item in chain_data:
                        item_strike = item.get('strike_price', 0)

                        if abs(float(item_strike) - float(strike)) < 0.01:
                            if opt_type.upper() == 'CE':
                                option_data = item.get('call_options', {})
                            else:
                                option_data = item.get('put_options', {})

                            if option_data:
                                market_data = option_data.get('market_data', {})
                                ltp = market_data.get('ltp', 0)

                                if ltp and float(ltp) > 0:
                                    logger.info(f"Upstox LTP (from chain): {ltp} for {sym_upper} {strike} {opt_type}")
                                    return float(ltp)

            # Method 3: Try Market Quote API with constructed instrument key
            logger.info("Trying Market Quote API with constructed instrument key...")

            # Map to NFO trading symbol format for options
            # Format: SYMBOL + EXPIRY_FORMAT + STRIKE + OPTION_TYPE
            # e.g., MIDCPNIFTY24FEB12800PE or NIFTY2460612800PE
            nfo_symbol_map = {
                'NIFTY': 'NIFTY',
                'BANKNIFTY': 'BANKNIFTY',
                'FINNIFTY': 'FINNIFTY',
                'MIDCPNIFTY': 'MIDCPNIFTY',
                'SENSEX': 'SENSEX',
                'BANKEX': 'BANKEX',
            }

            base_symbol = nfo_symbol_map.get(sym_upper, sym_upper)

            for exp_date in expiry_dates:
                try:
                    # Parse expiry date
                    exp_dt = datetime.strptime(exp_date, '%Y-%m-%d')

                    # Try different trading symbol formats
                    # Format 1: MIDCPNIFTY24FEB2612750PE (DD + MON + YY + strike + type)
                    # This is the correct Upstox format as per screenshot
                    exp_format1 = exp_dt.strftime('%d%b%y').upper()  # 24FEB26
                    trading_sym1 = f"{base_symbol}{exp_format1}{int(strike)}{opt_type.upper()}"

                    # Format 2: MIDCPNIFTY2460612800PE (YYMDD)
                    exp_format2 = exp_dt.strftime('%y%m%d')  # 260206
                    trading_sym2 = f"{base_symbol}{exp_format2}{int(strike)}{opt_type.upper()}"

                    # Format 3: MIDCPNIFTY26F0612800PE (YY + month code + DD)
                    month_codes = {1: 'J', 2: 'F', 3: 'M', 4: 'A', 5: 'M', 6: 'J',
                                   7: 'J', 8: 'A', 9: 'S', 10: 'O', 11: 'N', 12: 'D'}
                    month_code = month_codes.get(exp_dt.month, 'X')
                    exp_format3 = f"{exp_dt.strftime('%y')}{month_code}{exp_dt.strftime('%d')}"
                    trading_sym3 = f"{base_symbol}{exp_format3}{int(strike)}{opt_type.upper()}"

                    # Format 4: Try without year as well (legacy)
                    exp_format4 = exp_dt.strftime('%d%b').upper()  # 24FEB
                    trading_sym4 = f"{base_symbol}{exp_format4}{int(strike)}{opt_type.upper()}"

                    for trading_sym in [trading_sym1, trading_sym2, trading_sym3, trading_sym4]:
                        instrument_key = f"NSE_FO|{trading_sym}"
                        encoded_key = urllib.parse.quote(instrument_key, safe='')
                        ltp_url = f"/market-quote/ltp?instrument_key={encoded_key}"

                        logger.info(f"Trying market quote with key: {instrument_key}")
                        ltp_result = self._make_request("GET", ltp_url)
                        logger.info(f"Market quote result: success={ltp_result.get('success')}, has_data={bool(ltp_result.get('data'))}, response={str(ltp_result)[:200]}")

                        if ltp_result.get('success') and ltp_result.get('data'):
                            for key, quote_data in ltp_result['data'].items():
                                ltp = quote_data.get('last_price', 0)
                                if ltp and float(ltp) > 0:
                                    logger.info(f"Upstox LTP via market quote: {ltp} for {trading_sym}")
                                    return float(ltp)
                except Exception as e:
                    logger.warning(f"Error trying market quote format: {e}")
                    continue

            logger.warning(f"Upstox: Could not fetch LTP for {symbol} {strike} {opt_type}")
            return 0

        except Exception as e:
            logger.error(f"Upstox get_option_ltp error: {e}")
            return 0

    def get_futures_ltp(self, symbol: str, expiry: str = None) -> float:
        """
        Get LTP for a futures contract
        symbol: NIFTY, BANKNIFTY, SENSEX, MIDCPNIFTY, etc.
        expiry: Optional expiry date in YYYY-MM-DD format
        """
        try:
            import urllib.parse
            from datetime import datetime, timedelta

            sym_upper = symbol.upper()

            # Map symbol to Upstox instrument key format for index
            symbol_map = {
                'NIFTY': 'NSE_INDEX|Nifty 50',
                'BANKNIFTY': 'NSE_INDEX|Nifty Bank',
                'FINNIFTY': 'NSE_INDEX|Nifty Fin Service',
                'MIDCPNIFTY': 'NSE_INDEX|NIFTY MID SELECT',
                'SENSEX': 'BSE_INDEX|SENSEX',
                'BANKEX': 'BSE_INDEX|BANKEX',
            }

            instrument_key = symbol_map.get(sym_upper)
            if not instrument_key:
                logger.warning(f"Unknown symbol for Upstox futures: {sym_upper}")
                return 0

            # Find expiry date
            now = datetime.now()
            if expiry:
                expiry_dates = [expiry]
            else:
                # Futures typically expire on last Thursday of month
                # Try current and next month
                expiry_dates = []
                for months_ahead in range(3):
                    # Find last Thursday of month
                    if months_ahead == 0:
                        year, month = now.year, now.month
                    else:
                        next_month = now.month + months_ahead
                        year = now.year + (next_month - 1) // 12
                        month = ((next_month - 1) % 12) + 1

                    # Find last Thursday
                    import calendar
                    last_day = calendar.monthrange(year, month)[1]
                    last_date = datetime(year, month, last_day)
                    days_since_thursday = (last_date.weekday() - 3) % 7
                    last_thursday = last_date - timedelta(days=days_since_thursday)
                    expiry_dates.append(last_thursday.strftime('%Y-%m-%d'))

            encoded_key = urllib.parse.quote(instrument_key, safe='')

            # Try to get futures contract
            for exp_date in expiry_dates:
                contracts_url = f"/option/contract?instrument_key={encoded_key}&expiry_date={exp_date}"
                contracts_result = self._make_request("GET", contracts_url)

                if contracts_result.get('success') and contracts_result.get('data'):
                    for contract in contracts_result['data']:
                        contract_type = contract.get('instrument_type', '')
                        if contract_type == 'FUT':
                            fut_instrument_key = contract.get('instrument_key', '')
                            if fut_instrument_key:
                                # Get LTP using the instrument key
                                encoded_fut_key = urllib.parse.quote(fut_instrument_key, safe='')
                                ltp_url = f"/market-quote/ltp?instrument_key={encoded_fut_key}"
                                ltp_result = self._make_request("GET", ltp_url)

                                if ltp_result.get('success') and ltp_result.get('data'):
                                    for key, quote_data in ltp_result['data'].items():
                                        ltp = quote_data.get('last_price', 0)
                                        if ltp and float(ltp) > 0:
                                            logger.info(f"Upstox FUTURES LTP: {ltp} for {sym_upper}")
                                            return float(ltp)

            logger.warning(f"Upstox: Could not fetch FUT LTP for {symbol}")
            return 0

        except Exception as e:
            logger.error(f"Upstox get_futures_ltp error: {e}")
            return 0

    def get_option_expiries(self, symbol: str) -> List[str]:
        """
        Get available expiry dates for an option symbol
        Returns list of dates in YYYY-MM-DD format
        """
        try:
            import urllib.parse

            sym_upper = symbol.upper()

            # Map symbol to Upstox instrument key format
            symbol_map = {
                'NIFTY': 'NSE_INDEX|Nifty 50',
                'BANKNIFTY': 'NSE_INDEX|Nifty Bank',
                'FINNIFTY': 'NSE_INDEX|Nifty Fin Service',
                'MIDCPNIFTY': 'NSE_INDEX|NIFTY MID SELECT',
                'SENSEX': 'BSE_INDEX|SENSEX',
                'BANKEX': 'BSE_INDEX|BANKEX',
            }

            instrument_key = symbol_map.get(sym_upper)
            if not instrument_key:
                return []

            encoded_key = urllib.parse.quote(instrument_key, safe='')
            url = f"/option/contract?instrument_key={encoded_key}"

            result = self._make_request("GET", url)

            if result.get('success') and result.get('data'):
                expiries = set()
                for contract in result['data']:
                    expiry = contract.get('expiry')
                    if expiry:
                        expiries.add(expiry)
                return sorted(list(expiries))

            return []

        except Exception as e:
            logger.error(f"Error getting option expiries: {e}")
            return []

    def get_ltp(self, symbol: str) -> float:
        """Get LTP for any instrument by symbol"""
        try:
            quote = self.get_quote(symbol)
            if quote:
                return float(quote.get('last_price', 0))
            return 0
        except Exception as e:
            logger.error(f"Error getting LTP: {e}")
            return 0
