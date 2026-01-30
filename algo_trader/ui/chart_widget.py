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
    QLineEdit, QCheckBox, QSizePolicy
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


class CustomIndicatorDialog(QDialog):
    """Dialog for creating custom indicators using simple formulas"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Custom Indicator")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # Name
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., My SMA Cross")
        form.addRow("Indicator Name:", self.name_input)

        # Type
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Moving Average (SMA)",
            "Exponential MA (EMA)",
            "Weighted MA (WMA)",
            "Price Channel",
            "ATR Bands",
            "Custom Formula"
        ])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Indicator Type:", self.type_combo)

        layout.addLayout(form)

        # Parameters section
        self.params_group = QGroupBox("Parameters")
        self.params_layout = QFormLayout(self.params_group)

        # Period (for most indicators)
        self.period_spin = QSpinBox()
        self.period_spin.setRange(1, 500)
        self.period_spin.setValue(20)
        self.params_layout.addRow("Period:", self.period_spin)

        # Source
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Close", "Open", "High", "Low", "HL2 (High+Low)/2", "HLC3", "OHLC4"])
        self.params_layout.addRow("Source:", self.source_combo)

        # Offset
        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(-50, 50)
        self.offset_spin.setValue(0)
        self.params_layout.addRow("Offset:", self.offset_spin)

        # Multiplier (for bands)
        self.multiplier_spin = QDoubleSpinBox()
        self.multiplier_spin.setRange(0.1, 10.0)
        self.multiplier_spin.setValue(2.0)
        self.multiplier_spin.setDecimals(1)
        self.params_layout.addRow("Multiplier:", self.multiplier_spin)

        # Second period (for crosses)
        self.period2_spin = QSpinBox()
        self.period2_spin.setRange(1, 500)
        self.period2_spin.setValue(50)
        self.params_layout.addRow("Period 2 (optional):", self.period2_spin)

        layout.addWidget(self.params_group)

        # Custom formula section
        self.formula_group = QGroupBox("Custom Formula")
        formula_layout = QVBoxLayout(self.formula_group)

        formula_help = QLabel("""
<b>Available Variables:</b>
• close, open, high, low, volume
• sma(close, 20), ema(close, 20)
• rsi(close, 14), atr(high, low, close, 14)
• highest(high, 20), lowest(low, 20)

<b>Example Formulas:</b>
• sma(close, 20) - sma(close, 50)
• (highest(high, 20) + lowest(low, 20)) / 2
• close - sma(close, 20)
""")
        formula_help.setStyleSheet("color: #888; font-size: 11px;")
        formula_help.setTextFormat(Qt.TextFormat.RichText)
        formula_layout.addWidget(formula_help)

        self.formula_input = QLineEdit()
        self.formula_input.setPlaceholderText("e.g., sma(close, 20)")
        self.formula_input.setStyleSheet("font-family: monospace; font-size: 14px; padding: 8px;")
        formula_layout.addWidget(self.formula_input)

        self.formula_group.hide()  # Hidden by default
        layout.addWidget(self.formula_group)

        # Color selection
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Line Color:"))
        self.color_combo = QComboBox()
        self.color_combo.addItems([
            "Yellow", "Cyan", "Magenta", "Lime", "Orange",
            "White", "Red", "Green", "Blue", "Pink"
        ])
        color_layout.addWidget(self.color_combo)

        color_layout.addWidget(QLabel("Style:"))
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Solid", "Dashed", "Dotted"])
        color_layout.addWidget(self.style_combo)

        color_layout.addWidget(QLabel("Width:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 5)
        self.width_spin.setValue(1)
        color_layout.addWidget(self.width_spin)

        color_layout.addStretch()
        layout.addLayout(color_layout)

        # Plot on sub-panel option
        self.subplot_check = QCheckBox("Plot on separate panel (like RSI/MACD)")
        layout.addWidget(self.subplot_check)

        # Buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Indicator")
        self.add_btn.setStyleSheet("background: #4CAF50; color: white; padding: 10px; font-weight: bold;")
        self.add_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.add_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        self._on_type_changed(0)

    def _on_type_changed(self, index):
        """Update UI based on indicator type"""
        # Show/hide formula input
        if index == 5:  # Custom Formula
            self.formula_group.show()
            self.params_group.hide()
        else:
            self.formula_group.hide()
            self.params_group.show()

        # Show/hide multiplier for bands
        show_multiplier = index in [3, 4]  # Price Channel, ATR Bands
        self.multiplier_spin.setVisible(show_multiplier)
        # Find and hide/show the label
        for i in range(self.params_layout.rowCount()):
            item = self.params_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            if item and item.widget() and "Multiplier" in item.widget().text():
                item.widget().setVisible(show_multiplier)

    def get_indicator_config(self) -> Dict:
        """Get the custom indicator configuration"""
        ind_type = self.type_combo.currentText()

        # Map color names to matplotlib colors
        color_map = {
            "Yellow": "yellow", "Cyan": "cyan", "Magenta": "magenta",
            "Lime": "lime", "Orange": "orange", "White": "white",
            "Red": "red", "Green": "green", "Blue": "blue", "Pink": "pink"
        }

        # Map style to matplotlib linestyle
        style_map = {"Solid": "-", "Dashed": "--", "Dotted": ":"}

        # Map source to data column
        source_map = {
            "Close": "close", "Open": "open", "High": "high", "Low": "low",
            "HL2 (High+Low)/2": "hl2", "HLC3": "hlc3", "OHLC4": "ohlc4"
        }

        return {
            'name': self.name_input.text() or f"Custom {ind_type}",
            'type': ind_type,
            'period': self.period_spin.value(),
            'period2': self.period2_spin.value(),
            'source': source_map.get(self.source_combo.currentText(), "close"),
            'offset': self.offset_spin.value(),
            'multiplier': self.multiplier_spin.value(),
            'formula': self.formula_input.text() if ind_type == "Custom Formula" else None,
            'color': color_map.get(self.color_combo.currentText(), "yellow"),
            'linestyle': style_map.get(self.style_combo.currentText(), "-"),
            'linewidth': self.width_spin.value(),
            'subplot': self.subplot_check.isChecked()
        }


class InteractiveChart(FigureCanvas):
    """Interactive candlestick chart with order placement and draggable lines"""

    order_requested = pyqtSignal(str, float, str)  # symbol, price, side
    order_modified = pyqtSignal(dict)  # Emit when order line is dragged

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(12, 8), facecolor='#1e1e1e')
        super().__init__(self.fig)
        self.setParent(parent)

        # Enable auto-resize
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.setMinimumSize(400, 300)

        # Main price axis (will be recreated when indicators are set)
        self.ax = None
        self.ax_rsi = None
        self.ax_macd = None

        # Style settings
        self.bull_color = '#26a69a'  # Green
        self.bear_color = '#ef5350'  # Red
        self.grid_color = '#333333'
        self.text_color = '#cccccc'

        # Data
        self.ohlc_data = None
        self.symbol = ""
        self.indicators = {}  # Initialize BEFORE _setup_axes()

        # Setup axes after indicators is initialized
        self._setup_axes()
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
        self.mpl_connect('scroll_event', self._on_scroll)

        # Panning state
        self.panning = False
        self.pan_start = None

        self._setup_style()

    def _setup_axes(self):
        """Setup chart axes based on indicators"""
        self.fig.clear()

        # Check which sub-indicators are enabled
        show_rsi = self.indicators.get('rsi', False) if self.indicators else False
        show_macd = self.indicators.get('macd', False) if self.indicators else False

        # Calculate grid ratios
        if show_rsi and show_macd:
            # Main chart, RSI, MACD
            gs = self.fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.05)
            self.ax = self.fig.add_subplot(gs[0])
            self.ax_rsi = self.fig.add_subplot(gs[1], sharex=self.ax)
            self.ax_macd = self.fig.add_subplot(gs[2], sharex=self.ax)
        elif show_rsi:
            gs = self.fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05)
            self.ax = self.fig.add_subplot(gs[0])
            self.ax_rsi = self.fig.add_subplot(gs[1], sharex=self.ax)
            self.ax_macd = None
        elif show_macd:
            gs = self.fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05)
            self.ax = self.fig.add_subplot(gs[0])
            self.ax_macd = self.fig.add_subplot(gs[1], sharex=self.ax)
            self.ax_rsi = None
        else:
            self.ax = self.fig.add_subplot(111)
            self.ax_rsi = None
            self.ax_macd = None

        self.ax.set_facecolor('#1e1e1e')
        if self.ax_rsi:
            self.ax_rsi.set_facecolor('#1e1e1e')
        if self.ax_macd:
            self.ax_macd.set_facecolor('#1e1e1e')

    def resizeEvent(self, event):
        """Handle resize event to adjust chart"""
        super().resizeEvent(event)
        self.fig.tight_layout()
        self.draw()

    def _setup_style(self):
        """Setup chart style"""
        if self.ax is None:
            return
        self.ax.tick_params(colors=self.text_color)
        self.ax.spines['bottom'].set_color(self.grid_color)
        self.ax.spines['top'].set_color(self.grid_color)
        self.ax.spines['left'].set_color(self.grid_color)
        self.ax.spines['right'].set_color(self.grid_color)
        self.ax.grid(True, color=self.grid_color, linestyle='--', alpha=0.3)

        # Style sub-axes
        for sub_ax in [self.ax_rsi, self.ax_macd]:
            if sub_ax:
                sub_ax.tick_params(colors=self.text_color)
                sub_ax.spines['bottom'].set_color(self.grid_color)
                sub_ax.spines['top'].set_color(self.grid_color)
                sub_ax.spines['left'].set_color(self.grid_color)
                sub_ax.spines['right'].set_color(self.grid_color)
                sub_ax.grid(True, color=self.grid_color, linestyle='--', alpha=0.3)

        self.fig.tight_layout()

    def plot_candlestick(self, data: List[Dict], symbol: str):
        """Plot candlestick chart from OHLCV data"""
        if not data:
            return

        self.ohlc_data = data
        self.symbol = symbol

        # Recreate axes based on current indicators
        self._setup_axes()
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

        # Draw indicators (pass all OHLCV data for advanced indicators)
        self._draw_indicators(closes, highs, lows, volumes)

        # Draw order/position lines
        self._draw_order_lines()

        self.fig.tight_layout()
        self.draw()

    def _draw_indicators(self, closes: List[float], highs: List[float] = None,
                         lows: List[float] = None, volumes: List[float] = None):
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

        # Anchored VWAP indicator
        if 'anchored_vwap' in self.indicators and self.indicators['anchored_vwap']:
            if highs and lows and volumes:
                self._draw_anchored_vwap(highs, lows, closes, volumes,
                                         swing_period=self.indicators.get('vwap_swing_period', 50),
                                         adaptive_period=self.indicators.get('vwap_adaptive_period', 20),
                                         volatility_bias=self.indicators.get('vwap_volatility_bias', 10.0))

        # Supertrend indicator
        if 'supertrend' in self.indicators and self.indicators['supertrend']:
            if highs and lows:
                supertrend, direction = self._calculate_supertrend(highs, lows, closes, 10, 3.0)
                # Draw supertrend with color based on direction
                for i in range(1, len(x)):
                    if not np.isnan(supertrend[i]) and not np.isnan(supertrend[i-1]):
                        color = '#26a69a' if direction[i] == 1 else '#ef5350'
                        self.ax.plot([x[i-1], x[i]], [supertrend[i-1], supertrend[i]],
                                    color=color, linewidth=2, alpha=0.9)

        # RSI indicator (in sub-panel)
        if 'rsi' in self.indicators and self.indicators['rsi'] and self.ax_rsi:
            rsi = self._calculate_rsi(closes, 14)
            self.ax_rsi.clear()
            self.ax_rsi.set_facecolor('#1e1e1e')
            self.ax_rsi.plot(x, rsi, color='#ab47bc', linewidth=1.5, label='RSI 14')

            # Overbought/Oversold levels
            self.ax_rsi.axhline(y=70, color='#ef5350', linestyle='--', linewidth=0.8, alpha=0.7)
            self.ax_rsi.axhline(y=30, color='#26a69a', linestyle='--', linewidth=0.8, alpha=0.7)
            self.ax_rsi.axhline(y=50, color=self.grid_color, linestyle='-', linewidth=0.5, alpha=0.5)

            self.ax_rsi.set_ylim(0, 100)
            self.ax_rsi.set_ylabel('RSI', color=self.text_color, fontsize=9)
            self.ax_rsi.tick_params(colors=self.text_color)
            self.ax_rsi.grid(True, color=self.grid_color, linestyle='--', alpha=0.3)

            # Fill overbought/oversold zones
            self.ax_rsi.fill_between(x, 70, 100, alpha=0.1, color='#ef5350')
            self.ax_rsi.fill_between(x, 0, 30, alpha=0.1, color='#26a69a')

        # MACD indicator (in sub-panel)
        if 'macd' in self.indicators and self.indicators['macd'] and self.ax_macd:
            macd_line, signal_line, histogram = self._calculate_macd(closes, 12, 26, 9)
            self.ax_macd.clear()
            self.ax_macd.set_facecolor('#1e1e1e')

            # Draw histogram as bar chart
            hist_colors = ['#26a69a' if h >= 0 else '#ef5350' for h in histogram]
            self.ax_macd.bar(x, histogram, color=hist_colors, alpha=0.6, width=0.8)

            # Draw MACD and Signal lines
            self.ax_macd.plot(x, macd_line, color='#42a5f5', linewidth=1.5, label='MACD')
            self.ax_macd.plot(x, signal_line, color='#ffa726', linewidth=1.5, label='Signal')
            self.ax_macd.axhline(y=0, color=self.grid_color, linestyle='-', linewidth=0.5)

            self.ax_macd.set_ylabel('MACD', color=self.text_color, fontsize=9)
            self.ax_macd.tick_params(colors=self.text_color)
            self.ax_macd.grid(True, color=self.grid_color, linestyle='--', alpha=0.3)
            self.ax_macd.legend(loc='upper left', facecolor='#2e2e2e', edgecolor='#444444',
                               labelcolor=self.text_color, fontsize=8)

        # Draw custom indicators
        if 'custom' in self.indicators and self.indicators['custom']:
            for custom_ind in self.indicators['custom']:
                try:
                    self._draw_custom_indicator(custom_ind, closes, highs, lows, volumes, x)
                except Exception as e:
                    logger.error(f"Error drawing custom indicator {custom_ind.get('name')}: {e}")

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

    def _draw_custom_indicator(self, config: Dict, closes: List[float],
                                highs: List[float], lows: List[float],
                                volumes: List[float], x: List[int]):
        """Draw a custom indicator based on config"""
        ind_type = config.get('type', '')
        period = config.get('period', 20)
        source = config.get('source', 'close')
        color = config.get('color', 'yellow')
        linestyle = config.get('linestyle', '-')
        linewidth = config.get('linewidth', 1)
        name = config.get('name', 'Custom')
        multiplier = config.get('multiplier', 2.0)
        period2 = config.get('period2', 50)

        # Get source data
        if source == 'close':
            data = closes
        elif source == 'high':
            data = highs or closes
        elif source == 'low':
            data = lows or closes
        elif source == 'open':
            data = closes  # Would need opens passed
        elif source == 'hl2':
            data = [(h + l) / 2 for h, l in zip(highs or closes, lows or closes)]
        elif source == 'hlc3':
            data = [(h + l + c) / 3 for h, l, c in zip(highs or closes, lows or closes, closes)]
        elif source == 'ohlc4':
            data = [(h + l + c + c) / 4 for h, l, c in zip(highs or closes, lows or closes, closes)]  # Simplified
        else:
            data = closes

        # Calculate indicator based on type
        if ind_type == "Moving Average (SMA)":
            values = self._calculate_sma(data, period)
            self.ax.plot(x, values, color=color, linestyle=linestyle,
                        linewidth=linewidth, label=name, alpha=0.9)

            # If period2 is different, also plot second SMA (for cross detection)
            if period2 != period:
                values2 = self._calculate_sma(data, period2)
                self.ax.plot(x, values2, color=color, linestyle='--',
                            linewidth=linewidth, label=f"{name} ({period2})", alpha=0.7)

        elif ind_type == "Exponential MA (EMA)":
            values = self._calculate_ema(data, period)
            self.ax.plot(x, values, color=color, linestyle=linestyle,
                        linewidth=linewidth, label=name, alpha=0.9)

        elif ind_type == "Weighted MA (WMA)":
            values = self._calculate_wma(data, period)
            self.ax.plot(x, values, color=color, linestyle=linestyle,
                        linewidth=linewidth, label=name, alpha=0.9)

        elif ind_type == "Price Channel":
            # Donchian Channel style
            upper = []
            lower = []
            for i in range(len(data)):
                if i < period - 1:
                    upper.append(np.nan)
                    lower.append(np.nan)
                else:
                    if highs:
                        upper.append(max(highs[i-period+1:i+1]))
                    else:
                        upper.append(max(data[i-period+1:i+1]))
                    if lows:
                        lower.append(min(lows[i-period+1:i+1]))
                    else:
                        lower.append(min(data[i-period+1:i+1]))

            self.ax.plot(x, upper, color=color, linestyle=linestyle,
                        linewidth=linewidth, label=f"{name} Upper", alpha=0.9)
            self.ax.plot(x, lower, color=color, linestyle=linestyle,
                        linewidth=linewidth, label=f"{name} Lower", alpha=0.9)
            self.ax.fill_between(x, lower, upper, color=color, alpha=0.1)

        elif ind_type == "ATR Bands":
            # Calculate ATR and draw bands around price
            atr = self._calculate_atr(highs or closes, lows or closes, closes, period)
            middle = self._calculate_sma(closes, period)

            upper = [m + multiplier * a if not np.isnan(m) and not np.isnan(a) else np.nan
                    for m, a in zip(middle, atr)]
            lower = [m - multiplier * a if not np.isnan(m) and not np.isnan(a) else np.nan
                    for m, a in zip(middle, atr)]

            self.ax.plot(x, upper, color=color, linestyle=linestyle,
                        linewidth=linewidth, label=f"{name} Upper", alpha=0.9)
            self.ax.plot(x, lower, color=color, linestyle=linestyle,
                        linewidth=linewidth, alpha=0.9)
            self.ax.fill_between(x, lower, upper, color=color, alpha=0.1)

        elif ind_type == "Custom Formula":
            formula = config.get('formula', '')
            if formula:
                values = self._evaluate_formula(formula, closes, highs, lows, volumes)
                if values:
                    if config.get('subplot'):
                        # Would need to create separate subplot for this
                        pass
                    else:
                        self.ax.plot(x, values, color=color, linestyle=linestyle,
                                    linewidth=linewidth, label=name, alpha=0.9)

    def _calculate_wma(self, data: List[float], period: int) -> List[float]:
        """Calculate Weighted Moving Average"""
        result = [np.nan] * (period - 1)
        weights = list(range(1, period + 1))
        weight_sum = sum(weights)

        for i in range(period - 1, len(data)):
            wma = sum(w * d for w, d in zip(weights, data[i-period+1:i+1])) / weight_sum
            result.append(wma)
        return result

    def _calculate_atr(self, highs: List[float], lows: List[float],
                       closes: List[float], period: int = 14) -> List[float]:
        """Calculate Average True Range"""
        tr = [np.nan]
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            tr.append(max(high_low, high_close, low_close))

        # Calculate ATR using EMA of TR
        atr = [np.nan] * period
        if len(tr) > period:
            atr_val = np.mean([t for t in tr[1:period+1] if not np.isnan(t)])
            atr.append(atr_val)

            multiplier = 2 / (period + 1)
            for i in range(period + 1, len(tr)):
                if not np.isnan(tr[i]):
                    atr_val = (tr[i] - atr_val) * multiplier + atr_val
                atr.append(atr_val)

        return atr

    def _evaluate_formula(self, formula: str, closes: List[float],
                          highs: List[float], lows: List[float],
                          volumes: List[float]) -> Optional[List[float]]:
        """Evaluate a custom formula safely"""
        try:
            # Create a safe environment for formula evaluation
            import re

            # Replace function calls with actual calculations
            result = formula.lower()

            # Handle sma(source, period)
            sma_pattern = r'sma\((\w+),\s*(\d+)\)'
            for match in re.finditer(sma_pattern, result):
                source, period = match.groups()
                data = closes if source == 'close' else (highs if source == 'high' else lows)
                sma_vals = self._calculate_sma(data, int(period))
                # Store for later
                result = result.replace(match.group(), f'__sma_{source}_{period}__')

            # Handle ema(source, period)
            ema_pattern = r'ema\((\w+),\s*(\d+)\)'
            for match in re.finditer(ema_pattern, result):
                source, period = match.groups()
                data = closes if source == 'close' else (highs if source == 'high' else lows)
                ema_vals = self._calculate_ema(data, int(period))
                result = result.replace(match.group(), f'__ema_{source}_{period}__')

            # Simple evaluation: just calculate based on formula pattern
            # For safety, only allow specific operations
            if 'sma' in formula.lower():
                # Extract sma parameters
                match = re.search(sma_pattern, formula.lower())
                if match:
                    source, period = match.groups()
                    data = closes if source == 'close' else (highs if source == 'high' else lows)
                    return self._calculate_sma(data, int(period))

            if 'ema' in formula.lower():
                match = re.search(ema_pattern, formula.lower())
                if match:
                    source, period = match.groups()
                    data = closes if source == 'close' else (highs if source == 'high' else lows)
                    return self._calculate_ema(data, int(period))

            # Default: return closes
            return closes

        except Exception as e:
            logger.error(f"Formula evaluation error: {e}")
            return None

    def _calculate_rsi(self, closes: List[float], period: int = 14) -> List[float]:
        """Calculate Relative Strength Index"""
        rsi = [np.nan] * period

        # Calculate price changes
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]

        # Separate gains and losses
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        # First average
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        if avg_loss == 0:
            rsi.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))

        # Subsequent values using smoothing
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rsi.append(100)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100 - (100 / (1 + rs)))

        return rsi

    def _calculate_macd(self, closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9):
        """Calculate MACD (Moving Average Convergence Divergence)"""
        ema_fast = self._calculate_ema(closes, fast)
        ema_slow = self._calculate_ema(closes, slow)

        # MACD line
        macd_line = [np.nan] * len(closes)
        for i in range(len(closes)):
            if not np.isnan(ema_fast[i]) and not np.isnan(ema_slow[i]):
                macd_line[i] = ema_fast[i] - ema_slow[i]

        # Signal line (EMA of MACD)
        valid_macd = [m for m in macd_line if not np.isnan(m)]
        if len(valid_macd) < signal:
            signal_line = [np.nan] * len(closes)
        else:
            signal_ema = self._calculate_ema(valid_macd, signal)
            signal_line = [np.nan] * (len(closes) - len(signal_ema)) + signal_ema

        # Histogram
        histogram = [np.nan] * len(closes)
        for i in range(len(closes)):
            if not np.isnan(macd_line[i]) and not np.isnan(signal_line[i]):
                histogram[i] = macd_line[i] - signal_line[i]

        return macd_line, signal_line, histogram

    def _calculate_supertrend(self, highs: List[float], lows: List[float], closes: List[float],
                               period: int = 10, multiplier: float = 3.0):
        """Calculate Supertrend indicator"""
        atr = self._calculate_atr(highs, lows, closes, period)

        supertrend = [np.nan] * len(closes)
        direction = [0] * len(closes)  # 1 = up, -1 = down

        # Calculate basic bands
        upper_band = [np.nan] * len(closes)
        lower_band = [np.nan] * len(closes)

        for i in range(len(closes)):
            if not np.isnan(atr[i]):
                hl2 = (highs[i] + lows[i]) / 2
                upper_band[i] = hl2 + multiplier * atr[i]
                lower_band[i] = hl2 - multiplier * atr[i]

        # Calculate Supertrend
        for i in range(1, len(closes)):
            if np.isnan(upper_band[i]) or np.isnan(lower_band[i]):
                continue

            # Adjust bands based on previous values
            if not np.isnan(lower_band[i-1]):
                if lower_band[i] < lower_band[i-1] and closes[i-1] > lower_band[i-1]:
                    lower_band[i] = lower_band[i-1]

            if not np.isnan(upper_band[i-1]):
                if upper_band[i] > upper_band[i-1] and closes[i-1] < upper_band[i-1]:
                    upper_band[i] = upper_band[i-1]

            # Determine direction
            if i == period:
                direction[i] = 1 if closes[i] > upper_band[i] else -1
            else:
                if direction[i-1] == 1:
                    if closes[i] < lower_band[i]:
                        direction[i] = -1
                    else:
                        direction[i] = 1
                else:
                    if closes[i] > upper_band[i]:
                        direction[i] = 1
                    else:
                        direction[i] = -1

            # Set supertrend value
            if direction[i] == 1:
                supertrend[i] = lower_band[i]
            else:
                supertrend[i] = upper_band[i]

        return supertrend, direction

    def _find_swing_points(self, highs: List[float], lows: List[float], period: int = 50):
        """Find swing high and low pivot points"""
        swing_highs = []  # List of (index, price)
        swing_lows = []   # List of (index, price)

        for i in range(period, len(highs) - period):
            # Check for swing high
            is_swing_high = True
            for j in range(i - period, i + period + 1):
                if j != i and highs[j] >= highs[i]:
                    is_swing_high = False
                    break
            if is_swing_high:
                swing_highs.append((i, highs[i]))

            # Check for swing low
            is_swing_low = True
            for j in range(i - period, i + period + 1):
                if j != i and lows[j] <= lows[i]:
                    is_swing_low = False
                    break
            if is_swing_low:
                swing_lows.append((i, lows[i]))

        return swing_highs, swing_lows

    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14):
        """Calculate Average True Range"""
        atr = [np.nan] * period
        tr_list = []

        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)

        # First ATR is simple average
        if len(tr_list) >= period:
            atr_val = np.mean(tr_list[:period])
            atr.append(atr_val)

            # Subsequent ATR values use smoothing
            for i in range(period, len(tr_list)):
                atr_val = (atr_val * (period - 1) + tr_list[i]) / period
                atr.append(atr_val)

        return atr

    def _calculate_anchored_vwap(self, anchor_idx: int, closes: List[float], volumes: List[float],
                                  highs: List[float], lows: List[float],
                                  adaptive_period: int = 20, volatility_bias: float = 10.0,
                                  use_adapt: bool = False):
        """Calculate Anchored VWAP from a swing point with adaptive tracking"""
        vwap_line = [np.nan] * len(closes)

        if anchor_idx >= len(closes):
            return vwap_line

        # Calculate ATR for adaptation
        atr = self._calculate_atr(highs, lows, closes)
        base_apt = adaptive_period

        cum_pv = 0.0  # Cumulative price * volume
        cum_vol = 0.0  # Cumulative volume

        for i in range(anchor_idx, len(closes)):
            # Typical price
            typical_price = (highs[i] + lows[i] + closes[i]) / 3

            # Adaptive period based on ATR
            if use_adapt and i < len(atr) and not np.isnan(atr[i]) and atr[i] > 0:
                apt_raw = base_apt / (atr[i] / closes[i] * volatility_bias) if closes[i] > 0 else base_apt
                apt_clamped = max(5.0, min(300.0, apt_raw))
                apt_series = round(apt_clamped)
            else:
                apt_series = adaptive_period

            # Calculate alpha for EWMA
            decay = np.exp(-np.log(2.0) / max(1, apt_series))
            alpha = 1.0 - decay

            vol = volumes[i] if volumes[i] > 0 else 1

            # EWMA-style VWAP calculation
            pxv = typical_price * vol
            cum_pv = (1.0 - alpha) * cum_pv + alpha * pxv
            cum_vol = (1.0 - alpha) * cum_vol + alpha * vol

            if cum_vol > 0:
                vwap_line[i] = cum_pv / cum_vol

        return vwap_line

    def _draw_anchored_vwap(self, highs: List[float], lows: List[float], closes: List[float],
                            volumes: List[float], swing_period: int = 50,
                            adaptive_period: int = 20, volatility_bias: float = 10.0):
        """Draw Dynamic Swing Anchored VWAP indicator"""
        x = list(range(len(closes)))

        # Find swing points
        swing_highs, swing_lows = self._find_swing_points(highs, lows, min(swing_period // 2, len(closes) // 4))

        # Draw VWAP lines from recent swing points (limit to last few for clarity)
        max_lines = 4  # Show last 4 swing VWAPs

        # Draw from swing highs (bearish - red)
        for idx, price in swing_highs[-max_lines:]:
            vwap = self._calculate_anchored_vwap(
                idx, closes, volumes, highs, lows,
                adaptive_period, volatility_bias, use_adapt=True
            )
            self.ax.plot(x, vwap, color='#ef5350', linewidth=1.5, alpha=0.8, linestyle='-')
            # Mark swing high point
            self.ax.scatter([idx], [price], color='#ef5350', s=50, marker='v', zorder=5)
            self.ax.annotate(f'SH', (idx, price), textcoords="offset points",
                           xytext=(0, 10), ha='center', fontsize=8, color='#ef5350')

        # Draw from swing lows (bullish - green)
        for idx, price in swing_lows[-max_lines:]:
            vwap = self._calculate_anchored_vwap(
                idx, closes, volumes, highs, lows,
                adaptive_period, volatility_bias, use_adapt=True
            )
            self.ax.plot(x, vwap, color='#26a69a', linewidth=1.5, alpha=0.8, linestyle='-')
            # Mark swing low point
            self.ax.scatter([idx], [price], color='#26a69a', s=50, marker='^', zorder=5)
            self.ax.annotate(f'SL', (idx, price), textcoords="offset points",
                           xytext=(0, -15), ha='center', fontsize=8, color='#26a69a')

    def add_order_line(self, price: float, order_type: str, color: str = None, draggable: bool = True,
                       order_id: str = None, entry_price: float = None, quantity: int = 1):
        """Add horizontal line for an order - draggable by default, shows P&L if entry_price provided"""
        if color is None:
            color = '#26a69a' if 'BUY' in order_type.upper() or 'TARGET' in order_type.upper() else '#ef5350'

        # Calculate P&L if entry price is provided
        pnl_text = ""
        if entry_price and entry_price > 0:
            pnl = (price - entry_price) * quantity
            pnl_pct = ((price - entry_price) / entry_price) * 100
            pnl_color = '#26a69a' if pnl >= 0 else '#ef5350'
            pnl_sign = '+' if pnl >= 0 else ''
            pnl_text = f" | P&L: {pnl_sign}₹{pnl:.2f} ({pnl_sign}{pnl_pct:.1f}%)"

        # Create line and text objects
        line_obj = self.ax.axhline(y=price, color=color, linestyle='--', linewidth=2, alpha=0.8, picker=5)

        label_text = f" ⋮ {order_type}: ₹{price:.2f}{pnl_text}"
        text_obj = self.ax.text(self.ax.get_xlim()[1] * 0.98, price,
                               label_text,
                               color=color, va='center', fontsize=9, fontweight='bold',
                               bbox=dict(boxstyle='round,pad=0.3', facecolor='#2e2e2e', edgecolor=color, alpha=0.9))

        order_data = {
            'price': price,
            'type': order_type,
            'color': color,
            'line_obj': line_obj,
            'text_obj': text_obj,
            'draggable': draggable,
            'order_id': order_id,
            'entry_price': entry_price,
            'quantity': quantity
        }
        self.order_lines.append(order_data)
        self.draw()
        return order_data

    def _draw_order_lines(self):
        """Draw all order and position lines with P&L display"""
        # Get current LTP from chart data
        current_ltp = 0
        if self.ohlc_data:
            current_ltp = float(self.ohlc_data[-1].get('close', 0))

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
            price = order['price']
            entry_price = order.get('entry_price')
            quantity = order.get('quantity', 1)

            # Calculate P&L text
            pnl_text = ""
            if entry_price and entry_price > 0:
                pnl = (price - entry_price) * quantity
                pnl_pct = ((price - entry_price) / entry_price) * 100
                pnl_sign = '+' if pnl >= 0 else ''
                pnl_text = f" | {pnl_sign}₹{pnl:.0f} ({pnl_sign}{pnl_pct:.1f}%)"
            elif current_ltp > 0 and order['type'] in ['SL', 'Target', 'Entry']:
                # Show distance from current price
                diff = price - current_ltp
                diff_pct = (diff / current_ltp) * 100
                diff_sign = '+' if diff >= 0 else ''
                pnl_text = f" | {diff_sign}{diff_pct:.1f}% from LTP"

            line_obj = self.ax.axhline(y=price, color=order['color'],
                                      linestyle='--', linewidth=2, alpha=0.8, picker=5)

            label_text = f" ⋮ {order['type']}: ₹{price:.2f}{pnl_text}"
            text_obj = self.ax.text(self.ax.get_xlim()[1] * 0.98, price,
                                   label_text,
                                   color=order['color'], va='center', fontsize=9, fontweight='bold',
                                   bbox=dict(boxstyle='round,pad=0.3', facecolor='#2e2e2e',
                                            edgecolor=order['color'], alpha=0.9))
            order['line_obj'] = line_obj
            order['text_obj'] = text_obj

        # Draw position lines with P&L
        for pos in self.position_lines:
            price = pos['price']
            pnl_text = ""

            if current_ltp > 0:
                pnl = (current_ltp - price) * pos.get('quantity', 1)
                pnl_pct = ((current_ltp - price) / price) * 100
                pnl_sign = '+' if pnl >= 0 else ''
                pnl_color = '#26a69a' if pnl >= 0 else '#ef5350'
                pnl_text = f" | P&L: {pnl_sign}₹{pnl:.0f} ({pnl_sign}{pnl_pct:.1f}%)"

            self.ax.axhline(y=price, color=pos['color'],
                          linestyle='-', linewidth=3, alpha=0.9)
            self.ax.text(self.ax.get_xlim()[1] * 0.98, price,
                        f" 📍 {pos['type']}: ₹{price:.2f}{pnl_text}",
                        color=pos['color'], va='center', fontsize=10, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='#1e1e1e',
                                 edgecolor=pos['color'], alpha=0.95))

    def update_order_line_price(self, order_data: dict, new_price: float):
        """Update the price of an order line with P&L display"""
        old_price = order_data['price']
        order_data['price'] = new_price

        # Get current LTP
        current_ltp = 0
        if self.ohlc_data:
            current_ltp = float(self.ohlc_data[-1].get('close', 0))

        # Calculate P&L text
        entry_price = order_data.get('entry_price')
        quantity = order_data.get('quantity', 1)
        pnl_text = ""

        if entry_price and entry_price > 0:
            pnl = (new_price - entry_price) * quantity
            pnl_pct = ((new_price - entry_price) / entry_price) * 100
            pnl_sign = '+' if pnl >= 0 else ''
            pnl_text = f" | {pnl_sign}₹{pnl:.0f} ({pnl_sign}{pnl_pct:.1f}%)"
        elif current_ltp > 0:
            diff = new_price - current_ltp
            diff_pct = (diff / current_ltp) * 100
            diff_sign = '+' if diff >= 0 else ''
            pnl_text = f" | {diff_sign}{diff_pct:.1f}% from LTP"

        # Update line position
        if order_data.get('line_obj'):
            order_data['line_obj'].set_ydata([new_price, new_price])

        # Update text with P&L
        if order_data.get('text_obj'):
            order_data['text_obj'].set_position((self.ax.get_xlim()[1] * 0.98, new_price))
            order_data['text_obj'].set_text(f" ⋮ {order_data['type']}: ₹{new_price:.2f}{pnl_text}")

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

        # Middle click or Ctrl+Left click for panning
        if event.button == 2 or (event.button == 1 and event.key == 'control'):
            self.panning = True
            self.pan_start = (event.xdata, event.ydata)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
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

        # Handle panning
        if self.panning and self.pan_start and event.xdata and event.ydata:
            dx = self.pan_start[0] - event.xdata
            dy = self.pan_start[1] - event.ydata

            x_min, x_max = self.ax.get_xlim()
            y_min, y_max = self.ax.get_ylim()

            # Apply pan
            self.ax.set_xlim(x_min + dx, x_max + dx)
            self.ax.set_ylim(y_min + dy, y_max + dy)

            # Update order line text positions
            for order in self.order_lines:
                if order.get('text_obj'):
                    order['text_obj'].set_position(((x_max + dx) * 0.98, order['price']))

            self.draw()
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
        # Handle end of pan
        if self.panning:
            self.panning = False
            self.pan_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

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

    def _on_scroll(self, event):
        """Handle mouse scroll for zoom in/out"""
        if event.inaxes != self.ax:
            return

        # Get current axis limits
        x_min, x_max = self.ax.get_xlim()
        y_min, y_max = self.ax.get_ylim()

        # Get cursor position as center point for zoom
        x_center = event.xdata
        y_center = event.ydata

        if x_center is None or y_center is None:
            return

        # Zoom factor
        zoom_factor = 0.9 if event.button == 'up' else 1.1  # scroll up = zoom in, scroll down = zoom out

        # Calculate new limits centered on cursor position
        x_range = x_max - x_min
        y_range = y_max - y_min

        new_x_range = x_range * zoom_factor
        new_y_range = y_range * zoom_factor

        # Calculate how far cursor is from min (as fraction)
        x_frac = (x_center - x_min) / x_range if x_range > 0 else 0.5
        y_frac = (y_center - y_min) / y_range if y_range > 0 else 0.5

        # Apply zoom centered on cursor
        new_x_min = x_center - x_frac * new_x_range
        new_x_max = x_center + (1 - x_frac) * new_x_range
        new_y_min = y_center - y_frac * new_y_range
        new_y_max = y_center + (1 - y_frac) * new_y_range

        # Apply limits with bounds checking
        if self.ohlc_data:
            # Don't zoom out too far on x-axis
            data_len = len(self.ohlc_data)
            new_x_min = max(-5, new_x_min)
            new_x_max = min(data_len + 5, new_x_max)

            # Ensure minimum visible range (at least 10 candles)
            if new_x_max - new_x_min < 10:
                return

            # Don't zoom out too far on y-axis
            all_lows = [float(d.get('low', 0)) for d in self.ohlc_data]
            all_highs = [float(d.get('high', 0)) for d in self.ohlc_data]
            data_y_min = min(all_lows) * 0.95
            data_y_max = max(all_highs) * 1.05

            new_y_min = max(data_y_min, new_y_min)
            new_y_max = min(data_y_max, new_y_max)

        self.ax.set_xlim(new_x_min, new_x_max)
        self.ax.set_ylim(new_y_min, new_y_max)

        # Update order line text positions
        for order in self.order_lines:
            if order.get('text_obj'):
                order['text_obj'].set_position((new_x_max * 0.98, order['price']))

        self.draw()

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

        # Auto-load chart data on startup (works without broker using Yahoo Finance or sample data)
        QTimer.singleShot(500, self._load_chart_data)

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

        # Reset view button
        self.reset_btn = QPushButton("⌂")
        self.reset_btn.setToolTip("Reset View (Home)")
        self.reset_btn.setMaximumWidth(30)
        self.reset_btn.clicked.connect(self._reset_view)
        toolbar.addWidget(self.reset_btn)

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

        self.anchored_vwap_check = QCheckBox("Anchored VWAP")
        self.anchored_vwap_check.setToolTip("Dynamic Swing Anchored VWAP (Zeiierman)\nShows VWAP from swing highs/lows")
        self.anchored_vwap_check.stateChanged.connect(self._update_indicators)
        indicators_layout.addWidget(self.anchored_vwap_check)

        self.supertrend_check = QCheckBox("Supertrend")
        self.supertrend_check.setToolTip("Supertrend indicator (Period: 10, Multiplier: 3)")
        self.supertrend_check.stateChanged.connect(self._update_indicators)
        indicators_layout.addWidget(self.supertrend_check)

        self.rsi_check = QCheckBox("RSI (14)")
        self.rsi_check.setToolTip("Relative Strength Index\n70 = Overbought, 30 = Oversold")
        self.rsi_check.stateChanged.connect(self._update_indicators)
        indicators_layout.addWidget(self.rsi_check)

        self.macd_check = QCheckBox("MACD")
        self.macd_check.setToolTip("MACD (12, 26, 9)\nMoving Average Convergence Divergence")
        self.macd_check.stateChanged.connect(self._update_indicators)
        indicators_layout.addWidget(self.macd_check)

        # Custom Indicator Button
        indicators_layout.addWidget(QLabel(""))  # Spacer
        self.custom_indicator_btn = QPushButton("➕ Add Custom Indicator")
        self.custom_indicator_btn.setStyleSheet("""
            QPushButton {
                background: #2196F3;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1976D2;
            }
        """)
        self.custom_indicator_btn.clicked.connect(self._show_custom_indicator_dialog)
        indicators_layout.addWidget(self.custom_indicator_btn)

        # Custom indicators list
        self.custom_indicators_list = []

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
        instructions = QLabel("💡 Right-click: Place orders | Scroll: Zoom in/out | Ctrl+Drag or Middle-click: Pan | Drag order lines to modify")
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

    def _reset_view(self):
        """Reset chart to original view (fit all data)"""
        if self.chart.ohlc_data:
            data = self.chart.ohlc_data
            self.chart.ax.set_xlim(-1, len(data))

            lows = [float(d.get('low', 0)) for d in data]
            highs = [float(d.get('high', 0)) for d in data]
            y_min = min(lows) * 0.99
            y_max = max(highs) * 1.01
            self.chart.ax.set_ylim(y_min, y_max)

            # Update order line text positions
            for order in self.chart.order_lines:
                if order.get('text_obj'):
                    order['text_obj'].set_position((len(data) * 0.98, order['price']))

            self.chart.draw()

    def _update_indicators(self):
        """Update chart indicators"""
        indicators = {
            'sma20': self.sma20_check.isChecked(),
            'sma50': self.sma50_check.isChecked(),
            'ema20': self.ema20_check.isChecked(),
            'bb': self.bb_check.isChecked(),
            'anchored_vwap': self.anchored_vwap_check.isChecked(),
            'supertrend': self.supertrend_check.isChecked(),
            'rsi': self.rsi_check.isChecked(),
            'macd': self.macd_check.isChecked(),
            # Anchored VWAP settings (default values from Pine Script)
            'vwap_swing_period': 50,
            'vwap_adaptive_period': 20,
            'vwap_volatility_bias': 10.0,
            # Custom indicators
            'custom': self.custom_indicators_list
        }
        self.chart.set_indicators(indicators)

    def _show_custom_indicator_dialog(self):
        """Show dialog to add custom indicator"""
        dialog = CustomIndicatorDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_indicator_config()
            self.custom_indicators_list.append(config)
            self._update_indicators()
            QMessageBox.information(self, "Added",
                                   f"Custom indicator '{config['name']}' added!")

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
