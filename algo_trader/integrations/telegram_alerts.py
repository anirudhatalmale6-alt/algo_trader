"""
Telegram Alert Integration
Sends trade alerts and notifications to Telegram
"""
import requests
import threading
from typing import Optional, Dict, Any
from datetime import datetime
from loguru import logger


class TelegramAlerts:
    """
    Telegram Alert System

    Sends trading alerts to a Telegram bot.
    User needs to create a bot via @BotFather and get chat_id.
    """

    API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = False
        self._lock = threading.Lock()

    def configure(self, bot_token: str, chat_id: str):
        """Configure Telegram bot credentials"""
        self.bot_token = bot_token
        self.chat_id = chat_id
        logger.info("Telegram alerts configured")

    def enable(self):
        """Enable Telegram alerts"""
        if not self.bot_token or not self.chat_id:
            logger.warning("Cannot enable Telegram alerts - missing credentials")
            return False
        self.enabled = True
        logger.info("Telegram alerts enabled")
        return True

    def disable(self):
        """Disable Telegram alerts"""
        self.enabled = False
        logger.info("Telegram alerts disabled")

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured"""
        return bool(self.bot_token and self.chat_id)

    def test_connection(self) -> bool:
        """Test Telegram connection by sending a test message"""
        if not self.is_configured():
            return False

        try:
            result = self._send_message("🔔 Algo Trader: Test message - Connection successful!")
            return result
        except Exception as e:
            logger.error(f"Telegram test failed: {e}")
            return False

    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram"""
        if not self.is_configured():
            return False

        try:
            url = self.API_URL.format(token=self.bot_token)
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def _send_async(self, text: str):
        """Send message asynchronously"""
        thread = threading.Thread(target=self._send_message, args=(text,), daemon=True)
        thread.start()

    def send_trade_alert(self, action: str, symbol: str, quantity: int,
                         price: float = None, source: str = None):
        """Send trade execution alert"""
        if not self.enabled:
            return

        emoji = "🟢" if action.upper() == "BUY" else "🔴"
        price_str = f"₹{price:.2f}" if price else "Market"
        source_str = f"\n📊 Source: {source}" if source else ""

        message = f"""
{emoji} <b>Trade Executed</b>

📈 <b>{action.upper()}</b> {symbol}
📦 Quantity: {quantity}
💰 Price: {price_str}{source_str}
🕐 Time: {datetime.now().strftime('%H:%M:%S')}
"""
        self._send_async(message.strip())

    def send_signal_alert(self, signal_type: str, symbol: str, strategy: str = None):
        """Send strategy signal alert"""
        if not self.enabled:
            return

        emoji = "📈" if signal_type.upper() == "BUY" else "📉"
        strategy_str = f"\n📊 Strategy: {strategy}" if strategy else ""

        message = f"""
{emoji} <b>Signal Alert</b>

🎯 <b>{signal_type.upper()}</b> Signal for {symbol}{strategy_str}
🕐 Time: {datetime.now().strftime('%H:%M:%S')}
"""
        self._send_async(message.strip())

    def send_chartink_alert(self, symbol: str, scan_name: str,
                            action: str, price: float = None):
        """Send Chartink scanner alert"""
        if not self.enabled:
            return

        emoji = "🟢" if action.upper() == "BUY" else "🔴"
        price_str = f"₹{price:.2f}" if price else "N/A"

        message = f"""
{emoji} <b>Chartink Alert</b>

📊 Scanner: {scan_name}
📈 Stock: {symbol}
🎯 Action: {action.upper()}
💰 Price: {price_str}
🕐 Time: {datetime.now().strftime('%H:%M:%S')}
"""
        self._send_async(message.strip())

    def send_option_alert(self, action: str, symbol: str, strike: float,
                          option_type: str, expiry: str, premium: float = None):
        """Send options trade alert"""
        if not self.enabled:
            return

        emoji = "🟢" if action.upper() == "BUY" else "🔴"
        premium_str = f"₹{premium:.2f}" if premium else "Market"

        message = f"""
{emoji} <b>Options Trade</b>

📈 <b>{action.upper()}</b> {symbol}
🎯 Strike: {strike} {option_type}
📅 Expiry: {expiry}
💰 Premium: {premium_str}
🕐 Time: {datetime.now().strftime('%H:%M:%S')}
"""
        self._send_async(message.strip())

    def send_sl_hit_alert(self, symbol: str, sl_type: str, pnl: float):
        """Send stop loss hit alert"""
        if not self.enabled:
            return

        pnl_emoji = "🟢" if pnl >= 0 else "🔴"

        message = f"""
🛑 <b>Stop Loss Hit</b>

📈 Symbol: {symbol}
📊 Type: {sl_type}
{pnl_emoji} P&L: ₹{pnl:+.2f}
🕐 Time: {datetime.now().strftime('%H:%M:%S')}
"""
        self._send_async(message.strip())

    def send_target_hit_alert(self, symbol: str, pnl: float):
        """Send target hit alert"""
        if not self.enabled:
            return

        message = f"""
🎯 <b>Target Hit!</b>

📈 Symbol: {symbol}
🟢 Profit: ₹{pnl:+.2f}
🕐 Time: {datetime.now().strftime('%H:%M:%S')}
"""
        self._send_async(message.strip())

    def send_daily_summary(self, total_trades: int, total_pnl: float,
                           winning_trades: int, losing_trades: int):
        """Send end of day summary"""
        if not self.enabled:
            return

        pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        message = f"""
📊 <b>Daily Summary</b>

📈 Total Trades: {total_trades}
✅ Winning: {winning_trades}
❌ Losing: {losing_trades}
📊 Win Rate: {win_rate:.1f}%
{pnl_emoji} Net P&L: ₹{total_pnl:+.2f}

🕐 {datetime.now().strftime('%d-%m-%Y %H:%M')}
"""
        self._send_async(message.strip())

    def send_error_alert(self, error_message: str):
        """Send error notification"""
        if not self.enabled:
            return

        message = f"""
⚠️ <b>Error Alert</b>

{error_message}

🕐 Time: {datetime.now().strftime('%H:%M:%S')}
"""
        self._send_async(message.strip())
