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

    def __init__(self):
        self.active_scans = {}  # scan_name -> scan_config
        self.alert_callbacks = []  # List of callbacks to notify on alerts
        self._running = False
        self._thread = None
        self._session = requests.Session()

        # Set headers to mimic browser
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://chartink.com/screener/'
        })

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
        """
        # Handle legacy parameters
        if total_amount is not None:
            total_capital = total_amount
        if stock_quantity is not None and stock_quantity > 0:
            alloc_type = 'fixed_qty'
            alloc_value = stock_quantity

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
            'open_positions': {},  # symbol -> {'quantity': int, 'action': str, 'price': float, 'time': str}
            'squared_off': set(),  # symbols that have been squared off
        }
        logger.info(f"Added Chartink scan: {scan_name} (alloc={alloc_type}, value={alloc_value}, capital={total_capital})")

    def remove_scan(self, scan_name: str):
        """Remove a scan from monitoring"""
        if scan_name in self.active_scans:
            del self.active_scans[scan_name]
            logger.info(f"Removed Chartink scan: {scan_name}")

    def _parse_time(self, time_str: str) -> dtime:
        """Parse HH:MM time string to time object"""
        try:
            parts = time_str.strip().split(":")
            return dtime(int(parts[0]), int(parts[1]))
        except Exception:
            return dtime(9, 15)  # Default to market open

    def _is_scan_active(self, scan_config: Dict) -> bool:
        """Check if current time is within scan's active window (start_time to exit_time)"""
        now = datetime.now().time()
        start = self._parse_time(scan_config.get('start_time', '09:15'))
        exit_t = self._parse_time(scan_config.get('exit_time', '15:15'))
        return start <= now <= exit_t

    def _can_take_new_trade(self, scan_config: Dict) -> bool:
        """Check if new trades are allowed (before no_new_trade_time and under limits)"""
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

        # Track open position
        config['open_positions'][symbol] = {
            'quantity': quantity,
            'action': action,
            'price': price,
            'time': datetime.now().strftime("%H:%M:%S")
        }
        logger.info(f"Recorded trade: {scan_name} -> {action} {quantity} {symbol} @ {price}")

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
            response = self._session.get(url)

            if response.status_code != 200:
                logger.error(f"Failed to fetch Chartink URL: {response.status_code}")
                return None

            html = response.text
            import re

            patterns = [
                r'scan_clause\s*=\s*["\']([^"\']+)["\']',
                r'data-scan-clause=["\']([^"\']+)["\']',
                r'"scan_clause":\s*"([^"]+)"'
            ]

            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    return match.group(1)

            logger.warning(f"Could not extract scan condition from URL")
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
            # Get CSRF token
            csrf_response = self._session.get("https://chartink.com/screener/")
            csrf_token = self._session.cookies.get('XSRF-TOKEN', '')

            payload = {
                'scan_clause': scan_condition
            }

            headers = {
                'X-CSRF-TOKEN': csrf_token,
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
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
        new_symbols = current_symbols - last_symbols

        scan_config['last_results'] = current_symbols
        scan_config['last_scan'] = datetime.now()

        new_alerts = [alert for alert in current_results if alert.symbol in new_symbols]
        return new_alerts

    def _monitoring_loop(self):
        """Background monitoring loop with time controls"""
        logger.info("Chartink monitoring started")

        while self._running:
            for scan_name, scan_config in list(self.active_scans.items()):
                try:
                    # Check if scan is within active time window
                    if not self._is_scan_active(scan_config):
                        continue

                    # Check if it's exit time - square off positions
                    if self._is_exit_time(scan_config):
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
                        # Only process new alerts if we can take new trades
                        if self._can_take_new_trade(scan_config):
                            new_alerts = self._check_for_new_alerts(scan_name)

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
