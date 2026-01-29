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

    def send_alert(self, message: str):
        """Send a generic alert message"""
        if not self.enabled:
            return
        self._send_async(message)

    def is_enabled(self) -> bool:
        """Check if alerts are enabled"""
        return self.enabled


class TelegramBotController:
    """
    Telegram Bot Controller for remote algo management

    Commands:
    /status - Get current algo status, positions, P&L
    /positions - List all open positions
    /orders - List pending orders
    /pnl - Get current P&L
    /squareoff - Square off all positions
    /pause - Pause algo trading
    /resume - Resume algo trading
    /help - Show available commands
    """

    BASE_URL = "https://api.telegram.org/bot{token}"

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._running = False
        self._thread = None
        self._last_update_id = 0

        # Callbacks for commands
        self._command_handlers = {}
        self._status_callback = None
        self._positions_callback = None
        self._orders_callback = None
        self._pnl_callback = None
        self._squareoff_callback = None
        self._pause_callback = None
        self._resume_callback = None

        # State
        self.algo_paused = False

    def configure(self, bot_token: str, chat_id: str):
        """Configure bot credentials"""
        self.bot_token = bot_token
        self.chat_id = chat_id

    def register_status_callback(self, callback):
        """Register callback for /status command"""
        self._status_callback = callback

    def register_positions_callback(self, callback):
        """Register callback for /positions command"""
        self._positions_callback = callback

    def register_orders_callback(self, callback):
        """Register callback for /orders command"""
        self._orders_callback = callback

    def register_pnl_callback(self, callback):
        """Register callback for /pnl command"""
        self._pnl_callback = callback

    def register_squareoff_callback(self, callback):
        """Register callback for /squareoff command"""
        self._squareoff_callback = callback

    def register_pause_callback(self, callback):
        """Register callback for /pause command"""
        self._pause_callback = callback

    def register_resume_callback(self, callback):
        """Register callback for /resume command"""
        self._resume_callback = callback

    def start_listening(self):
        """Start listening for bot commands"""
        if not self.bot_token or not self.chat_id:
            logger.warning("Bot not configured")
            return False

        self._running = True

        def poll_loop():
            while self._running:
                try:
                    self._poll_updates()
                except Exception as e:
                    logger.error(f"Telegram poll error: {e}")
                threading.Event().wait(2)  # Poll every 2 seconds

        self._thread = threading.Thread(target=poll_loop, daemon=True)
        self._thread.start()
        logger.info("Telegram bot controller started")
        return True

    def stop_listening(self):
        """Stop listening for commands"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Telegram bot controller stopped")

    def _poll_updates(self):
        """Poll for new messages"""
        try:
            url = f"{self.BASE_URL.format(token=self.bot_token)}/getUpdates"
            params = {
                'offset': self._last_update_id + 1,
                'timeout': 1
            }
            response = requests.get(url, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data.get('result'):
                    for update in data['result']:
                        self._last_update_id = update['update_id']
                        self._handle_update(update)

        except Exception as e:
            logger.debug(f"Poll error: {e}")

    def _handle_update(self, update: Dict):
        """Handle incoming update"""
        message = update.get('message', {})
        text = message.get('text', '')
        chat_id = str(message.get('chat', {}).get('id', ''))

        # Only respond to configured chat
        if chat_id != str(self.chat_id):
            return

        # Handle commands
        if text.startswith('/'):
            command = text.split()[0].lower()
            self._handle_command(command, text)

    def _handle_command(self, command: str, full_text: str):
        """Handle bot command"""
        logger.info(f"Telegram command: {command}")

        if command == '/help':
            self._send_help()

        elif command == '/status':
            self._send_status()

        elif command == '/positions':
            self._send_positions()

        elif command == '/orders':
            self._send_orders()

        elif command == '/pnl':
            self._send_pnl()

        elif command == '/squareoff':
            self._handle_squareoff()

        elif command == '/pause':
            self._handle_pause()

        elif command == '/resume':
            self._handle_resume()

        elif command == '/start':
            self._send_welcome()

        else:
            self._send_message("❓ Unknown command. Type /help for available commands.")

    def _send_message(self, text: str):
        """Send message to chat"""
        try:
            url = f"{self.BASE_URL.format(token=self.bot_token)}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Send message error: {e}")

    def _send_welcome(self):
        """Send welcome message"""
        self._send_message("""
🤖 <b>Algo Trader Bot</b>

Welcome! I can help you control your algo trading remotely.

Type /help to see available commands.

🕐 {time}
""".format(time=datetime.now().strftime('%H:%M:%S')))

    def _send_help(self):
        """Send help message with available commands"""
        self._send_message("""
🤖 <b>Algo Trader Commands</b>

📊 <b>Monitoring:</b>
/status - Current algo status
/positions - Open positions
/orders - Pending orders
/pnl - Current P&L

⚙️ <b>Control:</b>
/pause - Pause trading
/resume - Resume trading
/squareoff - Square off all

❓ /help - Show this message
""")

    def _send_status(self):
        """Send algo status"""
        if self._status_callback:
            try:
                status = self._status_callback()
                self._send_message(status)
                return
            except Exception as e:
                logger.error(f"Status callback error: {e}")

        # Default status
        status_emoji = "⏸️" if self.algo_paused else "▶️"
        self._send_message(f"""
📊 <b>Algo Status</b>

{status_emoji} Status: {'PAUSED' if self.algo_paused else 'RUNNING'}
🕐 Time: {datetime.now().strftime('%H:%M:%S')}
""")

    def _send_positions(self):
        """Send positions list"""
        if self._positions_callback:
            try:
                positions = self._positions_callback()
                self._send_message(positions)
                return
            except Exception as e:
                logger.error(f"Positions callback error: {e}")

        self._send_message("📈 No positions data available")

    def _send_orders(self):
        """Send orders list"""
        if self._orders_callback:
            try:
                orders = self._orders_callback()
                self._send_message(orders)
                return
            except Exception as e:
                logger.error(f"Orders callback error: {e}")

        self._send_message("📋 No orders data available")

    def _send_pnl(self):
        """Send P&L"""
        if self._pnl_callback:
            try:
                pnl = self._pnl_callback()
                self._send_message(pnl)
                return
            except Exception as e:
                logger.error(f"PnL callback error: {e}")

        self._send_message("💰 No P&L data available")

    def _handle_squareoff(self):
        """Handle square off command"""
        if self._squareoff_callback:
            try:
                result = self._squareoff_callback()
                self._send_message(f"""
🛑 <b>Square Off Triggered</b>

{result}

🕐 Time: {datetime.now().strftime('%H:%M:%S')}
""")
                return
            except Exception as e:
                logger.error(f"Squareoff callback error: {e}")
                self._send_message(f"❌ Square off failed: {e}")
        else:
            self._send_message("⚠️ Square off not configured")

    def _handle_pause(self):
        """Handle pause command"""
        self.algo_paused = True
        if self._pause_callback:
            try:
                self._pause_callback()
            except Exception as e:
                logger.error(f"Pause callback error: {e}")

        self._send_message("""
⏸️ <b>Algo Trading PAUSED</b>

No new trades will be executed.
Existing positions are still monitored.

Type /resume to continue trading.
""")

    def _handle_resume(self):
        """Handle resume command"""
        self.algo_paused = False
        if self._resume_callback:
            try:
                self._resume_callback()
            except Exception as e:
                logger.error(f"Resume callback error: {e}")

        self._send_message("""
▶️ <b>Algo Trading RESUMED</b>

Trading is now active.
""")

    def is_paused(self) -> bool:
        """Check if algo is paused via Telegram"""
        return self.algo_paused
