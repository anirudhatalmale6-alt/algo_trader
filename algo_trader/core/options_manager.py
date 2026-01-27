"""
Options Manager - Handles Options Trading with Expiry, Strike Price, and Hedge Strategies
Supports NIFTY, BANKNIFTY, FINNIFTY, and Stock Options
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from loguru import logger


class OptionType(Enum):
    CE = "CE"  # Call
    PE = "PE"  # Put


class HedgeStrategy(Enum):
    NONE = "None"
    BULL_CALL_SPREAD = "Bull Call Spread"
    BEAR_PUT_SPREAD = "Bear Put Spread"
    STRADDLE = "Straddle"
    STRANGLE = "Strangle"
    IRON_CONDOR = "Iron Condor"
    IRON_BUTTERFLY = "Iron Butterfly"
    COVERED_CALL = "Covered Call"
    PROTECTIVE_PUT = "Protective Put"


class ExitType(Enum):
    MANUAL = "Manual"
    SL_PRICE = "SL Price"           # Fixed SL price per leg
    SL_PERCENT = "SL %"             # SL as % of premium
    TSL_PERCENT = "TSL %"           # Trailing SL %
    TSL_POINTS = "TSL Points"       # Trailing SL points
    TARGET_PRICE = "Target Price"   # Fixed target price
    TARGET_PERCENT = "Target %"     # Target as % of premium
    PNL_BASED = "P&L Based"         # SL/Target on total P&L of combined position


# Standard expiry dates for Indian indices
INDEX_LOT_SIZES = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
    "SENSEX": 10,
}

INDEX_STRIKE_GAPS = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "FINNIFTY": 50,
    "MIDCPNIFTY": 25,
    "SENSEX": 100,
}


@dataclass
class OptionLeg:
    """Single option leg"""
    leg_id: int
    symbol: str           # Base symbol (NIFTY, BANKNIFTY, etc.)
    expiry: str           # Expiry date string (e.g., "2026-01-29")
    strike: float         # Strike price
    option_type: OptionType  # CE or PE
    action: str           # BUY or SELL
    quantity: int         # Number of lots
    lot_size: int         # Lot size
    entry_price: float = 0.0   # Entry premium
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    trading_symbol: str = ""   # Full trading symbol for broker API

    def __post_init__(self):
        self._build_trading_symbol()

    def _build_trading_symbol(self):
        """Build broker-compatible trading symbol"""
        if self.expiry and self.strike:
            # Format: NIFTY26JAN19500CE (Upstox format)
            try:
                exp_date = datetime.strptime(self.expiry, "%Y-%m-%d")
                exp_str = exp_date.strftime("%y%b%d").upper()
                strike_str = str(int(self.strike)) if self.strike == int(self.strike) else str(self.strike)
                self.trading_symbol = f"{self.symbol}{exp_str}{strike_str}{self.option_type.value}"
            except Exception:
                self.trading_symbol = f"{self.symbol}_{self.expiry}_{self.strike}{self.option_type.value}"

    def update_price(self, price: float):
        """Update current price and calculate P&L"""
        self.current_price = price
        total_qty = self.quantity * self.lot_size

        if self.action == "BUY":
            self.pnl = (price - self.entry_price) * total_qty
        else:  # SELL
            self.pnl = (self.entry_price - price) * total_qty

        if self.entry_price > 0:
            self.pnl_percent = (self.pnl / (self.entry_price * total_qty)) * 100


@dataclass
class OptionPosition:
    """Complete options position (can have multiple legs for hedges)"""
    position_id: str
    symbol: str           # Base symbol
    strategy_type: HedgeStrategy
    legs: List[OptionLeg] = field(default_factory=list)
    created_at: datetime = None

    # P&L based exit settings
    exit_type: ExitType = ExitType.MANUAL
    sl_value: float = 0.0       # SL value (price, %, or P&L amount)
    target_value: float = 0.0   # Target value
    tsl_value: float = 0.0      # Trailing SL value (% or points)
    max_pnl: float = 0.0        # Max P&L reached (for trailing)

    # Computed
    total_pnl: float = 0.0
    total_pnl_percent: float = 0.0
    total_investment: float = 0.0
    is_active: bool = True

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def add_leg(self, leg: OptionLeg):
        """Add a leg to the position"""
        self.legs.append(leg)

    def update_pnl(self):
        """Calculate total P&L across all legs"""
        self.total_pnl = sum(leg.pnl for leg in self.legs)

        # Calculate total investment (premium paid for buy legs)
        buy_investment = sum(
            leg.entry_price * leg.quantity * leg.lot_size
            for leg in self.legs if leg.action == "BUY"
        )
        sell_premium = sum(
            leg.entry_price * leg.quantity * leg.lot_size
            for leg in self.legs if leg.action == "SELL"
        )
        self.total_investment = buy_investment - sell_premium

        if self.total_investment != 0:
            self.total_pnl_percent = (self.total_pnl / abs(self.total_investment)) * 100

        # Track max P&L for trailing SL
        if self.total_pnl > self.max_pnl:
            self.max_pnl = self.total_pnl

    def check_exit(self) -> Tuple[bool, str]:
        """Check if exit conditions are met based on P&L"""
        if self.exit_type == ExitType.MANUAL:
            return False, ""

        if self.exit_type == ExitType.PNL_BASED:
            # SL check: if total P&L goes below -sl_value
            if self.sl_value > 0 and self.total_pnl <= -self.sl_value:
                return True, f"P&L SL hit: ₹{self.total_pnl:.2f} <= -₹{self.sl_value:.2f}"

            # Target check: if total P&L reaches target_value
            if self.target_value > 0 and self.total_pnl >= self.target_value:
                return True, f"P&L Target hit: ₹{self.total_pnl:.2f} >= ₹{self.target_value:.2f}"

            # Trailing SL: if P&L drops tsl_value from max
            if self.tsl_value > 0 and self.max_pnl > 0:
                trail_sl_level = self.max_pnl - self.tsl_value
                if self.total_pnl <= trail_sl_level:
                    return True, f"Trailing SL hit: P&L ₹{self.total_pnl:.2f}, Max was ₹{self.max_pnl:.2f}"

        elif self.exit_type == ExitType.SL_PERCENT:
            if self.sl_value > 0 and self.total_investment != 0:
                sl_amount = abs(self.total_investment) * self.sl_value / 100
                if self.total_pnl <= -sl_amount:
                    return True, f"SL% hit: {self.sl_value}% loss"

            if self.target_value > 0 and self.total_investment != 0:
                target_amount = abs(self.total_investment) * self.target_value / 100
                if self.total_pnl >= target_amount:
                    return True, f"Target% hit: {self.target_value}% profit"

        elif self.exit_type == ExitType.TSL_PERCENT:
            if self.tsl_value > 0 and self.max_pnl > 0:
                trail_amount = self.max_pnl * self.tsl_value / 100
                if self.total_pnl <= (self.max_pnl - trail_amount):
                    return True, f"TSL% hit: dropped {self.tsl_value}% from max"

        elif self.exit_type == ExitType.TSL_POINTS:
            if self.tsl_value > 0 and self.max_pnl > 0:
                if self.total_pnl <= (self.max_pnl - self.tsl_value):
                    return True, f"TSL Points hit: dropped ₹{self.tsl_value} from max"

        return False, ""


class OptionsManager:
    """
    Manages options trading with:
    - Expiry date selection
    - Strike price selection
    - Hedge strategy building
    - P&L based SL/TSL/Target
    """

    def __init__(self):
        self.positions: Dict[str, OptionPosition] = {}
        self.closed_positions: List[OptionPosition] = []
        self._exit_callbacks: List = []
        self._pnl_callbacks: List = []
        self._next_leg_id = 1
        self._next_pos_id = 1

    def register_exit_callback(self, callback):
        """Register callback for when exit conditions are met"""
        self._exit_callbacks.append(callback)

    def register_pnl_callback(self, callback):
        """Register callback for P&L updates"""
        self._pnl_callbacks.append(callback)

    def get_expiry_dates(self, symbol: str, broker=None) -> List[str]:
        """
        Get available expiry dates for a symbol.
        If broker is connected, fetches from API. Otherwise returns calculated dates.
        """
        if broker and hasattr(broker, 'get_option_chain'):
            try:
                chain = broker.get_option_chain(symbol)
                if chain and 'expiry_dates' in chain:
                    return chain['expiry_dates']
            except Exception as e:
                logger.error(f"Error fetching expiry dates: {e}")

        # Calculate weekly/monthly expiry dates
        return self._calculate_expiry_dates(symbol)

    def _calculate_expiry_dates(self, symbol: str) -> List[str]:
        """Calculate upcoming expiry dates based on index"""
        today = date.today()
        expiry_dates = []

        # Weekly expiries - next 8 weeks
        # NIFTY: Thursday, BANKNIFTY: Wednesday, FINNIFTY: Tuesday
        expiry_day_map = {
            "NIFTY": 3,       # Thursday
            "BANKNIFTY": 2,   # Wednesday
            "FINNIFTY": 1,    # Tuesday
            "MIDCPNIFTY": 0,  # Monday
            "SENSEX": 4,      # Friday
        }

        target_day = expiry_day_map.get(symbol.upper(), 3)  # Default Thursday

        current = today
        while len(expiry_dates) < 8:
            days_ahead = target_day - current.weekday()
            if days_ahead < 0:
                days_ahead += 7
            if days_ahead == 0 and current == today:
                days_ahead = 0  # Include today if it's expiry
            next_expiry = current + timedelta(days=days_ahead)
            if next_expiry >= today:
                expiry_dates.append(next_expiry.strftime("%Y-%m-%d"))
            current = next_expiry + timedelta(days=1)

        # Also add monthly expiries (last Thursday of month) for next 3 months
        for month_offset in range(0, 4):
            m = today.month + month_offset
            y = today.year + (m - 1) // 12
            m = ((m - 1) % 12) + 1

            # Find last Thursday
            last_day = date(y, m + 1, 1) - timedelta(days=1) if m < 12 else date(y + 1, 1, 1) - timedelta(days=1)
            while last_day.weekday() != 3:  # Thursday
                last_day -= timedelta(days=1)

            exp_str = last_day.strftime("%Y-%m-%d")
            if exp_str not in expiry_dates and last_day >= today:
                expiry_dates.append(exp_str)

        return sorted(set(expiry_dates))

    def get_strike_prices(self, symbol: str, spot_price: float,
                         num_strikes: int = 20) -> List[float]:
        """
        Get available strike prices around spot price.

        Args:
            symbol: Index/stock symbol
            spot_price: Current spot/underlying price
            num_strikes: Number of strikes on each side of ATM
        """
        gap = INDEX_STRIKE_GAPS.get(symbol.upper(), 50)

        # Find ATM strike
        atm = round(spot_price / gap) * gap

        strikes = []
        for i in range(-num_strikes, num_strikes + 1):
            strike = atm + (i * gap)
            if strike > 0:
                strikes.append(strike)

        return strikes

    def get_lot_size(self, symbol: str) -> int:
        """Get lot size for a symbol"""
        return INDEX_LOT_SIZES.get(symbol.upper(), 1)

    def create_single_option(self, symbol: str, expiry: str, strike: float,
                             option_type: str, action: str, quantity: int,
                             entry_price: float, exit_type: str = "Manual",
                             sl_value: float = 0, target_value: float = 0,
                             tsl_value: float = 0) -> OptionPosition:
        """Create a single option position"""
        lot_size = self.get_lot_size(symbol)
        opt_type = OptionType.CE if option_type == "CE" else OptionType.PE

        leg = OptionLeg(
            leg_id=self._next_leg_id,
            symbol=symbol,
            expiry=expiry,
            strike=strike,
            option_type=opt_type,
            action=action,
            quantity=quantity,
            lot_size=lot_size,
            entry_price=entry_price
        )
        self._next_leg_id += 1

        pos_id = f"OPT_{self._next_pos_id}"
        self._next_pos_id += 1

        position = OptionPosition(
            position_id=pos_id,
            symbol=symbol,
            strategy_type=HedgeStrategy.NONE,
            exit_type=ExitType(exit_type) if exit_type in [e.value for e in ExitType] else ExitType.MANUAL,
            sl_value=sl_value,
            target_value=target_value,
            tsl_value=tsl_value
        )
        position.add_leg(leg)

        self.positions[pos_id] = position
        logger.info(f"Created option position {pos_id}: {symbol} {expiry} {strike}{opt_type.value} {action}")

        return position

    def create_custom_multileg(self, symbol: str, legs_data: List[Dict],
                                exit_type: str = "Manual",
                                sl_value: float = 0, target_value: float = 0,
                                tsl_value: float = 0) -> OptionPosition:
        """
        Create a custom multi-leg position where each leg has independent
        strike price and expiry date.

        Args:
            symbol: Base symbol (NIFTY, BANKNIFTY)
            legs_data: List of dicts, each with:
                - strike: Strike price
                - expiry: Expiry date string
                - option_type: "CE" or "PE"
                - action: "BUY" or "SELL"
                - quantity: Number of lots
                - entry_price: Entry premium
            exit_type: Exit type for combined P&L
            sl_value: SL value
            target_value: Target value
            tsl_value: TSL value
        """
        lot_size = self.get_lot_size(symbol)

        pos_id = f"OPT_{self._next_pos_id}"
        self._next_pos_id += 1

        position = OptionPosition(
            position_id=pos_id,
            symbol=symbol,
            strategy_type=HedgeStrategy.NONE,
            exit_type=ExitType(exit_type) if exit_type in [e.value for e in ExitType] else ExitType.MANUAL,
            sl_value=sl_value,
            target_value=target_value,
            tsl_value=tsl_value
        )

        for leg_data in legs_data:
            opt_type = OptionType.CE if leg_data["option_type"] == "CE" else OptionType.PE
            leg = OptionLeg(
                leg_id=self._next_leg_id,
                symbol=symbol,
                expiry=leg_data["expiry"],
                strike=leg_data["strike"],
                option_type=opt_type,
                action=leg_data["action"],
                quantity=leg_data.get("quantity", 1),
                lot_size=lot_size,
                entry_price=leg_data.get("entry_price", 0)
            )
            self._next_leg_id += 1
            position.add_leg(leg)

        self.positions[pos_id] = position

        legs_desc = ", ".join(
            f"{l['strike']}{l['option_type']} {l['action']} exp:{l['expiry']}"
            for l in legs_data
        )
        logger.info(f"Created multi-leg position {pos_id}: {symbol} [{legs_desc}]")

        return position

    def create_hedge_strategy(self, symbol: str, strategy: str,
                              expiry: str, spot_price: float,
                              quantity: int, entry_prices: Dict[str, float],
                              strike_config: Dict = None,
                              exit_type: str = "Manual",
                              sl_value: float = 0, target_value: float = 0,
                              tsl_value: float = 0) -> OptionPosition:
        """
        Create a hedge strategy position.

        Args:
            symbol: Base symbol
            strategy: Strategy name from HedgeStrategy
            expiry: Expiry date
            spot_price: Current spot price
            quantity: Number of lots
            entry_prices: Dict of leg_key -> entry_price
            strike_config: Optional custom strikes
            exit_type: Exit type
            sl_value: SL value
            target_value: Target value
            tsl_value: TSL value
        """
        lot_size = self.get_lot_size(symbol)
        gap = INDEX_STRIKE_GAPS.get(symbol.upper(), 50)
        atm = round(spot_price / gap) * gap

        pos_id = f"OPT_{self._next_pos_id}"
        self._next_pos_id += 1

        hedge_type = HedgeStrategy(strategy) if strategy in [h.value for h in HedgeStrategy] else HedgeStrategy.NONE

        position = OptionPosition(
            position_id=pos_id,
            symbol=symbol,
            strategy_type=hedge_type,
            exit_type=ExitType(exit_type) if exit_type in [e.value for e in ExitType] else ExitType.MANUAL,
            sl_value=sl_value,
            target_value=target_value,
            tsl_value=tsl_value
        )

        legs = self._build_strategy_legs(
            symbol, hedge_type, expiry, atm, gap, quantity,
            lot_size, entry_prices, strike_config
        )

        for leg in legs:
            position.add_leg(leg)

        self.positions[pos_id] = position
        logger.info(f"Created hedge position {pos_id}: {symbol} {strategy}")

        return position

    def _build_strategy_legs(self, symbol: str, strategy: HedgeStrategy,
                             expiry: str, atm: float, gap: float,
                             quantity: int, lot_size: int,
                             entry_prices: Dict, strike_config: Dict = None) -> List[OptionLeg]:
        """Build option legs for a hedge strategy"""
        legs = []

        if strategy == HedgeStrategy.STRADDLE:
            # Buy/Sell ATM CE + ATM PE
            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=atm, option_type=OptionType.CE, action="SELL",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("ce", 0)
            ))
            self._next_leg_id += 1
            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=atm, option_type=OptionType.PE, action="SELL",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("pe", 0)
            ))
            self._next_leg_id += 1

        elif strategy == HedgeStrategy.STRANGLE:
            otm_gap = strike_config.get("otm_gap", 1) if strike_config else 1
            ce_strike = atm + (gap * otm_gap)
            pe_strike = atm - (gap * otm_gap)

            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=ce_strike, option_type=OptionType.CE, action="SELL",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("ce", 0)
            ))
            self._next_leg_id += 1
            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=pe_strike, option_type=OptionType.PE, action="SELL",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("pe", 0)
            ))
            self._next_leg_id += 1

        elif strategy == HedgeStrategy.BULL_CALL_SPREAD:
            buy_strike = atm
            sell_strike = atm + gap
            if strike_config:
                buy_strike = strike_config.get("buy_strike", buy_strike)
                sell_strike = strike_config.get("sell_strike", sell_strike)

            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=buy_strike, option_type=OptionType.CE, action="BUY",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("buy_ce", 0)
            ))
            self._next_leg_id += 1
            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=sell_strike, option_type=OptionType.CE, action="SELL",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("sell_ce", 0)
            ))
            self._next_leg_id += 1

        elif strategy == HedgeStrategy.BEAR_PUT_SPREAD:
            buy_strike = atm
            sell_strike = atm - gap
            if strike_config:
                buy_strike = strike_config.get("buy_strike", buy_strike)
                sell_strike = strike_config.get("sell_strike", sell_strike)

            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=buy_strike, option_type=OptionType.PE, action="BUY",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("buy_pe", 0)
            ))
            self._next_leg_id += 1
            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=sell_strike, option_type=OptionType.PE, action="SELL",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("sell_pe", 0)
            ))
            self._next_leg_id += 1

        elif strategy == HedgeStrategy.IRON_CONDOR:
            otm_gap = strike_config.get("otm_gap", 2) if strike_config else 2
            hedge_gap = strike_config.get("hedge_gap", 3) if strike_config else 3

            # Sell OTM CE + Buy further OTM CE (upper side)
            sell_ce = atm + (gap * otm_gap)
            buy_ce = atm + (gap * hedge_gap)
            # Sell OTM PE + Buy further OTM PE (lower side)
            sell_pe = atm - (gap * otm_gap)
            buy_pe = atm - (gap * hedge_gap)

            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=sell_ce, option_type=OptionType.CE, action="SELL",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("sell_ce", 0)
            ))
            self._next_leg_id += 1
            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=buy_ce, option_type=OptionType.CE, action="BUY",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("buy_ce", 0)
            ))
            self._next_leg_id += 1
            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=sell_pe, option_type=OptionType.PE, action="SELL",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("sell_pe", 0)
            ))
            self._next_leg_id += 1
            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=buy_pe, option_type=OptionType.PE, action="BUY",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("buy_pe", 0)
            ))
            self._next_leg_id += 1

        elif strategy == HedgeStrategy.IRON_BUTTERFLY:
            hedge_gap = strike_config.get("hedge_gap", 2) if strike_config else 2

            # Sell ATM CE + ATM PE, Buy OTM CE + OTM PE
            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=atm, option_type=OptionType.CE, action="SELL",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("sell_ce", 0)
            ))
            self._next_leg_id += 1
            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=atm, option_type=OptionType.PE, action="SELL",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("sell_pe", 0)
            ))
            self._next_leg_id += 1
            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=atm + (gap * hedge_gap), option_type=OptionType.CE, action="BUY",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("buy_ce", 0)
            ))
            self._next_leg_id += 1
            legs.append(OptionLeg(
                leg_id=self._next_leg_id, symbol=symbol, expiry=expiry,
                strike=atm - (gap * hedge_gap), option_type=OptionType.PE, action="BUY",
                quantity=quantity, lot_size=lot_size,
                entry_price=entry_prices.get("buy_pe", 0)
            ))
            self._next_leg_id += 1

        return legs

    def update_leg_price(self, pos_id: str, leg_id: int, price: float):
        """Update price for a specific leg"""
        if pos_id not in self.positions:
            return

        position = self.positions[pos_id]
        for leg in position.legs:
            if leg.leg_id == leg_id:
                leg.update_price(price)
                break

        position.update_pnl()

        # Check exit conditions
        should_exit, reason = position.check_exit()
        if should_exit:
            logger.warning(f"EXIT triggered for {pos_id}: {reason}")
            for cb in self._exit_callbacks:
                try:
                    cb(position, reason)
                except Exception as e:
                    logger.error(f"Exit callback error: {e}")

        # Notify P&L update
        for cb in self._pnl_callbacks:
            try:
                cb(position)
            except Exception as e:
                logger.error(f"P&L callback error: {e}")

    def update_all_prices(self, pos_id: str, prices: Dict[int, float]):
        """Update prices for all legs at once"""
        if pos_id not in self.positions:
            return

        position = self.positions[pos_id]
        for leg in position.legs:
            if leg.leg_id in prices:
                leg.update_price(prices[leg.leg_id])

        position.update_pnl()

        # Check exit
        should_exit, reason = position.check_exit()
        if should_exit:
            logger.warning(f"EXIT triggered for {pos_id}: {reason}")
            for cb in self._exit_callbacks:
                try:
                    cb(position, reason)
                except Exception as e:
                    logger.error(f"Exit callback error: {e}")

        for cb in self._pnl_callbacks:
            try:
                cb(position)
            except Exception as e:
                logger.error(f"P&L callback error: {e}")

    def close_position(self, pos_id: str):
        """Close a position"""
        if pos_id not in self.positions:
            return

        position = self.positions[pos_id]
        position.is_active = False
        self.closed_positions.append(position)
        del self.positions[pos_id]
        logger.info(f"Closed option position {pos_id}, P&L: ₹{position.total_pnl:.2f}")

    def get_position(self, pos_id: str) -> Optional[OptionPosition]:
        """Get a specific position"""
        return self.positions.get(pos_id)

    def get_all_positions(self) -> List[OptionPosition]:
        """Get all active positions"""
        return list(self.positions.values())

    def get_total_pnl(self) -> float:
        """Get total P&L across all positions"""
        active_pnl = sum(p.total_pnl for p in self.positions.values())
        closed_pnl = sum(p.total_pnl for p in self.closed_positions)
        return active_pnl + closed_pnl

    def get_options_summary(self) -> Dict:
        """Get summary of all options positions"""
        active = list(self.positions.values())
        active_pnl = sum(p.total_pnl for p in active)
        closed_pnl = sum(p.total_pnl for p in self.closed_positions)

        return {
            "active_positions": len(active),
            "closed_positions": len(self.closed_positions),
            "active_pnl": active_pnl,
            "closed_pnl": closed_pnl,
            "total_pnl": active_pnl + closed_pnl,
            "winning": sum(1 for p in self.closed_positions if p.total_pnl > 0),
            "losing": sum(1 for p in self.closed_positions if p.total_pnl < 0),
        }
