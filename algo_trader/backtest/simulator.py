"""
Advanced Backtesting Simulator
Runs strategies on historical data with realistic trade execution
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import threading
import time
from loguru import logger


class TradeType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TradeStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass
class SimulatedTrade:
    """Represents a simulated trade in backtest"""
    trade_id: int
    symbol: str
    trade_type: TradeType
    entry_time: datetime
    entry_price: float
    quantity: int
    exit_time: datetime = None
    exit_price: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    status: TradeStatus = TradeStatus.OPEN
    exit_reason: str = ""
    # For tracking
    high_since_entry: float = 0.0
    low_since_entry: float = 0.0


@dataclass
class BacktestResult:
    """Results from a backtest run"""
    symbol: str
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_pnl: float
    total_pnl_percent: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    max_drawdown: float
    max_drawdown_percent: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    avg_trade_duration: float  # in minutes
    trades: List[SimulatedTrade] = field(default_factory=list)
    equity_curve: List[Dict] = field(default_factory=list)


class BacktestSimulator:
    """
    Advanced Backtesting Simulator

    Simulates strategy execution on historical data with:
    - Realistic order execution with slippage
    - Stop loss, target, trailing stop loss
    - Position sizing based on capital
    - Detailed trade log and statistics
    - Equity curve tracking
    """

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.available_capital = initial_capital

        self.trades: List[SimulatedTrade] = []
        self.open_trades: Dict[str, SimulatedTrade] = {}
        self.equity_curve: List[Dict] = []

        self._trade_counter = 0
        self._lock = threading.Lock()

        # Simulation settings
        self.slippage_percent = 0.05  # 0.05% slippage
        self.commission_per_trade = 20  # ₹20 per trade

        # Risk settings
        self.stop_loss_percent = 0.0
        self.target_percent = 0.0
        self.trailing_sl_percent = 0.0

        # Callbacks for UI updates
        self._trade_callbacks: List[Callable] = []
        self._progress_callbacks: List[Callable] = []

        # Simulation state
        self._running = False
        self._paused = False
        self._speed = 1.0  # 1.0 = normal, 2.0 = 2x speed, etc.

    def register_trade_callback(self, callback: Callable):
        """Register callback for trade events"""
        self._trade_callbacks.append(callback)

    def register_progress_callback(self, callback: Callable):
        """Register callback for progress updates"""
        self._progress_callbacks.append(callback)

    def set_risk_params(self, stop_loss: float = 0, target: float = 0,
                        trailing_sl: float = 0):
        """Set risk management parameters (in percentage)"""
        self.stop_loss_percent = stop_loss
        self.target_percent = target
        self.trailing_sl_percent = trailing_sl

    def set_speed(self, speed: float):
        """Set simulation speed (1.0 = normal)"""
        self._speed = max(0.1, min(10.0, speed))

    def pause(self):
        """Pause simulation"""
        self._paused = True

    def resume(self):
        """Resume simulation"""
        self._paused = False

    def stop(self):
        """Stop simulation"""
        self._running = False

    def _notify_trade(self, trade: SimulatedTrade, event: str):
        """Notify callbacks about trade event"""
        for callback in self._trade_callbacks:
            try:
                callback(trade, event)
            except Exception as e:
                logger.error(f"Trade callback error: {e}")

    def _notify_progress(self, current_idx: int, total: int,
                         current_time: datetime, current_price: float):
        """Notify callbacks about simulation progress"""
        for callback in self._progress_callbacks:
            try:
                callback(current_idx, total, current_time, current_price,
                        self.current_capital, len(self.open_trades))
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    def _calculate_slippage(self, price: float, is_buy: bool) -> float:
        """Calculate execution price with slippage"""
        slippage = price * (self.slippage_percent / 100)
        if is_buy:
            return price + slippage
        else:
            return price - slippage

    def _open_trade(self, symbol: str, trade_type: TradeType,
                    price: float, timestamp: datetime, quantity: int = 0):
        """Open a new trade"""
        with self._lock:
            # Calculate quantity if not specified
            if quantity <= 0:
                # Use 10% of available capital per trade
                trade_capital = self.available_capital * 0.1
                quantity = max(1, int(trade_capital / price))

            is_buy = trade_type == TradeType.LONG
            exec_price = self._calculate_slippage(price, is_buy)

            # Check if we have enough capital
            required = exec_price * quantity + self.commission_per_trade
            if required > self.available_capital:
                quantity = max(1, int((self.available_capital - self.commission_per_trade) / exec_price))
                if quantity <= 0:
                    logger.warning(f"Insufficient capital to open trade")
                    return None

            self._trade_counter += 1
            trade = SimulatedTrade(
                trade_id=self._trade_counter,
                symbol=symbol,
                trade_type=trade_type,
                entry_time=timestamp,
                entry_price=exec_price,
                quantity=quantity,
                high_since_entry=exec_price,
                low_since_entry=exec_price
            )

            # Update capital
            trade_value = exec_price * quantity + self.commission_per_trade
            self.available_capital -= trade_value

            self.trades.append(trade)
            self.open_trades[symbol] = trade

            logger.info(f"Opened {trade_type.value} trade: {symbol} @ ₹{exec_price:.2f} x {quantity}")
            self._notify_trade(trade, "OPEN")

            return trade

    def _close_trade(self, symbol: str, price: float, timestamp: datetime,
                     reason: str = "Signal"):
        """Close an existing trade"""
        with self._lock:
            if symbol not in self.open_trades:
                return None

            trade = self.open_trades[symbol]
            is_buy = trade.trade_type == TradeType.SHORT  # Closing long = sell, closing short = buy
            exec_price = self._calculate_slippage(price, is_buy)

            trade.exit_time = timestamp
            trade.exit_price = exec_price
            trade.exit_reason = reason
            trade.status = TradeStatus.CLOSED

            # Calculate P&L
            if trade.trade_type == TradeType.LONG:
                trade.pnl = (exec_price - trade.entry_price) * trade.quantity
            else:
                trade.pnl = (trade.entry_price - exec_price) * trade.quantity

            trade.pnl -= self.commission_per_trade  # Deduct exit commission
            trade.pnl_percent = (trade.pnl / (trade.entry_price * trade.quantity)) * 100

            # Update capital
            if trade.trade_type == TradeType.LONG:
                self.available_capital += exec_price * trade.quantity
            else:
                self.available_capital += trade.entry_price * trade.quantity + trade.pnl

            self.current_capital = self.available_capital

            del self.open_trades[symbol]

            logger.info(f"Closed trade: {symbol} @ ₹{exec_price:.2f}, P&L: ₹{trade.pnl:.2f} ({reason})")
            self._notify_trade(trade, "CLOSE")

            return trade

    def _check_risk_conditions(self, trade: SimulatedTrade, current_price: float) -> Optional[str]:
        """Check if any risk condition is hit"""
        entry = trade.entry_price

        # Update high/low since entry
        trade.high_since_entry = max(trade.high_since_entry, current_price)
        trade.low_since_entry = min(trade.low_since_entry, current_price)

        if trade.trade_type == TradeType.LONG:
            pnl_percent = ((current_price - entry) / entry) * 100

            # Stop Loss
            if self.stop_loss_percent > 0 and pnl_percent <= -self.stop_loss_percent:
                return "Stop Loss"

            # Target
            if self.target_percent > 0 and pnl_percent >= self.target_percent:
                return "Target"

            # Trailing Stop Loss
            if self.trailing_sl_percent > 0:
                high = trade.high_since_entry
                trail_price = high * (1 - self.trailing_sl_percent / 100)
                if current_price <= trail_price and current_price > entry:
                    return f"Trailing SL (High: ₹{high:.2f})"

        else:  # SHORT
            pnl_percent = ((entry - current_price) / entry) * 100

            # Stop Loss
            if self.stop_loss_percent > 0 and pnl_percent <= -self.stop_loss_percent:
                return "Stop Loss"

            # Target
            if self.target_percent > 0 and pnl_percent >= self.target_percent:
                return "Target"

            # Trailing Stop Loss
            if self.trailing_sl_percent > 0:
                low = trade.low_since_entry
                trail_price = low * (1 + self.trailing_sl_percent / 100)
                if current_price >= trail_price and current_price < entry:
                    return f"Trailing SL (Low: ₹{low:.2f})"

        return None

    def run_backtest(self, data: pd.DataFrame, strategy_func: Callable,
                     symbol: str = "UNKNOWN", strategy_name: str = "Strategy",
                     realtime_mode: bool = False) -> BacktestResult:
        """
        Run backtest on historical data

        Args:
            data: DataFrame with columns: datetime, open, high, low, close, volume
            strategy_func: Function that takes (row, index, data) and returns signal ('BUY', 'SELL', None)
            symbol: Symbol being tested
            strategy_name: Name of the strategy
            realtime_mode: If True, simulate real-time with delays for visualization

        Returns:
            BacktestResult with all statistics and trades
        """
        self._running = True
        self._paused = False

        # Reset state
        self.current_capital = self.initial_capital
        self.available_capital = self.initial_capital
        self.trades = []
        self.open_trades = {}
        self.equity_curve = []
        self._trade_counter = 0

        start_date = data.iloc[0]['datetime'] if 'datetime' in data.columns else datetime.now()
        end_date = data.iloc[-1]['datetime'] if 'datetime' in data.columns else datetime.now()

        total_rows = len(data)
        logger.info(f"Starting backtest: {symbol} from {start_date} to {end_date} ({total_rows} candles)")

        for idx, row in data.iterrows():
            if not self._running:
                break

            while self._paused and self._running:
                time.sleep(0.1)

            current_time = row.get('datetime', datetime.now())
            current_price = row['close']
            high = row['high']
            low = row['low']

            # Check risk conditions for open trades
            for sym, trade in list(self.open_trades.items()):
                # Check with high and low for more accurate SL/Target hit
                for check_price in [high, low, current_price]:
                    exit_reason = self._check_risk_conditions(trade, check_price)
                    if exit_reason:
                        self._close_trade(sym, check_price, current_time, exit_reason)
                        break

            # Get strategy signal
            signal = strategy_func(row, idx, data)

            # Process signal
            if signal == 'BUY':
                if symbol not in self.open_trades:
                    self._open_trade(symbol, TradeType.LONG, current_price, current_time)
                elif self.open_trades[symbol].trade_type == TradeType.SHORT:
                    # Close short and open long
                    self._close_trade(symbol, current_price, current_time, "Reverse Signal")
                    self._open_trade(symbol, TradeType.LONG, current_price, current_time)

            elif signal == 'SELL':
                if symbol not in self.open_trades:
                    self._open_trade(symbol, TradeType.SHORT, current_price, current_time)
                elif self.open_trades[symbol].trade_type == TradeType.LONG:
                    # Close long and open short
                    self._close_trade(symbol, current_price, current_time, "Reverse Signal")
                    self._open_trade(symbol, TradeType.SHORT, current_price, current_time)

            # Calculate current equity
            unrealized_pnl = 0
            for trade in self.open_trades.values():
                if trade.trade_type == TradeType.LONG:
                    unrealized_pnl += (current_price - trade.entry_price) * trade.quantity
                else:
                    unrealized_pnl += (trade.entry_price - current_price) * trade.quantity

            equity = self.available_capital + unrealized_pnl
            for trade in self.open_trades.values():
                equity += trade.entry_price * trade.quantity

            self.equity_curve.append({
                'datetime': current_time,
                'equity': equity,
                'price': current_price,
                'open_trades': len(self.open_trades)
            })

            # Notify progress
            self._notify_progress(idx, total_rows, current_time, current_price)

            # Simulate real-time delay
            if realtime_mode and self._running:
                time.sleep(0.1 / self._speed)

        # Close any remaining open trades at last price
        last_row = data.iloc[-1]
        last_price = last_row['close']
        last_time = last_row.get('datetime', datetime.now())

        for sym in list(self.open_trades.keys()):
            self._close_trade(sym, last_price, last_time, "End of Backtest")

        # Calculate results
        result = self._calculate_results(symbol, strategy_name, start_date, end_date)

        self._running = False
        logger.info(f"Backtest complete: {result.total_trades} trades, P&L: ₹{result.total_pnl:.2f}")

        return result

    def _calculate_results(self, symbol: str, strategy_name: str,
                          start_date: datetime, end_date: datetime) -> BacktestResult:
        """Calculate backtest statistics"""
        closed_trades = [t for t in self.trades if t.status == TradeStatus.CLOSED]

        winning = [t for t in closed_trades if t.pnl > 0]
        losing = [t for t in closed_trades if t.pnl <= 0]

        total_pnl = sum(t.pnl for t in closed_trades)
        total_wins = sum(t.pnl for t in winning)
        total_losses = abs(sum(t.pnl for t in losing))

        # Max drawdown
        max_equity = self.initial_capital
        max_drawdown = 0
        for point in self.equity_curve:
            eq = point['equity']
            max_equity = max(max_equity, eq)
            drawdown = max_equity - eq
            max_drawdown = max(max_drawdown, drawdown)

        # Average trade duration
        durations = []
        for t in closed_trades:
            if t.entry_time and t.exit_time:
                duration = (t.exit_time - t.entry_time).total_seconds() / 60
                durations.append(duration)
        avg_duration = np.mean(durations) if durations else 0

        result = BacktestResult(
            symbol=symbol,
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=self.current_capital,
            total_pnl=total_pnl,
            total_pnl_percent=(total_pnl / self.initial_capital) * 100,
            total_trades=len(closed_trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=(len(winning) / len(closed_trades) * 100) if closed_trades else 0,
            max_drawdown=max_drawdown,
            max_drawdown_percent=(max_drawdown / self.initial_capital) * 100,
            profit_factor=(total_wins / total_losses) if total_losses > 0 else float('inf'),
            avg_win=(total_wins / len(winning)) if winning else 0,
            avg_loss=(total_losses / len(losing)) if losing else 0,
            largest_win=max((t.pnl for t in winning), default=0),
            largest_loss=min((t.pnl for t in losing), default=0),
            avg_trade_duration=avg_duration,
            trades=closed_trades,
            equity_curve=self.equity_curve
        )

        return result

    def export_trades_csv(self, filepath: str):
        """Export trades to CSV"""
        import csv

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Trade ID', 'Symbol', 'Type', 'Entry Time', 'Entry Price',
                'Exit Time', 'Exit Price', 'Quantity', 'P&L', 'P&L %', 'Exit Reason'
            ])

            for trade in self.trades:
                if trade.status == TradeStatus.CLOSED:
                    writer.writerow([
                        trade.trade_id,
                        trade.symbol,
                        trade.trade_type.value,
                        trade.entry_time.strftime('%Y-%m-%d %H:%M:%S') if trade.entry_time else '',
                        f"{trade.entry_price:.2f}",
                        trade.exit_time.strftime('%Y-%m-%d %H:%M:%S') if trade.exit_time else '',
                        f"{trade.exit_price:.2f}",
                        trade.quantity,
                        f"{trade.pnl:.2f}",
                        f"{trade.pnl_percent:.2f}",
                        trade.exit_reason
                    ])

        logger.info(f"Exported {len(self.trades)} trades to {filepath}")
