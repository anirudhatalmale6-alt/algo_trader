"""
Auto Options Executor - Bridges Pine Script signals to Options trading
When a strategy generates BUY/SELL signal, automatically creates option positions
with configured strike selection, expiry, SL/TSL/Target
"""
from typing import Dict, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from loguru import logger


class StrikeSelection(Enum):
    ATM = "ATM"              # At the Money
    OTM_1 = "OTM +1"        # 1 strike OTM
    OTM_2 = "OTM +2"        # 2 strikes OTM
    OTM_3 = "OTM +3"        # 3 strikes OTM
    ITM_1 = "ITM -1"        # 1 strike ITM
    ITM_2 = "ITM -2"        # 2 strikes ITM


class SignalAction(Enum):
    BUY_CE = "BUY CE"           # Buy Call on BUY signal
    BUY_PE = "BUY PE"           # Buy Put on SELL signal
    SELL_CE = "SELL CE"         # Sell Call
    SELL_PE = "SELL PE"         # Sell Put
    STRADDLE = "Straddle"       # Sell ATM CE + PE
    STRANGLE = "Strangle"       # Sell OTM CE + PE


class ExpirySelection(Enum):
    CURRENT_WEEK = "Current Week"
    NEXT_WEEK = "Next Week"
    CURRENT_MONTH = "Current Month"


@dataclass
class AutoOptionsConfig:
    """Configuration for auto-options execution"""
    enabled: bool = False
    symbol: str = "NIFTY"             # Underlying symbol

    # What to do on BUY signal
    buy_signal_action: str = "BUY CE"    # Action from SignalAction
    # What to do on SELL signal
    sell_signal_action: str = "BUY PE"   # Action from SignalAction

    # Strike selection
    strike_selection: str = "ATM"

    # Expiry
    expiry_selection: str = "Current Week"

    # Quantity
    quantity: int = 1                    # Number of lots

    # Exit settings
    exit_type: str = "P&L Based"
    sl_value: float = 0.0               # SL (₹ or %)
    target_value: float = 0.0           # Target (₹ or %)
    tsl_value: float = 0.0              # Trailing SL

    # Auto close on opposite signal
    close_on_opposite: bool = True       # Close existing on opposite signal


class AutoOptionsExecutor:
    """
    Listens to strategy signals and auto-executes options trades.

    Flow:
    1. Pine Script strategy generates BUY/SELL signal
    2. AutoOptionsExecutor receives signal via callback
    3. Based on config: selects strike, expiry, action
    4. Creates option position via OptionsManager
    5. Applies SL/TSL/Target from config
    """

    def __init__(self, options_manager, strategy_engine=None):
        self.options_manager = options_manager
        self.strategy_engine = strategy_engine
        self.config = AutoOptionsConfig()
        self._broker = None
        self._trade_log: List[Dict] = []
        self._on_trade_callbacks: List[Callable] = []

        # Register with strategy engine
        if strategy_engine:
            strategy_engine.register_signal_callback(self._on_signal)

    def register_trade_callback(self, callback: Callable):
        """Register callback for when auto-trade is executed"""
        self._on_trade_callbacks.append(callback)

    def set_broker(self, broker):
        """Set the broker for fetching spot price"""
        self._broker = broker

    def update_config(self, **kwargs):
        """Update config values"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    def enable(self):
        """Enable auto-options execution"""
        self.config.enabled = True
        logger.info("Auto-options execution ENABLED")

    def disable(self):
        """Disable auto-options execution"""
        self.config.enabled = False
        logger.info("Auto-options execution DISABLED")

    def _on_signal(self, signal):
        """Handle incoming strategy signal"""
        if not self.config.enabled:
            return

        signal_type = signal.signal_type.value  # "BUY" or "SELL"
        logger.info(f"Auto-Options received signal: {signal_type} from {signal.strategy_name}")

        try:
            if signal_type == "BUY":
                action_str = self.config.buy_signal_action
            elif signal_type in ("SELL", "EXIT_LONG"):
                action_str = self.config.sell_signal_action
            else:
                logger.info(f"Ignoring signal type: {signal_type}")
                return

            # Close opposite positions if configured
            if self.config.close_on_opposite:
                self._close_existing_positions(signal_type)

            # Get spot price
            spot_price = self._get_spot_price(signal)

            if spot_price <= 0:
                logger.error("Could not determine spot price for auto-options")
                return

            # Get expiry
            expiry = self._get_expiry()
            if not expiry:
                logger.error("Could not determine expiry date")
                return

            # Get strike price
            strike = self._get_strike(spot_price)

            # Determine option type and action
            opt_type, trade_action = self._parse_action(action_str)

            # Check if it's a hedge strategy
            if action_str in ("Straddle", "Strangle"):
                self._execute_hedge(action_str, expiry, spot_price, signal)
            else:
                self._execute_single(opt_type, trade_action, strike, expiry, signal, spot_price)

        except Exception as e:
            logger.error(f"Auto-options execution error: {e}")

    def _get_spot_price(self, signal) -> float:
        """Get current spot price"""
        # Try signal price first
        if signal.price and signal.price > 0:
            return signal.price

        # Try fetching from broker
        if self._broker:
            try:
                quote = self._broker.get_quote(self.config.symbol, "NSE")
                if quote:
                    ltp = quote.get('last_price') or quote.get('ltp') or 0
                    if isinstance(ltp, dict):
                        ltp = ltp.get('last_price', 0)
                    return float(ltp)
            except Exception as e:
                logger.error(f"Error fetching spot: {e}")

        return 0.0

    def _get_expiry(self) -> Optional[str]:
        """Get expiry date based on config"""
        expiries = self.options_manager.get_expiry_dates(self.config.symbol)
        if not expiries:
            return None

        exp_sel = self.config.expiry_selection
        if exp_sel == "Current Week":
            return expiries[0]  # Nearest expiry
        elif exp_sel == "Next Week" and len(expiries) > 1:
            return expiries[1]
        elif exp_sel == "Current Month":
            return expiries[-1]  # Last expiry is monthly
        return expiries[0]

    def _get_strike(self, spot_price: float) -> float:
        """Get strike price based on config"""
        from algo_trader.core.options_manager import INDEX_STRIKE_GAPS

        gap = INDEX_STRIKE_GAPS.get(self.config.symbol.upper(), 50)
        atm = round(spot_price / gap) * gap

        sel = self.config.strike_selection
        if sel == "ATM":
            return atm
        elif sel == "OTM +1":
            return atm + gap
        elif sel == "OTM +2":
            return atm + (gap * 2)
        elif sel == "OTM +3":
            return atm + (gap * 3)
        elif sel == "ITM -1":
            return atm - gap
        elif sel == "ITM -2":
            return atm - (gap * 2)
        return atm

    def _parse_action(self, action_str: str):
        """Parse action string to option type and buy/sell"""
        action_map = {
            "BUY CE": ("CE", "BUY"),
            "BUY PE": ("PE", "BUY"),
            "SELL CE": ("CE", "SELL"),
            "SELL PE": ("PE", "SELL"),
        }
        return action_map.get(action_str, ("CE", "BUY"))

    def _execute_single(self, opt_type, trade_action, strike, expiry, signal, spot_price):
        """Execute a single option trade"""
        # For PE on sell signal, adjust strike for OTM
        if opt_type == "PE" and self.config.strike_selection.startswith("OTM"):
            from algo_trader.core.options_manager import INDEX_STRIKE_GAPS
            gap = INDEX_STRIKE_GAPS.get(self.config.symbol.upper(), 50)
            atm = round(spot_price / gap) * gap
            offset = int(self.config.strike_selection.split("+")[-1]) if "+" in self.config.strike_selection else 0
            strike = atm - (gap * offset)  # OTM for PE is below ATM

        # Estimate premium (use 0 if can't fetch - will be updated on first price feed)
        entry_premium = self._estimate_premium(strike, opt_type, expiry)

        position = self.options_manager.create_single_option(
            symbol=self.config.symbol,
            expiry=expiry,
            strike=strike,
            option_type=opt_type,
            action=trade_action,
            quantity=self.config.quantity,
            entry_price=entry_premium,
            exit_type=self.config.exit_type,
            sl_value=self.config.sl_value,
            target_value=self.config.target_value,
            tsl_value=self.config.tsl_value
        )

        trade_info = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "signal": signal.signal_type.value,
            "strategy": signal.strategy_name,
            "action": f"{trade_action} {self.config.symbol} {int(strike)}{opt_type}",
            "expiry": expiry,
            "qty": self.config.quantity,
            "premium": entry_premium,
            "position_id": position.position_id
        }

        self._trade_log.append(trade_info)
        logger.info(f"Auto-option executed: {trade_info['action']}")

        for cb in self._on_trade_callbacks:
            try:
                cb(trade_info)
            except Exception as e:
                logger.error(f"Trade callback error: {e}")

    def _execute_hedge(self, strategy_name, expiry, spot_price, signal):
        """Execute a hedge strategy"""
        entry_premium = self._estimate_premium(
            round(spot_price / 50) * 50, "CE", expiry
        )

        entry_prices = {
            "ce": entry_premium,
            "pe": entry_premium,
            "sell_ce": entry_premium,
            "sell_pe": entry_premium,
            "buy_ce": entry_premium * 0.5,
            "buy_pe": entry_premium * 0.5,
        }

        position = self.options_manager.create_hedge_strategy(
            symbol=self.config.symbol,
            strategy=strategy_name,
            expiry=expiry,
            spot_price=spot_price,
            quantity=self.config.quantity,
            entry_prices=entry_prices,
            exit_type=self.config.exit_type,
            sl_value=self.config.sl_value,
            target_value=self.config.target_value,
            tsl_value=self.config.tsl_value
        )

        trade_info = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "signal": signal.signal_type.value,
            "strategy": signal.strategy_name,
            "action": f"{strategy_name} {self.config.symbol}",
            "expiry": expiry,
            "qty": self.config.quantity,
            "premium": entry_premium,
            "position_id": position.position_id
        }

        self._trade_log.append(trade_info)
        logger.info(f"Auto-hedge executed: {trade_info['action']}")

        for cb in self._on_trade_callbacks:
            try:
                cb(trade_info)
            except Exception as e:
                logger.error(f"Trade callback error: {e}")

    def _estimate_premium(self, strike, opt_type, expiry) -> float:
        """Estimate option premium - try broker first, else use placeholder"""
        if self._broker:
            try:
                from algo_trader.core.options_manager import INDEX_LOT_SIZES
                # Try to fetch option quote
                # Build symbol for option quote
                symbol = self.config.symbol
                quote = self._broker.get_quote(
                    f"{symbol}_{expiry}_{int(strike)}{opt_type}", "NFO"
                )
                if quote:
                    ltp = quote.get('last_price') or quote.get('ltp') or 0
                    if isinstance(ltp, dict):
                        ltp = ltp.get('last_price', 0)
                    if float(ltp) > 0:
                        return float(ltp)
            except Exception:
                pass
        # Return 0 as placeholder - will be updated when price feed starts
        return 0.0

    def _close_existing_positions(self, signal_type: str):
        """Close existing positions on opposite signal"""
        positions = self.options_manager.get_all_positions()

        for pos in positions:
            if not pos.is_active:
                continue

            for leg in pos.legs:
                # BUY signal came -> close PE positions
                if signal_type == "BUY" and leg.option_type.value == "PE" and leg.action == "BUY":
                    logger.info(f"Closing PE position {pos.position_id} on BUY signal")
                    self.options_manager.close_position(pos.position_id)
                    break
                # SELL signal came -> close CE positions
                elif signal_type in ("SELL", "EXIT_LONG") and leg.option_type.value == "CE" and leg.action == "BUY":
                    logger.info(f"Closing CE position {pos.position_id} on SELL signal")
                    self.options_manager.close_position(pos.position_id)
                    break

    def get_trade_log(self) -> List[Dict]:
        """Get list of auto-executed trades"""
        return self._trade_log

    def get_config_dict(self) -> Dict:
        """Get config as dictionary"""
        return {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "buy_signal_action": self.config.buy_signal_action,
            "sell_signal_action": self.config.sell_signal_action,
            "strike_selection": self.config.strike_selection,
            "expiry_selection": self.config.expiry_selection,
            "quantity": self.config.quantity,
            "exit_type": self.config.exit_type,
            "sl_value": self.config.sl_value,
            "target_value": self.config.target_value,
            "tsl_value": self.config.tsl_value,
            "close_on_opposite": self.config.close_on_opposite,
        }
