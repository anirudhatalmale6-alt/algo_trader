"""
Chartink Scanner Integration
Monitors Chartink screeners and triggers trades based on scan results
"""
import requests
import time
import threading
from typing import Dict, List, Callable, Optional
from datetime import datetime, time as dtime
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ChartinkAlert:
    """Represents a stock alert from Chartink scanner"""
    symbol: str
    scan_name: str
    triggered_at: datetime
    price: float = None
    volume: int = None
    change_percent: float = None
    extra_data: Dict = None


class ChartinkScanner:
    """
    Chartink Scanner Integration

    Monitors Chartink screeners and triggers callbacks when stocks appear in scan results.
    Supports time controls, capital allocation, trade limits, and position tracking.
    """

    BASE_URL = "https://chartink.com/screener/"
    SCAN_API_URL = "https://chartink.com/screener/process"

    def __init__(self, cookie_file: str = None, test_mode: bool = False):
        self.active_scans = {}  # scan_name -> scan_config
        self.alert_callbacks = []  # List of callbacks to notify on alerts
        self._running = False
        self._thread = None
        self._session = requests.Session()
        self.test_mode = test_mode  # If True, skip time checks for testing

        # Set headers to mimic browser
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://chartink.com/screener/'
        })

        # Load cookies from file if provided
        if cookie_file:
            self._load_cookies(cookie_file)

    def _load_cookies(self, cookie_file: str):
        """Load cookies from Netscape cookie file format"""
        try:
            import os
            if not os.path.exists(cookie_file):
                logger.warning(f"Cookie file not found: {cookie_file}")
                return

            with open(cookie_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        domain, _, path, secure, expires, name, value = parts[:7]
                        # Clean domain (remove leading dot if present)
                        domain = domain.lstrip('.')
                        if 'chartink' in domain:
                            self._session.cookies.set(name, value, domain=domain, path=path)
                            logger.debug(f"Loaded cookie: {name}")

            logger.info(f"Loaded cookies from {cookie_file}")
        except Exception as e:
            logger.error(f"Error loading cookies: {e}")

    def register_alert_callback(self, callback: Callable[[ChartinkAlert], None]):
        """Register a callback to be called when alerts are triggered"""
        self.alert_callbacks.append(callback)
        logger.info(f"Registered Chartink alert callback")

    def add_scan(self, scan_name: str, scan_url: str = None, scan_condition: str = None,
                 interval: int = 60, action: str = "BUY", quantity: int = 1,
                 start_time: str = "09:15", exit_time: str = "15:15",
                 no_new_trade_time: str = "14:30",
                 total_capital: float = 0, alloc_type: str = "auto",
                 alloc_value: float = 0, max_trades: int = 0,
                 risk_config: Dict = None,
                 trigger_on_first: bool = True,  # Trigger signals on first scan
                 enabled: bool = True,  # Scanner ON/OFF toggle
                 # Legacy support
                 total_amount: float = None, stock_quantity: int = None):
        """
        Add a scan to monitor

        Args:
            scan_name: Unique name for this scan
            scan_url: Chartink screener URL
            scan_condition: Raw scan condition string
            interval: Scan interval in seconds (default: 60)
            action: Action to take when stock appears (BUY/SELL)
            quantity: Default quantity to trade per stock
            start_time: Time to start scanning (HH:MM format)
            exit_time: Time to square-off all positions (HH:MM format)
            no_new_trade_time: Stop taking new trades after this time (HH:MM format)
            total_capital: Total capital for this scanner (0 = unlimited)
            alloc_type: Per-stock allocation type: 'auto', 'fixed_qty', 'fixed_amount'
            alloc_value: Value for allocation (qty for fixed_qty, amount for fixed_amount)
            max_trades: Max number of trades allowed (0 = unlimited)
            risk_config: Risk management settings (SL, TSL, Target, MTM)
            trigger_on_first: If True, trigger signals on first scan (default: True)
            enabled: If True, scanner is active (default: True)
        """
        # Handle legacy parameters
        if total_amount is not None:
            total_capital = total_amount
        if stock_quantity is not None and stock_quantity > 0:
            alloc_type = 'fixed_qty'
            alloc_value = stock_quantity

        # Default risk config
        if risk_config is None:
            risk_config = {
                'sl_type': 'none', 'sl_value': 0,
                'target_type': 'none', 'target_value': 0,
                'tsl_enabled': False, 'tsl_type': 'points', 'tsl_value': 0,
                'profit_lock_enabled': False, 'profit_lock_type': 'points', 'profit_lock_value': 0,
                'mtm_profit': 0, 'mtm_loss': 0
            }

        self.active_scans[scan_name] = {
            'url': scan_url,
            'condition': scan_condition,
            'interval': interval,
            'action': action,
            'quantity': quantity,
            'last_results': set(),
            'last_scan': None,
            # Time controls
            'start_time': start_time,
            'exit_time': exit_time,
            'no_new_trade_time': no_new_trade_time,
            # Capital allocation
            'total_capital': total_capital,
            'amount_used': 0.0,
            # Per-stock allocation
            'alloc_type': alloc_type,  # 'auto', 'fixed_qty', 'fixed_amount'
            'alloc_value': alloc_value,
            # Trade limits
            'max_trades': max_trades,
            'trade_count': 0,
            # Position tracking - tracks what was actually bought/sold
            'open_positions': {},  # symbol -> {'quantity': int, 'action': str, 'price': float, 'time': str, 'high': float}
            'squared_off': set(),  # symbols that have been squared off
            # Risk management
            'risk_config': risk_config,
            'mtm_pnl': 0.0,  # Current MTM P&L for scanner
            'mtm_stopped': False,  # If MTM limit was hit
            # New features
            'trigger_on_first': trigger_on_first,  # Trigger on first scan
            'enabled': enabled,  # Scanner ON/OFF toggle
            'first_scan_done': False,  # Track if first scan is done
        }
        logger.info(f"Added Chartink scan: {scan_name} (alloc={alloc_type}, enabled={enabled}, trigger_first={trigger_on_first})")

    def remove_scan(self, scan_name: str):
        """Remove a scan from monitoring"""
        if scan_name in self.active_scans:
            del self.active_scans[scan_name]
            logger.info(f"Removed Chartink scan: {scan_name}")

    def toggle_scan(self, scan_name: str, enabled: bool = None) -> bool:
        """Toggle scanner ON/OFF. Returns new state."""
        if scan_name not in self.active_scans:
            return False
        config = self.active_scans[scan_name]
        if enabled is None:
            config['enabled'] = not config.get('enabled', True)
        else:
            config['enabled'] = enabled
        logger.info(f"Scanner '{scan_name}' {'enabled' if config['enabled'] else 'disabled'}")
        return config['enabled']

    def is_scan_enabled(self, scan_name: str) -> bool:
        """Check if scanner is enabled"""
        if scan_name not in self.active_scans:
            return False
        return self.active_scans[scan_name].get('enabled', True)

    def _parse_time(self, time_str: str) -> dtime:
        """Parse HH:MM time string to time object"""
        try:
            parts = time_str.strip().split(":")
            return dtime(int(parts[0]), int(parts[1]))
        except Exception:
            return dtime(9, 15)  # Default to market open

    def _is_scan_active(self, scan_config: Dict) -> bool:
        """Check if current time is within scan's active window (start_time to exit_time)"""
        # Skip time check in test mode
        if self.test_mode:
            return True
        now = datetime.now().time()
        start = self._parse_time(scan_config.get('start_time', '09:15'))
        exit_t = self._parse_time(scan_config.get('exit_time', '15:15'))
        return start <= now <= exit_t

    def _can_take_new_trade(self, scan_config: Dict) -> bool:
        """Check if new trades are allowed (before no_new_trade_time and under limits)"""
        # Skip time check in test mode
        if self.test_mode:
            # Still check trade limits even in test mode
            max_trades = scan_config.get('max_trades', 0)
            if max_trades > 0 and scan_config.get('trade_count', 0) >= max_trades:
                return False
            total_capital = scan_config.get('total_capital', scan_config.get('total_amount', 0))
            if total_capital > 0 and scan_config.get('amount_used', 0) >= total_capital:
                return False
            return True

        now = datetime.now().time()
        no_new = self._parse_time(scan_config.get('no_new_trade_time', '14:30'))

        # Time check
        if now > no_new:
            return False

        # Max trades check
        max_trades = scan_config.get('max_trades', 0)
        if max_trades > 0 and scan_config.get('trade_count', 0) >= max_trades:
            return False

        # Capital check (use total_capital, fallback to total_amount for legacy)
        total_capital = scan_config.get('total_capital', scan_config.get('total_amount', 0))
        if total_capital > 0 and scan_config.get('amount_used', 0) >= total_capital:
            return False

        return True

    def _is_exit_time(self, scan_config: Dict) -> bool:
        """Check if it's time to square off positions"""
        # In test mode, never trigger auto exit (allow testing anytime)
        if self.test_mode:
            return False
        now = datetime.now().time()
        exit_t = self._parse_time(scan_config.get('exit_time', '15:15'))
        return now >= exit_t

    def _get_trade_quantity(self, scan_config: Dict, price: float = 0) -> int:
        """Calculate quantity for a trade based on allocation settings"""
        alloc_type = scan_config.get('alloc_type', 'auto')
        alloc_value = scan_config.get('alloc_value', 0)
        total_capital = scan_config.get('total_capital', 0)

        # Fixed Quantity per stock
        if alloc_type == 'fixed_qty' and alloc_value > 0:
            return int(alloc_value)

        # Fixed Amount per stock (calculate qty from price)
        if alloc_type == 'fixed_amount' and alloc_value > 0 and price > 0:
            qty = int(alloc_value / price)
            return max(qty, 1)

        # Auto mode - use total capital / price if available
        if total_capital > 0 and price > 0:
            remaining = total_capital - scan_config.get('amount_used', 0)
            if remaining > 0:
                qty = int(remaining / price)
                return max(qty, 1)
            return 0

        # Legacy support - check old stock_quantity field
        stock_qty = scan_config.get('stock_quantity', 0)
        if stock_qty > 0:
            return stock_qty

        # Fall back to default quantity
        return scan_config.get('quantity', 1)

    def record_trade(self, scan_name: str, symbol: str, action: str, quantity: int, price: float):
        """Record a trade that was actually executed"""
        if scan_name not in self.active_scans:
            return

        config = self.active_scans[scan_name]
        config['trade_count'] = config.get('trade_count', 0) + 1
        config['amount_used'] = config.get('amount_used', 0) + (price * quantity)

        # Track open position with high price for TSL
        config['open_positions'][symbol] = {
            'quantity': quantity,
            'action': action,
            'price': price,
            'high': price,  # Track highest price for TSL
            'low': price,   # Track lowest price for short TSL
            'time': datetime.now().strftime("%H:%M:%S"),
            'profit_locked': False  # For profit lock feature
        }
        logger.info(f"Recorded trade: {scan_name} -> {action} {quantity} {symbol} @ {price}")

    def update_position_price(self, scan_name: str, symbol: str, current_price: float) -> Dict:
        """
        Update position with current price and check risk conditions.
        Returns dict with exit signals if any triggered.
        """
        if scan_name not in self.active_scans:
            return {}

        config = self.active_scans[scan_name]
        if symbol not in config['open_positions']:
            return {}

        pos = config['open_positions'][symbol]
        risk = config.get('risk_config', {})

        entry_price = pos['price']
        quantity = pos['quantity']
        action = pos['action']

        # Calculate P&L
        if action == "BUY":
            pnl = (current_price - entry_price) * quantity
            pnl_points = current_price - entry_price
            pnl_percent = ((current_price - entry_price) / entry_price) * 100
            # Update high for TSL
            pos['high'] = max(pos.get('high', entry_price), current_price)
        else:  # SELL / Short
            pnl = (entry_price - current_price) * quantity
            pnl_points = entry_price - current_price
            pnl_percent = ((entry_price - current_price) / entry_price) * 100
            # Update low for TSL
            pos['low'] = min(pos.get('low', entry_price), current_price)

        pos['current_price'] = current_price
        pos['pnl'] = pnl
        pos['pnl_points'] = pnl_points
        pos['pnl_percent'] = pnl_percent

        exit_signal = {}

        # Check Stop Loss
        sl_type = risk.get('sl_type', 'none')
        sl_value = risk.get('sl_value', 0)
        if sl_type != 'none' and sl_value > 0:
            sl_hit = False
            if sl_type == 'points' and pnl_points <= -sl_value:
                sl_hit = True
            elif sl_type == 'percent' and pnl_percent <= -sl_value:
                sl_hit = True
            elif sl_type == 'amount' and pnl <= -sl_value:
                sl_hit = True

            if sl_hit:
                exit_signal = {'type': 'SL', 'reason': f'Stop Loss hit ({sl_type}: {sl_value})'}
                logger.info(f"SL hit for {symbol}: {exit_signal['reason']}")

        # Check Target
        if not exit_signal:
            target_type = risk.get('target_type', 'none')
            target_value = risk.get('target_value', 0)
            if target_type != 'none' and target_value > 0:
                target_hit = False
                if target_type == 'points' and pnl_points >= target_value:
                    target_hit = True
                elif target_type == 'percent' and pnl_percent >= target_value:
                    target_hit = True
                elif target_type == 'amount' and pnl >= target_value:
                    target_hit = True

                if target_hit:
                    exit_signal = {'type': 'TARGET', 'reason': f'Target hit ({target_type}: {target_value})'}
                    logger.info(f"Target hit for {symbol}: {exit_signal['reason']}")

        # Check Trailing Stop Loss
        if not exit_signal and risk.get('tsl_enabled', False):
            tsl_type = risk.get('tsl_type', 'points')
            tsl_value = risk.get('tsl_value', 0)

            if tsl_value > 0:
                if action == "BUY":
                    high = pos.get('high', entry_price)
                    if tsl_type == 'points':
                        tsl_price = high - tsl_value
                    else:  # percent
                        tsl_price = high * (1 - tsl_value / 100)

                    if current_price <= tsl_price and current_price > entry_price:
                        exit_signal = {'type': 'TSL', 'reason': f'Trailing SL hit (from high {high:.2f})'}
                else:  # SELL
                    low = pos.get('low', entry_price)
                    if tsl_type == 'points':
                        tsl_price = low + tsl_value
                    else:
                        tsl_price = low * (1 + tsl_value / 100)

                    if current_price >= tsl_price and current_price < entry_price:
                        exit_signal = {'type': 'TSL', 'reason': f'Trailing SL hit (from low {low:.2f})'}

        # Check Profit Lock (move SL to breakeven)
        if not exit_signal and risk.get('profit_lock_enabled', False) and not pos.get('profit_locked', False):
            lock_type = risk.get('profit_lock_type', 'points')
            lock_value = risk.get('profit_lock_value', 0)

            if lock_value > 0:
                lock_triggered = False
                if lock_type == 'points' and pnl_points >= lock_value:
                    lock_triggered = True
                elif lock_type == 'amount' and pnl >= lock_value:
                    lock_triggered = True

                if lock_triggered:
                    pos['profit_locked'] = True
                    pos['lock_price'] = entry_price  # SL moved to breakeven
                    logger.info(f"Profit locked for {symbol} at breakeven")

        # If profit is locked and price falls below entry
        if not exit_signal and pos.get('profit_locked', False):
            if action == "BUY" and current_price <= entry_price:
                exit_signal = {'type': 'PROFIT_LOCK', 'reason': 'Profit lock triggered - price fell to entry'}
            elif action == "SELL" and current_price >= entry_price:
                exit_signal = {'type': 'PROFIT_LOCK', 'reason': 'Profit lock triggered - price rose to entry'}

        return exit_signal

    def get_scanner_mtm(self, scan_name: str) -> float:
        """Get total MTM P&L for a scanner"""
        if scan_name not in self.active_scans:
            return 0.0

        config = self.active_scans[scan_name]
        total_pnl = 0.0
        for symbol, pos in config.get('open_positions', {}).items():
            total_pnl += pos.get('pnl', 0.0)

        config['mtm_pnl'] = total_pnl
        return total_pnl

    def check_mtm_limits(self, scan_name: str) -> Optional[str]:
        """Check if MTM limits are breached. Returns reason if breached, None otherwise."""
        if scan_name not in self.active_scans:
            return None

        config = self.active_scans[scan_name]
        if config.get('mtm_stopped', False):
            return "MTM limit already triggered"

        risk = config.get('risk_config', {})
        mtm_profit = risk.get('mtm_profit', 0)
        mtm_loss = risk.get('mtm_loss', 0)

        current_mtm = self.get_scanner_mtm(scan_name)

        if mtm_profit > 0 and current_mtm >= mtm_profit:
            config['mtm_stopped'] = True
            return f"MTM Profit target hit: ₹{current_mtm:.2f}"

        if mtm_loss > 0 and current_mtm <= -mtm_loss:
            config['mtm_stopped'] = True
            return f"MTM Loss limit hit: ₹{current_mtm:.2f}"

        return None

    def is_mtm_stopped(self, scan_name: str) -> bool:
        """Check if scanner is stopped due to MTM limit"""
        if scan_name not in self.active_scans:
            return False
        return self.active_scans[scan_name].get('mtm_stopped', False)

    def record_squareoff(self, scan_name: str, symbol: str):
        """Record that a position was squared off"""
        if scan_name not in self.active_scans:
            return

        config = self.active_scans[scan_name]
        if symbol in config['open_positions']:
            del config['open_positions'][symbol]
            config['squared_off'].add(symbol)
            logger.info(f"Squared off: {scan_name} -> {symbol}")

    def get_open_positions(self, scan_name: str) -> Dict:
        """Get open positions for a scanner"""
        if scan_name not in self.active_scans:
            return {}
        return self.active_scans[scan_name].get('open_positions', {})

    def get_positions_to_squareoff(self, scan_name: str) -> List[Dict]:
        """Get positions that need to be squared off (only actually traded positions)"""
        if scan_name not in self.active_scans:
            return []

        config = self.active_scans[scan_name]
        positions = []
        for symbol, pos in config.get('open_positions', {}).items():
            # Reverse the action for square-off
            exit_action = "SELL" if pos['action'] == "BUY" else "BUY"
            positions.append({
                'symbol': symbol,
                'exit_action': exit_action,
                'quantity': pos['quantity'],
                'entry_price': pos['price'],
                'entry_time': pos['time']
            })
        return positions

    def reset_daily_counters(self, scan_name: str = None):
        """Reset daily trade counters (call at start of day)"""
        scans = [scan_name] if scan_name else list(self.active_scans.keys())
        for name in scans:
            if name in self.active_scans:
                config = self.active_scans[name]
                config['trade_count'] = 0
                config['amount_used'] = 0.0
                config['open_positions'] = {}
                config['squared_off'] = set()
                config['last_results'] = set()
                logger.info(f"Reset daily counters for scan: {name}")

    def get_scan_condition_from_url(self, url: str) -> Optional[str]:
        """Extract scan condition from Chartink URL"""
        try:
            # First, get CSRF token from main page
            main_resp = self._session.get("https://chartink.com/screener/")

            response = self._session.get(url)

            if response.status_code != 200:
                logger.error(f"Failed to fetch Chartink URL: {response.status_code}")
                return None

            html = response.text
            import re
            import json

            # NEW FORMAT (2024+): Chartink uses Vue.js with :scan-json attribute containing atlas_query
            # Look for atlas_query in the scan-json data or inline JSON
            atlas_patterns = [
                # Pattern for atlas_query in JSON (handles escaped quotes)
                r'"atlas_query"\s*:\s*"([^"]+)"',
                r"'atlas_query'\s*:\s*'([^']+)'",
                # Pattern in :scan-json Vue attribute
                r':scan-json=["\'][^"\']*atlas_query["\']?\s*:\s*["\']([^"\']+)["\']',
                # Pattern with HTML entity encoding
                r'atlas_query&quot;:&quot;([^&]+)&quot;',
            ]

            for pattern in atlas_patterns:
                match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
                if match:
                    condition = match.group(1)
                    # Unescape HTML entities and JSON escapes
                    condition = condition.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                    condition = condition.replace('\\u003c', '<').replace('\\u003e', '>')
                    condition = condition.replace('\\"', '"').replace("\\'", "'")
                    logger.info(f"Extracted atlas_query from URL: {condition[:50]}...")
                    return condition

            # Try to find JSON data in script tags or Vue components
            json_match = re.search(r':scan-json="([^"]+)"', html)
            if json_match:
                try:
                    json_str = json_match.group(1)
                    # Unescape HTML entities
                    json_str = json_str.replace('&quot;', '"').replace('&amp;', '&')
                    json_str = json_str.replace('&lt;', '<').replace('&gt;', '>')
                    data = json.loads(json_str)
                    if 'atlas_query' in data:
                        condition = data['atlas_query']
                        logger.info(f"Extracted atlas_query from JSON: {condition[:50]}...")
                        return condition
                except json.JSONDecodeError:
                    pass

            # LEGACY FORMAT: Try old scan_clause patterns for backward compatibility
            legacy_patterns = [
                r'scan_clause\s*=\s*["\']([^"\']+)["\']',
                r'data-scan-clause=["\']([^"\']+)["\']',
                r'"scan_clause":\s*"([^"]+)"',
                r'id="scan_clause"[^>]*value="([^"]+)"',
                r'name="scan_clause"[^>]*value="([^"]+)"',
                r'var\s+scan_clause\s*=\s*["\']([^"\']+)["\']',
                r'scanClause\s*[:=]\s*["\']([^"\']+)["\']',
            ]

            for pattern in legacy_patterns:
                match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
                if match:
                    condition = match.group(1)
                    # Unescape HTML entities
                    condition = condition.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                    logger.info(f"Extracted scan_clause from URL: {condition[:50]}...")
                    return condition

            # Try to extract from hidden input
            input_match = re.search(r'<input[^>]*id=["\']scan_clause["\'][^>]*value=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if input_match:
                return input_match.group(1)

            # Log HTML snippet for debugging
            logger.warning(f"Could not extract scan condition from URL. HTML length: {len(html)}")

            # Debug: Check what patterns exist in HTML
            if 'atlas_query' in html:
                idx = html.find('atlas_query')
                snippet = html[max(0, idx-50):idx+150]
                logger.debug(f"HTML snippet around 'atlas_query': {snippet}")
            elif 'scan_clause' in html.lower():
                idx = html.lower().find('scan_clause')
                snippet = html[max(0, idx-100):idx+200]
                logger.debug(f"HTML snippet around 'scan_clause': {snippet}")

            return None

        except Exception as e:
            logger.error(f"Error extracting scan condition: {e}")
            return None

    def run_scan(self, scan_name: str) -> List[ChartinkAlert]:
        """Run a specific scan and return results"""
        if scan_name not in self.active_scans:
            logger.error(f"Scan '{scan_name}' not found")
            return []

        scan_config = self.active_scans[scan_name]
        scan_condition = scan_config.get('condition')

        # If we have URL but no condition, extract it
        if not scan_condition and scan_config.get('url'):
            scan_condition = self.get_scan_condition_from_url(scan_config['url'])
            if scan_condition:
                scan_config['condition'] = scan_condition

        if not scan_condition:
            logger.error(f"No scan condition available for '{scan_name}'")
            return []

        try:
            # Get CSRF token from meta tag (not cookie - cookie doesn't work)
            csrf_response = self._session.get("https://chartink.com/screener/")
            csrf_token = ''

            # Extract CSRF token from meta tag in HTML
            import re
            csrf_match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', csrf_response.text)
            if csrf_match:
                csrf_token = csrf_match.group(1)
            else:
                logger.warning("Could not find CSRF token in HTML")

            payload = {
                'scan_clause': scan_condition
            }

            headers = {
                'X-CSRF-TOKEN': csrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Referer': 'https://chartink.com/screener/'
            }

            response = self._session.post(
                self.SCAN_API_URL,
                data=payload,
                headers=headers
            )

            if response.status_code != 200:
                logger.error(f"Scan request failed: {response.status_code}")
                return []

            data = response.json()

            alerts = []
            stocks = data.get('data', [])

            for stock in stocks:
                symbol = stock.get('nsecode', stock.get('bsecode', ''))
                if symbol:
                    alert = ChartinkAlert(
                        symbol=symbol,
                        scan_name=scan_name,
                        triggered_at=datetime.now(),
                        price=float(stock.get('close', 0)) if stock.get('close') else None,
                        volume=int(stock.get('volume', 0)) if stock.get('volume') else None,
                        change_percent=float(stock.get('per_chg', 0)) if stock.get('per_chg') else None,
                        extra_data=stock
                    )
                    alerts.append(alert)

            logger.info(f"Scan '{scan_name}' returned {len(alerts)} stocks")
            return alerts

        except Exception as e:
            logger.error(f"Error running scan '{scan_name}': {e}")
            return []

    def _check_for_new_alerts(self, scan_name: str) -> List[ChartinkAlert]:
        """Check for new stocks in scan results (not seen before)"""
        scan_config = self.active_scans[scan_name]
        current_results = self.run_scan(scan_name)

        current_symbols = {alert.symbol for alert in current_results}
        last_symbols = scan_config.get('last_results', set())

        # Check if this is the first scan and trigger_on_first is enabled
        is_first_scan = not scan_config.get('first_scan_done', False)
        trigger_on_first = scan_config.get('trigger_on_first', True)

        if is_first_scan and trigger_on_first:
            # First scan - trigger for all stocks
            new_symbols = current_symbols
            scan_config['first_scan_done'] = True
            logger.info(f"First scan for '{scan_name}' - triggering for all {len(new_symbols)} stocks")
        else:
            # Normal behavior - only new stocks
            new_symbols = current_symbols - last_symbols

        scan_config['last_results'] = current_symbols
        scan_config['last_scan'] = datetime.now()

        new_alerts = [alert for alert in current_results if alert.symbol in new_symbols]
        return new_alerts

    def _monitoring_loop(self):
        """Background monitoring loop with time controls"""
        logger.info("=== CHARTINK MONITORING LOOP STARTED ===")
        logger.info(f"Active scans to monitor: {list(self.active_scans.keys())}")
        logger.info(f"Test mode: {self.test_mode}")

        while self._running:
            logger.info(f"--- Monitoring loop iteration, {len(self.active_scans)} scans ---")
            for scan_name, scan_config in list(self.active_scans.items()):
                try:
                    logger.info(f"Checking scanner '{scan_name}': enabled={scan_config.get('enabled', True)}")
                    # Check if scanner is enabled
                    if not scan_config.get('enabled', True):
                        logger.info(f"Scanner '{scan_name}' is DISABLED, skipping")
                        continue

                    # Check if scan is within active time window
                    is_active = self._is_scan_active(scan_config)
                    logger.info(f"Scanner '{scan_name}' is_scan_active={is_active}, test_mode={self.test_mode}, start={scan_config.get('start_time')}, exit={scan_config.get('exit_time')}")
                    if not is_active:
                        logger.info(f"Scanner '{scan_name}' outside active time window, skipping")
                        continue

                    # Check if it's exit time - square off positions
                    is_exit = self._is_exit_time(scan_config)
                    logger.info(f"Scanner '{scan_name}' is_exit_time={is_exit}")
                    if is_exit:
                        positions = self.get_positions_to_squareoff(scan_name)
                        if positions:
                            logger.info(f"Exit time reached for '{scan_name}', squaring off {len(positions)} positions")
                            for pos in positions:
                                alert = ChartinkAlert(
                                    symbol=pos['symbol'],
                                    scan_name=scan_name,
                                    triggered_at=datetime.now(),
                                    price=pos.get('entry_price')
                                )
                                # Mark as square-off alert
                                alert.extra_data = {
                                    'is_squareoff': True,
                                    'exit_action': pos['exit_action'],
                                    'quantity': pos['quantity']
                                }
                                for callback in self.alert_callbacks:
                                    try:
                                        callback(alert)
                                    except Exception as e:
                                        logger.error(f"Square-off callback error: {e}")
                        continue  # Don't take new trades at exit time

                    # Check if it's time to run this scan
                    last_scan = scan_config.get('last_scan')
                    interval = scan_config.get('interval', 60)

                    if last_scan is None or (datetime.now() - last_scan).seconds >= interval:
                        logger.info(f"Running scan '{scan_name}' (first_scan={last_scan is None}, trigger_on_first={scan_config.get('trigger_on_first')})")
                        # Only process new alerts if we can take new trades
                        can_trade = self._can_take_new_trade(scan_config)
                        logger.info(f"Scan '{scan_name}' can_take_new_trade={can_trade}, trade_count={scan_config.get('trade_count', 0)}, max_trades={scan_config.get('max_trades', 0)}")
                        if can_trade:
                            new_alerts = self._check_for_new_alerts(scan_name)
                            logger.info(f"Scan '{scan_name}' found {len(new_alerts)} new alerts, callbacks registered: {len(self.alert_callbacks)}")

                            for alert in new_alerts:
                                # Calculate quantity based on allocation
                                trade_qty = self._get_trade_quantity(scan_config, alert.price or 0)
                                if trade_qty <= 0:
                                    logger.info(f"Skipping {alert.symbol} - no quantity/capital available")
                                    continue

                                alert.extra_data = alert.extra_data or {}
                                alert.extra_data['calculated_quantity'] = trade_qty

                                logger.info(f"New Chartink alert: {alert.symbol} from {scan_name} (qty={trade_qty})")
                                for callback in self.alert_callbacks:
                                    try:
                                        callback(alert)
                                    except Exception as e:
                                        logger.error(f"Alert callback error: {e}")
                        else:
                            # Still run scan to update last_results but don't trigger trades
                            self._check_for_new_alerts(scan_name)
                            logger.debug(f"Scan '{scan_name}' - new trades blocked (time/limit reached)")

                except Exception as e:
                    logger.error(f"Error in scan '{scan_name}': {e}")

            time.sleep(5)

        logger.info("Chartink monitoring stopped")

    def start_monitoring(self):
        """Start background monitoring of all scans"""
        if self._running:
            logger.warning("Monitoring already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
        logger.info("Chartink monitoring thread started")

    def stop_monitoring(self):
        """Stop background monitoring"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Chartink monitoring stopped")

    def get_active_scans(self) -> List[Dict]:
        """Get list of active scans with their status"""
        return [
            {
                'name': name,
                'url': config.get('url'),
                'interval': config.get('interval'),
                'action': config.get('action'),
                'quantity': config.get('quantity'),
                'last_scan': config.get('last_scan'),
                'stocks_count': len(config.get('last_results', set())),
                'start_time': config.get('start_time', '09:15'),
                'exit_time': config.get('exit_time', '15:15'),
                'no_new_trade_time': config.get('no_new_trade_time', '14:30'),
                'total_capital': config.get('total_capital', config.get('total_amount', 0)),
                'alloc_type': config.get('alloc_type', 'auto'),
                'alloc_value': config.get('alloc_value', 0),
                'max_trades': config.get('max_trades', 0),
                'trade_count': config.get('trade_count', 0),
                'amount_used': config.get('amount_used', 0),
                'open_positions_count': len(config.get('open_positions', {})),
                'risk_config': config.get('risk_config', {}),
                'mtm_pnl': config.get('mtm_pnl', 0.0),
                'mtm_stopped': config.get('mtm_stopped', False),
                # New fields
                'enabled': config.get('enabled', True),
                'trigger_on_first': config.get('trigger_on_first', True),
            }
            for name, config in self.active_scans.items()
        ]

    def test_scan(self, scan_url: str) -> List[Dict]:
        """Test a scan URL and return results (for validation)"""
        temp_name = f"_test_{int(time.time())}"
        self.add_scan(temp_name, scan_url=scan_url)

        alerts = self.run_scan(temp_name)
        self.remove_scan(temp_name)

        return [
            {
                'symbol': alert.symbol,
                'price': alert.price,
                'volume': alert.volume,
                'change_percent': alert.change_percent
            }
            for alert in alerts
        ]
