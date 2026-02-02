"""
Upstox Broker Integration
API Documentation: https://upstox.com/developer/api-documentation/
"""
import requests
import json
from typing import Dict, List, Optional
from urllib.parse import urlencode
from datetime import datetime
from loguru import logger

from .base import BaseBroker, BrokerOrder


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
            return True
        return False

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
                logger.warning(f"Upstox API non-200 response: {response.status_code} - {result}")
                return self._handle_error(result, endpoint)

        except Exception as e:
            logger.error(f"Upstox API error: {e}")
            return {'success': False, 'message': str(e)}

    def _format_symbol(self, symbol: str, exchange: str) -> str:
        """Format symbol for Upstox API"""
        # Upstox uses format: NSE_EQ|RELIANCE for equity
        # NSE_FO|NIFTY23JAN19500CE for F&O
        exchange_map = {
            'NSE': 'NSE_EQ',
            'BSE': 'BSE_EQ',
            'NFO': 'NSE_FO',
            'MCX': 'MCX_FO'
        }
        ex = exchange_map.get(exchange, 'NSE_EQ')
        return f"{ex}|{symbol}"

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

        result = self._make_request("POST", "/order/place", payload)

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

            # Find expiry dates to try
            now = datetime.now()
            expiry_dates = []

            if expiry:
                expiry_dates.append(expiry)
            else:
                # Find next few Thursdays (weekly expiries)
                for weeks_ahead in range(4):
                    days_until_thursday = (3 - now.weekday()) % 7
                    if days_until_thursday == 0 and now.hour >= 15 and weeks_ahead == 0:
                        days_until_thursday = 7
                    next_exp = now + timedelta(days=days_until_thursday + (weeks_ahead * 7))
                    expiry_dates.append(next_exp.strftime('%Y-%m-%d'))

            encoded_key = urllib.parse.quote(instrument_key, safe='')

            # Method 1: Try Option Chain API first
            for exp_date in expiry_dates:
                url = f"/option/chain?instrument_key={encoded_key}&expiry_date={exp_date}"
                logger.info(f"Upstox option chain request: {url}")

                result = self._make_request("GET", url)
                logger.debug(f"Option chain response: success={result.get('success')}, data_len={len(result.get('data', []))}, raw={str(result)[:500]}")

                if result.get('success') and result.get('data'):
                    chain_data = result['data']
                    logger.info(f"Upstox: Got {len(chain_data)} strikes for expiry {exp_date}")

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
                                    logger.info(f"Upstox LTP found: {ltp} for {sym_upper} {strike} {opt_type}")
                                    return float(ltp)

            # Method 2: Try Option Contracts API to get instrument key, then LTP API
            logger.info("Trying Option Contracts + LTP API method...")
            for exp_date in expiry_dates:
                contracts_url = f"/option/contract?instrument_key={encoded_key}&expiry_date={exp_date}"
                contracts_result = self._make_request("GET", contracts_url)
                logger.debug(f"Option contracts response: success={contracts_result.get('success')}, data_len={len(contracts_result.get('data', []))}")

                if contracts_result.get('success') and contracts_result.get('data'):
                    for contract in contracts_result['data']:
                        contract_strike = contract.get('strike_price', 0)
                        contract_type = contract.get('instrument_type', '')  # CE or PE

                        if (abs(float(contract_strike) - float(strike)) < 0.01 and
                            contract_type.upper() == opt_type.upper()):

                            option_instrument_key = contract.get('instrument_key', '')
                            if option_instrument_key:
                                # Now get LTP using the instrument key
                                encoded_opt_key = urllib.parse.quote(option_instrument_key, safe='')
                                ltp_url = f"/market-quote/ltp?instrument_key={encoded_opt_key}"
                                ltp_result = self._make_request("GET", ltp_url)

                                if ltp_result.get('success') and ltp_result.get('data'):
                                    # Response format: {"data": {"NSE_FO:NIFTY...": {"last_price": 123.45}}}
                                    for key, quote_data in ltp_result['data'].items():
                                        ltp = quote_data.get('last_price', 0)
                                        if ltp and float(ltp) > 0:
                                            logger.info(f"Upstox LTP via contracts API: {ltp} for {sym_upper} {strike} {opt_type}")
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
                    # Format 1: MIDCPNIFTY24FEB12800PE (full month)
                    exp_format1 = exp_dt.strftime('%d%b').upper()  # 24FEB
                    trading_sym1 = f"{base_symbol}{exp_format1}{int(strike)}{opt_type.upper()}"

                    # Format 2: MIDCPNIFTY2460612800PE (YYMDD)
                    exp_format2 = exp_dt.strftime('%y%m%d')  # 240206
                    trading_sym2 = f"{base_symbol}{exp_format2}{int(strike)}{opt_type.upper()}"

                    # Format 3: MIDCPNIFTY24F0612800PE (YY + month code + DD)
                    month_codes = {1: 'J', 2: 'F', 3: 'M', 4: 'A', 5: 'M', 6: 'J',
                                   7: 'J', 8: 'A', 9: 'S', 10: 'O', 11: 'N', 12: 'D'}
                    month_code = month_codes.get(exp_dt.month, 'X')
                    exp_format3 = f"{exp_dt.strftime('%y')}{month_code}{exp_dt.strftime('%d')}"
                    trading_sym3 = f"{base_symbol}{exp_format3}{int(strike)}{opt_type.upper()}"

                    for trading_sym in [trading_sym1, trading_sym2, trading_sym3]:
                        instrument_key = f"NSE_FO|{trading_sym}"
                        encoded_key = urllib.parse.quote(instrument_key, safe='')
                        ltp_url = f"/market-quote/ltp?instrument_key={encoded_key}"

                        logger.debug(f"Trying market quote with key: {instrument_key}")
                        ltp_result = self._make_request("GET", ltp_url)

                        if ltp_result.get('success') and ltp_result.get('data'):
                            for key, quote_data in ltp_result['data'].items():
                                ltp = quote_data.get('last_price', 0)
                                if ltp and float(ltp) > 0:
                                    logger.info(f"Upstox LTP via market quote: {ltp} for {trading_sym}")
                                    return float(ltp)
                except Exception as e:
                    logger.debug(f"Error trying market quote format: {e}")
                    continue

            logger.warning(f"Upstox: Could not fetch LTP for {symbol} {strike} {opt_type}")
            return 0

        except Exception as e:
            logger.error(f"Upstox get_option_ltp error: {e}")
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
