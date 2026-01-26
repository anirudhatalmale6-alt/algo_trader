"""
Chartink Scanner Integration
Monitors Chartink screeners and triggers trades based on scan results
"""
import requests
import time
import threading
from typing import Dict, List, Callable, Optional
from datetime import datetime
from dataclasses import dataclass
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
    Supports both URL-based scanning and webhook alerts.
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
                 interval: int = 60, action: str = "BUY", quantity: int = 1):
        """
        Add a scan to monitor

        Args:
            scan_name: Unique name for this scan
            scan_url: Chartink screener URL (e.g., https://chartink.com/screener/your-scan)
            scan_condition: Raw scan condition string (alternative to URL)
            interval: Scan interval in seconds (default: 60)
            action: Action to take when stock appears (BUY/SELL)
            quantity: Quantity to trade
        """
        self.active_scans[scan_name] = {
            'url': scan_url,
            'condition': scan_condition,
            'interval': interval,
            'action': action,
            'quantity': quantity,
            'last_results': set(),
            'last_scan': None
        }
        logger.info(f"Added Chartink scan: {scan_name}")

    def remove_scan(self, scan_name: str):
        """Remove a scan from monitoring"""
        if scan_name in self.active_scans:
            del self.active_scans[scan_name]
            logger.info(f"Removed Chartink scan: {scan_name}")

    def get_scan_condition_from_url(self, url: str) -> Optional[str]:
        """
        Extract scan condition from Chartink URL
        """
        try:
            # Get the page to extract CSRF token and scan condition
            response = self._session.get(url)

            if response.status_code != 200:
                logger.error(f"Failed to fetch Chartink URL: {response.status_code}")
                return None

            # Extract scan condition from page
            # Chartink stores scan condition in a hidden input or JavaScript
            html = response.text

            # Try to find scan condition in the page
            import re

            # Look for scan condition in various formats
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
        """
        Run a specific scan and return results
        """
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

            # Extract CSRF token from cookies or page
            csrf_token = self._session.cookies.get('XSRF-TOKEN', '')

            # Run the scan
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

            # Parse results
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
        """
        Check for new stocks in scan results (not seen before)
        """
        scan_config = self.active_scans[scan_name]
        current_results = self.run_scan(scan_name)

        # Get symbols from current results
        current_symbols = {alert.symbol for alert in current_results}

        # Find new symbols (not in last results)
        last_symbols = scan_config.get('last_results', set())
        new_symbols = current_symbols - last_symbols

        # Update last results
        scan_config['last_results'] = current_symbols
        scan_config['last_scan'] = datetime.now()

        # Filter alerts to only new ones
        new_alerts = [alert for alert in current_results if alert.symbol in new_symbols]

        return new_alerts

    def _monitoring_loop(self):
        """Background monitoring loop"""
        logger.info("Chartink monitoring started")

        while self._running:
            for scan_name, scan_config in list(self.active_scans.items()):
                try:
                    # Check if it's time to run this scan
                    last_scan = scan_config.get('last_scan')
                    interval = scan_config.get('interval', 60)

                    if last_scan is None or (datetime.now() - last_scan).seconds >= interval:
                        new_alerts = self._check_for_new_alerts(scan_name)

                        # Notify callbacks for new alerts
                        for alert in new_alerts:
                            logger.info(f"New Chartink alert: {alert.symbol} from {scan_name}")
                            for callback in self.alert_callbacks:
                                try:
                                    callback(alert)
                                except Exception as e:
                                    logger.error(f"Alert callback error: {e}")

                except Exception as e:
                    logger.error(f"Error in scan '{scan_name}': {e}")

            # Sleep between scan cycles
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
                'stocks_count': len(config.get('last_results', set()))
            }
            for name, config in self.active_scans.items()
        ]

    def test_scan(self, scan_url: str) -> List[Dict]:
        """
        Test a scan URL and return results (for validation)
        """
        # Add temporary scan
        temp_name = f"_test_{int(time.time())}"
        self.add_scan(temp_name, scan_url=scan_url)

        # Run scan
        alerts = self.run_scan(temp_name)

        # Remove temporary scan
        self.remove_scan(temp_name)

        # Return results as dict
        return [
            {
                'symbol': alert.symbol,
                'price': alert.price,
                'volume': alert.volume,
                'change_percent': alert.change_percent
            }
            for alert in alerts
        ]
