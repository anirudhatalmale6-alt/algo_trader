"""
Advanced Interactive Chart Widget with Order Placement
"""
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from loguru import logger

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QSpinBox, QDoubleSpinBox, QGroupBox, QFormLayout,
    QMessageBox, QMenu, QToolBar, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QDialogButtonBox,
    QLineEdit, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import matplotlib.dates as mdates
import mplfinance as mpf


class OrderDialog(QDialog):
    """Dialog for placing orders from chart"""

    def __init__(self, symbol: str, price: float, side: str = "BUY", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Place {side} Order - {symbol}")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.symbol_label = QLabel(symbol)
        self.symbol_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        form.addRow("Symbol:", self.symbol_label)

        self.side_combo = QComboBox()
        self.side_combo.addItems(["BUY", "SELL"])
        self.side_combo.setCurrentText(side)
        form.addRow("Side:", self.side_combo)

        self.order_type = QComboBox()
        self.order_type.addItems(["MARKET", "LIMIT", "SL", "SL-M"])
        form.addRow("Order Type:", self.order_type)

        self.quantity = QSpinBox()
        self.quantity.setRange(1, 10000)
        self.quantity.setValue(1)
        form.addRow("Quantity:", self.quantity)

        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0.01, 999999)
        self.price_input.setDecimals(2)
        self.price_input.setValue(price)
        self.price_input.setPrefix("₹ ")
        form.addRow("Price:", self.price_input)

        self.trigger_price = QDoubleSpinBox()
        self.trigger_price.setRange(0, 999999)
        self.trigger_price.setDecimals(2)
        self.trigger_price.setPrefix("₹ ")
        form.addRow("Trigger Price:", self.trigger_price)

        self.product = QComboBox()
        self.product.addItems(["CNC", "MIS", "NRML"])
        form.addRow("Product:", self.product)

        layout.addLayout(form)

        # SL and Target
        risk_group = QGroupBox("Risk Management")
        risk_layout = QFormLayout(risk_group)

        self.sl_price = QDoubleSpinBox()
        self.sl_price.setRange(0, 999999)
        self.sl_price.setDecimals(2)
        self.sl_price.setPrefix("₹ ")
        self.sl_price.setSpecialValueText("No SL")
        risk_layout.addRow("Stop Loss:", self.sl_price)

        self.target_price = QDoubleSpinBox()
        self.target_price.setRange(0, 999999)
        self.target_price.setDecimals(2)
        self.target_price.setPrefix("₹ ")
        self.target_price.setSpecialValueText("No Target")
        risk_layout.addRow("Target:", self.target_price)

        layout.addWidget(risk_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Update UI based on order type
        self.order_type.currentTextChanged.connect(self._on_order_type_changed)
        self._on_order_type_changed(self.order_type.currentText())

    def _on_order_type_changed(self, order_type: str):
        """Update UI based on order type"""
        if order_type == "MARKET":
            self.price_input.setEnabled(False)
            self.trigger_price.setEnabled(False)
        elif order_type == "LIMIT":
            self.price_input.setEnabled(True)
            self.trigger_price.setEnabled(False)
        else:  # SL, SL-M
            self.price_input.setEnabled(order_type == "SL")
            self.trigger_price.setEnabled(True)

    def get_order_data(self) -> Dict:
        """Get order data from dialog"""
        return {
            'side': self.side_combo.currentText(),
            'order_type': self.order_type.currentText(),
            'quantity': self.quantity.value(),
            'price': self.price_input.value(),
            'trigger_price': self.trigger_price.value(),
            'product': self.product.currentText(),
            'sl_price': self.sl_price.value() if self.sl_price.value() > 0 else None,
            'target_price': self.target_price.value() if self.target_price.value() > 0 else None
        }


class ModifyOrderDialog(QDialog):
    """Dialog for modifying order price after dragging"""

    def __init__(self, order_type: str, old_price: float, new_price: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Modify {order_type}")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        # Info
        info_label = QLabel(f"Drag {order_type} line to new price")
        info_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(info_label)

        # Prices
        form = QFormLayout()

        old_label = QLabel(f"₹{old_price:.2f}")
        old_label.setStyleSheet("color: gray;")
        form.addRow("Old Price:", old_label)

        self.new_price_input = QDoubleSpinBox()
        self.new_price_input.setRange(0.01, 999999)
        self.new_price_input.setDecimals(2)
        self.new_price_input.setValue(new_price)
        self.new_price_input.setPrefix("₹ ")
        self.new_price_input.setStyleSheet("font-weight: bold; font-size: 14px;")
        form.addRow("New Price:", self.new_price_input)

        layout.addLayout(form)

        # Options
        self.auto_modify = QCheckBox("Auto-modify order (no confirmation)")
        layout.addWidget(self.auto_modify)

        # Buttons
        btn_layout = QHBoxLayout()

        self.modify_btn = QPushButton("✓ Modify Order")
        self.modify_btn.setStyleSheet("background-color: #26a69a; color: white; font-weight: bold; padding: 8px;")
        self.modify_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.modify_btn)

        self.cancel_btn = QPushButton("✕ Cancel")
        self.cancel_btn.setStyleSheet("background-color: #ef5350; color: white; padding: 8px;")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def get_new_price(self) -> float:
        return self.new_price_input.value()

    def is_auto_modify(self) -> bool:
        return self.auto_modify.isChecked()


class InteractiveChart(FigureCanvas):
    """Interactive candlestick chart with order placement and draggable lines"""

    order_requested = pyqtSignal(str, float, str)  # symbol, price, side
    order_modified = pyqtSignal(dict)  # Emit when order line is dragged

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(12, 8), facecolor='#1e1e1e')
        super().__init__(self.fig)
        self.setParent(parent)

        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1e1e1e')

        # Style settings
        self.bull_color = '#26a69a'  # Green
        self.bear_color = '#ef5350'  # Red
        self.grid_color = '#333333'
        self.text_color = '#cccccc'

        # Data
        self.ohlc_data = None
        self.symbol = ""
        self.indicators = {}
        self.order_lines = []  # List of dicts: {price, type, color, line_obj, text_obj, draggable}
        self.position_lines = []

        # Drawing mode
        self.drawing_mode = None  # 'trendline', 'horizontal', 'rectangle'
        self.drawing_start = None
        self.temp_line = None
        self.drawings = []

        # Dragging state
        self.dragging_line = None  # Currently dragged order line
        self.drag_start_y = None

        # Auto-modify setting
        self.auto_modify_enabled = False

        # Connect mouse events
        self.mpl_connect('button_press_event', self._on_click)
        self.mpl_connect('motion_notify_event', self._on_motion)
        self.mpl_connect('button_release_event', self._on_release)

        self._setup_style()

    def _setup_style(self):
        """Setup chart style"""
        self.ax.tick_params(colors=self.text_color)
        self.ax.spines['bottom'].set_color(self.grid_color)
        self.ax.spines['top'].set_color(self.grid_color)
        self.ax.spines['left'].set_color(self.grid_color)
        self.ax.spines['right'].set_color(self.grid_color)
        self.ax.grid(True, color=self.grid_color, linestyle='--', alpha=0.3)
        self.fig.tight_layout()

    def plot_candlestick(self, data: List[Dict], symbol: str):
        """Plot candlestick chart from OHLCV data"""
        if not data:
            return

        self.ohlc_data = data
        self.symbol = symbol
        self.ax.clear()
        self._setup_style()

        # Prepare data
        dates = []
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []

        for candle in data:
            dates.append(candle.get('timestamp', candle.get('date', '')))
            opens.append(float(candle.get('open', 0)))
            highs.append(float(candle.get('high', 0)))
            lows.append(float(candle.get('low', 0)))
            closes.append(float(candle.get('close', 0)))
            volumes.append(float(candle.get('volume', 0)))

        # Draw candlesticks
        width = 0.6
        for i in range(len(dates)):
            if closes[i] >= opens[i]:
                color = self.bull_color
                body_bottom = opens[i]
            else:
                color = self.bear_color
                body_bottom = closes[i]

            body_height = abs(closes[i] - opens[i])

            # Body
            rect = Rectangle((i - width/2, body_bottom), width, body_height,
                           facecolor=color, edgecolor=color, linewidth=1)
            self.ax.add_patch(rect)

            # Wicks
            self.ax.plot([i, i], [lows[i], min(opens[i], closes[i])], color=color, linewidth=1)
            self.ax.plot([i, i], [max(opens[i], closes[i]), highs[i]], color=color, linewidth=1)

        # Set axis
        self.ax.set_xlim(-1, len(dates))

        # Calculate y limits with some padding
        min_price = min(lows) * 0.99
        max_price = max(highs) * 1.01
        self.ax.set_ylim(min_price, max_price)

        # X-axis labels (show every nth label)
        step = max(1, len(dates) // 10)
        self.ax.set_xticks(range(0, len(dates), step))
        self.ax.set_xticklabels([str(dates[i])[:10] for i in range(0, len(dates), step)],
                                rotation=45, ha='right', color=self.text_color)

        self.ax.set_ylabel('Price (₹)', color=self.text_color)
        self.ax.set_title(f'{symbol} - Candlestick Chart', color=self.text_color, fontsize=14)

        # Draw indicators
        self._draw_indicators(closes)

        # Draw order/position lines
        self._draw_order_lines()

        self.fig.tight_layout()
        self.draw()

    def _draw_indicators(self, closes: List[float]):
        """Draw technical indicators"""
        x = list(range(len(closes)))

        if 'sma20' in self.indicators and self.indicators['sma20']:
            sma20 = self._calculate_sma(closes, 20)
            self.ax.plot(x, sma20, color='#ffa726', linewidth=1, label='SMA 20', alpha=0.8)

        if 'sma50' in self.indicators and self.indicators['sma50']:
            sma50 = self._calculate_sma(closes, 50)
            self.ax.plot(x, sma50, color='#42a5f5', linewidth=1, label='SMA 50', alpha=0.8)

        if 'ema20' in self.indicators and self.indicators['ema20']:
            ema20 = self._calculate_ema(closes, 20)
            self.ax.plot(x, ema20, color='#ab47bc', linewidth=1, label='EMA 20', alpha=0.8)

        if 'bb' in self.indicators and self.indicators['bb']:
            upper, middle, lower = self._calculate_bollinger(closes, 20)
            self.ax.fill_between(x, lower, upper, color='#607d8b', alpha=0.2)
            self.ax.plot(x, middle, color='#607d8b', linewidth=1, linestyle='--')

        if self.indicators:
            self.ax.legend(loc='upper left', facecolor='#2e2e2e', edgecolor='#444444',
                          labelcolor=self.text_color)

    def _calculate_sma(self, data: List[float], period: int) -> List[float]:
        """Calculate Simple Moving Average"""
        result = [np.nan] * (period - 1)
        for i in range(period - 1, len(data)):
            result.append(np.mean(data[i-period+1:i+1]))
        return result

    def _calculate_ema(self, data: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average"""
        result = [np.nan] * (period - 1)
        multiplier = 2 / (period + 1)
        ema = np.mean(data[:period])
        result.append(ema)

        for i in range(period, len(data)):
            ema = (data[i] - ema) * multiplier + ema
            result.append(ema)
        return result

    def _calculate_bollinger(self, data: List[float], period: int = 20, std_dev: float = 2):
        """Calculate Bollinger Bands"""
        middle = self._calculate_sma(data, period)
        upper = []
        lower = []

        for i in range(len(data)):
            if i < period - 1:
                upper.append(np.nan)
                lower.append(np.nan)
            else:
                std = np.std(data[i-period+1:i+1])
                upper.append(middle[i] + std_dev * std)
                lower.append(middle[i] - std_dev * std)

        return upper, middle, lower

    def add_order_line(self, price: float, order_type: str, color: str = None, draggable: bool = True, order_id: str = None):
        """Add horizontal line for an order - draggable by default"""
        if color is None:
            color = '#26a69a' if 'BUY' in order_type.upper() or 'TARGET' in order_type.upper() else '#ef5350'

        # Create line and text objects
        line_obj = self.ax.axhline(y=price, color=color, linestyle='--', linewidth=2, alpha=0.8, picker=5)
        text_obj = self.ax.text(self.ax.get_xlim()[1] * 0.98, price,
                               f" ⋮ {order_type}: ₹{price:.2f}",
                               color=color, va='center', fontsize=9, fontweight='bold',
                               bbox=dict(boxstyle='round,pad=0.3', facecolor='#2e2e2e', edgecolor=color, alpha=0.9))

        order_data = {
            'price': price,
            'type': order_type,
            'color': color,
            'line_obj': line_obj,
            'text_obj': text_obj,
            'draggable': draggable,
            'order_id': order_id
        }
        self.order_lines.append(order_data)
        self.draw()
        return order_data

    def _draw_order_lines(self):
        """Draw all order and position lines"""
        # Clear existing line objects first
        for order in self.order_lines:
            if 'line_obj' in order and order['line_obj']:
                try:
                    order['line_obj'].remove()
                except:
                    pass
            if 'text_obj' in order and order['text_obj']:
                try:
                    order['text_obj'].remove()
                except:
                    pass

        # Redraw all order lines
        for order in self.order_lines:
            line_obj = self.ax.axhline(y=order['price'], color=order['color'],
                                      linestyle='--', linewidth=2, alpha=0.8, picker=5)
            text_obj = self.ax.text(self.ax.get_xlim()[1] * 0.98, order['price'],
                                   f" ⋮ {order['type']}: ₹{order['price']:.2f}",
                                   color=order['color'], va='center', fontsize=9, fontweight='bold',
                                   bbox=dict(boxstyle='round,pad=0.3', facecolor='#2e2e2e',
                                            edgecolor=order['color'], alpha=0.9))
            order['line_obj'] = line_obj
            order['text_obj'] = text_obj

        # Draw position lines
        for pos in self.position_lines:
            self.ax.axhline(y=pos['price'], color=pos['color'],
                          linestyle='-', linewidth=3, alpha=0.9)
            self.ax.text(self.ax.get_xlim()[1] * 0.98, pos['price'],
                        f" 📍 {pos['type']}: ₹{pos['price']:.2f}",
                        color=pos['color'], va='center', fontsize=10, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='#1e1e1e',
                                 edgecolor=pos['color'], alpha=0.95))

    def update_order_line_price(self, order_data: dict, new_price: float):
        """Update the price of an order line"""
        old_price = order_data['price']
        order_data['price'] = new_price

        # Update line position
        if order_data.get('line_obj'):
            order_data['line_obj'].set_ydata([new_price, new_price])

        # Update text
        if order_data.get('text_obj'):
            order_data['text_obj'].set_position((self.ax.get_xlim()[1] * 0.98, new_price))
            order_data['text_obj'].set_text(f" ⋮ {order_data['type']}: ₹{new_price:.2f}")

        self.draw()
        return old_price

    def clear_order_lines(self):
        """Clear all order lines"""
        for order in self.order_lines:
            if 'line_obj' in order and order['line_obj']:
                try:
                    order['line_obj'].remove()
                except:
                    pass
            if 'text_obj' in order and order['text_obj']:
                try:
                    order['text_obj'].remove()
                except:
                    pass
        self.order_lines = []
        if self.ohlc_data:
            self.plot_candlestick(self.ohlc_data, self.symbol)

    def _find_nearest_order_line(self, y_pos: float, tolerance: float = None) -> Optional[dict]:
        """Find the nearest order line to a y position"""
        if tolerance is None:
            # Calculate tolerance based on y-axis range
            y_range = self.ax.get_ylim()[1] - self.ax.get_ylim()[0]
            tolerance = y_range * 0.02  # 2% of visible range

        nearest = None
        min_dist = tolerance

        for order in self.order_lines:
            if order.get('draggable', True):
                dist = abs(order['price'] - y_pos)
                if dist < min_dist:
                    min_dist = dist
                    nearest = order

        return nearest

    def set_drawing_mode(self, mode: str):
        """Set drawing mode for chart annotations"""
        self.drawing_mode = mode
        self.drawing_start = None

    def _on_click(self, event):
        """Handle mouse click"""
        if event.inaxes != self.ax:
            return

        if event.button == 3:  # Right click - show context menu
            self._show_context_menu(event)
            return

        if event.button == 1:  # Left click
            # Check if clicking near an order line to start dragging
            nearest_line = self._find_nearest_order_line(event.ydata)
            if nearest_line and nearest_line.get('draggable', True):
                self.dragging_line = nearest_line
                self.drag_start_y = event.ydata
                self.setCursor(Qt.CursorShape.SizeVerCursor)
                return

        if self.drawing_mode:
            self.drawing_start = (event.xdata, event.ydata)

    def _on_motion(self, event):
        """Handle mouse motion"""
        if event.inaxes != self.ax:
            return

        # Handle dragging order line
        if self.dragging_line and event.ydata:
            new_price = round(event.ydata, 2)
            self.update_order_line_price(self.dragging_line, new_price)
            return

        # Check if hovering near an order line
        nearest = self._find_nearest_order_line(event.ydata) if event.ydata else None
        if nearest and nearest.get('draggable', True):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        # Preview drawing
        if not self.drawing_start:
            return

        if self.temp_line:
            self.temp_line.remove()
            self.temp_line = None

        if self.drawing_mode == 'horizontal':
            self.temp_line = self.ax.axhline(y=self.drawing_start[1],
                                            color='#ffffff', linestyle=':', alpha=0.5)
        elif self.drawing_mode == 'trendline':
            self.temp_line, = self.ax.plot([self.drawing_start[0], event.xdata],
                                           [self.drawing_start[1], event.ydata],
                                           color='#ffffff', linestyle=':', alpha=0.5)

        self.draw()

    def _on_release(self, event):
        """Handle mouse release"""
        # Handle end of drag
        if self.dragging_line:
            self.setCursor(Qt.CursorShape.ArrowCursor)

            if event.ydata:
                old_price = self.drag_start_y
                new_price = round(event.ydata, 2)

                if abs(new_price - old_price) > 0.01:  # Meaningful drag
                    # Show modification dialog
                    if self.auto_modify_enabled:
                        # Auto-modify without dialog
                        self._emit_order_modification(self.dragging_line, old_price, new_price)
                    else:
                        # Show dialog
                        dialog = ModifyOrderDialog(self.dragging_line['type'], old_price, new_price, self.parent())
                        if dialog.exec() == QDialog.DialogCode.Accepted:
                            final_price = dialog.get_new_price()
                            self.update_order_line_price(self.dragging_line, final_price)
                            self._emit_order_modification(self.dragging_line, old_price, final_price)
                            if dialog.is_auto_modify():
                                self.auto_modify_enabled = True
                        else:
                            # Restore original position
                            self.update_order_line_price(self.dragging_line, old_price)

            self.dragging_line = None
            self.drag_start_y = None
            return

        if event.inaxes != self.ax or not self.drawing_start:
            return

        if self.temp_line:
            self.temp_line.remove()
            self.temp_line = None

        # Add permanent drawing
        if self.drawing_mode == 'horizontal':
            line = self.ax.axhline(y=self.drawing_start[1],
                                  color='#ffeb3b', linestyle='-', linewidth=1)
            self.drawings.append(line)
        elif self.drawing_mode == 'trendline':
            line, = self.ax.plot([self.drawing_start[0], event.xdata],
                                [self.drawing_start[1], event.ydata],
                                color='#ffeb3b', linestyle='-', linewidth=1)
            self.drawings.append(line)

        self.drawing_start = None
        self.draw()

    def _emit_order_modification(self, order_data: dict, old_price: float, new_price: float):
        """Emit signal when order is modified by dragging"""
        modification_data = {
            'order_type': order_data['type'],
            'old_price': old_price,
            'new_price': new_price,
            'order_id': order_data.get('order_id'),
            'symbol': self.symbol
        }
        self.order_modified.emit(modification_data)
        logger.info(f"Order modified: {order_data['type']} from ₹{old_price:.2f} to ₹{new_price:.2f}")

    def _show_context_menu(self, event):
        """Show context menu for order placement"""
        if event.ydata is None:
            return

        price = round(event.ydata, 2)

        menu = QMenu()

        buy_action = menu.addAction(f"BUY @ ₹{price}")
        sell_action = menu.addAction(f"SELL @ ₹{price}")
        menu.addSeparator()
        sl_action = menu.addAction(f"Set SL @ ₹{price}")
        target_action = menu.addAction(f"Set Target @ ₹{price}")
        menu.addSeparator()
        horizontal_action = menu.addAction("Draw Horizontal Line")
        clear_action = menu.addAction("Clear Drawings")

        # Get cursor position in screen coordinates
        cursor_pos = self.mapToGlobal(self.mapFromParent(
            self.parent().mapFromGlobal(self.cursor().pos())
        ))

        action = menu.exec(cursor_pos)

        if action == buy_action:
            self.order_requested.emit(self.symbol, price, "BUY")
        elif action == sell_action:
            self.order_requested.emit(self.symbol, price, "SELL")
        elif action == sl_action:
            self.add_order_line(price, "SL", '#ef5350')
            self.draw()
        elif action == target_action:
            self.add_order_line(price, "Target", '#26a69a')
            self.draw()
        elif action == horizontal_action:
            line = self.ax.axhline(y=price, color='#ffeb3b', linestyle='-', linewidth=1)
            self.drawings.append(line)
            self.draw()
        elif action == clear_action:
            for drawing in self.drawings:
                drawing.remove()
            self.drawings = []
            self.draw()

    def set_indicators(self, indicators: Dict[str, bool]):
        """Set which indicators to show"""
        self.indicators = indicators
        if self.ohlc_data:
            self.plot_candlestick(self.ohlc_data, self.symbol)


class ChartWidget(QWidget):
    """Main chart widget with controls"""

    order_placed = pyqtSignal(dict)  # Emit when order is placed
    order_modified_signal = pyqtSignal(dict)  # Emit when order is modified by dragging

    def __init__(self, parent=None):
        super().__init__(parent)
        self.broker = None
        self.current_symbol = "NIFTY"

        self._init_ui()

    def _init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()

        # Symbol selector
        toolbar.addWidget(QLabel("Symbol:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.setEditable(True)
        self.symbol_combo.setMinimumWidth(150)
        self.symbol_combo.addItems([
            "NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "INFY",
            "HDFCBANK", "ICICIBANK", "SBIN", "TATASTEEL", "ITC"
        ])
        self.symbol_combo.currentTextChanged.connect(self._on_symbol_changed)
        toolbar.addWidget(self.symbol_combo)

        # Interval selector
        toolbar.addWidget(QLabel("Interval:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["1m", "5m", "15m", "30m", "1h", "1d", "1w"])
        self.interval_combo.setCurrentText("1d")
        self.interval_combo.currentTextChanged.connect(self._load_chart_data)
        toolbar.addWidget(self.interval_combo)

        # Days selector
        toolbar.addWidget(QLabel("Days:"))
        self.days_spin = QSpinBox()
        self.days_spin.setRange(10, 365)
        self.days_spin.setValue(90)
        self.days_spin.valueChanged.connect(self._load_chart_data)
        toolbar.addWidget(self.days_spin)

        # Refresh button
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self._load_chart_data)
        toolbar.addWidget(self.refresh_btn)

        toolbar.addStretch()

        # Drawing tools
        toolbar.addWidget(QLabel("Draw:"))

        self.horizontal_btn = QPushButton("━")
        self.horizontal_btn.setToolTip("Horizontal Line")
        self.horizontal_btn.setMaximumWidth(30)
        self.horizontal_btn.clicked.connect(lambda: self._set_drawing_mode('horizontal'))
        toolbar.addWidget(self.horizontal_btn)

        self.trendline_btn = QPushButton("╱")
        self.trendline_btn.setToolTip("Trendline")
        self.trendline_btn.setMaximumWidth(30)
        self.trendline_btn.clicked.connect(lambda: self._set_drawing_mode('trendline'))
        toolbar.addWidget(self.trendline_btn)

        self.clear_btn = QPushButton("✕")
        self.clear_btn.setToolTip("Clear Drawings")
        self.clear_btn.setMaximumWidth(30)
        self.clear_btn.clicked.connect(self._clear_drawings)
        toolbar.addWidget(self.clear_btn)

        layout.addLayout(toolbar)

        # Main content - splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Chart
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)
        chart_layout.setContentsMargins(0, 0, 0, 0)

        self.chart = InteractiveChart(self)
        self.chart.order_requested.connect(self._on_order_requested)
        self.chart.order_modified.connect(self._on_order_modified)

        self.toolbar = NavigationToolbar(self.chart, self)
        chart_layout.addWidget(self.toolbar)
        chart_layout.addWidget(self.chart)

        splitter.addWidget(chart_widget)

        # Right panel - indicators & orders
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Indicators
        indicators_group = QGroupBox("Indicators")
        indicators_layout = QVBoxLayout(indicators_group)

        self.sma20_check = QCheckBox("SMA 20")
        self.sma20_check.stateChanged.connect(self._update_indicators)
        indicators_layout.addWidget(self.sma20_check)

        self.sma50_check = QCheckBox("SMA 50")
        self.sma50_check.stateChanged.connect(self._update_indicators)
        indicators_layout.addWidget(self.sma50_check)

        self.ema20_check = QCheckBox("EMA 20")
        self.ema20_check.stateChanged.connect(self._update_indicators)
        indicators_layout.addWidget(self.ema20_check)

        self.bb_check = QCheckBox("Bollinger Bands")
        self.bb_check.stateChanged.connect(self._update_indicators)
        indicators_layout.addWidget(self.bb_check)

        right_layout.addWidget(indicators_group)

        # Quick order
        order_group = QGroupBox("Quick Order")
        order_layout = QFormLayout(order_group)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 10000)
        self.qty_spin.setValue(1)
        order_layout.addRow("Quantity:", self.qty_spin)

        self.product_combo = QComboBox()
        self.product_combo.addItems(["MIS", "CNC", "NRML"])
        order_layout.addRow("Product:", self.product_combo)

        btn_layout = QHBoxLayout()
        self.buy_btn = QPushButton("BUY")
        self.buy_btn.setStyleSheet("background-color: #26a69a; color: white; font-weight: bold;")
        self.buy_btn.clicked.connect(lambda: self._quick_order("BUY"))
        btn_layout.addWidget(self.buy_btn)

        self.sell_btn = QPushButton("SELL")
        self.sell_btn.setStyleSheet("background-color: #ef5350; color: white; font-weight: bold;")
        self.sell_btn.clicked.connect(lambda: self._quick_order("SELL"))
        btn_layout.addWidget(self.sell_btn)

        order_layout.addRow(btn_layout)

        right_layout.addWidget(order_group)

        # Open orders
        orders_group = QGroupBox("Open Orders")
        orders_layout = QVBoxLayout(orders_group)

        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(4)
        self.orders_table.setHorizontalHeaderLabels(["Type", "Price", "Qty", "Action"])
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.orders_table.setMaximumHeight(150)
        orders_layout.addWidget(self.orders_table)

        right_layout.addWidget(orders_group)
        right_layout.addStretch()

        splitter.addWidget(right_panel)
        splitter.setSizes([800, 200])

        layout.addWidget(splitter)

        # Instructions
        instructions = QLabel("💡 Right-click on chart to place orders | Drag to draw lines")
        instructions.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(instructions)

    def set_broker(self, broker):
        """Set broker for data and order placement"""
        self.broker = broker
        self._load_chart_data()

    def _on_symbol_changed(self, symbol: str):
        """Handle symbol change"""
        self.current_symbol = symbol.strip().upper()
        self._load_chart_data()

    def _load_chart_data(self):
        """Load chart data for current symbol"""
        symbol = self.symbol_combo.currentText().strip().upper()
        interval = self.interval_combo.currentText()
        days = self.days_spin.value()

        if not symbol:
            return

        self.current_symbol = symbol

        # Try to get data from broker or Yahoo Finance
        data = []

        if self.broker and hasattr(self.broker, 'get_historical_data'):
            try:
                data = self.broker.get_historical_data(symbol, "NSE", interval, days=days)
            except Exception as e:
                logger.debug(f"Broker historical data error: {e}")

        if not data:
            # Try Yahoo Finance
            try:
                from algo_trader.data.historical import HistoricalDataFetcher
                fetcher = HistoricalDataFetcher()

                # Map interval
                interval_map = {
                    '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
                    '1h': '1h', '1d': '1d', '1w': '1wk'
                }
                yf_interval = interval_map.get(interval, '1d')

                data = fetcher.fetch_yahoo_data(symbol, days=days, interval=yf_interval)
            except Exception as e:
                logger.error(f"Yahoo Finance error: {e}")

        if not data:
            # Generate sample data
            data = self._generate_sample_data(symbol, days)

        self.chart.plot_candlestick(data, symbol)
        self._update_indicators()

    def _generate_sample_data(self, symbol: str, days: int) -> List[Dict]:
        """Generate sample OHLCV data"""
        data = []
        base_price = 100 if symbol not in ["NIFTY", "BANKNIFTY"] else 20000

        for i in range(days):
            date = datetime.now() - timedelta(days=days-i)
            open_price = base_price + np.random.randn() * (base_price * 0.02)
            high = open_price + abs(np.random.randn() * (base_price * 0.015))
            low = open_price - abs(np.random.randn() * (base_price * 0.015))
            close = low + np.random.random() * (high - low)
            volume = int(np.random.random() * 1000000)

            base_price = close

            data.append({
                'timestamp': date.strftime('%Y-%m-%d'),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': volume
            })

        return data

    def _set_drawing_mode(self, mode: str):
        """Set chart drawing mode"""
        self.chart.set_drawing_mode(mode)

    def _clear_drawings(self):
        """Clear all chart drawings"""
        for drawing in self.chart.drawings:
            drawing.remove()
        self.chart.drawings = []
        self.chart.clear_order_lines()
        self.chart.draw()

    def _update_indicators(self):
        """Update chart indicators"""
        indicators = {
            'sma20': self.sma20_check.isChecked(),
            'sma50': self.sma50_check.isChecked(),
            'ema20': self.ema20_check.isChecked(),
            'bb': self.bb_check.isChecked()
        }
        self.chart.set_indicators(indicators)

    def _on_order_requested(self, symbol: str, price: float, side: str):
        """Handle order request from chart"""
        dialog = OrderDialog(symbol, price, side, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            order_data = dialog.get_order_data()
            order_data['symbol'] = symbol

            # Add order line to chart
            self.chart.add_order_line(order_data['price'],
                                     f"{order_data['side']} {order_data['order_type']}")

            # Add SL/Target lines if set
            if order_data.get('sl_price'):
                self.chart.add_order_line(order_data['sl_price'], "SL", '#ef5350')
            if order_data.get('target_price'):
                self.chart.add_order_line(order_data['target_price'], "Target", '#26a69a')

            self.chart.draw()

            # Emit order signal
            self.order_placed.emit(order_data)

    def _quick_order(self, side: str):
        """Place quick market order"""
        if not self.current_symbol:
            QMessageBox.warning(self, "Error", "Please select a symbol")
            return

        # Get last price from chart data
        price = 0
        if self.chart.ohlc_data:
            price = self.chart.ohlc_data[-1].get('close', 0)

        order_data = {
            'symbol': self.current_symbol,
            'side': side,
            'order_type': 'MARKET',
            'quantity': self.qty_spin.value(),
            'price': price,
            'product': self.product_combo.currentText()
        }

        # Confirm
        reply = QMessageBox.question(
            self, "Confirm Order",
            f"{side} {order_data['quantity']} qty of {self.current_symbol} at MARKET?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.order_placed.emit(order_data)
            QMessageBox.information(self, "Order Placed", f"{side} order submitted!")

    def _on_order_modified(self, modification_data: dict):
        """Handle order modification from chart dragging"""
        logger.info(f"Order modified via drag: {modification_data}")

        # Emit signal for main window to handle
        self.order_modified_signal.emit(modification_data)

        # Show status message
        order_type = modification_data.get('order_type', 'Order')
        old_price = modification_data.get('old_price', 0)
        new_price = modification_data.get('new_price', 0)

        QMessageBox.information(
            self, "Order Modified",
            f"{order_type} modified!\n\n"
            f"Old Price: ₹{old_price:.2f}\n"
            f"New Price: ₹{new_price:.2f}\n\n"
            f"{'✓ Order will be modified on broker' if self.broker else '(Paper Trading Mode)'}"
        )
