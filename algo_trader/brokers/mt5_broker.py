"""
MetaTrader 5 (MT5) Broker Integration
Supports: Exness, XM, Vantage, and any MT5-compatible broker
Trading: Forex, Crypto, Commodities, Indices
"""
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None

from algo_trader.brokers.base import BaseBroker, BrokerOrder


class MT5Broker(BaseBroker):
    """
    MetaTrader 5 Broker Integration

    Works with any MT5-compatible broker:
    - Exness
    - XM
    - Vantage
    - IC Markets
    - Pepperstone
    - And many more...

    Supports:
    - Forex pairs (EURUSD, GBPUSD, etc.)
    - Crypto (BTCUSD, ETHUSD, etc.)
    - Commodities (XAUUSD/Gold, XAGUSD/Silver, Oil)
    - Indices (US30, US500, etc.)
    """

    # Timeframe mapping
    TIMEFRAMES = {
        '1m': mt5.TIMEFRAME_M1 if MT5_AVAILABLE else 1,
        '5m': mt5.TIMEFRAME_M5 if MT5_AVAILABLE else 5,
        '15m': mt5.TIMEFRAME_M15 if MT5_AVAILABLE else 15,
        '30m': mt5.TIMEFRAME_M30 if MT5_AVAILABLE else 30,
        '1h': mt5.TIMEFRAME_H1 if MT5_AVAILABLE else 60,
        '4h': mt5.TIMEFRAME_H4 if MT5_AVAILABLE else 240,
        '1d': mt5.TIMEFRAME_D1 if MT5_AVAILABLE else 1440,
        '1w': mt5.TIMEFRAME_W1 if MT5_AVAILABLE else 10080,
    }

    # Order type mapping
    ORDER_TYPES = {
        'MARKET': mt5.ORDER_TYPE_BUY if MT5_AVAILABLE else 0,  # Will be adjusted for sell
        'LIMIT': mt5.ORDER_TYPE_BUY_LIMIT if MT5_AVAILABLE else 2,
        'STOP': mt5.ORDER_TYPE_BUY_STOP if MT5_AVAILABLE else 4,
        'SL': mt5.ORDER_TYPE_BUY_STOP if MT5_AVAILABLE else 4,
    }

    def __init__(self, login: int = None, password: str = None, server: str = None,
                 path: str = None, **kwargs):
        """
        Initialize MT5 Broker

        Args:
            login: MT5 account number
            password: MT5 password
            server: MT5 server name (e.g., "Exness-MT5Real", "XM-MT5-Real")
            path: Optional path to MT5 terminal (if not in default location)
        """
        # Call parent with dummy values (MT5 doesn't use API keys)
        super().__init__(api_key=str(login or ''), api_secret=password or '', **kwargs)

        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.broker_name = "MT5"

        if not MT5_AVAILABLE:
            logger.warning("MetaTrader5 package not installed. Run: pip install MetaTrader5")

    def authenticate(self, **kwargs) -> bool:
        """
        Connect and authenticate with MT5 terminal
        """
        if not MT5_AVAILABLE:
            logger.error("MetaTrader5 package not available")
            return False

        # Override with kwargs if provided
        login = kwargs.get('login', self.login)
        password = kwargs.get('password', self.password)
        server = kwargs.get('server', self.server)
        path = kwargs.get('path', self.path)

        try:
            # Initialize MT5
            if path:
                initialized = mt5.initialize(path=path)
            else:
                initialized = mt5.initialize()

            if not initialized:
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False

            # Login to account
            if login and password and server:
                authorized = mt5.login(
                    login=int(login),
                    password=password,
                    server=server
                )

                if not authorized:
                    logger.error(f"MT5 login failed: {mt5.last_error()}")
                    mt5.shutdown()
                    return False

            # Get account info to verify connection
            account_info = mt5.account_info()
            if account_info is None:
                logger.error("Failed to get account info")
                return False

            self.is_authenticated = True
            logger.info(f"MT5 connected: Account #{account_info.login}, "
                       f"Balance: {account_info.balance} {account_info.currency}")

            return True

        except Exception as e:
            logger.error(f"MT5 authentication error: {e}")
            return False

    def get_login_url(self) -> str:
        """MT5 doesn't use OAuth - return instructions instead"""
        return "MT5 uses direct login. Please provide: login (account number), password, and server name."

    def generate_session(self, auth_code: str) -> bool:
        """MT5 doesn't use OAuth sessions"""
        return self.authenticate()

    def disconnect(self):
        """Disconnect from MT5"""
        if MT5_AVAILABLE:
            mt5.shutdown()
            self.is_authenticated = False
            logger.info("MT5 disconnected")

    def get_account_info(self) -> Dict:
        """Get detailed account information"""
        if not self._check_connection():
            return {}

        account = mt5.account_info()
        if account is None:
            return {}

        return {
            'login': account.login,
            'name': account.name,
            'server': account.server,
            'currency': account.currency,
            'balance': account.balance,
            'equity': account.equity,
            'margin': account.margin,
            'free_margin': account.margin_free,
            'margin_level': account.margin_level,
            'profit': account.profit,
            'leverage': account.leverage,
            'trade_allowed': account.trade_allowed,
            'trade_expert': account.trade_expert,
        }

    def place_order(self, symbol: str = None, exchange: str = None,
                    transaction_type: str = None, order_type: str = 'MARKET',
                    quantity: float = None, price: float = None,
                    trigger_price: float = None, product_type: str = None,
                    stop_loss: float = None, take_profit: float = None,
                    comment: str = "", magic: int = 0, **kwargs) -> Dict:
        """
        Place an order on MT5

        Args:
            symbol: Trading symbol (e.g., "EURUSD", "BTCUSD", "XAUUSD")
            transaction_type: "BUY" or "SELL"
            order_type: "MARKET", "LIMIT", "STOP"
            quantity: Lot size (e.g., 0.01, 0.1, 1.0)
            price: Limit/Stop price (for pending orders)
            stop_loss: Stop loss price
            take_profit: Take profit price
            comment: Order comment
            magic: Magic number for EA identification
        """
        if not self._check_connection():
            return {'success': False, 'message': 'Not connected to MT5'}

        # Handle BrokerOrder object
        if isinstance(symbol, BrokerOrder):
            order = symbol
            symbol = order.symbol
            transaction_type = order.transaction_type
            order_type = order.order_type
            quantity = order.quantity
            price = order.price
            trigger_price = order.trigger_price

        try:
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                # Try with suffix variations
                for suffix in ['', '.r', '.e', 'm', 'micro']:
                    test_symbol = symbol + suffix
                    symbol_info = mt5.symbol_info(test_symbol)
                    if symbol_info:
                        symbol = test_symbol
                        break

                if symbol_info is None:
                    return {'success': False, 'message': f'Symbol {symbol} not found'}

            # Make sure symbol is visible in Market Watch
            if not symbol_info.visible:
                mt5.symbol_select(symbol, True)

            # Get current price
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return {'success': False, 'message': f'Cannot get price for {symbol}'}

            # Determine order type and price
            is_buy = transaction_type.upper() == 'BUY'

            if order_type.upper() == 'MARKET':
                mt5_order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
                order_price = tick.ask if is_buy else tick.bid
            elif order_type.upper() == 'LIMIT':
                mt5_order_type = mt5.ORDER_TYPE_BUY_LIMIT if is_buy else mt5.ORDER_TYPE_SELL_LIMIT
                order_price = price
            elif order_type.upper() in ['STOP', 'SL']:
                mt5_order_type = mt5.ORDER_TYPE_BUY_STOP if is_buy else mt5.ORDER_TYPE_SELL_STOP
                order_price = trigger_price or price
            else:
                mt5_order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
                order_price = tick.ask if is_buy else tick.bid

            # Normalize lot size
            lot_size = float(quantity)
            lot_size = max(symbol_info.volume_min, min(lot_size, symbol_info.volume_max))
            lot_size = round(lot_size / symbol_info.volume_step) * symbol_info.volume_step

            # Prepare order request
            request = {
                "action": mt5.TRADE_ACTION_DEAL if order_type.upper() == 'MARKET' else mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": lot_size,
                "type": mt5_order_type,
                "price": order_price,
                "deviation": 20,  # Maximum price deviation in points
                "magic": magic,
                "comment": comment or "AlgoTrader",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # Add SL/TP if provided
            if stop_loss:
                request["sl"] = stop_loss
            if take_profit:
                request["tp"] = take_profit

            # Send order
            result = mt5.order_send(request)

            if result is None:
                return {'success': False, 'message': f'Order failed: {mt5.last_error()}'}

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    'success': False,
                    'message': f'Order failed: {result.comment}',
                    'retcode': result.retcode
                }

            logger.info(f"MT5 Order placed: {transaction_type} {lot_size} {symbol} @ {order_price}")

            return {
                'success': True,
                'order_id': str(result.order),
                'deal_id': str(result.deal) if result.deal else None,
                'price': result.price,
                'volume': result.volume,
                'message': 'Order placed successfully'
            }

        except Exception as e:
            logger.error(f"MT5 order error: {e}")
            return {'success': False, 'message': str(e)}

    def modify_order(self, order_id: str, price: float = None,
                     stop_loss: float = None, take_profit: float = None, **kwargs) -> Dict:
        """Modify a pending order"""
        if not self._check_connection():
            return {'success': False, 'message': 'Not connected to MT5'}

        try:
            order_ticket = int(order_id)

            # Get order info
            order = mt5.orders_get(ticket=order_ticket)
            if not order:
                return {'success': False, 'message': f'Order {order_id} not found'}

            order = order[0]

            request = {
                "action": mt5.TRADE_ACTION_MODIFY,
                "order": order_ticket,
                "price": price or order.price_open,
                "sl": stop_loss or order.sl,
                "tp": take_profit or order.tp,
            }

            result = mt5.order_send(request)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {'success': False, 'message': result.comment}

            return {'success': True, 'message': 'Order modified successfully'}

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def cancel_order(self, order_id: str) -> Dict:
        """Cancel a pending order"""
        if not self._check_connection():
            return {'success': False, 'message': 'Not connected to MT5'}

        try:
            order_ticket = int(order_id)

            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": order_ticket,
            }

            result = mt5.order_send(request)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {'success': False, 'message': result.comment}

            return {'success': True, 'message': 'Order cancelled successfully'}

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def close_position(self, symbol: str = None, position_id: int = None,
                       volume: float = None) -> Dict:
        """Close an open position"""
        if not self._check_connection():
            return {'success': False, 'message': 'Not connected to MT5'}

        try:
            # Get position
            if position_id:
                positions = mt5.positions_get(ticket=position_id)
            elif symbol:
                positions = mt5.positions_get(symbol=symbol)
            else:
                return {'success': False, 'message': 'Specify symbol or position_id'}

            if not positions:
                return {'success': False, 'message': 'Position not found'}

            position = positions[0]
            close_volume = volume or position.volume

            # Determine close direction
            close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY

            tick = mt5.symbol_info_tick(position.symbol)
            close_price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": close_volume,
                "type": close_type,
                "position": position.ticket,
                "price": close_price,
                "deviation": 20,
                "magic": position.magic,
                "comment": "Close by AlgoTrader",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {'success': False, 'message': result.comment}

            return {'success': True, 'message': 'Position closed successfully'}

        except Exception as e:
            return {'success': False, 'message': str(e)}

    def get_order_status(self, order_id: str) -> Dict:
        """Get status of a specific order"""
        if not self._check_connection():
            return {}

        try:
            order_ticket = int(order_id)

            # Check pending orders
            order = mt5.orders_get(ticket=order_ticket)
            if order:
                o = order[0]
                return {
                    'order_id': str(o.ticket),
                    'symbol': o.symbol,
                    'type': 'BUY' if o.type in [0, 2, 4] else 'SELL',
                    'volume': o.volume_current,
                    'price': o.price_open,
                    'sl': o.sl,
                    'tp': o.tp,
                    'status': 'PENDING',
                    'time': datetime.fromtimestamp(o.time_setup)
                }

            # Check history
            history = mt5.history_orders_get(ticket=order_ticket)
            if history:
                o = history[0]
                return {
                    'order_id': str(o.ticket),
                    'symbol': o.symbol,
                    'type': 'BUY' if o.type in [0, 2, 4] else 'SELL',
                    'volume': o.volume_current,
                    'price': o.price_open,
                    'status': 'EXECUTED' if o.state == mt5.ORDER_STATE_FILLED else 'CANCELLED',
                    'time': datetime.fromtimestamp(o.time_setup)
                }

            return {'order_id': order_id, 'status': 'NOT_FOUND'}

        except Exception as e:
            return {'error': str(e)}

    def get_orders(self) -> List[Dict]:
        """Get all pending orders"""
        if not self._check_connection():
            return []

        try:
            orders = mt5.orders_get()
            if orders is None:
                return []

            result = []
            for o in orders:
                order_type_map = {
                    0: 'BUY', 1: 'SELL',
                    2: 'BUY_LIMIT', 3: 'SELL_LIMIT',
                    4: 'BUY_STOP', 5: 'SELL_STOP'
                }

                result.append({
                    'order_id': str(o.ticket),
                    'symbol': o.symbol,
                    'side': 'BUY' if o.type in [0, 2, 4] else 'SELL',
                    'order_type': order_type_map.get(o.type, 'UNKNOWN'),
                    'quantity': o.volume_current,
                    'price': o.price_open,
                    'sl': o.sl,
                    'tp': o.tp,
                    'status': 'PENDING',
                    'time': datetime.fromtimestamp(o.time_setup).isoformat(),
                    'comment': o.comment
                })

            return result

        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []

    def get_positions(self) -> List[Dict]:
        """Get all open positions"""
        if not self._check_connection():
            return []

        try:
            positions = mt5.positions_get()
            if positions is None:
                return []

            result = []
            for p in positions:
                result.append({
                    'position_id': str(p.ticket),
                    'symbol': p.symbol,
                    'side': 'BUY' if p.type == 0 else 'SELL',
                    'quantity': p.volume,
                    'entry_price': p.price_open,
                    'current_price': p.price_current,
                    'sl': p.sl,
                    'tp': p.tp,
                    'pnl': p.profit,
                    'swap': p.swap,
                    'time': datetime.fromtimestamp(p.time).isoformat(),
                    'magic': p.magic,
                    'comment': p.comment,
                    'exchange': 'MT5'
                })

            return result

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_holdings(self) -> List[Dict]:
        """MT5 doesn't have 'holdings' concept - return positions instead"""
        return self.get_positions()

    def get_funds(self) -> Dict:
        """Get account balance and margin info"""
        if not self._check_connection():
            return {}

        account = mt5.account_info()
        if account is None:
            return {}

        return {
            'available_margin': account.margin_free,
            'used_margin': account.margin,
            'total_balance': account.balance,
            'equity': account.equity,
            'profit': account.profit,
            'currency': account.currency,
            'leverage': account.leverage,
            'margin_level': account.margin_level
        }

    def get_quote(self, symbol: str, exchange: str = None) -> Dict:
        """Get current quote for a symbol"""
        if not self._check_connection():
            return {}

        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return {}

            symbol_info = mt5.symbol_info(symbol)

            return {
                'symbol': symbol,
                'bid': tick.bid,
                'ask': tick.ask,
                'last': tick.last,
                'volume': tick.volume,
                'time': datetime.fromtimestamp(tick.time).isoformat(),
                'spread': round((tick.ask - tick.bid) / symbol_info.point) if symbol_info else None,
                'high': tick.last,  # MT5 tick doesn't have high/low
                'low': tick.last,
            }

        except Exception as e:
            logger.error(f"Error getting quote: {e}")
            return {}

    def get_historical_data(self, symbol: str, exchange: str = None,
                           interval: str = '1d', from_date: str = None,
                           to_date: str = None, days: int = 100) -> List[Dict]:
        """
        Get historical OHLCV data

        Args:
            symbol: Trading symbol
            interval: '1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w'
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            days: Number of days if from_date not specified
        """
        if not self._check_connection():
            return []

        try:
            # Get timeframe
            timeframe = self.TIMEFRAMES.get(interval, mt5.TIMEFRAME_D1)

            # Calculate date range
            if from_date:
                start = datetime.strptime(from_date, '%Y-%m-%d')
            else:
                start = datetime.now() - timedelta(days=days)

            if to_date:
                end = datetime.strptime(to_date, '%Y-%m-%d')
            else:
                end = datetime.now()

            # Get rates
            rates = mt5.copy_rates_range(symbol, timeframe, start, end)

            if rates is None or len(rates) == 0:
                logger.warning(f"No data for {symbol}")
                return []

            result = []
            for rate in rates:
                result.append({
                    'timestamp': datetime.fromtimestamp(rate['time']).isoformat(),
                    'open': rate['open'],
                    'high': rate['high'],
                    'low': rate['low'],
                    'close': rate['close'],
                    'volume': rate['tick_volume'],
                    'spread': rate['spread']
                })

            return result

        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return []

    def get_symbols(self, group: str = None) -> List[Dict]:
        """
        Get available trading symbols

        Args:
            group: Filter by group (e.g., "*USD*", "Forex*", "Crypto*")
        """
        if not self._check_connection():
            return []

        try:
            if group:
                symbols = mt5.symbols_get(group=group)
            else:
                symbols = mt5.symbols_get()

            if symbols is None:
                return []

            result = []
            for s in symbols:
                result.append({
                    'symbol': s.name,
                    'description': s.description,
                    'currency_base': s.currency_base,
                    'currency_profit': s.currency_profit,
                    'digits': s.digits,
                    'lot_min': s.volume_min,
                    'lot_max': s.volume_max,
                    'lot_step': s.volume_step,
                    'contract_size': s.trade_contract_size,
                    'spread': s.spread,
                    'trade_mode': s.trade_mode,
                })

            return result

        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return []

    def get_forex_symbols(self) -> List[str]:
        """Get list of Forex pairs"""
        symbols = self.get_symbols(group="*Forex*,*forex*,*FX*")
        if not symbols:
            # Try common forex pairs
            common_forex = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD',
                          'NZDUSD', 'USDCAD', 'EURGBP', 'EURJPY', 'GBPJPY']
            return [s for s in common_forex if mt5.symbol_info(s)]
        return [s['symbol'] for s in symbols]

    def get_crypto_symbols(self) -> List[str]:
        """Get list of Crypto pairs"""
        symbols = self.get_symbols(group="*Crypto*,*crypto*,*BTC*,*ETH*")
        if not symbols:
            common_crypto = ['BTCUSD', 'ETHUSD', 'LTCUSD', 'XRPUSD', 'BCHUSD']
            return [s for s in common_crypto if mt5.symbol_info(s)]
        return [s['symbol'] for s in symbols]

    def get_commodity_symbols(self) -> List[str]:
        """Get list of Commodity symbols"""
        symbols = self.get_symbols(group="*XAU*,*XAG*,*Oil*,*Gold*,*Silver*")
        if not symbols:
            common_commodities = ['XAUUSD', 'XAGUSD', 'XBRUSD', 'XTIUSD']
            return [s for s in common_commodities if mt5.symbol_info(s)]
        return [s['symbol'] for s in symbols]

    def is_market_open(self, symbol: str = None) -> bool:
        """Check if market is open for trading"""
        if not self._check_connection():
            return False

        try:
            if symbol:
                info = mt5.symbol_info(symbol)
                if info:
                    return info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL

            # Forex is open 24/5
            now = datetime.now()
            # Closed on weekends (Saturday and Sunday)
            if now.weekday() >= 5:
                return False
            return True

        except Exception:
            return False

    def _check_connection(self) -> bool:
        """Check if connected to MT5"""
        if not MT5_AVAILABLE:
            logger.error("MetaTrader5 package not installed")
            return False

        if not self.is_authenticated:
            logger.warning("Not authenticated with MT5")
            return False

        # Verify connection is still alive
        account = mt5.account_info()
        if account is None:
            self.is_authenticated = False
            logger.warning("MT5 connection lost")
            return False

        return True


# Create alias for backwards compatibility
MetaTraderBroker = MT5Broker
