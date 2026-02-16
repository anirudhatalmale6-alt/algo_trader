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

from algo_trader.brokers.upstox import UpstoxBroker
from algo_trader.brokers.alice_blue import AliceBlueBroker
from algo_trader.brokers.base import BrokerOrder

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'mukesh-algo-secret-key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global state
active_broker = None
broker_config = {}
watchlist = []

# ===== PAGE ROUTES =====

@app.route('/')
def index():
    return render_template('index.html')

# ===== BROKER API =====

@app.route('/api/broker/login-url', methods=['POST'])
def get_login_url():
    global active_broker, broker_config
    try:
        data = request.json
        broker_type = data.get('broker_type', 'upstox')
        api_key = data.get('api_key', '')
        api_secret = data.get('api_secret', '')
        user_id = data.get('user_id', '')
        app_code = data.get('app_code', '')
        redirect_uri = data.get('redirect_uri', 'http://127.0.0.1:5000/callback')

        broker_config = data

        if broker_type == 'upstox':
            active_broker = UpstoxBroker(api_key, api_secret, redirect_uri)
        elif broker_type == 'alice_blue':
            active_broker = AliceBlueBroker(api_key, app_code, user_id, redirect_uri)
        else:
            return jsonify({'success': False, 'message': f'Unknown broker: {broker_type}'})

        login_url = active_broker.get_login_url()
        return jsonify({'success': True, 'login_url': login_url})

    except Exception as e:
        logger.error(f"Login URL error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/broker/authenticate', methods=['POST'])
def authenticate():
    global active_broker
    try:
        data = request.json
        auth_code = data.get('auth_code', '')

        if not active_broker:
            return jsonify({'success': False, 'message': 'No broker initialized. Get login URL first.'})

        if not auth_code:
            return jsonify({'success': False, 'message': 'Auth code is required'})

        result = active_broker.generate_session(auth_code)
        if result:
            return jsonify({
                'success': True,
                'message': 'Authentication successful',
                'broker': active_broker.broker_name,
                'is_authenticated': True
            })
        else:
            return jsonify({'success': False, 'message': 'Authentication failed. Check credentials.'})

    except Exception as e:
        logger.error(f"Auth error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/broker/status')
def broker_status():
    if active_broker and active_broker.is_authenticated:
        return jsonify({
            'success': True,
            'connected': True,
            'broker': active_broker.broker_name,
        })
    return jsonify({'success': True, 'connected': False, 'broker': None})


@app.route('/callback')
def oauth_callback():
    """Handle OAuth callback from broker"""
    auth_code = request.args.get('authCode') or request.args.get('code') or request.args.get('auth_code', '')
    user_id = request.args.get('userId', '')
    return render_template('callback.html', auth_code=auth_code, user_id=user_id)


# ===== MARKET DATA =====

@app.route('/api/ltp/<symbol>')
def get_ltp(symbol):
    if not active_broker or not active_broker.is_authenticated:
        return jsonify({'success': False, 'message': 'Broker not connected'})

    try:
        exchange = request.args.get('exchange', 'NSE')
        ltp = active_broker.get_ltp(symbol, exchange)
        return jsonify({'success': True, 'symbol': symbol, 'ltp': ltp})
    except Exception as e:
        logger.error(f"LTP error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/option-ltp')
def get_option_ltp():
    if not active_broker or not active_broker.is_authenticated:
        return jsonify({'success': False, 'message': 'Broker not connected'})

    try:
        symbol = request.args.get('symbol', 'NIFTY')
        strike = int(request.args.get('strike', 0))
        opt_type = request.args.get('opt_type', 'CE')

        ltp = active_broker.get_option_ltp(symbol, strike, opt_type)
        return jsonify({'success': True, 'symbol': symbol, 'strike': strike, 'opt_type': opt_type, 'ltp': ltp})
    except Exception as e:
        logger.error(f"Option LTP error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/market-data')
def market_data():
    """Get market data for ticker (NIFTY, SENSEX, BANKNIFTY, VIX)"""
    if not active_broker or not active_broker.is_authenticated:
        # Return simulated data when no broker connected
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
        indices = ['NIFTY', 'BANKNIFTY', 'SENSEX', 'INDIAVIX']
        data = []
        for idx in indices:
            try:
                exchange = 'BSE' if idx in ['SENSEX'] else 'NSE'
                ltp = active_broker.get_ltp(idx, exchange)
                data.append({'symbol': idx, 'ltp': ltp, 'change': 0})
            except:
                data.append({'symbol': idx, 'ltp': 0, 'change': 0})

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logger.error(f"Market data error: {e}")
        return jsonify({'success': False, 'message': str(e)})


# ===== ORDERS =====

@app.route('/api/order/place', methods=['POST'])
def place_order():
    if not active_broker or not active_broker.is_authenticated:
        return jsonify({'success': False, 'message': 'Broker not connected'})

    try:
        data = request.json
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

        result = active_broker.place_order(order)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Order error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/orders')
def get_orders():
    if not active_broker or not active_broker.is_authenticated:
        return jsonify({'success': True, 'orders': []})

    try:
        orders = active_broker.get_orders()
        return jsonify({'success': True, 'orders': orders})
    except Exception as e:
        logger.error(f"Orders error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/positions')
def get_positions():
    if not active_broker or not active_broker.is_authenticated:
        return jsonify({'success': True, 'positions': []})

    try:
        positions = active_broker.get_positions()
        return jsonify({'success': True, 'positions': positions})
    except Exception as e:
        logger.error(f"Positions error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/holdings')
def get_holdings():
    if not active_broker or not active_broker.is_authenticated:
        return jsonify({'success': True, 'holdings': []})

    try:
        holdings = active_broker.get_holdings()
        return jsonify({'success': True, 'holdings': holdings})
    except Exception as e:
        logger.error(f"Holdings error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/funds')
def get_funds():
    if not active_broker or not active_broker.is_authenticated:
        return jsonify({'success': True, 'funds': {}})

    try:
        funds = active_broker.get_funds()
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
