"""
CPR (Central Pivot Range) Option Sale Strategy
Based on DeuceDavis CPR Option Sale Strategy

Signals:
- BULLISH (Sell Put): Price > Top Pivot
- BEARISH (Sell Call): Price < Bottom Pivot
- SIDEWAYS (Iron Condor): Price between Top & Bottom Pivot
"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, List, Tuple
import threading
import time

logger = logging.getLogger(__name__)


class CPRSignal(Enum):
    """CPR Trade Signals"""
    NO_SIGNAL = "No Signal"
    BULLISH = "Bullish (Sell Put)"
    BEARISH = "Bearish (Sell Call)"
    SIDEWAYS = "Sideways (Iron Condor)"


class PremiumZone(Enum):
    """Premium Zone Quality"""
    OPTIMAL = "Optimal (Hedge)"
    GOOD = "Good"
    DECENT = "Decent"
    STANDARD = "Standard"


@dataclass
class CPRLevels:
    """CPR Pivot Levels"""
    # Traditional Pivots
    central_pivot: float = 0.0
    top_pivot: float = 0.0
    bottom_pivot: float = 0.0
    cpr_range: float = 0.0

    # Traditional Support/Resistance
    r1: float = 0.0
    r2: float = 0.0
    r3: float = 0.0
    s1: float = 0.0
    s2: float = 0.0
    s3: float = 0.0

    # Camarilla Pivots
    cam_r1: float = 0.0
    cam_r2: float = 0.0
    cam_r3: float = 0.0
    cam_r4: float = 0.0
    cam_r5: float = 0.0
    cam_s1: float = 0.0
    cam_s2: float = 0.0
    cam_s3: float = 0.0
    cam_s4: float = 0.0
    cam_s5: float = 0.0

    # Developing CPR (next day projected)
    dev_central_pivot: float = 0.0
    dev_top_pivot: float = 0.0
    dev_bottom_pivot: float = 0.0


@dataclass
class CPRTradeSignal:
    """CPR Trade Signal with details"""
    signal: CPRSignal
    premium_zone: PremiumZone
    strike_value: float
    strike_value_2: float  # For Iron Condor (second leg)
    timestamp: datetime
    symbol: str
    current_price: float
    cpr_levels: CPRLevels


class CPRCalculator:
    """Calculate CPR and related pivot levels"""

    @staticmethod
    def calculate_traditional_pivots(high: float, low: float, close: float) -> CPRLevels:
        """Calculate Traditional Pivot Points and CPR"""
        levels = CPRLevels()

        # Central Pivot Range
        levels.central_pivot = (high + low + close) / 3
        temp_bottom_pivot = (high + low) / 2
        temp_top_pivot = (levels.central_pivot - temp_bottom_pivot) + levels.central_pivot

        # Ensure top > bottom
        if temp_bottom_pivot > temp_top_pivot:
            levels.bottom_pivot = temp_top_pivot
            levels.top_pivot = temp_bottom_pivot
        else:
            levels.bottom_pivot = temp_bottom_pivot
            levels.top_pivot = temp_top_pivot

        levels.cpr_range = levels.top_pivot - levels.bottom_pivot

        # Traditional Support/Resistance
        pivot_range = high - low
        levels.s1 = 2 * levels.central_pivot - high
        levels.s2 = levels.central_pivot - pivot_range
        levels.s3 = levels.s1 - pivot_range
        levels.r1 = 2 * levels.central_pivot - low
        levels.r2 = levels.central_pivot + pivot_range
        levels.r3 = levels.r1 + pivot_range

        return levels

    @staticmethod
    def calculate_camarilla_pivots(high: float, low: float, close: float,
                                    existing_levels: CPRLevels) -> CPRLevels:
        """Add Camarilla Pivot Points to existing levels"""
        pivot_range = high - low

        existing_levels.cam_r5 = high / low * close
        existing_levels.cam_r4 = close + pivot_range * 1.1 / 2
        existing_levels.cam_r3 = close + pivot_range * 1.1 / 4
        existing_levels.cam_r2 = close + pivot_range * 1.1 / 6
        existing_levels.cam_r1 = close + pivot_range * 1.1 / 12

        existing_levels.cam_s1 = close - pivot_range * 1.1 / 12
        existing_levels.cam_s2 = close - pivot_range * 1.1 / 6
        existing_levels.cam_s3 = close - pivot_range * 1.1 / 4
        existing_levels.cam_s4 = close - pivot_range * 1.1 / 2
        existing_levels.cam_s5 = close - (existing_levels.cam_r5 - close)

        return existing_levels

    @staticmethod
    def calculate_developing_cpr(dev_high: float, dev_low: float, dev_close: float,
                                  existing_levels: CPRLevels) -> CPRLevels:
        """Calculate developing (next day) CPR"""
        existing_levels.dev_central_pivot = (dev_high + dev_low + dev_close) / 3
        dev_temp_bottom = (dev_high + dev_low) / 2
        dev_temp_top = (existing_levels.dev_central_pivot - dev_temp_bottom) + existing_levels.dev_central_pivot

        if dev_temp_bottom > dev_temp_top:
            existing_levels.dev_bottom_pivot = dev_temp_top
            existing_levels.dev_top_pivot = dev_temp_bottom
        else:
            existing_levels.dev_bottom_pivot = dev_temp_bottom
            existing_levels.dev_top_pivot = dev_temp_top

        return existing_levels

    @staticmethod
    def calculate_all(high: float, low: float, close: float,
                      dev_high: float = None, dev_low: float = None,
                      dev_close: float = None) -> CPRLevels:
        """Calculate all pivot levels"""
        levels = CPRCalculator.calculate_traditional_pivots(high, low, close)
        levels = CPRCalculator.calculate_camarilla_pivots(high, low, close, levels)

        if dev_high and dev_low and dev_close:
            levels = CPRCalculator.calculate_developing_cpr(dev_high, dev_low, dev_close, levels)

        return levels


class CPRSignalGenerator:
    """Generate trading signals based on CPR levels"""

    # Strike gap for each symbol (standard NSE F&O strike gaps)
    STRIKE_GAPS = {
        # Indices
        "NIFTY": 50,
        "BANKNIFTY": 100,
        "FINNIFTY": 50,
        "MIDCPNIFTY": 25,
        "SENSEX": 100,
        "BANKEX": 100,
        # Default for stocks - most F&O stocks have different gaps
        # High-priced stocks (>2000) typically have 50 gap
        # Mid-priced stocks (500-2000) typically have 25 or 20 gap
        # Low-priced stocks (<500) typically have 10 or 5 gap
    }

    def __init__(self, strike_method: str = "Traditional Pivot S1/R1",
                 spread_method: str = "Auto"):
        self.strike_method = strike_method
        self.spread_method = spread_method

    def get_signal(self, current_price: float, cpr_levels: CPRLevels,
                   symbol: str = "NIFTY") -> CPRTradeSignal:
        """Generate trading signal based on current price and CPR levels"""

        # Determine trade direction
        if current_price > cpr_levels.top_pivot:
            signal = CPRSignal.BULLISH
        elif current_price < cpr_levels.bottom_pivot:
            signal = CPRSignal.BEARISH
        elif cpr_levels.bottom_pivot <= current_price <= cpr_levels.top_pivot:
            signal = CPRSignal.SIDEWAYS
        else:
            signal = CPRSignal.NO_SIGNAL

        # Calculate strike values
        strike_value, strike_value_2 = self._calculate_strikes(
            current_price, cpr_levels, signal, symbol
        )

        # Determine premium zone
        premium_zone = self._get_premium_zone(current_price, cpr_levels, strike_value)

        return CPRTradeSignal(
            signal=signal,
            premium_zone=premium_zone,
            strike_value=strike_value,
            strike_value_2=strike_value_2,
            timestamp=datetime.now(),
            symbol=symbol,
            current_price=current_price,
            cpr_levels=cpr_levels
        )

    def _calculate_strikes(self, current_price: float, cpr_levels: CPRLevels,
                           signal: CPRSignal, symbol: str = "NIFTY") -> Tuple[float, float]:
        """Calculate strike prices based on method"""
        spread_value = self._get_strike_gap(symbol, current_price)

        if self.strike_method == "Traditional Pivot S1/R1":
            call_trigger = cpr_levels.r1
            put_trigger = cpr_levels.s1
        elif self.strike_method == "Camarilla Pivot R1/S1":
            call_trigger = cpr_levels.cam_r1
            put_trigger = cpr_levels.cam_s1
        elif self.strike_method == "Camarilla Pivot R2/S2":
            call_trigger = cpr_levels.cam_r2
            put_trigger = cpr_levels.cam_s2
        else:
            call_trigger = cpr_levels.central_pivot
            put_trigger = cpr_levels.central_pivot

        # Calculate strike values based on signal
        if signal == CPRSignal.BULLISH:
            # Sell Put - strike below current price
            strike_value = self._round_to_strike(put_trigger, spread_value, "Put")
            strike_value_2 = 0
        elif signal == CPRSignal.BEARISH:
            # Sell Call - strike above current price
            strike_value = self._round_to_strike(call_trigger, spread_value, "Call")
            strike_value_2 = 0
        elif signal == CPRSignal.SIDEWAYS:
            # Iron Condor - both calls and puts
            strike_value = self._round_to_strike(call_trigger, spread_value, "Call")
            strike_value_2 = self._round_to_strike(put_trigger, spread_value, "Put")
        else:
            strike_value = 0
            strike_value_2 = 0

        return strike_value, strike_value_2

    def _get_strike_gap(self, symbol: str, current_price: float) -> float:
        """Get strike gap based on symbol (NSE F&O standard gaps)"""
        symbol_upper = symbol.upper()

        # Check if symbol has a defined strike gap
        if symbol_upper in self.STRIKE_GAPS:
            return float(self.STRIKE_GAPS[symbol_upper])

        # For F&O stocks, calculate based on price (NSE standard rules)
        # These are approximate - actual gaps depend on NSE circulars
        if current_price >= 5000:
            return 100.0  # High-priced stocks like MRF
        elif current_price >= 2000:
            return 50.0   # Stocks like MARUTI, BOSCH
        elif current_price >= 1000:
            return 25.0   # Most large-cap stocks
        elif current_price >= 500:
            return 20.0   # Mid-cap stocks
        elif current_price >= 250:
            return 10.0   # Lower mid-cap
        elif current_price >= 100:
            return 5.0    # Low-priced stocks
        else:
            return 2.5    # Very low-priced stocks

    def _round_to_strike(self, value: float, strike_gap: float, option_type: str) -> float:
        """Round value to valid strike price based on symbol's strike gap"""
        if option_type == "Call":
            # Round up to next valid strike for calls
            return round((value // strike_gap + 1) * strike_gap)
        else:
            # Round down to previous valid strike for puts
            return round((value // strike_gap) * strike_gap)

    def _get_premium_zone(self, current_price: float, cpr_levels: CPRLevels,
                          strike_value: float) -> PremiumZone:
        """Determine premium zone quality"""
        # Simplified zone calculation
        if strike_value < cpr_levels.bottom_pivot and current_price < cpr_levels.bottom_pivot:
            return PremiumZone.OPTIMAL
        elif strike_value < cpr_levels.bottom_pivot and current_price < cpr_levels.central_pivot:
            return PremiumZone.GOOD
        elif strike_value > cpr_levels.top_pivot and current_price > cpr_levels.top_pivot:
            return PremiumZone.OPTIMAL
        elif strike_value > cpr_levels.top_pivot and current_price > cpr_levels.central_pivot:
            return PremiumZone.GOOD
        elif cpr_levels.bottom_pivot <= current_price <= cpr_levels.top_pivot:
            return PremiumZone.DECENT
        else:
            return PremiumZone.STANDARD


class CPRAutoTrader:
    """Auto-trade based on CPR signals"""

    def __init__(self, symbol: str = "NIFTY", timeframe: str = "D",
                 auto_trade_enabled: bool = False, test_mode: bool = True,
                 hedging_enabled: bool = True):
        self.symbol = symbol
        self.timeframe = timeframe
        self.auto_trade_enabled = auto_trade_enabled
        self.test_mode = test_mode
        self.hedging_enabled = hedging_enabled  # Enable protective hedging

        self.calculator = CPRCalculator()
        self.signal_generator = CPRSignalGenerator()

        self.current_signal: Optional[CPRTradeSignal] = None
        self.last_trade_signal: Optional[CPRSignal] = None
        self.cpr_levels: Optional[CPRLevels] = None

        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

        # Callbacks
        self.on_signal_change = None  # Callback when signal changes
        self.on_trade_executed = None  # Callback when trade is executed
        self.on_levels_updated = None  # Callback when CPR levels update

    def _get_symbol_strike_gap(self, symbol: str) -> int:
        """Get strike gap for a symbol (NSE F&O standard gaps)"""
        symbol_upper = symbol.upper()

        # Index-specific strike gaps
        strike_gaps = {
            "NIFTY": 50,
            "BANKNIFTY": 100,
            "FINNIFTY": 50,
            "MIDCPNIFTY": 25,
            "SENSEX": 100,
            "BANKEX": 100,
        }

        if symbol_upper in strike_gaps:
            return strike_gaps[symbol_upper]

        # For stocks, use the signal generator's logic
        # Default to 50 for unknown symbols
        return 50

    def set_prior_day_data(self, high: float, low: float, close: float):
        """Set prior day OHLC data for CPR calculation"""
        self.cpr_levels = self.calculator.calculate_all(high, low, close)
        logger.info(f"CPR Levels calculated - CP: {self.cpr_levels.central_pivot:.2f}, "
                   f"TC: {self.cpr_levels.top_pivot:.2f}, BC: {self.cpr_levels.bottom_pivot:.2f}")

        if self.on_levels_updated:
            self.on_levels_updated(self.cpr_levels)

    def update_price(self, current_price: float) -> Optional[CPRTradeSignal]:
        """Update current price and check for signals"""
        if not self.cpr_levels:
            logger.warning("CPR levels not set. Call set_prior_day_data first.")
            return None

        # Generate signal
        new_signal = self.signal_generator.get_signal(
            current_price, self.cpr_levels, self.symbol
        )

        # Check if signal changed
        signal_changed = (self.current_signal is None or
                         self.current_signal.signal != new_signal.signal)

        self.current_signal = new_signal

        if signal_changed:
            logger.info(f"Signal changed to: {new_signal.signal.value} "
                       f"at price {current_price:.2f}")

            if self.on_signal_change:
                self.on_signal_change(new_signal)

            # Auto-trade if enabled and signal is actionable
            if (self.auto_trade_enabled and
                new_signal.signal != CPRSignal.NO_SIGNAL and
                new_signal.signal != self.last_trade_signal):
                self._execute_trade(new_signal)

        return new_signal

    def _execute_trade(self, signal: CPRTradeSignal):
        """Execute trade based on signal with hedging"""
        # Get strike gap based on symbol (for hedge calculation)
        strike_gap = self._get_symbol_strike_gap(signal.symbol)
        # Hedge is 2 strikes away for protection
        hedge_distance = strike_gap * 2

        trade_details = {
            'signal': signal.signal.value,
            'symbol': signal.symbol,
            'strike': signal.strike_value,
            'strike_2': signal.strike_value_2,
            'premium_zone': signal.premium_zone.value,
            'price': signal.current_price,
            'timestamp': signal.timestamp.isoformat(),
            'test_mode': self.test_mode,
            'hedging_enabled': self.hedging_enabled,
            'strike_gap': strike_gap
        }

        if signal.signal == CPRSignal.BULLISH:
            # Bull Put Spread (Credit Spread with Hedge)
            # Sell Put + Buy lower Put for protection
            trade_details['action'] = 'BULL_PUT_SPREAD'
            trade_details['option_type'] = 'PE'
            trade_details['sell_strike'] = signal.strike_value
            trade_details['buy_strike'] = signal.strike_value - hedge_distance  # Hedge
            logger.info(f"AUTO-TRADE: Bull Put Spread - "
                       f"Sell PE {signal.strike_value}, Buy PE {trade_details['buy_strike']}")

        elif signal.signal == CPRSignal.BEARISH:
            # Bear Call Spread (Credit Spread with Hedge)
            # Sell Call + Buy higher Call for protection
            trade_details['action'] = 'BEAR_CALL_SPREAD'
            trade_details['option_type'] = 'CE'
            trade_details['sell_strike'] = signal.strike_value
            trade_details['buy_strike'] = signal.strike_value + hedge_distance  # Hedge
            logger.info(f"AUTO-TRADE: Bear Call Spread - "
                       f"Sell CE {signal.strike_value}, Buy CE {trade_details['buy_strike']}")

        elif signal.signal == CPRSignal.SIDEWAYS:
            # Iron Condor (already hedged)
            trade_details['action'] = 'IRON_CONDOR'
            trade_details['option_type'] = 'IC'
            trade_details['ce_sell_strike'] = signal.strike_value
            trade_details['pe_sell_strike'] = signal.strike_value_2
            trade_details['ce_buy_strike'] = signal.strike_value + hedge_distance
            trade_details['pe_buy_strike'] = signal.strike_value_2 - hedge_distance
            logger.info(f"AUTO-TRADE: Iron Condor - "
                       f"Sell CE {signal.strike_value}, Sell PE {signal.strike_value_2}, "
                       f"Buy CE {trade_details['ce_buy_strike']}, Buy PE {trade_details['pe_buy_strike']}")

        self.last_trade_signal = signal.signal

        if self.on_trade_executed:
            self.on_trade_executed(trade_details)

    def start_monitoring(self, price_callback):
        """Start monitoring for signals (runs in background thread)"""
        if self._running:
            return

        self._running = True
        self._price_callback = price_callback
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("CPR monitoring started")

    def stop_monitoring(self):
        """Stop monitoring"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("CPR monitoring stopped")

    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                # Get current price from callback
                if self._price_callback:
                    current_price = self._price_callback()
                    if current_price:
                        self.update_price(current_price)

                time.sleep(1)  # Check every second
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)

    def get_status(self) -> Dict:
        """Get current status"""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'auto_trade_enabled': self.auto_trade_enabled,
            'test_mode': self.test_mode,
            'running': self._running,
            'current_signal': self.current_signal.signal.value if self.current_signal else None,
            'cpr_levels': {
                'central_pivot': self.cpr_levels.central_pivot if self.cpr_levels else 0,
                'top_pivot': self.cpr_levels.top_pivot if self.cpr_levels else 0,
                'bottom_pivot': self.cpr_levels.bottom_pivot if self.cpr_levels else 0,
            } if self.cpr_levels else None
        }
