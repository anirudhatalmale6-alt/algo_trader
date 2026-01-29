"""
Alert Manager - Price and Indicator Alerts
"""
import threading
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from loguru import logger


class AlertType(Enum):
    PRICE_ABOVE = "PRICE_ABOVE"
    PRICE_BELOW = "PRICE_BELOW"
    PRICE_CROSS_UP = "PRICE_CROSS_UP"  # Price crosses above a level
    PRICE_CROSS_DOWN = "PRICE_CROSS_DOWN"  # Price crosses below a level
    RSI_OVERBOUGHT = "RSI_OVERBOUGHT"  # RSI > 70
    RSI_OVERSOLD = "RSI_OVERSOLD"  # RSI < 30
    MACD_BULLISH = "MACD_BULLISH"  # MACD crosses above signal
    MACD_BEARISH = "MACD_BEARISH"  # MACD crosses below signal
    SUPERTREND_BUY = "SUPERTREND_BUY"
    SUPERTREND_SELL = "SUPERTREND_SELL"
    PERCENT_CHANGE = "PERCENT_CHANGE"  # Price moves by X%


class AlertStatus(Enum):
    ACTIVE = "ACTIVE"
    TRIGGERED = "TRIGGERED"
    EXPIRED = "EXPIRED"
    DISABLED = "DISABLED"


@dataclass
class Alert:
    """Represents a price or indicator alert"""
    id: str
    symbol: str
    exchange: str
    alert_type: AlertType
    target_value: float  # Price level or indicator value
    message: str = ""
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: datetime = None
    triggered_at: datetime = None
    repeat: bool = False  # Alert once or repeat
    notification_channels: List[str] = field(default_factory=lambda: ["app", "telegram"])

    # For cross alerts, track previous value
    previous_value: float = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class AlertManager:
    """
    Manages price and indicator alerts

    Features:
    - Price alerts (above/below/cross)
    - Indicator alerts (RSI, MACD, Supertrend)
    - Multiple notification channels
    - Persistent storage
    """

    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self._alert_counter = 0
        self._running = False
        self._thread = None
        self._price_feed = None
        self._lock = threading.Lock()

        # Callbacks
        self.alert_callbacks: List[Callable] = []

        # Telegram integration
        self.telegram = None

    def register_callback(self, callback: Callable):
        """Register callback for alert triggers"""
        self.alert_callbacks.append(callback)

    def set_telegram(self, telegram):
        """Set Telegram integration for notifications"""
        self.telegram = telegram

    def create_price_alert(self, symbol: str, alert_type: str, price: float,
                           exchange: str = "NSE", message: str = "",
                           repeat: bool = False) -> Alert:
        """
        Create a price alert

        Args:
            symbol: Stock symbol
            alert_type: "above", "below", "cross_up", "cross_down"
            price: Target price level
            exchange: Exchange
            message: Custom message
            repeat: Alert every time or just once
        """
        alert_type_map = {
            "above": AlertType.PRICE_ABOVE,
            "below": AlertType.PRICE_BELOW,
            "cross_up": AlertType.PRICE_CROSS_UP,
            "cross_down": AlertType.PRICE_CROSS_DOWN,
        }

        alert_enum = alert_type_map.get(alert_type.lower(), AlertType.PRICE_ABOVE)

        with self._lock:
            self._alert_counter += 1
            alert_id = f"ALERT_{self._alert_counter:04d}"

            alert = Alert(
                id=alert_id,
                symbol=symbol.upper(),
                exchange=exchange,
                alert_type=alert_enum,
                target_value=price,
                message=message or f"{symbol} {alert_type} ₹{price:.2f}",
                repeat=repeat
            )

            self.alerts[alert_id] = alert
            logger.info(f"Created alert: {alert_id} - {alert.message}")

            return alert

    def create_indicator_alert(self, symbol: str, indicator: str,
                                condition: str = None, value: float = None,
                                exchange: str = "NSE", message: str = "") -> Alert:
        """
        Create an indicator alert

        Args:
            symbol: Stock symbol
            indicator: "rsi", "macd", "supertrend"
            condition: For RSI: "overbought", "oversold"
                      For MACD: "bullish", "bearish"
                      For Supertrend: "buy", "sell"
            value: Custom threshold (e.g., RSI 80 instead of default 70)
            exchange: Exchange
            message: Custom message
        """
        indicator_map = {
            ("rsi", "overbought"): (AlertType.RSI_OVERBOUGHT, 70),
            ("rsi", "oversold"): (AlertType.RSI_OVERSOLD, 30),
            ("macd", "bullish"): (AlertType.MACD_BULLISH, 0),
            ("macd", "bearish"): (AlertType.MACD_BEARISH, 0),
            ("supertrend", "buy"): (AlertType.SUPERTREND_BUY, 0),
            ("supertrend", "sell"): (AlertType.SUPERTREND_SELL, 0),
        }

        key = (indicator.lower(), condition.lower() if condition else "")
        alert_type, default_value = indicator_map.get(key, (AlertType.RSI_OVERBOUGHT, 70))

        target_value = value if value is not None else default_value

        with self._lock:
            self._alert_counter += 1
            alert_id = f"ALERT_{self._alert_counter:04d}"

            alert = Alert(
                id=alert_id,
                symbol=symbol.upper(),
                exchange=exchange,
                alert_type=alert_type,
                target_value=target_value,
                message=message or f"{symbol} {indicator.upper()} {condition}",
                repeat=True  # Indicator alerts usually repeat
            )

            self.alerts[alert_id] = alert
            logger.info(f"Created indicator alert: {alert_id} - {alert.message}")

            return alert

    def create_percent_change_alert(self, symbol: str, percent: float,
                                     exchange: str = "NSE", message: str = "") -> Alert:
        """Create alert when price moves by X%"""
        with self._lock:
            self._alert_counter += 1
            alert_id = f"ALERT_{self._alert_counter:04d}"

            alert = Alert(
                id=alert_id,
                symbol=symbol.upper(),
                exchange=exchange,
                alert_type=AlertType.PERCENT_CHANGE,
                target_value=percent,
                message=message or f"{symbol} moves {percent}%",
                repeat=True
            )

            self.alerts[alert_id] = alert
            logger.info(f"Created % change alert: {alert_id}")

            return alert

    def delete_alert(self, alert_id: str):
        """Delete an alert"""
        with self._lock:
            if alert_id in self.alerts:
                del self.alerts[alert_id]
                logger.info(f"Deleted alert: {alert_id}")

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID"""
        return self.alerts.get(alert_id)

    def get_all_alerts(self) -> List[Alert]:
        """Get all alerts"""
        return list(self.alerts.values())

    def get_active_alerts(self) -> List[Alert]:
        """Get only active alerts"""
        return [a for a in self.alerts.values() if a.status == AlertStatus.ACTIVE]

    def get_alerts_for_symbol(self, symbol: str) -> List[Alert]:
        """Get alerts for a specific symbol"""
        return [a for a in self.alerts.values() if a.symbol == symbol.upper()]

    def disable_alert(self, alert_id: str):
        """Disable an alert"""
        if alert_id in self.alerts:
            self.alerts[alert_id].status = AlertStatus.DISABLED
            logger.info(f"Disabled alert: {alert_id}")

    def enable_alert(self, alert_id: str):
        """Enable a disabled alert"""
        if alert_id in self.alerts:
            self.alerts[alert_id].status = AlertStatus.ACTIVE
            logger.info(f"Enabled alert: {alert_id}")

    def check_price_alert(self, alert: Alert, current_price: float) -> bool:
        """Check if a price alert should trigger"""
        if alert.status != AlertStatus.ACTIVE:
            return False

        triggered = False

        if alert.alert_type == AlertType.PRICE_ABOVE:
            triggered = current_price >= alert.target_value

        elif alert.alert_type == AlertType.PRICE_BELOW:
            triggered = current_price <= alert.target_value

        elif alert.alert_type == AlertType.PRICE_CROSS_UP:
            if alert.previous_value is not None:
                triggered = (alert.previous_value < alert.target_value and
                            current_price >= alert.target_value)
            alert.previous_value = current_price

        elif alert.alert_type == AlertType.PRICE_CROSS_DOWN:
            if alert.previous_value is not None:
                triggered = (alert.previous_value > alert.target_value and
                            current_price <= alert.target_value)
            alert.previous_value = current_price

        return triggered

    def check_indicator_alert(self, alert: Alert, indicator_value: float,
                               signal_value: float = None) -> bool:
        """Check if an indicator alert should trigger"""
        if alert.status != AlertStatus.ACTIVE:
            return False

        triggered = False

        if alert.alert_type == AlertType.RSI_OVERBOUGHT:
            triggered = indicator_value >= alert.target_value

        elif alert.alert_type == AlertType.RSI_OVERSOLD:
            triggered = indicator_value <= alert.target_value

        elif alert.alert_type == AlertType.MACD_BULLISH:
            if alert.previous_value is not None and signal_value is not None:
                # MACD crossed above signal line
                triggered = (alert.previous_value < signal_value and
                            indicator_value >= signal_value)
            alert.previous_value = indicator_value

        elif alert.alert_type == AlertType.MACD_BEARISH:
            if alert.previous_value is not None and signal_value is not None:
                # MACD crossed below signal line
                triggered = (alert.previous_value > signal_value and
                            indicator_value <= signal_value)
            alert.previous_value = indicator_value

        return triggered

    def trigger_alert(self, alert: Alert, current_value: float):
        """Handle alert trigger"""
        alert.triggered_at = datetime.now()

        if not alert.repeat:
            alert.status = AlertStatus.TRIGGERED

        logger.warning(f"ALERT TRIGGERED: {alert.message} (Current: {current_value:.2f})")

        # Notify callbacks
        event_data = {
            'alert_id': alert.id,
            'symbol': alert.symbol,
            'alert_type': alert.alert_type.value,
            'target_value': alert.target_value,
            'current_value': current_value,
            'message': alert.message,
            'timestamp': alert.triggered_at
        }

        for callback in self.alert_callbacks:
            try:
                callback(event_data)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

        # Send Telegram notification
        if self.telegram and self.telegram.is_enabled():
            self._send_telegram_alert(alert, current_value)

    def _send_telegram_alert(self, alert: Alert, current_value: float):
        """Send alert notification via Telegram"""
        emoji = "🔔"
        if "BUY" in alert.alert_type.value or "BULLISH" in alert.alert_type.value:
            emoji = "🟢"
        elif "SELL" in alert.alert_type.value or "BEARISH" in alert.alert_type.value:
            emoji = "🔴"

        message = f"""
{emoji} <b>Alert Triggered!</b>

📈 Symbol: {alert.symbol}
🎯 Condition: {alert.alert_type.value}
📊 Target: {alert.target_value:.2f}
💰 Current: {current_value:.2f}

📝 {alert.message}
🕐 Time: {datetime.now().strftime('%H:%M:%S')}
"""
        self.telegram._send_async(message.strip())

    def update_price(self, symbol: str, current_price: float, exchange: str = "NSE"):
        """Update price and check alerts for a symbol"""
        symbol = symbol.upper()

        for alert in self.get_alerts_for_symbol(symbol):
            if alert.exchange != exchange:
                continue

            if alert.alert_type in [AlertType.PRICE_ABOVE, AlertType.PRICE_BELOW,
                                    AlertType.PRICE_CROSS_UP, AlertType.PRICE_CROSS_DOWN]:
                if self.check_price_alert(alert, current_price):
                    self.trigger_alert(alert, current_price)

    def update_indicator(self, symbol: str, indicator: str, value: float,
                         signal_value: float = None, exchange: str = "NSE"):
        """Update indicator value and check alerts"""
        symbol = symbol.upper()

        indicator_types = {
            "rsi": [AlertType.RSI_OVERBOUGHT, AlertType.RSI_OVERSOLD],
            "macd": [AlertType.MACD_BULLISH, AlertType.MACD_BEARISH],
            "supertrend": [AlertType.SUPERTREND_BUY, AlertType.SUPERTREND_SELL]
        }

        relevant_types = indicator_types.get(indicator.lower(), [])

        for alert in self.get_alerts_for_symbol(symbol):
            if alert.exchange != exchange:
                continue
            if alert.alert_type not in relevant_types:
                continue

            if self.check_indicator_alert(alert, value, signal_value):
                self.trigger_alert(alert, value)

    def start_monitoring(self, price_feed=None, interval: float = 2.0):
        """Start background monitoring for price alerts"""
        self._price_feed = price_feed
        self._running = True

        def monitor_loop():
            while self._running:
                if self._price_feed:
                    # Get unique symbols from active alerts
                    symbols = set(a.symbol for a in self.get_active_alerts())

                    for symbol in symbols:
                        try:
                            quote = self._price_feed.get_quote(symbol, "NSE")
                            if quote and 'ltp' in quote:
                                self.update_price(symbol, quote['ltp'], "NSE")
                        except Exception as e:
                            logger.error(f"Alert monitor error for {symbol}: {e}")

                time.sleep(interval)

        self._thread = threading.Thread(target=monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Alert monitoring started")

    def stop_monitoring(self):
        """Stop background monitoring"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Alert monitoring stopped")

    def get_summary(self) -> Dict:
        """Get alert summary"""
        alerts = self.get_all_alerts()
        return {
            'total': len(alerts),
            'active': len([a for a in alerts if a.status == AlertStatus.ACTIVE]),
            'triggered': len([a for a in alerts if a.status == AlertStatus.TRIGGERED]),
            'disabled': len([a for a in alerts if a.status == AlertStatus.DISABLED])
        }
