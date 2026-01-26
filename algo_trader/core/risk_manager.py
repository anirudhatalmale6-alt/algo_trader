"""
Risk Manager - Handles Trailing Stop Loss, MTM P&L, and Risk Management
"""
import threading
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from loguru import logger


class StopLossType(Enum):
    FIXED = "FIXED"  # Fixed stop loss price
    PERCENTAGE = "PERCENTAGE"  # Percentage based
    TRAILING = "TRAILING"  # Trailing stop loss
    TRAILING_PERCENTAGE = "TRAILING_PERCENTAGE"  # Trailing with percentage


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

        self._running = False
        self._thread = None
        self._price_feed = None

        # Risk settings
        self.max_loss_per_trade_percent = 2.0
        self.max_daily_loss = None
        self.max_positions = 10

    def register_mtm_callback(self, callback: Callable):
        """Register callback for MTM updates"""
        self.mtm_callbacks.append(callback)

    def register_sl_hit_callback(self, callback: Callable):
        """Register callback for stop loss hits"""
        self.sl_hit_callbacks.append(callback)

    def register_target_hit_callback(self, callback: Callable):
        """Register callback for target hits"""
        self.target_hit_callbacks.append(callback)

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
