"""
MUKESH ALGO - Web Trading App Backend
Flask + SocketIO for real-time trading
"""
import sys
import os

# Add parent directory to path for broker imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from loguru import logger
import json
import threading
import time
import requests as http_requests

from algo_trader.brokers.upstox import UpstoxBroker
from algo_trader.brokers.alice_blue import AliceBlueBroker
from algo_trader.brokers.base import BrokerOrder

# MT5 for Exness (optional - requires MetaTrader5 package on Windows)
try:
    from algo_trader.brokers.mt5_broker import MT5Broker
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    MT5Broker = None

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'mukesh-algo-secret-key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global state - Multi-broker & Multi-user support
# Structure: { "broker_id": { "broker": BrokerInstance, "config": {...}, "user": "username" } }
connected_brokers = {}
active_broker_id = None  # Currently selected broker for trading
pending_broker = None  # Broker being authenticated (not yet connected)
pending_broker_config = {}
watchlist = []
instruments_cache = {}  # exchange -> list of instruments


def get_active_broker():
    """Get the currently active broker instance"""
    if active_broker_id and active_broker_id in connected_brokers:
        return connected_brokers[active_broker_id]['broker']
    return None


def make_broker_id(broker_type, user_id):
    """Create unique broker ID like 'alice_blue_515175' """
    return f"{broker_type}_{user_id}".replace(' ', '_')

# ===== PAGE ROUTES =====

@app.route('/')
def index():
    return render_template('index.html')

# ===== BROKER API =====

@app.route('/api/broker/login-url', methods=['POST'])
def get_login_url():
    global pending_broker, pending_broker_config
    try:
        data = request.json
        broker_type = data.get('broker_type', 'upstox')
        api_key = data.get('api_key', '')
        api_secret = data.get('api_secret', '')
        user_id = data.get('user_id', '')
        app_code = data.get('app_code', '')
        redirect_uri = data.get('redirect_uri', 'http://127.0.0.1:5000/callback')

        pending_broker_config = data

        if broker_type == 'upstox':
            pending_broker = UpstoxBroker(api_key, api_secret, redirect_uri)
        elif broker_type == 'alice_blue':
            pending_broker = AliceBlueBroker(api_key, app_code, user_id, redirect_uri)
            # Alice Blue uses direct API login (no browser redirect needed)
            return jsonify({
                'success': True,
                'login_url': '',
                'direct_login': True,
                'message': 'Alice Blue uses direct API login. Click Authenticate to connect.'
            })
        elif broker_type == 'exness':
            if not MT5_AVAILABLE:
                return jsonify({'success': False, 'message': 'MetaTrader5 package not installed. Run: pip install MetaTrader5 (Windows only)'})
            mt5_login = int(user_id) if user_id else 0
            mt5_password = api_key
            mt5_server = api_secret
            pending_broker = MT5Broker(login=mt5_login, password=mt5_password, server=mt5_server)
            return jsonify({
                'success': True,
                'login_url': '',
                'direct_login': True,
                'message': 'Exness uses direct MT5 login. Click Authenticate to connect.'
            })
        else:
            return jsonify({'success': False, 'message': f'Unknown broker: {broker_type}'})

        login_url = pending_broker.get_login_url()
        return jsonify({'success': True, 'login_url': login_url})

    except Exception as e:
        logger.error(f"Login URL error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/broker/authenticate', methods=['POST'])
def authenticate():
    global pending_broker, active_broker_id, connected_brokers
    try:
        data = request.json
        auth_code = data.get('auth_code', '')

        if not pending_broker:
            return jsonify({'success': False, 'message': 'No broker initialized. Get login URL first.'})

        auth_success = False
        broker_label = ''

        # MT5/Exness uses direct login
        if MT5_AVAILABLE and MT5Broker and isinstance(pending_broker, MT5Broker):
            result = pending_broker.authenticate()
            auth_success = bool(result)
            broker_label = 'Exness (MT5)'
            if not auth_success:
                return jsonify({'success': False, 'message': 'MT5 connection failed. Make sure MetaTrader 5 terminal is running and credentials are correct.'})
        elif isinstance(pending_broker, AliceBlueBroker):
            # Alice Blue: use direct API login (no auth code needed)
            result = pending_broker.direct_login()
            if isinstance(result, dict):
                auth_success = result.get('success', False)
                if not auth_success:
                    error_msg = result.get('error', 'Authentication failed')
                    return jsonify({'success': False, 'message': f'Alice Blue: {error_msg}'})
            else:
                auth_success = bool(result)

            if not auth_success:
                return jsonify({'success': False, 'message': 'Alice Blue authentication failed. Check User ID and API Key.'})

            broker_label = 'Alice Blue'
        else:
            if not auth_code:
                return jsonify({'success': False, 'message': 'Auth code is required'})

            result = pending_broker.generate_session(auth_code)

            if isinstance(result, dict):
                auth_success = result.get('success', False)
                if not auth_success:
                    error_msg = result.get('error', 'Authentication failed')
                    return jsonify({'success': False, 'message': f'{pending_broker.broker_name}: {error_msg}'})
            else:
                auth_success = bool(result)

            if not auth_success:
                return jsonify({'success': False, 'message': 'Authentication failed. Check credentials.'})

            broker_label = pending_broker.broker_name

        # Auth succeeded - add to connected brokers pool
        user_id = pending_broker_config.get('user_id', '')
        broker_type = pending_broker_config.get('broker_type', 'unknown')
        broker_id = make_broker_id(broker_type, user_id)

        connected_brokers[broker_id] = {
            'broker': pending_broker,
            'config': pending_broker_config.copy(),
            'broker_type': broker_type,
            'broker_name': broker_label or broker_type,
            'user_id': user_id,
            'connected_at': time.strftime('%d %b %Y %I:%M %p')
        }

        # Auto-select as active if none selected
        if not active_broker_id:
            active_broker_id = broker_id

        logger.info(f"Broker connected: {broker_id} (total: {len(connected_brokers)})")
        pending_broker = None

        return jsonify({
            'success': True,
            'message': f'Connected to {broker_label} successfully!',
            'broker': broker_label,
            'broker_id': broker_id,
            'is_authenticated': True,
            'total_connected': len(connected_brokers)
        })

    except Exception as e:
        logger.error(f"Auth error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/broker/status')
def broker_status():
    brokers_list = []
    for bid, bdata in connected_brokers.items():
        broker = bdata['broker']
        brokers_list.append({
            'broker_id': bid,
            'broker_type': bdata['broker_type'],
            'broker_name': bdata['broker_name'],
            'user_id': bdata['user_id'],
            'connected': broker.is_authenticated,
            'is_active': bid == active_broker_id,
            'connected_at': bdata.get('connected_at', '')
        })

    active = get_active_broker()
    return jsonify({
        'success': True,
        'connected': active is not None and active.is_authenticated,
        'broker': active.broker_name if active else None,
        'active_broker_id': active_broker_id,
        'brokers': brokers_list,
        'total_connected': len(brokers_list)
    })


@app.route('/api/broker/select', methods=['POST'])
def select_broker():
    """Switch the active broker for trading"""
    global active_broker_id
    data = request.json
    broker_id = data.get('broker_id', '')

    if broker_id not in connected_brokers:
        return jsonify({'success': False, 'message': f'Broker {broker_id} not found'})

    active_broker_id = broker_id
    bdata = connected_brokers[broker_id]
    logger.info(f"Active broker switched to: {broker_id}")
    return jsonify({
        'success': True,
        'message': f'Switched to {bdata["broker_name"]} ({bdata["user_id"]})',
        'active_broker_id': broker_id
    })


@app.route('/api/broker/disconnect', methods=['POST'])
def disconnect_broker():
    """Disconnect a specific broker"""
    global active_broker_id, connected_brokers
    data = request.json
    broker_id = data.get('broker_id', '')

    if broker_id not in connected_brokers:
        return jsonify({'success': False, 'message': f'Broker {broker_id} not found'})

    bdata = connected_brokers.pop(broker_id)
    logger.info(f"Broker disconnected: {broker_id}")

    # If we disconnected the active broker, switch to another
    if active_broker_id == broker_id:
        active_broker_id = next(iter(connected_brokers), None)

    return jsonify({
        'success': True,
        'message': f'{bdata["broker_name"]} disconnected',
        'active_broker_id': active_broker_id,
        'total_connected': len(connected_brokers)
    })


@app.route('/api/instruments')
def get_instruments():
    """Fetch instruments from broker master contract. Returns F&O + equity list."""
    global instruments_cache
    try:
        exchanges = request.args.get('exchanges', 'NSE,NFO').split(',')
        result = []

        for exchange in exchanges:
            exchange = exchange.strip().upper()
            # Check cache first
            if exchange in instruments_cache and len(instruments_cache[exchange]) > 0:
                result.extend(instruments_cache[exchange])
                continue

            # Download from Alice Blue master contract API
            try:
                url = f"https://v2api.aliceblueonline.com/restpy/contract_master?exch={exchange}"
                logger.info(f"Downloading {exchange} master contract from {url}")
                headers = {'Accept-Encoding': 'gzip, deflate', 'Accept': 'application/json'}
                response = http_requests.get(url, timeout=120, headers=headers)
                if response.status_code == 200:
                    raw_data = response.json()
                    # Response format: {"NFO": [...]} - data nested under exchange key
                    data = raw_data.get(exchange, raw_data if isinstance(raw_data, list) else [])
                    instruments = []
                    from datetime import datetime as dt
                    for item in data:
                        trading_symbol = item.get('trading_symbol', '')
                        formatted_name = item.get('formatted_ins_name', item.get('symbol', ''))
                        token = item.get('token', 0)
                        expiry_ts = item.get('expiry_date', 0)
                        lot_size = item.get('lot_size', 1)
                        inst_type = item.get('instrument_type', '')
                        strike = item.get('strike_price', '')
                        opt_type = item.get('option_type', '')

                        # Convert expiry timestamp to readable date
                        expiry_str = ''
                        if expiry_ts and isinstance(expiry_ts, (int, float)) and expiry_ts > 0:
                            try:
                                expiry_str = dt.fromtimestamp(expiry_ts / 1000).strftime('%d %b %y')
                            except:
                                expiry_str = ''

                        if trading_symbol:
                            instruments.append({
                                'symbol': trading_symbol,
                                'name': formatted_name,
                                'exchange': exchange,
                                'token': str(token),
                                'expiry': expiry_str,
                                'lot_size': str(lot_size)
                            })

                    instruments_cache[exchange] = instruments
                    result.extend(instruments)
                    logger.info(f"Loaded {len(instruments)} instruments for {exchange}")
                else:
                    logger.warning(f"Failed to download {exchange} master: HTTP {response.status_code}")
            except Exception as e:
                logger.error(f"Error downloading {exchange} master: {e}")

        return jsonify({
            'success': True,
            'count': len(result),
            'instruments': result
        })
    except Exception as e:
        logger.error(f"Instruments error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/instruments/search')
def search_instruments():
    """Search instruments by keyword. Returns max 20 results."""
    global instruments_cache
    try:
        query = request.args.get('q', '').upper().strip()
        exchange = request.args.get('exchange', '').upper().strip()

        if len(query) < 2:
            return jsonify({'success': True, 'results': []})

        results = []
        # Split query into words - ALL words must match in symbol or name
        query_words = query.split()
        exchanges_to_search = [exchange] if exchange else list(instruments_cache.keys())

        for exch in exchanges_to_search:
            if exch not in instruments_cache:
                continue
            for inst in instruments_cache[exch]:
                sym = inst.get('symbol', '').upper()
                name = inst.get('name', '').upper()
                combined = sym + ' ' + name
                # All words must be found in the combined symbol+name
                if all(word in combined for word in query_words):
                    results.append(inst)
                    if len(results) >= 20:
                        break
            if len(results) >= 20:
                break

        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/callback')
def oauth_callback():
    """Handle OAuth callback from broker"""
    auth_code = request.args.get('authCode') or request.args.get('code') or request.args.get('auth_code', '')
    user_id = request.args.get('userId', '')
    return render_template('callback.html', auth_code=auth_code, user_id=user_id)


# ===== MARKET DATA =====

@app.route('/api/ltp/<symbol>')
@app.route('/api/ltp')
def get_ltp(symbol=None):
    # Support both /api/ltp/<symbol> and /api/ltp?symbol=X
    if symbol is None:
        symbol = request.args.get('symbol', '')
    if not symbol:
        return jsonify({'success': False, 'message': 'No symbol provided'})

    broker_id = request.args.get('broker_id', '')
    broker = connected_brokers[broker_id]['broker'] if broker_id in connected_brokers else get_active_broker()
    if not broker or not broker.is_authenticated:
        return jsonify({'success': False, 'message': 'Broker not connected'})

    try:
        import re
        exchange = request.args.get('exchange', 'NSE')

        # Auto-detect NFO for option/future symbols
        if exchange == 'NSE':
            if (re.search(r'\d{2}[A-Z]{3}\d{2}[CPF]', symbol) or
                symbol.endswith('FUT') or
                re.search(r'\d+CE$|\d+PE$', symbol)):
                exchange = 'NFO'
            elif symbol.startswith('SENSEX') and len(symbol) > 6:
                exchange = 'BFO'

        # Use broker's get_ltp which handles token lookup and correct API calls
        ltp = broker.get_ltp(symbol, exchange)

        # If broker didn't find it, try -EQ suffix variants
        if not ltp or ltp == 0:
            if symbol.endswith('-EQ'):
                ltp = broker.get_ltp(symbol.replace('-EQ', ''), exchange)
            elif exchange == 'NSE':
                ltp = broker.get_ltp(symbol + '-EQ', exchange)

        logger.info(f"LTP for {symbol} ({exchange}): {ltp}")
        return jsonify({'success': True, 'symbol': symbol, 'ltp': float(ltp) if ltp else 0})
    except Exception as e:
        logger.error(f"LTP error for {symbol}: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/option-ltp')
def get_option_ltp():
    broker = get_active_broker()
    if not broker or not broker.is_authenticated:
        return jsonify({'success': False, 'message': 'Broker not connected'})

    try:
        symbol = request.args.get('symbol', 'NIFTY')
        strike = int(request.args.get('strike', 0))
        opt_type = request.args.get('opt_type', 'CE')

        ltp = broker.get_option_ltp(symbol, strike, opt_type)
        return jsonify({'success': True, 'symbol': symbol, 'strike': strike, 'opt_type': opt_type, 'ltp': ltp})
    except Exception as e:
        logger.error(f"Option LTP error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/market-data')
def market_data():
    """Get market data for ticker (NIFTY, SENSEX, BANKNIFTY, VIX)"""
    broker = get_active_broker()
    if not broker or not broker.is_authenticated:
        return jsonify({
            'success': True,
            'data': [
                {'symbol': 'NIFTY', 'ltp': 0, 'change': 0},
                {'symbol': 'BANKNIFTY', 'ltp': 0, 'change': 0},
                {'symbol': 'SENSEX', 'ltp': 0, 'change': 0},
                {'symbol': 'INDIAVIX', 'ltp': 0, 'change': 0},
            ]
        })

    try:
        # Alice Blue uses specific trading symbols for indices
        index_symbols = {
            'NIFTY': [('NIFTY', 'NSE'), ('Nifty 50', 'NSE'), ('NIFTY 50', 'NSE')],
            'BANKNIFTY': [('BANKNIFTY', 'NSE'), ('Nifty Bank', 'NSE'), ('NIFTY BANK', 'NSE')],
            'SENSEX': [('SENSEX', 'BSE'), ('SENSEX', 'BFO')],
            'INDIAVIX': [('INDIAVIX', 'NSE'), ('India VIX', 'NSE'), ('NIFTY VIX', 'NSE')],
        }
        data = []
        for idx, variants in index_symbols.items():
            ltp = 0
            for sym, exchange in variants:
                try:
                    ltp = broker.get_ltp(sym, exchange)
                    if ltp and float(ltp) > 0:
                        break
                except:
                    continue
            data.append({'symbol': idx, 'ltp': float(ltp) if ltp else 0, 'change': 0})

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"Market data error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/ltp/bulk', methods=['POST'])
def get_bulk_ltp():
    """Fetch LTP for multiple symbols in one call using tokens"""
    broker = get_active_broker()
    if not broker or not broker.is_authenticated:
        return jsonify({'success': False, 'message': 'Broker not connected'})

    try:
        import re
        data = request.json or {}
        symbols = data.get('symbols', [])  # [{symbol, exchange}]

        if not symbols:
            return jsonify({'success': True, 'data': {}})

        result_map = {}

        for item in symbols:
            sym = item.get('symbol', '')
            exch = item.get('exchange', 'NSE')

            # Auto-detect exchange
            if exch == 'NSE':
                if (re.search(r'\d{2}[A-Z]{3}\d{2}[CPF]', sym) or
                    sym.endswith('FUT') or re.search(r'\d+CE$|\d+PE$', sym)):
                    exch = 'NFO'

            try:
                ltp = broker.get_ltp(sym, exch)
                if ltp and float(ltp) > 0:
                    result_map[sym] = float(ltp)
                    continue
                # Try -EQ suffix variants
                if sym.endswith('-EQ'):
                    ltp = broker.get_ltp(sym.replace('-EQ', ''), exch)
                elif exch == 'NSE':
                    ltp = broker.get_ltp(sym + '-EQ', exch)
                if ltp and float(ltp) > 0:
                    result_map[sym] = float(ltp)
            except:
                pass

        return jsonify({'success': True, 'data': result_map})
    except Exception as e:
        logger.error(f"Bulk LTP error: {e}")
        return jsonify({'success': False, 'message': str(e)})


# ===== ORDERS =====

@app.route('/api/order/place', methods=['POST'])
def place_order():
    data = request.json
    # Allow specifying which broker to trade on
    broker_id = data.get('broker_id', '')
    broker = connected_brokers[broker_id]['broker'] if broker_id in connected_brokers else get_active_broker()
    target_id = broker_id or active_broker_id

    if not broker or not broker.is_authenticated:
        return jsonify({'success': False, 'message': 'Broker not connected'})

    try:
        order = BrokerOrder(
            symbol=data.get('symbol'),
            exchange=data.get('exchange', 'NSE'),
            transaction_type=data.get('transaction_type', 'BUY'),
            order_type=data.get('order_type', 'MARKET'),
            quantity=int(data.get('quantity', 1)),
            price=float(data.get('price', 0)) if data.get('price') else None,
            trigger_price=float(data.get('trigger_price', 0)) if data.get('trigger_price') else None,
            product=data.get('product', 'CNC')
        )

        result = broker.place_order(order)
        if isinstance(result, dict):
            result['broker_id'] = target_id
        return jsonify(result)

    except Exception as e:
        logger.error(f"Order error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/orders')
def get_orders():
    broker_id = request.args.get('broker_id', '')
    # If broker_id='all', merge orders from all brokers
    if broker_id == 'all':
        all_orders = []
        for bid, bdata in connected_brokers.items():
            b = bdata['broker']
            if b.is_authenticated:
                try:
                    orders = b.get_orders()
                    for o in orders:
                        o['broker_id'] = bid
                        o['broker_name'] = bdata['broker_name']
                    all_orders.extend(orders)
                except:
                    pass
        return jsonify({'success': True, 'orders': all_orders})

    broker = connected_brokers[broker_id]['broker'] if broker_id in connected_brokers else get_active_broker()
    if not broker or not broker.is_authenticated:
        return jsonify({'success': True, 'orders': []})
    try:
        orders = broker.get_orders()
        return jsonify({'success': True, 'orders': orders})
    except Exception as e:
        logger.error(f"Orders error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/positions')
def get_positions():
    broker_id = request.args.get('broker_id', '')
    if broker_id == 'all':
        all_positions = []
        for bid, bdata in connected_brokers.items():
            b = bdata['broker']
            if b.is_authenticated:
                try:
                    positions = b.get_positions()
                    for p in positions:
                        p['broker_id'] = bid
                        p['broker_name'] = bdata['broker_name']
                    all_positions.extend(positions)
                except:
                    pass
        return jsonify({'success': True, 'positions': all_positions})

    broker = connected_brokers[broker_id]['broker'] if broker_id in connected_brokers else get_active_broker()
    if not broker or not broker.is_authenticated:
        return jsonify({'success': True, 'positions': []})
    try:
        positions = broker.get_positions()
        return jsonify({'success': True, 'positions': positions})
    except Exception as e:
        logger.error(f"Positions error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/holdings')
def get_holdings():
    broker_id = request.args.get('broker_id', '')
    if broker_id == 'all':
        all_holdings = []
        for bid, bdata in connected_brokers.items():
            b = bdata['broker']
            if b.is_authenticated:
                try:
                    holdings = b.get_holdings()
                    for h in holdings:
                        h['broker_id'] = bid
                        h['broker_name'] = bdata['broker_name']
                    all_holdings.extend(holdings)
                except:
                    pass
        return jsonify({'success': True, 'holdings': all_holdings})

    broker = connected_brokers[broker_id]['broker'] if broker_id in connected_brokers else get_active_broker()
    if not broker or not broker.is_authenticated:
        return jsonify({'success': True, 'holdings': []})
    try:
        holdings = broker.get_holdings()
        return jsonify({'success': True, 'holdings': holdings})
    except Exception as e:
        logger.error(f"Holdings error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/funds')
def get_funds():
    broker_id = request.args.get('broker_id', '')
    if broker_id == 'all':
        all_funds = {}
        for bid, bdata in connected_brokers.items():
            b = bdata['broker']
            if b.is_authenticated:
                try:
                    funds = b.get_funds()
                    all_funds[bid] = {'broker_name': bdata['broker_name'], 'user_id': bdata['user_id'], 'funds': funds}
                except:
                    pass
        return jsonify({'success': True, 'funds': all_funds, 'multi': True})

    broker = connected_brokers[broker_id]['broker'] if broker_id in connected_brokers else get_active_broker()
    if not broker or not broker.is_authenticated:
        return jsonify({'success': True, 'funds': {}})
    try:
        funds = broker.get_funds()
        return jsonify({'success': True, 'funds': funds})
    except Exception as e:
        logger.error(f"Funds error: {e}")
        return jsonify({'success': False, 'message': str(e)})


# ===== WATCHLIST =====

@app.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    return jsonify({'success': True, 'watchlist': watchlist})


@app.route('/api/watchlist/add', methods=['POST'])
def add_to_watchlist():
    global watchlist
    data = request.json
    symbol = data.get('symbol', '').upper()
    if symbol and symbol not in [w['symbol'] for w in watchlist]:
        watchlist.append({'symbol': symbol, 'ltp': 0, 'change': 0})
    return jsonify({'success': True, 'watchlist': watchlist})


@app.route('/api/watchlist/remove', methods=['POST'])
def remove_from_watchlist():
    global watchlist
    data = request.json
    symbol = data.get('symbol', '').upper()
    watchlist = [w for w in watchlist if w['symbol'] != symbol]
    return jsonify({'success': True, 'watchlist': watchlist})


@app.route('/api/watchlist/clear', methods=['POST'])
def clear_watchlist():
    global watchlist
    watchlist = []
    return jsonify({'success': True, 'watchlist': watchlist})


# ===== SCANNER API =====

# Scanner state
active_scanners = {}
deployed_strategies = {}


@app.route('/api/scanner/start', methods=['POST'])
def start_scanner():
    """Start a Chartink scanner"""
    data = request.json
    url = data.get('url', '')
    interval = int(data.get('interval', 5))

    if not url:
        return jsonify({'success': False, 'error': 'Scanner URL required'})

    scanner_id = f"scanner_{int(time.time())}"
    active_scanners[scanner_id] = {
        'url': url,
        'interval': interval,
        'start_time': data.get('startTime', '09:15'),
        'end_time': data.get('endTime', '15:15'),
        'no_new_trade_time': data.get('noNewTradeTime', '14:30'),
        'capital_mode': data.get('capitalMode', 'auto'),
        'capital_value': data.get('capitalValue', '50000'),
        'max_trades': int(data.get('maxTrades', 10)),
        'sl_percent': float(data.get('slPercent', 1.5)),
        'target_percent': float(data.get('targetPercent', 3.0)),
        'tsl_percent': float(data.get('tslPercent', 0.5)),
        'status': 'running',
        'trades': 0,
        'started_at': time.strftime('%H:%M:%S')
    }

    logger.info(f"Scanner started: {scanner_id} - URL: {url}")
    return jsonify({'success': True, 'scanner_id': scanner_id})


@app.route('/api/scanner/stop', methods=['POST'])
def stop_scanner():
    """Stop all active scanners"""
    for sid in list(active_scanners.keys()):
        active_scanners[sid]['status'] = 'stopped'
    active_scanners.clear()
    logger.info("All scanners stopped")
    return jsonify({'success': True})


@app.route('/api/scanner/status', methods=['GET'])
def scanner_status():
    """Get scanner status"""
    return jsonify({
        'success': True,
        'scanners': [
            {
                'id': sid,
                'url': s['url'],
                'interval': s['interval'],
                'status': s['status'],
                'trades': s['trades'],
                'started_at': s['started_at']
            }
            for sid, s in active_scanners.items()
        ]
    })


# ===== STRATEGY API =====

@app.route('/api/strategy/deploy', methods=['POST'])
def deploy_strategy():
    """Deploy a strategy from marketplace"""
    data = request.json
    strategy_id = data.get('strategy_id', '')

    if not strategy_id:
        return jsonify({'success': False, 'error': 'Strategy ID required'})

    broker = get_active_broker()
    broker_name = 'Demo'
    if active_broker_id and active_broker_id in connected_brokers:
        broker_name = connected_brokers[active_broker_id].get('broker_name', 'Active Broker')

    deploy_id = f"{strategy_id}_{int(time.time())}"
    deployed_strategies[deploy_id] = {
        'strategy_id': strategy_id,
        'broker': broker_name,
        'status': 'running',
        'trades': 0,
        'pnl': 0.0,
        'deployed_at': time.strftime('%Y-%m-%d %H:%M:%S')
    }

    logger.info(f"Strategy deployed: {strategy_id} on {broker_name}")
    return jsonify({'success': True, 'deploy_id': deploy_id, 'broker': broker_name})


@app.route('/api/strategy/stop', methods=['POST'])
def stop_strategy():
    """Stop a deployed strategy"""
    data = request.json
    deploy_id = data.get('deploy_id', '')

    if deploy_id in deployed_strategies:
        deployed_strategies[deploy_id]['status'] = 'stopped'
        logger.info(f"Strategy stopped: {deploy_id}")
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Strategy not found'})


@app.route('/api/strategy/list', methods=['GET'])
def list_strategies():
    """List deployed strategies"""
    return jsonify({
        'success': True,
        'strategies': [
            {
                'deploy_id': did,
                'strategy_id': s['strategy_id'],
                'broker': s['broker'],
                'status': s['status'],
                'trades': s['trades'],
                'pnl': s['pnl'],
                'deployed_at': s['deployed_at']
            }
            for did, s in deployed_strategies.items()
        ]
    })


# ===== WEBSOCKET =====

@socketio.on('connect')
def handle_connect():
    logger.info("WebSocket client connected")
    emit('status', {'connected': True})


@socketio.on('subscribe_ltp')
def handle_subscribe(data):
    """Subscribe to LTP updates for a symbol"""
    symbol = data.get('symbol', '')
    logger.info(f"LTP subscription: {symbol}")


@socketio.on('disconnect')
def handle_disconnect():
    logger.info("WebSocket client disconnected")


# ===== MAIN =====

if __name__ == '__main__':
    logger.info("Starting MUKESH ALGO Web Server...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
