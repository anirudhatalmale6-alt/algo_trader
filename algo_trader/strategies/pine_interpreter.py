"""
Pine Script Interpreter
Executes parsed Pine Script strategies
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from algo_trader.strategies.pine_parser import ParsedStrategy
from algo_trader.strategies.indicators import Indicators
from algo_trader.core.strategy_engine import Signal, SignalType


class PineScriptInterpreter:
    """
    Executes Pine Script strategies
    Converts parsed strategy into trading signals
    """

    def __init__(self, strategy: ParsedStrategy):
        self.strategy = strategy
        self.indicators = Indicators()
        self.variables = {}
        self.data = None  # OHLCV DataFrame
        self.current_bar = 0
        self.position = 0  # Current position: 1 = long, -1 = short, 0 = flat

        # Initialize variables from strategy
        self._init_variables()

    def _init_variables(self):
        """Initialize strategy variables and inputs"""
        # Copy input default values
        for name, params in self.strategy.inputs.items():
            self.variables[name] = params.get('defval', 0)

        # Copy variable declarations
        for name, value in self.strategy.variables.items():
            self.variables[name] = value

    def set_input(self, name: str, value: Any):
        """Set input parameter value"""
        self.variables[name] = value

    def load_data(self, data: pd.DataFrame):
        """
        Load OHLCV data for strategy execution
        DataFrame must have columns: open, high, low, close, volume
        Index should be datetime
        """
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in data.columns:
                raise ValueError(f"Missing required column: {col}")

        self.data = data.copy()
        self.data.columns = self.data.columns.str.lower()

        # Add calculated price columns
        self.data['hl2'] = (self.data['high'] + self.data['low']) / 2
        self.data['hlc3'] = (self.data['high'] + self.data['low'] + self.data['close']) / 3
        self.data['ohlc4'] = (self.data['open'] + self.data['high'] + self.data['low'] + self.data['close']) / 4
        self.data['hlcc4'] = (self.data['high'] + self.data['low'] + 2 * self.data['close']) / 4

        # Calculate all indicators
        self._calculate_indicators()

    def _calculate_indicators(self):
        """Pre-calculate all indicators used in strategy"""
        for indicator in self.strategy.indicators:
            func_name = indicator['function']
            params = indicator['params']

            try:
                result = self._call_indicator(func_name, params)
                if result is not None:
                    # Store result in variables
                    var_name = f"_ind_{len(self.variables)}"
                    self.variables[var_name] = result
            except Exception as e:
                logger.error(f"Error calculating indicator {func_name}: {e}")

    def _call_indicator(self, func_name: str, params: List) -> Any:
        """Call an indicator function"""
        # Resolve parameters
        resolved_params = [self._resolve_value(p) for p in params]

        # Map Pine Script function to our implementation
        indicator_map = {
            'ta.sma': lambda p: self.indicators.sma(p[0], int(p[1])),
            'ta.ema': lambda p: self.indicators.ema(p[0], int(p[1])),
            'ta.wma': lambda p: self.indicators.wma(p[0], int(p[1])),
            'ta.vwma': lambda p: self.indicators.vwma(p[0], self.data['volume'], int(p[1])),
            'ta.rma': lambda p: self.indicators.rma(p[0], int(p[1])),
            'ta.rsi': lambda p: self.indicators.rsi(p[0], int(p[1]) if len(p) > 1 else 14),
            'ta.atr': lambda p: self.indicators.atr(self.data['high'], self.data['low'], self.data['close'], int(p[0]) if p else 14),
            'ta.tr': lambda p: self.indicators.tr(self.data['high'], self.data['low'], self.data['close']),
            'ta.highest': lambda p: self.indicators.highest(p[0], int(p[1])),
            'ta.lowest': lambda p: self.indicators.lowest(p[0], int(p[1])),
            'ta.crossover': lambda p: self.indicators.crossover(p[0], p[1]),
            'ta.crossunder': lambda p: self.indicators.crossunder(p[0], p[1]),
            'ta.change': lambda p: self.indicators.change(p[0], int(p[1]) if len(p) > 1 else 1),
            'ta.mom': lambda p: self.indicators.mom(p[0], int(p[1]) if len(p) > 1 else 10),
            'ta.roc': lambda p: self.indicators.roc(p[0], int(p[1]) if len(p) > 1 else 10),
            'ta.vwap': lambda p: self.indicators.vwap(self.data['high'], self.data['low'], self.data['close'], self.data['volume']),
            'ta.cci': lambda p: self.indicators.cci(self.data['high'], self.data['low'], self.data['close'], int(p[0]) if p else 20),
            'ta.adx': lambda p: self.indicators.adx(self.data['high'], self.data['low'], self.data['close'], int(p[0]) if p else 14),
        }

        # Handle MACD (returns tuple)
        if func_name == 'ta.macd':
            source = resolved_params[0] if resolved_params else self.data['close']
            fast = int(resolved_params[1]) if len(resolved_params) > 1 else 12
            slow = int(resolved_params[2]) if len(resolved_params) > 2 else 26
            signal = int(resolved_params[3]) if len(resolved_params) > 3 else 9
            return self.indicators.macd(source, fast, slow, signal)

        # Handle Bollinger Bands (returns tuple)
        if func_name == 'ta.bb':
            source = resolved_params[0] if resolved_params else self.data['close']
            length = int(resolved_params[1]) if len(resolved_params) > 1 else 20
            mult = float(resolved_params[2]) if len(resolved_params) > 2 else 2.0
            return self.indicators.bollinger_bands(source, length, mult)

        # Handle Stochastic (returns tuple)
        if func_name == 'ta.stoch':
            k_len = int(resolved_params[0]) if resolved_params else 14
            k_smooth = int(resolved_params[1]) if len(resolved_params) > 1 else 1
            d_smooth = int(resolved_params[2]) if len(resolved_params) > 2 else 3
            return self.indicators.stoch(self.data['high'], self.data['low'], self.data['close'],
                                        k_len, k_smooth, d_smooth)

        # Handle SuperTrend (returns tuple)
        if func_name == 'ta.supertrend':
            length = int(resolved_params[0]) if resolved_params else 10
            mult = float(resolved_params[1]) if len(resolved_params) > 1 else 3.0
            return self.indicators.supertrend(self.data['high'], self.data['low'], self.data['close'],
                                             length, mult)

        # Call mapped indicator
        if func_name in indicator_map:
            return indicator_map[func_name](resolved_params)

        logger.warning(f"Unknown indicator: {func_name}")
        return None

    def _resolve_value(self, value: Any) -> Any:
        """Resolve a value (variable reference, literal, or expression)"""
        if value is None:
            return None

        # Direct values
        if isinstance(value, (int, float, str, bool)):
            return value

        # Pandas Series
        if isinstance(value, pd.Series):
            return value

        # Dictionary (expression or variable reference)
        if isinstance(value, dict):
            # Variable reference
            if 'var' in value:
                var_name = value['var']
                # Built-in price variables
                if var_name in ('open', 'high', 'low', 'close', 'volume',
                               'hl2', 'hlc3', 'ohlc4', 'hlcc4'):
                    return self.data[var_name]

                # Built-in variables
                if var_name == 'bar_index':
                    return pd.Series(range(len(self.data)), index=self.data.index)

                # Strategy position
                if var_name == 'strategy.position_size':
                    return self.position

                # User variables
                if var_name in self.variables:
                    return self.variables[var_name]

                return None

            # Function call
            if 'function' in value:
                return self._call_indicator(value['function'], value.get('params', []))

            # Binary operation
            if 'op' in value:
                return self._eval_operation(value)

            # Ternary
            if 'ternary' in value:
                condition = self._resolve_value(value['condition'])
                if self._is_true(condition):
                    return self._resolve_value(value['true'])
                else:
                    return self._resolve_value(value['false'])

        return value

    def _eval_operation(self, expr: Dict) -> Any:
        """Evaluate a binary or unary operation"""
        op = expr['op']

        # Unary operations
        if op == 'neg':
            return -self._resolve_value(expr['value'])
        if op == 'not':
            return ~self._resolve_value(expr['value'])

        # Binary operations
        left = self._resolve_value(expr['left'])
        right = self._resolve_value(expr['right'])

        # Arithmetic
        if op == '+':
            return left + right
        if op == '-':
            return left - right
        if op == '*':
            return left * right
        if op == '/':
            return left / right
        if op == '%':
            return left % right

        # Comparison
        if op == '==':
            return left == right
        if op == '!=':
            return left != right
        if op == '>':
            return left > right
        if op == '<':
            return left < right
        if op == '>=':
            return left >= right
        if op == '<=':
            return left <= right

        # Logical
        if op == 'and':
            return left & right
        if op == 'or':
            return left | right

        return None

    def _is_true(self, value: Any) -> bool:
        """Check if a value is truthy"""
        if isinstance(value, pd.Series):
            return value.iloc[-1] if len(value) > 0 else False
        if isinstance(value, (np.bool_, bool)):
            return bool(value)
        return bool(value)

    def process_candle(self, symbol: str, candle: Dict) -> Optional[Signal]:
        """
        Process a new candle and generate signals

        candle should have: open, high, low, close, volume, time
        """
        if self.data is None:
            return None

        # Append new candle to data
        new_row = pd.DataFrame([{
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'volume': candle['volume']
        }], index=[candle.get('time', datetime.now())])

        self.data = pd.concat([self.data, new_row])

        # Recalculate price columns
        self.data['hl2'] = (self.data['high'] + self.data['low']) / 2
        self.data['hlc3'] = (self.data['high'] + self.data['low'] + self.data['close']) / 3
        self.data['ohlc4'] = (self.data['open'] + self.data['high'] + self.data['low'] + self.data['close']) / 4

        # Recalculate indicators
        self._calculate_indicators()

        self.current_bar = len(self.data) - 1

        # Check entry conditions
        for entry in self.strategy.entry_conditions:
            signal = self._check_entry(entry, symbol)
            if signal:
                return signal

        # Check exit conditions
        for exit_cond in self.strategy.exit_conditions:
            signal = self._check_exit(exit_cond, symbol)
            if signal:
                return signal

        return Signal(signal_type=SignalType.NONE, symbol=symbol)

    def _check_entry(self, entry: Dict, symbol: str) -> Optional[Signal]:
        """Check entry condition and generate signal"""
        params = entry.get('params', {})
        direction = params.get('direction', 'long')

        # Check when condition if present
        when_cond = params.get('when')
        if when_cond:
            if not self._is_true(self._resolve_value(when_cond)):
                return None

        # Determine signal type
        if direction == 'long' or params.get('id') == 'strategy.long':
            signal_type = SignalType.BUY
        else:
            signal_type = SignalType.SELL

        # Check position
        if signal_type == SignalType.BUY and self.position >= 1:
            return None
        if signal_type == SignalType.SELL and self.position <= -1:
            return None

        # Update position
        if signal_type == SignalType.BUY:
            self.position = 1
        else:
            self.position = -1

        return Signal(
            signal_type=signal_type,
            symbol=symbol,
            price=float(self.data['close'].iloc[-1]),
            quantity=params.get('qty', 1),
            stop_loss=params.get('stop'),
            target=params.get('limit')
        )

    def _check_exit(self, exit_cond: Dict, symbol: str) -> Optional[Signal]:
        """Check exit condition and generate signal"""
        func_name = exit_cond.get('function', '')
        params = exit_cond.get('params', {})

        # Check when condition if present
        when_cond = params.get('when')
        if when_cond:
            if not self._is_true(self._resolve_value(when_cond)):
                return None

        # strategy.close_all
        if 'close_all' in func_name:
            if self.position != 0:
                signal_type = SignalType.EXIT_LONG if self.position > 0 else SignalType.SELL
                self.position = 0
                return Signal(
                    signal_type=signal_type,
                    symbol=symbol,
                    price=float(self.data['close'].iloc[-1])
                )

        # strategy.close or strategy.exit
        if self.position > 0:
            signal_type = SignalType.EXIT_LONG
            self.position = 0
            return Signal(
                signal_type=signal_type,
                symbol=symbol,
                price=float(self.data['close'].iloc[-1])
            )
        elif self.position < 0:
            signal_type = SignalType.BUY  # Cover short
            self.position = 0
            return Signal(
                signal_type=signal_type,
                symbol=symbol,
                price=float(self.data['close'].iloc[-1])
            )

        return None

    def run_backtest(self, initial_capital: float = 100000) -> Dict:
        """
        Run backtest on loaded data
        Returns backtest results
        """
        if self.data is None:
            return {'error': 'No data loaded'}

        trades = []
        equity = initial_capital
        equity_curve = [initial_capital]
        position = 0
        entry_price = 0

        for i in range(1, len(self.data)):
            self.current_bar = i

            # Get current bar data
            bar = self.data.iloc[i]

            # Check all conditions
            for entry in self.strategy.entry_conditions:
                if position == 0:  # Only enter if flat
                    # Simplified condition check for backtest
                    params = entry.get('params', {})
                    direction = params.get('direction', 'long')

                    # Check if we should enter
                    when_cond = params.get('when')
                    should_enter = True

                    if when_cond:
                        resolved = self._resolve_value(when_cond)
                        if isinstance(resolved, pd.Series):
                            should_enter = bool(resolved.iloc[i]) if i < len(resolved) else False
                        else:
                            should_enter = bool(resolved)

                    if should_enter:
                        position = 1 if direction == 'long' else -1
                        entry_price = bar['close']
                        trades.append({
                            'type': 'entry',
                            'direction': direction,
                            'price': entry_price,
                            'time': self.data.index[i],
                            'bar': i
                        })

            # Check exits
            for exit_cond in self.strategy.exit_conditions:
                if position != 0:
                    params = exit_cond.get('params', {})
                    when_cond = params.get('when')
                    should_exit = True

                    if when_cond:
                        resolved = self._resolve_value(when_cond)
                        if isinstance(resolved, pd.Series):
                            should_exit = bool(resolved.iloc[i]) if i < len(resolved) else False
                        else:
                            should_exit = bool(resolved)

                    if should_exit:
                        exit_price = bar['close']
                        pnl = (exit_price - entry_price) * position
                        equity += pnl

                        trades.append({
                            'type': 'exit',
                            'price': exit_price,
                            'pnl': pnl,
                            'time': self.data.index[i],
                            'bar': i
                        })

                        position = 0
                        entry_price = 0

            equity_curve.append(equity)

        # Calculate metrics
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) < 0]

        # Calculate max drawdown
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.cummax()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_drawdown = abs(drawdown.min()) * 100

        # Calculate Sharpe ratio (simplified)
        if len(equity_curve) > 1:
            returns = pd.Series(equity_curve).pct_change().dropna()
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() != 0 else 0
        else:
            sharpe = 0

        total_trades = len([t for t in trades if t['type'] == 'exit'])
        gross_profit = sum(t.get('pnl', 0) for t in winning_trades)
        gross_loss = abs(sum(t.get('pnl', 0) for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        return {
            'initial_capital': initial_capital,
            'final_capital': equity,
            'total_return': ((equity - initial_capital) / initial_capital) * 100,
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'profit_factor': profit_factor,
            'trades': trades,
            'equity_curve': equity_curve
        }
