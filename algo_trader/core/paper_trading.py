"""
Paper Trading / Simulator Module
Simulates trades without real money for testing strategies
"""
import threading
import random
from typing import Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class OrderStatus(Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class PaperOrder:
    """Represents a simulated order"""
    order_id: str
    symbol: str
    action: str  # BUY or SELL
    quantity: int
    order_type: str  # MARKET, LIMIT
    price: float = 0.0  # For LIMIT orders
    executed_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.now)
    executed_at: datetime = None
    source: str = ""  # Strategy name, Chartink scanner, etc.


@dataclass
class PaperPosition:
    """Represents a simulated position"""
    symbol: str
    quantity: int
    avg_price: float
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    action: str = "BUY"  # BUY = Long, SELL = Short


class PaperTradingSimulator:
    """
    Paper Trading Simulator

    Simulates order execution and position tracking without real money.
    Useful for testing strategies before going live.
    """

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.available_capital = initial_capital
        self.used_capital = 0.0

        self.orders: Dict[str, PaperOrder] = {}
        self.positions: Dict[str, PaperPosition] = {}
        self.trade_history: List[Dict] = []

        self._order_counter = 0
        self._lock = threading.Lock()

        # Callbacks
        self._order_callbacks: List[Callable] = []
        self._position_callbacks: List[Callable] = []

        # Simulation settings
        self.slippage_percent = 0.05  # 0.05% slippage
        self.execution_delay_ms = 100  # Simulated delay

        # Stats
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0

        logger.info(f"Paper Trading Simulator initialized with ₹{initial_capital:,.2f}")

    def register_order_callback(self, callback: Callable):
        """Register callback for order updates"""
        self._order_callbacks.append(callback)

    def register_position_callback(self, callback: Callable):
        """Register callback for position updates"""
        self._position_callbacks.append(callback)

    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        self._order_counter += 1
        return f"PAPER_{datetime.now().strftime('%Y%m%d')}_{self._order_counter:06d}"

    def _simulate_price(self, base_price: float, action: str) -> float:
        """Simulate execution price with slippage"""
        slippage = base_price * (self.slippage_percent / 100)
        # Buy at slightly higher, sell at slightly lower (unfavorable slippage)
        if action.upper() == "BUY":
            return base_price + slippage
        else:
            return base_price - slippage

    def place_order(self, symbol: str, action: str, quantity: int,
                    order_type: str = "MARKET", price: float = 0.0,
                    source: str = "") -> Dict:
        """
        Place a simulated order

        Args:
            symbol: Stock/instrument symbol
            action: BUY or SELL
            quantity: Number of shares/lots
            order_type: MARKET or LIMIT
            price: Price for LIMIT orders, or current market price for MARKET
            source: Source of the order (strategy name, scanner, etc.)

        Returns:
            Dict with 'success', 'order_id', and 'message' keys
        """
        with self._lock:
            if quantity <= 0:
                logger.error("Invalid quantity")
                return {'success': False, 'order_id': None, 'message': 'Invalid quantity'}

            if price <= 0 and order_type == "MARKET":
                logger.error("Price required for simulation")
                return {'success': False, 'order_id': None, 'message': 'Price required for MARKET order'}

            # Check capital for BUY orders
            required_capital = price * quantity
            if action.upper() == "BUY" and required_capital > self.available_capital:
                logger.warning(f"Insufficient capital: need ₹{required_capital:.2f}, have ₹{self.available_capital:.2f}")
                return {'success': False, 'order_id': None, 'message': f'Insufficient capital: need ₹{required_capital:.2f}'}

            order_id = self._generate_order_id()

            order = PaperOrder(
                order_id=order_id,
                symbol=symbol.upper(),
                action=action.upper(),
                quantity=quantity,
                order_type=order_type,
                price=price,
                source=source
            )

            self.orders[order_id] = order
            logger.info(f"Paper order placed: {order_id} - {action} {quantity} {symbol} @ ₹{price:.2f}")

            # Execute immediately for MARKET orders
            if order_type == "MARKET":
                self._execute_order(order_id, price)

            return {'success': True, 'order_id': order_id, 'message': 'Order executed'}

    def _execute_order(self, order_id: str, market_price: float):
        """Execute a pending order"""
        if order_id not in self.orders:
            return

        order = self.orders[order_id]
        if order.status != OrderStatus.PENDING:
            return

        # Simulate execution price with slippage
        executed_price = self._simulate_price(market_price, order.action)
        order.executed_price = executed_price
        order.status = OrderStatus.EXECUTED
        order.executed_at = datetime.now()

        trade_value = executed_price * order.quantity

        # Update capital
        if order.action == "BUY":
            self.available_capital -= trade_value
            self.used_capital += trade_value
        else:
            self.available_capital += trade_value
            self.used_capital -= trade_value

        # Update position
        self._update_position(order)

        # Record trade
        self.trade_history.append({
            'order_id': order_id,
            'symbol': order.symbol,
            'action': order.action,
            'quantity': order.quantity,
            'price': executed_price,
            'value': trade_value,
            'timestamp': order.executed_at,
            'source': order.source
        })

        self.total_trades += 1
        logger.info(f"Paper order executed: {order_id} @ ₹{executed_price:.2f}")

        # Notify callbacks
        for callback in self._order_callbacks:
            try:
                callback(order)
            except Exception as e:
                logger.error(f"Order callback error: {e}")

    def _update_position(self, order: PaperOrder):
        """Update position after order execution"""
        symbol = order.symbol

        if symbol in self.positions:
            pos = self.positions[symbol]

            if order.action == pos.action:
                # Adding to position
                total_value = (pos.avg_price * pos.quantity) + (order.executed_price * order.quantity)
                total_qty = pos.quantity + order.quantity
                pos.avg_price = total_value / total_qty
                pos.quantity = total_qty
            else:
                # Reducing/closing position
                if order.quantity >= pos.quantity:
                    # Close position
                    pnl = self._calculate_pnl(pos, order.executed_price, pos.quantity)
                    self.total_pnl += pnl
                    if pnl >= 0:
                        self.winning_trades += 1
                    else:
                        self.losing_trades += 1

                    remaining_qty = order.quantity - pos.quantity
                    del self.positions[symbol]

                    # If there's remaining quantity, create opposite position
                    if remaining_qty > 0:
                        self.positions[symbol] = PaperPosition(
                            symbol=symbol,
                            quantity=remaining_qty,
                            avg_price=order.executed_price,
                            current_price=order.executed_price,
                            action=order.action
                        )
                else:
                    # Partial close
                    pnl = self._calculate_pnl(pos, order.executed_price, order.quantity)
                    self.total_pnl += pnl
                    if pnl >= 0:
                        self.winning_trades += 1
                    else:
                        self.losing_trades += 1
                    pos.quantity -= order.quantity
        else:
            # New position
            self.positions[symbol] = PaperPosition(
                symbol=symbol,
                quantity=order.quantity,
                avg_price=order.executed_price,
                current_price=order.executed_price,
                action=order.action
            )

        # Notify callbacks
        for callback in self._position_callbacks:
            try:
                callback(self.positions.get(symbol))
            except Exception as e:
                logger.error(f"Position callback error: {e}")

    def _calculate_pnl(self, position: PaperPosition, exit_price: float, quantity: int) -> float:
        """Calculate P&L for closing a position"""
        if position.action == "BUY":
            return (exit_price - position.avg_price) * quantity
        else:
            return (position.avg_price - exit_price) * quantity

    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for all positions"""
        with self._lock:
            for symbol, price in prices.items():
                if symbol in self.positions:
                    pos = self.positions[symbol]
                    pos.current_price = price
                    if pos.action == "BUY":
                        pos.pnl = (price - pos.avg_price) * pos.quantity
                    else:
                        pos.pnl = (pos.avg_price - price) * pos.quantity
                    pos.pnl_percent = (pos.pnl / (pos.avg_price * pos.quantity)) * 100

    def get_position(self, symbol: str) -> Optional[PaperPosition]:
        """Get position for a symbol"""
        return self.positions.get(symbol.upper())

    def get_all_positions(self) -> List[Dict]:
        """Get all open positions"""
        return [
            {
                'symbol': pos.symbol,
                'quantity': pos.quantity,
                'avg_price': pos.avg_price,
                'current_price': pos.current_price,
                'pnl': pos.pnl,
                'pnl_percent': pos.pnl_percent,
                'action': pos.action
            }
            for pos in self.positions.values()
        ]

    def get_order(self, order_id: str) -> Optional[PaperOrder]:
        """Get order by ID"""
        return self.orders.get(order_id)

    def get_trade_history(self) -> List[Dict]:
        """Get all trade history"""
        return self.trade_history.copy()

    def get_stats(self) -> Dict:
        """Get trading statistics"""
        unrealized_pnl = sum(pos.pnl for pos in self.positions.values())
        total_equity = self.available_capital + self.used_capital + unrealized_pnl

        return {
            'initial_capital': self.initial_capital,
            'available_capital': self.available_capital,
            'used_capital': self.used_capital,
            'total_equity': total_equity,
            'total_pnl': self.total_pnl,
            'unrealized_pnl': unrealized_pnl,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            'open_positions': len(self.positions)
        }

    def reset(self, initial_capital: float = None):
        """Reset simulator to initial state"""
        with self._lock:
            if initial_capital:
                self.initial_capital = initial_capital
            self.available_capital = self.initial_capital
            self.used_capital = 0.0
            self.orders.clear()
            self.positions.clear()
            self.trade_history.clear()
            self._order_counter = 0
            self.total_trades = 0
            self.winning_trades = 0
            self.losing_trades = 0
            self.total_pnl = 0.0
            logger.info(f"Paper Trading Simulator reset with ₹{self.initial_capital:,.2f}")

    def export_trades_to_csv(self, filepath: str):
        """Export trade history to CSV file"""
        import csv

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'order_id', 'timestamp', 'symbol', 'action',
                'quantity', 'price', 'value', 'source'
            ])
            writer.writeheader()
            for trade in self.trade_history:
                row = trade.copy()
                row['timestamp'] = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                writer.writerow(row)

        logger.info(f"Exported {len(self.trade_history)} trades to {filepath}")
