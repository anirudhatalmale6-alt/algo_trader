"""
Alice Blue Broker Integration
API Documentation: https://ant.aliceblueonline.com/
"""
import requests
import hashlib
import json
from typing import Dict, List, Optional
from urllib.parse import urlencode
from datetime import datetime, timedelta
from loguru import logger

from .base import BaseBroker, BrokerOrder


class AliceBlueBroker(BaseBroker):
    """
    Alice Blue ANT API Integration
    Updated for Open API v1 (2025)
    """

    BASE_URL = "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/api"
    AUTH_URL = "https://ant.aliceblueonline.com"
    # Authentication endpoints - try Open API first, then legacy SSO
    SESSION_URLS = [
        "https://ant.aliceblueonline.com/open-api/od/v1/vendor/getUserDetails",
        "https://ant.aliceblueonline.com/rest/AliceBlueAPIService/sso/getUserDetails",
    ]

    def __init__(self, api_key: str, app_code: str = None, user_id: str = None,
                 redirect_uri: str = "http://127.0.0.1:5000/callback"):
        # api_key = Secret Key (long), app_code = App Code (short)
        # Strip spaces from secret key - portal may show with spaces but key works without
        clean_key = api_key.replace(' ', '') if api_key else ''
        super().__init__(clean_key, "")
        self.broker_name = "alice_blue"
        self.user_id = user_id.strip() if user_id else user_id
        self.app_code = app_code.strip() if app_code else app_code
        self.secret_key = clean_key  # Long key for checksum calculation (spaces removed)
        self.redirect_uri = redirect_uri
        self.session_id = None

    def get_login_url(self) -> str:
        """Get Alice Blue OAuth login URL"""
        # Use App Code (short code) for login URL, not Secret Key
        return f"{self.AUTH_URL}/?appcode={self.app_code}"

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

    def generate_session(self, auth_code: str) -> dict:
        """Generate session using authorization code. Returns dict with success/error details."""
        try:
            auth_code = auth_code.strip()

            # Try multiple checksum variants:
            # Official docs say: SHA-256(userId + authCode + apiSecret)
            # Some implementations uppercase userId, some don't
            checksum_variants = [
                (self.user_id + auth_code + self.secret_key, "userId+authCode+secretKey"),
                (self.user_id.upper() + auth_code + self.secret_key, "USERID+authCode+secretKey"),
            ]

            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            logger.info(f"Alice Blue OAuth auth: user_id={self.user_id}, auth_code={auth_code}, secret_key_len={len(self.secret_key)}")

            last_error = ""
            for hash_input, variant_name in checksum_variants:
                checksum = hashlib.sha256(hash_input.encode()).hexdigest()
                payload = {'checkSum': checksum}

                logger.info(f"Trying checksum variant: {variant_name} → {checksum[:20]}...")

                for url in self.SESSION_URLS:
                    logger.info(f"  POST {url}")
                    try:
                        response = requests.post(url, json=payload, headers=headers, timeout=30)
                        logger.info(f"  Response: status={response.status_code}, body={response.text[:500]}")

                        data = response.json()

                        if response.status_code == 200:
                            stat = data.get('stat', '').lower() if data.get('stat') else ''
                            if stat == 'ok' or data.get('userSession'):
                                self.session_id = data.get('userSession')
                                self.access_token = data.get('userSession')
                                self.client_id = data.get('clientId')
                                self.is_authenticated = True
                                logger.info(f"Alice Blue auth SUCCESS via {variant_name} at {url}")
                                return {'success': True}

                        last_error = data.get('emsg', data.get('message', data.get('errorMessage', '')))
                        if not last_error:
                            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                        logger.warning(f"  Failed: {last_error}")

                    except requests.exceptions.RequestException as e:
                        last_error = f"Connection error: {e}"
                        logger.warning(f"  Connection failed: {e}")
                        continue

            # OAuth failed - try direct login as automatic fallback
            logger.info("OAuth auth code failed, trying direct login (getAPIEncpkey → getUserSID)...")
            direct_result = self.direct_login()
            if direct_result.get('success'):
                return direct_result

            error_detail = last_error or "Authentication failed on all methods"
            logger.error(f"Alice Blue auth failed: {error_detail}")
            return {'success': False, 'error': error_detail}

        except Exception as e:
            logger.error(f"Alice Blue auth error: {e}")
            return {'success': False, 'error': str(e)}

    def direct_login(self) -> dict:
        """Direct API login without browser redirect (official SDK method).
        Uses encryption key + SHA-256 hash approach.
        Requires: user_id and api_key (secret_key).
        """
        try:
            headers = {
                'X-SAS-Version': '2.0',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            # Step 1: Get encryption key
            logger.info(f"Alice Blue direct login: user_id={self.user_id}, api_key_len={len(self.secret_key) if self.secret_key else 0}")
            enc_payload = {'userId': self.user_id.upper()}
            url1 = f"{self.BASE_URL}/customer/getAPIEncpkey"
            logger.info(f"Step 1: POST {url1} payload={enc_payload}")
            enc_response = requests.post(url1, json=enc_payload, headers=headers, timeout=30)
            logger.info(f"Step 1 response: status={enc_response.status_code}, body={enc_response.text[:500]}")
            enc_data = enc_response.json()

            enc_key = enc_data.get('encKey')
            if not enc_key:
                error = enc_data.get('emsg', enc_data.get('message', 'Failed to get encryption key'))
                logger.error(f"Alice Blue: No encryption key - {error}")
                return {'success': False, 'error': error}

            # Step 2: Create SHA-256 hash of userId + apiKey + encKey
            hash_input = self.user_id.upper() + self.secret_key + enc_key
            user_data = hashlib.sha256(hash_input.encode()).hexdigest()
            logger.info(f"Step 2: hash({self.user_id.upper()} + key[{len(self.secret_key)}chars] + encKey) = {user_data[:20]}...")

            # Step 3: Get session ID
            session_payload = {
                'userId': self.user_id.upper(),
                'userData': user_data
            }
            url2 = f"{self.BASE_URL}/customer/getUserSID"
            logger.info(f"Step 3: POST {url2}")
            session_response = requests.post(url2, json=session_payload, headers=headers, timeout=30)
            logger.info(f"Step 3 response: status={session_response.status_code}, body={session_response.text[:500]}")
            session_data = session_response.json()

            if session_data.get('stat') == 'Ok' and session_data.get('sessionID'):
                self.session_id = session_data['sessionID']
                self.access_token = session_data['sessionID']
                self.is_authenticated = True
                logger.info(f"Alice Blue direct login successful!")
                return {'success': True}
            else:
                error = session_data.get('emsg', session_data.get('message', 'Failed to get session'))
                logger.error(f"Alice Blue direct login failed: {error}")
                return {'success': False, 'error': error}

        except Exception as e:
            logger.error(f"Alice Blue direct login error: {e}")
            return {'success': False, 'error': str(e)}

    def _get_headers(self) -> Dict:
        """Get headers for authenticated requests"""
        # Alice Blue requires: Bearer USER_ID SESSION_ID (as per official SDK)
        return {
            'Authorization': f'Bearer {self.user_id.upper()} {self.session_id}',
            'X-SAS-Version': '2.0',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make authenticated API request"""
        if not self.is_authenticated:
            return {'success': False, 'message': 'Not authenticated'}

        url = f"{self.BASE_URL}{endpoint}"
        logger.debug(f"Alice Blue API: {method} {endpoint}")

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
                logger.error(f"Alice Blue API error ({endpoint}): HTTP {response.status_code} - {result}")
                result['success'] = False
                return result

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
        """Get instrument token for a symbol from master contract data"""
        if not hasattr(self, '_master_cache'):
            self._master_cache = {}

        # Download and cache master contract for the exchange
        if exchange not in self._master_cache:
            try:
                contracts = self.download_master_contract(exchange)
                if contracts:
                    self._master_cache[exchange] = {
                        item.get('trading_symbol', item.get('symbol', '')): item.get('token', 0)
                        for item in contracts
                    }
                    logger.info(f"Cached {len(self._master_cache[exchange])} instruments for {exchange}")
                else:
                    self._master_cache[exchange] = {}
            except Exception as e:
                logger.error(f"Failed to cache master for {exchange}: {e}")
                self._master_cache[exchange] = {}

        # Look up token
        cache = self._master_cache.get(exchange, {})
        if symbol in cache:
            return cache[symbol]
        # Try without -EQ suffix
        if symbol.endswith('-EQ') and symbol[:-3] in cache:
            return cache[symbol[:-3]]
        # Try with -EQ suffix
        if '-EQ' not in symbol and (symbol + '-EQ') in cache:
            return cache[symbol + '-EQ']
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
            url = f"https://v2api.aliceblueonline.com/restpy/contract_master?exch={exchange.upper()}"
            headers = {'Accept-Encoding': 'gzip, deflate', 'Accept': 'application/json'}
            response = requests.get(url, timeout=120, headers=headers)
            if response.status_code == 200:
                raw_data = response.json()
                # Response format: {"NSE": [...]} - data nested under exchange key
                data = raw_data.get(exchange.upper(), raw_data if isinstance(raw_data, list) else [])
                return data
        except Exception as e:
            logger.error(f"Failed to download master contract: {e}")
        return []

    def get_option_ltp(self, symbol: str, strike: int, opt_type: str, expiry: str = None) -> float:
        """
        Get LTP for an option contract from AliceBlue
        symbol: NIFTY, BANKNIFTY, SENSEX, etc.
        strike: Strike price (e.g., 25200)
        opt_type: CE or PE

        AliceBlue symbol format: BANKNIFTY26224 57700PE
        - YY = 2-digit year
        - M = single digit month (2 for Feb)
        - DD = 2-digit day
        Example: BANKNIFTY2622457700PE for BANKNIFTY 24-Feb-26 57700 PE
        """
        try:
            # Determine exchange
            if symbol.upper() in ['SENSEX', 'BANKEX']:
                exchange = 'BFO'  # BSE F&O
            else:
                exchange = 'NFO'  # NSE F&O

            from datetime import datetime, timedelta

            now = datetime.now()
            sym_upper = symbol.upper()

            # Generate multiple expiry date candidates (next few Thursdays)
            expiry_candidates = []
            for weeks_ahead in range(5):
                days_until_thursday = (3 - now.weekday()) % 7
                if days_until_thursday == 0 and now.hour >= 15 and weeks_ahead == 0:
                    days_until_thursday = 7
                exp_date = now + timedelta(days=days_until_thursday + (weeks_ahead * 7))
                expiry_candidates.append(exp_date)

            # Try multiple symbol formats for each expiry
            for exp_date in expiry_candidates:
                # Format 1: BANKNIFTY26224 (YY + single digit month + DD)
                # For Feb 24, 2026: 26 + 2 + 24 = 26224
                format1 = f"{sym_upper}{exp_date.strftime('%y')}{exp_date.month}{exp_date.strftime('%d')}{int(strike)}{opt_type.upper()}"

                # Format 2: BANKNIFTY2602 24 (YY + MM + DD)
                format2 = f"{sym_upper}{exp_date.strftime('%y%m%d')}{int(strike)}{opt_type.upper()}"

                # Format 3: BANKNIFTY24FEB26 (DD + MMM + YY)
                format3 = f"{sym_upper}{exp_date.strftime('%d%b%y').upper()}{int(strike)}{opt_type.upper()}"

                # Format 4: BANKNIFTY26FEB24 (YY + MMM + DD)
                format4 = f"{sym_upper}{exp_date.strftime('%y%b%d').upper()}{int(strike)}{opt_type.upper()}"

                formats_to_try = [format1, format2, format3, format4]

                for trading_symbol in formats_to_try:
                    logger.debug(f"AliceBlue: Trying symbol {trading_symbol}")
                    ltp = self.get_ltp(trading_symbol, exchange)
                    if ltp and float(ltp) > 0:
                        logger.info(f"AliceBlue LTP found: {ltp} for {trading_symbol}")
                        return float(ltp)

            # Try monthly expiry format
            expiry_month = now.strftime('%y%b').upper()  # e.g., 26FEB
            monthly_symbol = f"{sym_upper}{expiry_month}{int(strike)}{opt_type.upper()}"
            ltp = self.get_ltp(monthly_symbol, exchange)
            if ltp and float(ltp) > 0:
                logger.info(f"AliceBlue LTP found (monthly): {ltp} for {monthly_symbol}")
                return float(ltp)

            logger.warning(f"AliceBlue: Could not fetch option LTP for {symbol} {strike} {opt_type}")
            return 0

        except Exception as e:
            logger.error(f"Error fetching option LTP from AliceBlue: {e}")
            return 0

    def _get_nse_prev_close(self, symbol: str, exchange: str = "NSE") -> float:
        """Get official previous close from NSE India API.
        This gives the exact same value that Alice Blue and all brokers use.
        Caches result per symbol since prev close doesn't change during the day."""
        if not hasattr(self, '_prev_close_cache'):
            self._prev_close_cache = {}

        # Clean symbol for NSE API (remove -EQ suffix, etc.)
        clean_sym = symbol.replace('-EQ', '').replace('-BE', '').strip()
        cache_key = f"{clean_sym}"
        if cache_key in self._prev_close_cache:
            return self._prev_close_cache[cache_key]

        # Only works for NSE/NFO equities, not MCX/BSE
        if exchange not in ('NSE', 'NFO', 'BSE', 'BFO'):
            return 0.0

        try:
            if not hasattr(self, '_nse_session'):
                self._nse_session = requests.Session()
                self._nse_session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json',
                    'Accept-Language': 'en-US,en;q=0.9',
                })
                # Get cookies from NSE main page
                try:
                    self._nse_session.get('https://www.nseindia.com', timeout=10)
                except:
                    pass

            # For index symbols, use different endpoint
            index_map = {
                'NIFTY': 'NIFTY 50', 'NIFTY 50': 'NIFTY 50',
                'BANKNIFTY': 'NIFTY BANK', 'NIFTY BANK': 'NIFTY BANK',
                'INDIAVIX': 'INDIA VIX', 'INDIA VIX': 'INDIA VIX',
            }

            if clean_sym.upper() in index_map:
                idx_name = index_map[clean_sym.upper()]
                url = f'https://www.nseindia.com/api/allIndices'
                r = self._nse_session.get(url, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    for idx in data.get('data', []):
                        if idx.get('index') == idx_name:
                            pc = self._safe_float(idx.get('previousClose', 0))
                            if pc > 0:
                                self._prev_close_cache[cache_key] = pc
                                logger.info(f"NSE prev close for {clean_sym}: {pc} (index)")
                                return pc
            else:
                # Equity quote - URL-encode symbol for special chars (M&M, L&T etc.)
                from urllib.parse import quote
                encoded_sym = quote(clean_sym)
                url = f'https://www.nseindia.com/api/quote-equity?symbol={encoded_sym}'
                r = self._nse_session.get(url, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    pi = data.get('priceInfo', {})
                    pc = self._safe_float(pi.get('previousClose', 0))
                    if pc > 0:
                        self._prev_close_cache[cache_key] = pc
                        logger.info(f"NSE prev close for {clean_sym}: {pc}")
                        return pc
                elif r.status_code == 403:
                    # Session expired, refresh cookies and retry
                    try:
                        import time
                        time.sleep(0.5)
                        self._nse_session.get('https://www.nseindia.com', timeout=10)
                        time.sleep(0.3)
                        r = self._nse_session.get(url, timeout=10)
                        if r.status_code == 200:
                            data = r.json()
                            pi = data.get('priceInfo', {})
                            pc = self._safe_float(pi.get('previousClose', 0))
                            if pc > 0:
                                self._prev_close_cache[cache_key] = pc
                                logger.info(f"NSE prev close for {clean_sym}: {pc} (retry)")
                                return pc
                    except:
                        pass

        except Exception as e:
            logger.warning(f"NSE API error for {clean_sym}: {e}")

        return 0.0

    def _get_prev_close_fallback(self, token: int, exchange: str, symbol: str = "") -> float:
        """Fallback: Get previous close from chart/history API if NSE API fails."""
        if not hasattr(self, '_prev_close_cache_hist'):
            self._prev_close_cache_hist = {}

        cache_key = f"{exchange}:{token}"
        if cache_key in self._prev_close_cache_hist:
            return self._prev_close_cache_hist[cache_key]

        try:
            now = datetime.now()
            from_ts = str(int((now - timedelta(days=5)).timestamp())) + '000'
            to_ts = str(int(now.timestamp())) + '000'

            payload = {
                "token": str(token),
                "exchange": exchange,
                "from": from_ts,
                "to": to_ts,
                "resolution": "D"
            }

            url = f"{self.BASE_URL}/chart/history"
            headers = self._get_headers()
            response = requests.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get('stat') == 'Ok' and data.get('result'):
                    candles = data['result']
                    if len(candles) >= 2:
                        prev_close = float(candles[-2].get('close', 0))
                    elif len(candles) == 1:
                        prev_close = float(candles[-1].get('open', 0))
                    else:
                        prev_close = 0.0

                    if prev_close > 0:
                        self._prev_close_cache_hist[cache_key] = prev_close
                        return prev_close
        except Exception as e:
            logger.error(f"Chart history error for {symbol}: {e}")

        return 0.0

    @staticmethod
    def _get_first_valid(data: Dict, keys: list, default=None):
        """Get the first non-None value from a dict for a list of possible keys"""
        for key in keys:
            val = data.get(key)
            if val is not None:
                return val
        return default

    @staticmethod
    def _safe_float(val, default=0.0):
        """Safely convert a value to float, handling strings, None, empty, 'NA', etc."""
        if val is None:
            return default
        try:
            s = str(val).strip()
            if not s or s in ('NA', 'N/A', '--', '-', ''):
                return default
            return float(s)
        except (ValueError, TypeError):
            return default

    def _extract_quote_data(self, result) -> Dict:
        """Extract LTP, change, change% and prev close from ScripQuoteDetails response.
        Handles various response structures: flat dict, nested dict, list of dicts."""

        # Flatten the response to a single dict with the actual data
        data = result
        if isinstance(result, list) and len(result) > 0:
            data = result[0]  # Some APIs return list of dicts
        if isinstance(data, dict):
            # Try various nesting patterns
            for nested_key in ['data', 'result', 'scrip', 'quote', 'scripData']:
                nested = data.get(nested_key)
                if isinstance(nested, dict) and len(nested) > 3:
                    data = nested
                    break
                elif isinstance(nested, list) and len(nested) > 0 and isinstance(nested[0], dict):
                    data = nested[0]
                    break

        if not isinstance(data, dict):
            logger.warning(f"Unexpected response type: {type(data)}")
            return {'ltp': 0, 'change': 0, 'change_pct': 0, 'prev_close': 0}

        # Extract values using _get_first_valid (checks for None, not falsy)
        ltp = self._safe_float(self._get_first_valid(data, ['LTP', 'ltp', 'Ltp', 'lastTradedPrice', 'LastTradedPrice', 'last_traded_price']))
        prev_close = self._safe_float(self._get_first_valid(data, ['PrvClose', 'prvClose', 'pClose', 'YClose', 'yClose', 'Close', 'close', 'previous_close', 'PreviousClose', 'previousClose']))
        change = self._safe_float(self._get_first_valid(data, ['Change', 'change', 'Chng', 'chng', 'NetChng', 'netChng', 'priceChange', 'PriceChange']))
        change_pct = self._safe_float(self._get_first_valid(data, ['PerChange', 'perChange', 'ChngPer', 'chngPer', 'pChange', 'PerChng', 'ChangePer', 'change_per', 'percentChange', 'PercentChange']))

        # Calculate change from prev_close if API didn't return usable change values
        if ltp > 0 and prev_close > 0 and change == 0.0 and change_pct == 0.0:
            change = round(ltp - prev_close, 2)
            if prev_close != 0:
                change_pct = round((change / prev_close) * 100, 2)

        return {'ltp': ltp, 'change': change, 'change_pct': change_pct, 'prev_close': prev_close}

    def get_scrip_quote(self, symbol: str, exchange: str = "NSE") -> Dict:
        """Get full quote data (LTP + change + prev close) for a symbol"""
        try:
            token = self._get_instrument_token(symbol, exchange)
            quote = None

            if token and token != 0:
                # Get LTP from ScripDetails (this works reliably)
                payload = {'exch': exchange, 'symbol': str(token)}
                result = self._make_request("POST", "/ScripDetails/getScripQuoteDetails", payload)

                if isinstance(result, dict) and (result.get('stat') == 'Ok' or result.get('success')):
                    quote = self._extract_quote_data(result)
                elif isinstance(result, list):
                    quote = self._extract_quote_data(result)

            # Fallback with trading symbol as string if token didn't work
            if not quote or quote['ltp'] <= 0:
                payload = {'exch': exchange, 'symbol': symbol}
                result = self._make_request("POST", "/ScripDetails/getScripQuoteDetails", payload)
                if isinstance(result, dict) and (result.get('stat') == 'Ok' or result.get('success')):
                    quote = self._extract_quote_data(result)

            if not quote or quote['ltp'] <= 0:
                return {'ltp': 0, 'change': 0, 'change_pct': 0, 'prev_close': 0}

            # If ScripDetails didn't provide change data, get prev close from NSE
            if quote['ltp'] > 0 and quote['change'] == 0.0 and quote['prev_close'] <= 0:
                # Try 1: NSE India official API (exact match with Alice Blue)
                # Get the trading symbol for NSE lookup
                trading_sym = symbol.replace('-EQ', '').replace('-BE', '')
                prev_close = self._get_nse_prev_close(trading_sym, exchange)

                # Try 2: Chart/history API as fallback
                if prev_close <= 0:
                    effective_token = token if token and token != 0 else 0
                    if effective_token:
                        prev_close = self._get_prev_close_fallback(effective_token, exchange, symbol)

                if prev_close > 0:
                    quote['prev_close'] = prev_close
                    quote['change'] = round(quote['ltp'] - prev_close, 2)
                    quote['change_pct'] = round((quote['change'] / prev_close) * 100, 2)

            return quote
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return {'ltp': 0, 'change': 0, 'change_pct': 0, 'prev_close': 0}

    def get_ltp(self, symbol: str, exchange: str = "NSE") -> float:
        """Get LTP for any instrument using ScripDetails/getScripQuoteDetails"""
        quote = self.get_scrip_quote(symbol, exchange)
        return quote['ltp']
