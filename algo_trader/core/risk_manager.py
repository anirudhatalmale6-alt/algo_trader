"""
Risk Manager - Handles Trailing Stop Loss, MTM P&L, Risk Management, and Auto Square-off
"""
import threading
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, date, time as dt_time
from enum import Enum
from loguru import logger


class StopLossType(Enum):
    FIXED = "FIXED"  # Fixed stop loss price
    PERCENTAGE = "PERCENTAGE"  # Percentage based
    TRAILING = "TRAILING"  # Trailing stop loss
    TRAILING_PERCENTAGE = "TRAILING_PERCENTAGE"  # Trailing with percentage


class SquareOffReason(Enum):
    MANUAL = "MANUAL"
    STOP_LOSS = "STOP_LOSS"
    TARGET = "TARGET"
    DAILY_PROFIT_TARGET = "DAILY_PROFIT_TARGET"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    TIME_BASED = "TIME_BASED"
    POSITION_PROFIT = "POSITION_PROFIT"
    POSITION_LOSS = "POSITION_LOSS"


@dataclass
class AutoSquareOffSettings:
    """Settings for auto square-off"""
    # Daily P&L limits
    daily_profit_target: float = None  # Square off all if daily profit reaches this
    daily_loss_limit: float = None  # Square off all if daily loss reaches this

    # Time-based square-off
    square_off_time: dt_time = None  # Auto square-off at this time (e.g., 3:15 PM)

    # Per-position limits (percentage)
    position_profit_percent: float = None  # Square off position at this profit %
    position_loss_percent: float = None  # Square off position at this loss %

    # Per-position limits (absolute)
    position_profit_amount: float = None  # Square off position at this profit amount
    position_loss_amount: float = None  # Square off position at this loss amount

    # Trailing square-off
    trailing_profit_percent: float = None  # Lock in profits with trailing

    # Enable flags
    enabled: bool = True
    notify_on_square_off: bool = True


@dataclass
class Position:
    """Represents an open position"""
    symbol: str
    exchange: str
    quantity: int
    entry_price: float
    current_price: float = 0.0
    stop_loss: float = None
    target: float = None
    trailing_sl_percent: float = None
    trailing_sl_points: float = None
    highest_price: float = None  # For trailing SL
    lowest_price: float = None  # For short positions
    entry_time: datetime = None
    broker: str = None
    order_id: str = None
    pnl: float = 0.0
    pnl_percent: float = 0.0

    def __post_init__(self):
        if self.entry_time is None:
            self.entry_time = datetime.now()
        if self.highest_price is None:
            self.highest_price = self.entry_price
        if self.lowest_price is None:
            self.lowest_price = self.entry_price
        if self.current_price == 0:
            self.current_price = self.entry_price


@dataclass
class MTMSummary:
    """Mark-to-Market Summary"""
    date: date
    total_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    positions: List[Dict] = field(default_factory=list)


class RiskManager:
    """
    Risk Manager for handling:
    - Trailing Stop Loss
    - MTM (Mark-to-Market) P&L
    - Position tracking
    - Risk limits
    """

    def __init__(self):
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        self.closed_positions: List[Position] = []
        self.mtm_callbacks: List[Callable] = []
        self.sl_hit_callbacks: List[Callable] = []
        self.target_hit_callbacks: List[Callable] = []
        self.square_off_callbacks: List[Callable] = []

        self._running = False
        self._thread = None
        self._price_feed = None
        self._broker = None  # Broker instance for executing square-off orders

        # Risk settings
        self.max_loss_per_trade_percent = 2.0
        self.max_daily_loss = None
        self.max_positions = 10

        # Auto square-off settings
        self.auto_square_off = AutoSquareOffSettings()
        self._squared_off_today = False  # Track if daily square-off already triggered
        self._position_max_profits: Dict[str, float] = {}  # Track max profit for trailing

    def register_mtm_callback(self, callback: Callable):
        """Register callback for MTM updates"""
        self.mtm_callbacks.append(callback)

    def register_sl_hit_callback(self, callback: Callable):
        """Register callback for stop loss hits"""
        self.sl_hit_callbacks.append(callback)

    def register_target_hit_callback(self, callback: Callable):
        """Register callback for target hits"""
        self.target_hit_callbacks.append(callback)

    def register_square_off_callback(self, callback: Callable):
        """Register callback for auto square-off events"""
        self.square_off_callbacks.append(callback)

    def set_broker(self, broker):
        """Set broker instance for executing square-off orders"""
        self._broker = broker

    def add_position(self, symbol: str, quantity: int, entry_price: float,
                    exchange: str = "NSE", stop_loss: float = None,
                    target: float = None, trailing_sl_percent: float = None,
                    trailing_sl_points: float = None, broker: str = None,
                    order_id: str = None) -> Position:
        """
        Add a new position to track

        Args:
            symbol: Stock symbol
            quantity: Quantity (positive for long, negative for short)
            entry_price: Entry price
            exchange: Exchange
            stop_loss: Fixed stop loss price
            target: Target price
            trailing_sl_percent: Trailing SL as percentage (e.g., 2 for 2%)
            trailing_sl_points: Trailing SL in points
            broker: Broker name
            order_id: Broker order ID
        """
        position = Position(
            symbol=symbol,
            exchange=exchange,
            quantity=quantity,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            trailing_sl_percent=trailing_sl_percent,
            trailing_sl_points=trailing_sl_points,
            broker=broker,
            order_id=order_id
        )

        key = f"{exchange}:{symbol}"
        self.positions[key] = position
        logger.info(f"Added position: {key} @ {entry_price}, Qty: {quantity}")

        return position

    def update_price(self, symbol: str, current_price: float, exchange: str = "NSE"):
        """
        Update current price for a position and check SL/Target

        Args:
            symbol: Stock symbol
            current_price: Current market price
            exchange: Exchange
        """
        key = f"{exchange}:{symbol}"

        if key not in self.positions:
            return

        position = self.positions[key]
        position.current_price = current_price

        # Update P&L
        if position.quantity > 0:  # Long position
            position.pnl = (current_price - position.entry_price) * position.quantity
            position.pnl_percent = ((current_price - position.entry_price) / position.entry_price) * 100

            # Update highest price for trailing SL
            if current_price > position.highest_price:
                position.highest_price = current_price
                self._update_trailing_sl(position)
        else:  # Short position
            position.pnl = (position.entry_price - current_price) * abs(position.quantity)
            position.pnl_percent = ((position.entry_price - current_price) / position.entry_price) * 100

            # Update lowest price for trailing SL
            if current_price < position.lowest_price:
                position.lowest_price = current_price
                self._update_trailing_sl(position)

        # Check stop loss
        if self._check_stop_loss(position):
            self._trigger_stop_loss(position)

        # Check target
        if self._check_target(position):
            self._trigger_target(position)

        # Notify MTM callbacks
        self._notify_mtm_update()

    def _update_trailing_sl(self, position: Position):
        """Update trailing stop loss based on price movement"""
        if position.quantity > 0:  # Long position
            if position.trailing_sl_percent:
                new_sl = position.highest_price * (1 - position.trailing_sl_percent / 100)
                if position.stop_loss is None or new_sl > position.stop_loss:
                    position.stop_loss = round(new_sl, 2)
                    logger.info(f"Updated TSL for {position.symbol}: {position.stop_loss}")

            elif position.trailing_sl_points:
                new_sl = position.highest_price - position.trailing_sl_points
                if position.stop_loss is None or new_sl > position.stop_loss:
                    position.stop_loss = round(new_sl, 2)
                    logger.info(f"Updated TSL for {position.symbol}: {position.stop_loss}")

        else:  # Short position
            if position.trailing_sl_percent:
                new_sl = position.lowest_price * (1 + position.trailing_sl_percent / 100)
                if position.stop_loss is None or new_sl < position.stop_loss:
                    position.stop_loss = round(new_sl, 2)
                    logger.info(f"Updated TSL for {position.symbol}: {position.stop_loss}")

            elif position.trailing_sl_points:
                new_sl = position.lowest_price + position.trailing_sl_points
                if position.stop_loss is None or new_sl < position.stop_loss:
                    position.stop_loss = round(new_sl, 2)
                    logger.info(f"Updated TSL for {position.symbol}: {position.stop_loss}")

    def _check_stop_loss(self, position: Position) -> bool:
        """Check if stop loss is hit"""
        if position.stop_loss is None:
            return False

        if position.quantity > 0:  # Long position
            return position.current_price <= position.stop_loss
        else:  # Short position
            return position.current_price >= position.stop_loss

    def _check_target(self, position: Position) -> bool:
        """Check if target is hit"""
        if position.target is None:
            return False

        if position.quantity > 0:  # Long position
            return position.current_price >= position.target
        else:  # Short position
            return position.current_price <= position.target

    def _trigger_stop_loss(self, position: Position):
        """Handle stop loss hit"""
        logger.warning(f"STOP LOSS HIT: {position.symbol} @ {position.current_price}")

        for callback in self.sl_hit_callbacks:
            try:
                callback(position)
            except Exception as e:
                logger.error(f"SL callback error: {e}")

    def _trigger_target(self, position: Position):
        """Handle target hit"""
        logger.info(f"TARGET HIT: {position.symbol} @ {position.current_price}")

        for callback in self.target_hit_callbacks:
            try:
                callback(position)
            except Exception as e:
                logger.error(f"Target callback error: {e}")

    def _notify_mtm_update(self):
        """Notify MTM update callbacks"""
        mtm = self.get_mtm_summary()
        for callback in self.mtm_callbacks:
            try:
                callback(mtm)
            except Exception as e:
                logger.error(f"MTM callback error: {e}")

        # Check auto square-off conditions
        self.check_auto_square_off()

    def close_position(self, symbol: str, exit_price: float, exchange: str = "NSE"):
        """Close a position"""
        key = f"{exchange}:{symbol}"

        if key not in self.positions:
            logger.warning(f"Position {key} not found")
            return

        position = self.positions[key]
        position.current_price = exit_price

        # Calculate final P&L
        if position.quantity > 0:
            position.pnl = (exit_price - position.entry_price) * position.quantity
        else:
            position.pnl = (position.entry_price - exit_price) * abs(position.quantity)

        position.pnl_percent = (position.pnl / (position.entry_price * abs(position.quantity))) * 100

        # Move to closed positions
        self.closed_positions.append(position)
        del self.positions[key]

        logger.info(f"Closed position: {key} @ {exit_price}, P&L: {position.pnl:.2f}")

    def get_position(self, symbol: str, exchange: str = "NSE") -> Optional[Position]:
        """Get a specific position"""
        key = f"{exchange}:{symbol}"
        return self.positions.get(key)

    def get_all_positions(self) -> List[Position]:
        """Get all open positions"""
        return list(self.positions.values())

    def get_mtm_summary(self) -> MTMSummary:
        """Get current MTM summary"""
        summary = MTMSummary(date=date.today())

        # Calculate unrealized P&L from open positions
        for position in self.positions.values():
            summary.unrealized_pnl += position.pnl
            summary.positions.append({
                'symbol': position.symbol,
                'exchange': position.exchange,
                'quantity': position.quantity,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'pnl': position.pnl,
                'pnl_percent': position.pnl_percent,
                'stop_loss': position.stop_loss,
                'target': position.target
            })

        # Calculate realized P&L from closed positions today
        today = date.today()
        for position in self.closed_positions:
            if position.entry_time.date() == today:
                summary.realized_pnl += position.pnl
                summary.total_trades += 1
                if position.pnl > 0:
                    summary.winning_trades += 1
                elif position.pnl < 0:
                    summary.losing_trades += 1

        summary.total_pnl = summary.realized_pnl + summary.unrealized_pnl

        return summary

    def set_trailing_sl(self, symbol: str, trailing_percent: float = None,
                       trailing_points: float = None, exchange: str = "NSE"):
        """Set or update trailing stop loss for a position"""
        key = f"{exchange}:{symbol}"

        if key not in self.positions:
            logger.warning(f"Position {key} not found")
            return

        position = self.positions[key]
        position.trailing_sl_percent = trailing_percent
        position.trailing_sl_points = trailing_points

        # Immediately update SL based on current high/low
        self._update_trailing_sl(position)

        logger.info(f"Set TSL for {symbol}: {trailing_percent}% / {trailing_points} points")

    def set_stop_loss(self, symbol: str, stop_loss: float, exchange: str = "NSE"):
        """Set fixed stop loss for a position"""
        key = f"{exchange}:{symbol}"

        if key not in self.positions:
            logger.warning(f"Position {key} not found")
            return

        position = self.positions[key]
        position.stop_loss = stop_loss
        logger.info(f"Set SL for {symbol}: {stop_loss}")

    def set_target(self, symbol: str, target: float, exchange: str = "NSE"):
        """Set target for a position"""
        key = f"{exchange}:{symbol}"

        if key not in self.positions:
            logger.warning(f"Position {key} not found")
            return

        position = self.positions[key]
        position.target = target
        logger.info(f"Set target for {symbol}: {target}")

    def start_monitoring(self, price_feed=None, interval: float = 1.0):
        """
        Start background monitoring of positions

        Args:
            price_feed: Object with get_quote(symbol, exchange) method
            interval: Update interval in seconds
        """
        self._price_feed = price_feed
        self._running = True

        def monitor_loop():
            while self._running:
                if self._price_feed:
                    for key, position in list(self.positions.items()):
                        try:
                            quote = self._price_feed.get_quote(position.symbol, position.exchange)
                            if quote and 'ltp' in quote:
                                self.update_price(position.symbol, quote['ltp'], position.exchange)
                        except Exception as e:
                            logger.error(f"Error fetching price for {position.symbol}: {e}")
                time.sleep(interval)

        self._thread = threading.Thread(target=monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Risk manager monitoring started")

    def stop_monitoring(self):
        """Stop background monitoring"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Risk manager monitoring stopped")

    def get_daily_pnl(self) -> float:
        """Get total P&L for today"""
        return self.get_mtm_summary().total_pnl

    def check_risk_limits(self) -> Dict:
        """Check if any risk limits are breached"""
        mtm = self.get_mtm_summary()

        breaches = {
            'max_positions': len(self.positions) >= self.max_positions,
            'max_daily_loss': False
        }

        if self.max_daily_loss and mtm.total_pnl < -self.max_daily_loss:
            breaches['max_daily_loss'] = True

        return breaches

    # ==================== AUTO SQUARE-OFF METHODS ====================

    def configure_auto_square_off(self,
                                   daily_profit_target: float = None,
                                   daily_loss_limit: float = None,
                                   square_off_time: str = None,  # "15:15" format
                                   position_profit_percent: float = None,
                                   position_loss_percent: float = None,
                                   position_profit_amount: float = None,
                                   position_loss_amount: float = None,
                                   trailing_profit_percent: float = None,
                                   enabled: bool = True):
        """
        Configure auto square-off settings

        Args:
            daily_profit_target: Square off all positions when total daily profit reaches this
            daily_loss_limit: Square off all positions when total daily loss reaches this
            square_off_time: Time to auto square-off (format: "HH:MM", e.g., "15:15")
            position_profit_percent: Square off individual position at this profit %
            position_loss_percent: Square off individual position at this loss %
            position_profit_amount: Square off individual position at this profit amount
            position_loss_amount: Square off individual position at this loss amount
            trailing_profit_percent: Trailing profit lock (square off when price falls this % from peak)
            enabled: Enable/disable auto square-off
        """
        self.auto_square_off.daily_profit_target = daily_profit_target
        self.auto_square_off.daily_loss_limit = daily_loss_limit

        if square_off_time:
            try:
                hours, minutes = map(int, square_off_time.split(':'))
                self.auto_square_off.square_off_time = dt_time(hours, minutes)
            except ValueError:
                logger.error(f"Invalid square-off time format: {square_off_time}")

        self.auto_square_off.position_profit_percent = position_profit_percent
        self.auto_square_off.position_loss_percent = position_loss_percent
        self.auto_square_off.position_profit_amount = position_profit_amount
        self.auto_square_off.position_loss_amount = position_loss_amount
        self.auto_square_off.trailing_profit_percent = trailing_profit_percent
        self.auto_square_off.enabled = enabled

        logger.info(f"Auto square-off configured: {self.auto_square_off}")

    def check_auto_square_off(self):
        """
        Check all auto square-off conditions and execute if triggered.
        Call this method periodically (e.g., on every price update)
        """
        if not self.auto_square_off.enabled or self._squared_off_today:
            return

        settings = self.auto_square_off
        mtm = self.get_mtm_summary()
        current_time = datetime.now().time()

        # 1. Check time-based square-off
        if settings.square_off_time:
            if current_time >= settings.square_off_time:
                self._execute_square_off_all(SquareOffReason.TIME_BASED,
                    f"Market closing time {settings.square_off_time}")
                return

        # 2. Check daily profit target
        if settings.daily_profit_target and mtm.total_pnl >= settings.daily_profit_target:
            self._execute_square_off_all(SquareOffReason.DAILY_PROFIT_TARGET,
                f"Daily profit target ₹{settings.daily_profit_target} reached! P&L: ₹{mtm.total_pnl:.2f}")
            return

        # 3. Check daily loss limit
        if settings.daily_loss_limit and mtm.total_pnl <= -settings.daily_loss_limit:
            self._execute_square_off_all(SquareOffReason.DAILY_LOSS_LIMIT,
                f"Daily loss limit ₹{settings.daily_loss_limit} hit! P&L: ₹{mtm.total_pnl:.2f}")
            return

        # 4. Check per-position limits
        for key, position in list(self.positions.items()):
            self._check_position_square_off(position)

    def _check_position_square_off(self, position: Position):
        """Check if a single position should be squared off"""
        settings = self.auto_square_off
        key = f"{position.exchange}:{position.symbol}"

        # Update max profit tracking for trailing
        if key not in self._position_max_profits:
            self._position_max_profits[key] = position.pnl
        elif position.pnl > self._position_max_profits[key]:
            self._position_max_profits[key] = position.pnl

        # Check profit percentage
        if settings.position_profit_percent and position.pnl_percent >= settings.position_profit_percent:
            self._execute_square_off_position(position, SquareOffReason.POSITION_PROFIT,
                f"Position profit {position.pnl_percent:.1f}% >= {settings.position_profit_percent}%")
            return

        # Check loss percentage
        if settings.position_loss_percent and position.pnl_percent <= -settings.position_loss_percent:
            self._execute_square_off_position(position, SquareOffReason.POSITION_LOSS,
                f"Position loss {position.pnl_percent:.1f}% >= {settings.position_loss_percent}%")
            return

        # Check profit amount
        if settings.position_profit_amount and position.pnl >= settings.position_profit_amount:
            self._execute_square_off_position(position, SquareOffReason.POSITION_PROFIT,
                f"Position profit ₹{position.pnl:.2f} >= ₹{settings.position_profit_amount}")
            return

        # Check loss amount
        if settings.position_loss_amount and position.pnl <= -settings.position_loss_amount:
            self._execute_square_off_position(position, SquareOffReason.POSITION_LOSS,
                f"Position loss ₹{abs(position.pnl):.2f} >= ₹{settings.position_loss_amount}")
            return

        # Check trailing profit
        if settings.trailing_profit_percent and key in self._position_max_profits:
            max_profit = self._position_max_profits[key]
            if max_profit > 0:  # Only trail when in profit
                # Calculate how much profit has fallen from peak
                profit_drop = max_profit - position.pnl
                drop_percent = (profit_drop / max_profit) * 100 if max_profit > 0 else 0

                if drop_percent >= settings.trailing_profit_percent:
                    self._execute_square_off_position(position, SquareOffReason.POSITION_PROFIT,
                        f"Trailing profit: fell {drop_percent:.1f}% from peak ₹{max_profit:.2f}")
                    return

    def _execute_square_off_position(self, position: Position, reason: SquareOffReason, message: str):
        """Execute square-off for a single position"""
        logger.warning(f"AUTO SQUARE-OFF [{reason.value}]: {position.symbol} - {message}")

        # Execute order via broker
        if self._broker:
            try:
                # Determine order side (opposite of position)
                side = "SELL" if position.quantity > 0 else "BUY"

                order_result = self._broker.place_order(
                    symbol=position.symbol,
                    exchange=position.exchange,
                    side=side,
                    quantity=abs(position.quantity),
                    order_type="MARKET",
                    product="MIS"
                )
                logger.info(f"Square-off order placed: {order_result}")

            except Exception as e:
                logger.error(f"Failed to place square-off order: {e}")

        # Close position in tracking
        self.close_position(position.symbol, position.current_price, position.exchange)

        # Remove from max profit tracking
        key = f"{position.exchange}:{position.symbol}"
        if key in self._position_max_profits:
            del self._position_max_profits[key]

        # Notify callbacks
        self._notify_square_off(position, reason, message)

    def _execute_square_off_all(self, reason: SquareOffReason, message: str):
        """Execute square-off for all positions"""
        logger.warning(f"AUTO SQUARE-OFF ALL [{reason.value}]: {message}")

        self._squared_off_today = True

        for key, position in list(self.positions.items()):
            self._execute_square_off_position(position, reason, message)

        logger.info("All positions squared off")

    def _notify_square_off(self, position: Position, reason: SquareOffReason, message: str):
        """Notify square-off callbacks"""
        event_data = {
            'symbol': position.symbol,
            'exchange': position.exchange,
            'quantity': position.quantity,
            'entry_price': position.entry_price,
            'exit_price': position.current_price,
            'pnl': position.pnl,
            'pnl_percent': position.pnl_percent,
            'reason': reason.value,
            'message': message,
            'timestamp': datetime.now()
        }

        for callback in self.square_off_callbacks:
            try:
                callback(event_data)
            except Exception as e:
                logger.error(f"Square-off callback error: {e}")

    def reset_daily_tracking(self):
        """Reset daily tracking (call at start of each trading day)"""
        self._squared_off_today = False
        self._position_max_profits.clear()
        self.closed_positions = [p for p in self.closed_positions
                                 if p.entry_time.date() != date.today()]
        logger.info("Daily tracking reset")

    def get_auto_square_off_status(self) -> Dict:
        """Get current auto square-off status and settings"""
        mtm = self.get_mtm_summary()
        settings = self.auto_square_off

        status = {
            'enabled': settings.enabled,
            'squared_off_today': self._squared_off_today,
            'current_daily_pnl': mtm.total_pnl,
            'settings': {
                'daily_profit_target': settings.daily_profit_target,
                'daily_loss_limit': settings.daily_loss_limit,
                'square_off_time': str(settings.square_off_time) if settings.square_off_time else None,
                'position_profit_percent': settings.position_profit_percent,
                'position_loss_percent': settings.position_loss_percent,
                'position_profit_amount': settings.position_profit_amount,
                'position_loss_amount': settings.position_loss_amount,
                'trailing_profit_percent': settings.trailing_profit_percent
            },
            'progress': {}
        }

        # Calculate progress towards limits
        if settings.daily_profit_target:
            status['progress']['daily_profit'] = (mtm.total_pnl / settings.daily_profit_target) * 100

        if settings.daily_loss_limit:
            status['progress']['daily_loss'] = (abs(mtm.total_pnl) / settings.daily_loss_limit) * 100 if mtm.total_pnl < 0 else 0

        return status
