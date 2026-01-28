"""
Main Application Window
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton,
    QLabel, QComboBox, QLineEdit, QTextEdit, QSplitter,
    QMessageBox, QStatusBar, QToolBar, QGroupBox, QFormLayout,
    QHeaderView, QDialog, QSpinBox, QDoubleSpinBox, QCheckBox,
    QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QTime, pyqtSignal
from PyQt6.QtGui import QAction, QFont

from algo_trader.core.config import Config
from algo_trader.core.database import Database
from algo_trader.core.order_manager import OrderManager
from algo_trader.core.strategy_engine import StrategyEngine
from algo_trader.core.risk_manager import RiskManager
from algo_trader.core.options_manager import (
    OptionsManager, OptionType, HedgeStrategy, ExitType
)
from algo_trader.core.auto_options import (
    AutoOptionsExecutor, StrikeSelection, SignalAction, ExpirySelection
)
from algo_trader.brokers import UpstoxBroker, AliceBlueBroker

from loguru import logger


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Initialize components
        self.config = Config()
        self.db = Database()
        self.order_manager = OrderManager(self.db)
        self.strategy_engine = StrategyEngine(self.order_manager, self.db)

        # Active broker connections
        self.brokers = {}

        self._init_ui()
        self._load_configured_brokers()
        self._setup_timers()

    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Algo Trader - Pine Script & Chartink Trading")

        # Window size settings - resizable from small to large
        self.setMinimumSize(600, 400)  # Minimum size for corner mode
        self.resize(1200, 800)  # Default size

        # Load saved window geometry if available
        self._load_window_geometry()

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create toolbar
        self._create_toolbar()

        # Create tab widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Add tabs
        self._create_dashboard_tab()
        self._create_strategies_tab()
        self._create_chartink_tab()
        self._create_orders_tab()
        self._create_positions_tab()
        self._create_risk_tab()
        self._create_options_tab()
        self._create_backtest_tab()
        self._create_settings_tab()

        # Load strategies after all tabs are created
        self._load_strategies()
        self._load_chartink_scans()
        self._init_risk_manager()
        self._init_options_manager()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _create_toolbar(self):
        """Create application toolbar"""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        # Connect broker action
        connect_action = QAction("Connect Broker", self)
        connect_action.triggered.connect(self._show_broker_dialog)
        toolbar.addAction(connect_action)

        toolbar.addSeparator()

        # Refresh action
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self._refresh_data)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        # Broker selector
        toolbar.addWidget(QLabel("Active Broker: "))
        self.broker_combo = QComboBox()
        self.broker_combo.setMinimumWidth(150)
        toolbar.addWidget(self.broker_combo)

    def _create_dashboard_tab(self):
        """Create dashboard tab"""
        dashboard = QWidget()
        layout = QVBoxLayout(dashboard)

        # Top row - Account summary
        summary_group = QGroupBox("Account Summary")
        summary_layout = QHBoxLayout(summary_group)

        self.available_margin_label = QLabel("Available Margin: ₹0")
        self.used_margin_label = QLabel("Used Margin: ₹0")
        self.total_pnl_label = QLabel("Total P&L: ₹0")

        for label in [self.available_margin_label, self.used_margin_label, self.total_pnl_label]:
            label.setFont(QFont("Arial", 12))
            summary_layout.addWidget(label)

        layout.addWidget(summary_group)

        # Active strategies section
        strategies_group = QGroupBox("Active Strategies")
        strategies_layout = QVBoxLayout(strategies_group)

        self.active_strategies_table = QTableWidget()
        self.active_strategies_table.setColumnCount(4)
        self.active_strategies_table.setHorizontalHeaderLabels(["Strategy", "Status", "Signals Today", "P&L"])
        self.active_strategies_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        strategies_layout.addWidget(self.active_strategies_table)

        layout.addWidget(strategies_group)

        # Recent signals section
        signals_group = QGroupBox("Recent Signals")
        signals_layout = QVBoxLayout(signals_group)

        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(5)
        self.signals_table.setHorizontalHeaderLabels(["Time", "Strategy", "Symbol", "Signal", "Price"])
        self.signals_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        signals_layout.addWidget(self.signals_table)

        layout.addWidget(signals_group)

        self.tabs.addTab(dashboard, "Dashboard")

    def _create_strategies_tab(self):
        """Create strategies management tab"""
        strategies = QWidget()
        layout = QHBoxLayout(strategies)

        # Left panel - Strategy list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        left_layout.addWidget(QLabel("Strategies"))

        self.strategy_list = QTableWidget()
        self.strategy_list.setColumnCount(3)
        self.strategy_list.setHorizontalHeaderLabels(["Name", "Type", "Active"])
        self.strategy_list.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.strategy_list.cellClicked.connect(self._on_strategy_selected)
        left_layout.addWidget(self.strategy_list)

        btn_layout = QHBoxLayout()
        self.new_strategy_btn = QPushButton("New Strategy")
        self.new_strategy_btn.clicked.connect(self._new_strategy)
        self.delete_strategy_btn = QPushButton("Delete")
        self.delete_strategy_btn.clicked.connect(self._delete_strategy)
        btn_layout.addWidget(self.new_strategy_btn)
        btn_layout.addWidget(self.delete_strategy_btn)
        left_layout.addLayout(btn_layout)

        # Right panel - Strategy editor
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        right_layout.addWidget(QLabel("Pine Script Editor"))

        self.strategy_name_edit = QLineEdit()
        self.strategy_name_edit.setPlaceholderText("Strategy Name")
        right_layout.addWidget(self.strategy_name_edit)

        self.pine_script_editor = QTextEdit()
        self.pine_script_editor.setPlaceholderText(
            "Paste your Pine Script here...\n\n"
            "Example:\n"
            "//@version=5\n"
            "strategy('My Strategy', overlay=true)\n\n"
            "fast_ma = ta.sma(close, 10)\n"
            "slow_ma = ta.sma(close, 20)\n\n"
            "if ta.crossover(fast_ma, slow_ma)\n"
            "    strategy.entry('Long', strategy.long)\n\n"
            "if ta.crossunder(fast_ma, slow_ma)\n"
            "    strategy.close('Long')"
        )
        self.pine_script_editor.setFont(QFont("Consolas", 10))
        right_layout.addWidget(self.pine_script_editor)

        editor_btn_layout = QHBoxLayout()
        self.save_strategy_btn = QPushButton("Save Strategy")
        self.save_strategy_btn.clicked.connect(self._save_strategy)
        self.validate_btn = QPushButton("Validate")
        self.validate_btn.clicked.connect(self._validate_strategy)
        self.activate_btn = QPushButton("Activate")
        self.activate_btn.clicked.connect(self._activate_strategy)
        editor_btn_layout.addWidget(self.save_strategy_btn)
        editor_btn_layout.addWidget(self.validate_btn)
        editor_btn_layout.addWidget(self.activate_btn)
        right_layout.addLayout(editor_btn_layout)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter)

        self.tabs.addTab(strategies, "Strategies")

    def _create_chartink_tab(self):
        """Create Chartink scanner integration tab with time controls & allocation"""
        chartink_scroll = QScrollArea()
        chartink_scroll.setWidgetResizable(True)
        chartink_inner = QWidget()
        layout = QVBoxLayout(chartink_inner)

        # === Add Scanner Section ===
        add_scan_group = QGroupBox("Add Chartink Scanner")
        add_scan_main = QHBoxLayout(add_scan_group)

        # Left column - Basic info
        left_form = QFormLayout()

        self.chartink_scan_name = QLineEdit()
        self.chartink_scan_name.setPlaceholderText("e.g., My Breakout Scanner")
        left_form.addRow("Scan Name:", self.chartink_scan_name)

        self.chartink_scan_url = QLineEdit()
        self.chartink_scan_url.setPlaceholderText("https://chartink.com/screener/your-scanner-name")
        left_form.addRow("Scanner URL:", self.chartink_scan_url)

        self.chartink_action = QComboBox()
        self.chartink_action.addItems(["BUY", "SELL"])
        left_form.addRow("Action:", self.chartink_action)

        self.chartink_quantity = QSpinBox()
        self.chartink_quantity.setRange(1, 10000)
        self.chartink_quantity.setValue(1)
        left_form.addRow("Default Qty:", self.chartink_quantity)

        self.chartink_interval = QSpinBox()
        self.chartink_interval.setRange(30, 3600)
        self.chartink_interval.setValue(60)
        self.chartink_interval.setSuffix(" seconds")
        left_form.addRow("Scan Interval:", self.chartink_interval)

        add_scan_main.addLayout(left_form)

        # Middle column - Time controls
        mid_form = QFormLayout()

        self.chartink_start_time = QComboBox()
        self.chartink_start_time.setEditable(True)
        for h in range(9, 16):
            for m in (0, 15, 30, 45):
                self.chartink_start_time.addItem(f"{h:02d}:{m:02d}")
        self.chartink_start_time.setCurrentText("09:15")
        mid_form.addRow("Start Time:", self.chartink_start_time)

        self.chartink_exit_time = QComboBox()
        self.chartink_exit_time.setEditable(True)
        for h in range(9, 16):
            for m in (0, 15, 30, 45):
                self.chartink_exit_time.addItem(f"{h:02d}:{m:02d}")
        self.chartink_exit_time.setCurrentText("15:15")
        mid_form.addRow("Exit / Square-off Time:", self.chartink_exit_time)

        self.chartink_no_new_trade_time = QComboBox()
        self.chartink_no_new_trade_time.setEditable(True)
        for h in range(9, 16):
            for m in (0, 15, 30, 45):
                self.chartink_no_new_trade_time.addItem(f"{h:02d}:{m:02d}")
        self.chartink_no_new_trade_time.setCurrentText("14:30")
        mid_form.addRow("No New Trade After:", self.chartink_no_new_trade_time)

        add_scan_main.addLayout(mid_form)

        # Right column - Capital & Limits
        right_form = QFormLayout()

        # Per-Stock Allocation Type
        self.chartink_alloc_type = QComboBox()
        self.chartink_alloc_type.addItems(["Auto (Capital ÷ Stocks)", "Fixed Qty", "Fixed Amount"])
        self.chartink_alloc_type.currentIndexChanged.connect(self._on_chartink_alloc_type_changed)
        right_form.addRow("Per-Stock:", self.chartink_alloc_type)

        # Per-Stock Value (qty or amount based on type)
        alloc_value_layout = QHBoxLayout()
        self.chartink_alloc_value = QDoubleSpinBox()
        self.chartink_alloc_value.setRange(0, 99999999)
        self.chartink_alloc_value.setDecimals(0)
        self.chartink_alloc_value.setValue(0)
        self.chartink_alloc_value.setEnabled(False)  # Disabled for "Auto" mode
        self.chartink_alloc_value_label = QLabel("(Auto)")
        alloc_value_layout.addWidget(self.chartink_alloc_value)
        alloc_value_layout.addWidget(self.chartink_alloc_value_label)
        right_form.addRow("Value:", alloc_value_layout)

        self.chartink_total_capital = QDoubleSpinBox()
        self.chartink_total_capital.setRange(0, 99999999)
        self.chartink_total_capital.setDecimals(0)
        self.chartink_total_capital.setValue(0)
        self.chartink_total_capital.setPrefix("₹ ")
        self.chartink_total_capital.setSpecialValueText("Unlimited")
        right_form.addRow("Total Capital:", self.chartink_total_capital)

        self.chartink_max_trades = QSpinBox()
        self.chartink_max_trades.setRange(0, 1000)
        self.chartink_max_trades.setValue(0)
        self.chartink_max_trades.setSpecialValueText("Unlimited")
        right_form.addRow("Max Trades:", self.chartink_max_trades)

        add_scan_main.addLayout(right_form)

        layout.addWidget(add_scan_group)

        # Buttons row
        btn_layout = QHBoxLayout()
        self.add_chartink_scan_btn = QPushButton("Add Scanner")
        self.add_chartink_scan_btn.clicked.connect(self._add_chartink_scan)
        self.test_chartink_scan_btn = QPushButton("Test Scanner")
        self.test_chartink_scan_btn.clicked.connect(self._test_chartink_scan)
        btn_layout.addWidget(self.add_chartink_scan_btn)
        btn_layout.addWidget(self.test_chartink_scan_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # === Active Scanners Table ===
        scans_group = QGroupBox("Active Scanners")
        scans_layout = QVBoxLayout(scans_group)

        self.chartink_scans_table = QTableWidget()
        self.chartink_scans_table.setColumnCount(10)
        self.chartink_scans_table.setHorizontalHeaderLabels([
            "Name", "Action", "Per-Stock", "Start", "Exit", "No New",
            "Capital", "Max Trades", "Trades Done", "Remove"
        ])
        self.chartink_scans_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        scans_layout.addWidget(self.chartink_scans_table)

        # Start/Stop monitoring buttons
        monitor_btn_layout = QHBoxLayout()
        self.start_chartink_btn = QPushButton("Start Monitoring")
        self.start_chartink_btn.clicked.connect(self._start_chartink_monitoring)
        self.stop_chartink_btn = QPushButton("Stop Monitoring")
        self.stop_chartink_btn.clicked.connect(self._stop_chartink_monitoring)
        self.stop_chartink_btn.setEnabled(False)
        self.reset_chartink_btn = QPushButton("Reset Daily Counters")
        self.reset_chartink_btn.clicked.connect(self._reset_chartink_counters)
        monitor_btn_layout.addWidget(self.start_chartink_btn)
        monitor_btn_layout.addWidget(self.stop_chartink_btn)
        monitor_btn_layout.addWidget(self.reset_chartink_btn)
        scans_layout.addLayout(monitor_btn_layout)

        layout.addWidget(scans_group)

        # === Open Positions Section ===
        positions_group = QGroupBox("Scanner Open Positions (Only Executed Trades)")
        positions_layout = QVBoxLayout(positions_group)

        self.chartink_positions_table = QTableWidget()
        self.chartink_positions_table.setColumnCount(6)
        self.chartink_positions_table.setHorizontalHeaderLabels([
            "Scanner", "Symbol", "Action", "Qty", "Entry Price", "Entry Time"
        ])
        self.chartink_positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        positions_layout.addWidget(self.chartink_positions_table)

        layout.addWidget(positions_group)

        # === Alerts Log ===
        alerts_group = QGroupBox("Recent Alerts")
        alerts_layout = QVBoxLayout(alerts_group)

        self.chartink_alerts_table = QTableWidget()
        self.chartink_alerts_table.setColumnCount(6)
        self.chartink_alerts_table.setHorizontalHeaderLabels([
            "Time", "Scanner", "Symbol", "Price", "Qty", "Action Taken"
        ])
        self.chartink_alerts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        alerts_layout.addWidget(self.chartink_alerts_table)

        layout.addWidget(alerts_group)

        chartink_scroll.setWidget(chartink_inner)
        self.tabs.addTab(chartink_scroll, "Chartink")

    def _create_orders_tab(self):
        """Create orders management tab"""
        orders = QWidget()
        layout = QVBoxLayout(orders)

        # Manual order section
        order_group = QGroupBox("Place Manual Order")
        order_layout = QFormLayout(order_group)

        self.order_symbol = QLineEdit()
        self.order_symbol.setPlaceholderText("e.g., RELIANCE")
        order_layout.addRow("Symbol:", self.order_symbol)

        self.order_exchange = QComboBox()
        self.order_exchange.addItems(["NSE", "BSE", "NFO", "MCX"])
        order_layout.addRow("Exchange:", self.order_exchange)

        self.order_type = QComboBox()
        self.order_type.addItems(["BUY", "SELL"])
        order_layout.addRow("Type:", self.order_type)

        self.order_quantity = QSpinBox()
        self.order_quantity.setRange(1, 10000)
        self.order_quantity.setValue(1)
        order_layout.addRow("Quantity:", self.order_quantity)

        self.order_price_type = QComboBox()
        self.order_price_type.addItems(["MARKET", "LIMIT", "SL", "SL-M"])
        order_layout.addRow("Price Type:", self.order_price_type)

        self.order_price = QDoubleSpinBox()
        self.order_price.setRange(0, 100000)
        self.order_price.setDecimals(2)
        order_layout.addRow("Price:", self.order_price)

        self.place_order_btn = QPushButton("Place Order")
        self.place_order_btn.clicked.connect(self._place_manual_order)
        order_layout.addRow(self.place_order_btn)

        layout.addWidget(order_group)

        # Order book
        layout.addWidget(QLabel("Order Book"))
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(8)
        self.orders_table.setHorizontalHeaderLabels([
            "Time", "Symbol", "Type", "Qty", "Price", "Status", "Broker Order ID", "Actions"
        ])
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.orders_table)

        self.tabs.addTab(orders, "Orders")

    def _create_positions_tab(self):
        """Create positions tab"""
        positions = QWidget()
        layout = QVBoxLayout(positions)

        # Positions table
        layout.addWidget(QLabel("Current Positions"))
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(7)
        self.positions_table.setHorizontalHeaderLabels([
            "Symbol", "Exchange", "Qty", "Avg Price", "LTP", "P&L", "Actions"
        ])
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.positions_table)

        # Holdings table
        layout.addWidget(QLabel("Holdings"))
        self.holdings_table = QTableWidget()
        self.holdings_table.setColumnCount(6)
        self.holdings_table.setHorizontalHeaderLabels([
            "Symbol", "Qty", "Avg Price", "Current Value", "P&L", "P&L %"
        ])
        self.holdings_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.holdings_table)

        self.tabs.addTab(positions, "Positions")

    def _create_risk_tab(self):
        """Create Risk Management tab with TSL and MTM"""
        risk = QWidget()
        layout = QVBoxLayout(risk)

        # MTM Summary Section
        mtm_group = QGroupBox("MTM (Mark-to-Market) Summary")
        mtm_layout = QVBoxLayout(mtm_group)

        mtm_info_layout = QHBoxLayout()
        self.mtm_total_pnl = QLabel("Total P&L: ₹0.00")
        self.mtm_total_pnl.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.mtm_realized = QLabel("Realized: ₹0.00")
        self.mtm_unrealized = QLabel("Unrealized: ₹0.00")
        self.mtm_trades = QLabel("Trades: 0 (W: 0 / L: 0)")

        mtm_info_layout.addWidget(self.mtm_total_pnl)
        mtm_info_layout.addWidget(self.mtm_realized)
        mtm_info_layout.addWidget(self.mtm_unrealized)
        mtm_info_layout.addWidget(self.mtm_trades)
        mtm_layout.addLayout(mtm_info_layout)

        layout.addWidget(mtm_group)

        # Add Position with TSL Section
        add_pos_group = QGroupBox("Add Position with Trailing Stop Loss")
        add_pos_layout = QFormLayout(add_pos_group)

        self.risk_symbol = QLineEdit()
        self.risk_symbol.setPlaceholderText("e.g., RELIANCE")
        add_pos_layout.addRow("Symbol:", self.risk_symbol)

        self.risk_exchange = QComboBox()
        self.risk_exchange.addItems(["NSE", "BSE", "NFO"])
        add_pos_layout.addRow("Exchange:", self.risk_exchange)

        self.risk_quantity = QSpinBox()
        self.risk_quantity.setRange(-10000, 10000)
        self.risk_quantity.setValue(1)
        add_pos_layout.addRow("Quantity (+Long/-Short):", self.risk_quantity)

        self.risk_entry_price = QDoubleSpinBox()
        self.risk_entry_price.setRange(0.01, 100000)
        self.risk_entry_price.setDecimals(2)
        add_pos_layout.addRow("Entry Price:", self.risk_entry_price)

        self.risk_sl_type = QComboBox()
        self.risk_sl_type.addItems(["Fixed Price", "Trailing %", "Trailing Points"])
        self.risk_sl_type.currentTextChanged.connect(self._on_sl_type_changed)
        add_pos_layout.addRow("Stop Loss Type:", self.risk_sl_type)

        self.risk_sl_value = QDoubleSpinBox()
        self.risk_sl_value.setRange(0, 100000)
        self.risk_sl_value.setDecimals(2)
        add_pos_layout.addRow("SL Value:", self.risk_sl_value)

        self.risk_target = QDoubleSpinBox()
        self.risk_target.setRange(0, 100000)
        self.risk_target.setDecimals(2)
        add_pos_layout.addRow("Target Price (optional):", self.risk_target)

        add_pos_btn = QPushButton("Add Position")
        add_pos_btn.clicked.connect(self._add_risk_position)
        add_pos_layout.addRow(add_pos_btn)

        layout.addWidget(add_pos_group)

        # Tracked Positions Section
        tracked_group = QGroupBox("Tracked Positions (with TSL)")
        tracked_layout = QVBoxLayout(tracked_group)

        self.risk_positions_table = QTableWidget()
        self.risk_positions_table.setColumnCount(10)
        self.risk_positions_table.setHorizontalHeaderLabels([
            "Symbol", "Qty", "Entry", "LTP", "SL", "Target", "High/Low", "P&L", "P&L %", "Actions"
        ])
        self.risk_positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tracked_layout.addWidget(self.risk_positions_table)

        # Control buttons
        btn_layout = QHBoxLayout()
        self.start_risk_monitor_btn = QPushButton("Start Monitoring")
        self.start_risk_monitor_btn.clicked.connect(self._start_risk_monitoring)
        self.stop_risk_monitor_btn = QPushButton("Stop Monitoring")
        self.stop_risk_monitor_btn.clicked.connect(self._stop_risk_monitoring)
        self.stop_risk_monitor_btn.setEnabled(False)
        self.refresh_risk_btn = QPushButton("Refresh")
        self.refresh_risk_btn.clicked.connect(self._refresh_risk_positions)

        btn_layout.addWidget(self.start_risk_monitor_btn)
        btn_layout.addWidget(self.stop_risk_monitor_btn)
        btn_layout.addWidget(self.refresh_risk_btn)
        tracked_layout.addLayout(btn_layout)

        layout.addWidget(tracked_group)

        self.tabs.addTab(risk, "Risk/TSL")

    def _create_options_tab(self):
        """Create Options Trading tab with Expiry, Strike, Hedge strategies"""
        # Use scroll area so content is not squeezed
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        options = QWidget()
        layout = QVBoxLayout(options)
        layout.setSpacing(8)

        # --- Options P&L Summary ---
        opt_summary_group = QGroupBox("Options P&L Summary")
        opt_summary_layout = QHBoxLayout(opt_summary_group)
        self.opt_total_pnl = QLabel("Total P&L: ₹0.00")
        self.opt_total_pnl.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self.opt_active_count = QLabel("Active: 0")
        self.opt_closed_count = QLabel("Closed: 0")
        opt_summary_layout.addWidget(self.opt_total_pnl)
        opt_summary_layout.addWidget(self.opt_active_count)
        opt_summary_layout.addWidget(self.opt_closed_count)
        layout.addWidget(opt_summary_group)

        # --- Auto Options (Signal -> Options) ---
        auto_group = QGroupBox("Auto Options (Strategy Signal → Automatic Option Trade)")
        auto_main_layout = QVBoxLayout(auto_group)

        # Row 1: Enable + Symbol + Close opposite + Save
        auto_top = QHBoxLayout()
        self.auto_opt_enabled = QCheckBox("Enable Auto-Options")
        auto_top.addWidget(self.auto_opt_enabled)

        auto_top.addWidget(QLabel("Symbol:"))
        self.auto_opt_symbol = QComboBox()
        self.auto_opt_symbol.addItems(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"])
        self.auto_opt_symbol.setEditable(True)
        auto_top.addWidget(self.auto_opt_symbol)

        self.auto_opt_close_opposite = QCheckBox("Close on Opposite Signal")
        self.auto_opt_close_opposite.setChecked(True)
        auto_top.addWidget(self.auto_opt_close_opposite)

        self.auto_opt_hedge_enabled = QCheckBox("Enable Hedge (Leg 2)")
        auto_top.addWidget(self.auto_opt_hedge_enabled)

        auto_main_layout.addLayout(auto_top)

        # Row 2: Leg 1 and Leg 2 side by side
        legs_row = QHBoxLayout()

        # Leg 1 config
        leg1_group = QGroupBox("Leg 1 (Main Trade)")
        leg1_layout = QFormLayout(leg1_group)
        leg1_layout.setSpacing(3)

        self.auto_leg1_type = QComboBox()
        self.auto_leg1_type.addItems(["CE", "PE"])
        leg1_layout.addRow("Type:", self.auto_leg1_type)

        self.auto_leg1_action = QComboBox()
        self.auto_leg1_action.addItems(["BUY", "SELL"])
        leg1_layout.addRow("Action:", self.auto_leg1_action)

        self.auto_leg1_strike = QComboBox()
        self.auto_leg1_strike.addItems([s.value for s in StrikeSelection])
        leg1_layout.addRow("Strike:", self.auto_leg1_strike)

        self.auto_leg1_expiry = QComboBox()
        self.auto_leg1_expiry.addItems([e.value for e in ExpirySelection])
        leg1_layout.addRow("Expiry:", self.auto_leg1_expiry)

        self.auto_leg1_qty = QSpinBox()
        self.auto_leg1_qty.setRange(1, 500)
        self.auto_leg1_qty.setValue(1)
        self.auto_leg1_qty.setSuffix(" lots")
        leg1_layout.addRow("Qty:", self.auto_leg1_qty)

        legs_row.addWidget(leg1_group)

        # Leg 2 config (Hedge)
        leg2_group = QGroupBox("Leg 2 (Hedge - Separate Strike/Expiry)")
        leg2_layout = QFormLayout(leg2_group)
        leg2_layout.setSpacing(3)

        self.auto_leg2_type = QComboBox()
        self.auto_leg2_type.addItems(["CE", "PE"])
        leg2_layout.addRow("Type:", self.auto_leg2_type)

        self.auto_leg2_action = QComboBox()
        self.auto_leg2_action.addItems(["BUY", "SELL"])
        self.auto_leg2_action.setCurrentText("SELL")
        leg2_layout.addRow("Action:", self.auto_leg2_action)

        self.auto_leg2_strike = QComboBox()
        self.auto_leg2_strike.addItems([s.value for s in StrikeSelection])
        self.auto_leg2_strike.setCurrentText("OTM +3")
        leg2_layout.addRow("Strike:", self.auto_leg2_strike)

        self.auto_leg2_expiry = QComboBox()
        self.auto_leg2_expiry.addItems([e.value for e in ExpirySelection])
        leg2_layout.addRow("Expiry:", self.auto_leg2_expiry)

        self.auto_leg2_qty = QSpinBox()
        self.auto_leg2_qty.setRange(1, 500)
        self.auto_leg2_qty.setValue(1)
        self.auto_leg2_qty.setSuffix(" lots")
        leg2_layout.addRow("Qty:", self.auto_leg2_qty)

        legs_row.addWidget(leg2_group)

        # SL/Target/TSL config
        exit_group_auto = QGroupBox("Exit (Combined P&L)")
        exit_auto_layout = QFormLayout(exit_group_auto)
        exit_auto_layout.setSpacing(3)

        self.auto_opt_exit_type = QComboBox()
        self.auto_opt_exit_type.addItems([e.value for e in ExitType])
        self.auto_opt_exit_type.setCurrentText("P&L Based")
        exit_auto_layout.addRow("Exit:", self.auto_opt_exit_type)

        self.auto_opt_sl = QDoubleSpinBox()
        self.auto_opt_sl.setRange(0, 1000000)
        self.auto_opt_sl.setPrefix("₹")
        exit_auto_layout.addRow("SL:", self.auto_opt_sl)

        self.auto_opt_target = QDoubleSpinBox()
        self.auto_opt_target.setRange(0, 1000000)
        self.auto_opt_target.setPrefix("₹")
        exit_auto_layout.addRow("Target:", self.auto_opt_target)

        self.auto_opt_tsl = QDoubleSpinBox()
        self.auto_opt_tsl.setRange(0, 1000000)
        self.auto_opt_tsl.setPrefix("₹")
        exit_auto_layout.addRow("TSL:", self.auto_opt_tsl)

        save_auto_btn = QPushButton("Save Auto Config")
        save_auto_btn.clicked.connect(self._save_auto_options_config)
        exit_auto_layout.addRow(save_auto_btn)

        legs_row.addWidget(exit_group_auto)

        auto_main_layout.addLayout(legs_row)

        # Legacy hidden combos for backward compat
        self.auto_opt_buy_action = QComboBox()
        self.auto_opt_buy_action.addItems([s.value for s in SignalAction])
        self.auto_opt_buy_action.setVisible(False)
        self.auto_opt_sell_action = QComboBox()
        self.auto_opt_sell_action.addItems([s.value for s in SignalAction])
        self.auto_opt_sell_action.setCurrentText("BUY PE")
        self.auto_opt_sell_action.setVisible(False)

        layout.addWidget(auto_group)

        # --- Auto Trade Log ---
        self.auto_trade_log_table = QTableWidget()
        self.auto_trade_log_table.setColumnCount(6)
        self.auto_trade_log_table.setHorizontalHeaderLabels([
            "Time", "Signal", "Strategy", "Action", "Expiry", "Qty"
        ])
        self.auto_trade_log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.auto_trade_log_table.setMaximumHeight(100)
        layout.addWidget(self.auto_trade_log_table)

        # --- Manual Multi-Leg Builder ---
        build_group = QGroupBox("Manual Option Builder (Multi-Leg - Each Leg Separate Strike & Expiry)")
        build_layout = QVBoxLayout(build_group)

        # Top row: Symbol, Spot, Load buttons
        top_form = QHBoxLayout()

        top_form.addWidget(QLabel("Symbol:"))
        self.opt_symbol = QComboBox()
        self.opt_symbol.addItems(["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"])
        self.opt_symbol.setEditable(True)
        self.opt_symbol.currentTextChanged.connect(self._on_opt_symbol_changed)
        top_form.addWidget(self.opt_symbol)

        top_form.addWidget(QLabel("Spot:"))
        self.opt_spot_price = QDoubleSpinBox()
        self.opt_spot_price.setRange(0, 200000)
        self.opt_spot_price.setDecimals(2)
        self.opt_spot_price.setPrefix("₹")
        top_form.addWidget(self.opt_spot_price)

        fetch_spot_btn = QPushButton("Fetch Spot")
        fetch_spot_btn.clicked.connect(self._fetch_spot_price)
        top_form.addWidget(fetch_spot_btn)

        load_expiry_btn = QPushButton("Load Expiries")
        load_expiry_btn.clicked.connect(self._load_expiry_dates)
        top_form.addWidget(load_expiry_btn)

        load_strikes_btn = QPushButton("Load Strikes")
        load_strikes_btn.clicked.connect(self._load_strike_prices)
        top_form.addWidget(load_strikes_btn)

        self.opt_lot_size = QLabel("Lot: 25")
        top_form.addWidget(self.opt_lot_size)

        build_layout.addLayout(top_form)

        # Hidden combo for expiry/strike data (used by leg rows)
        self.opt_expiry = QComboBox()
        self.opt_expiry.setVisible(False)
        build_layout.addWidget(self.opt_expiry)
        self.opt_strike = QComboBox()
        self.opt_strike.setEditable(True)
        self.opt_strike.setVisible(False)
        build_layout.addWidget(self.opt_strike)

        # Leg builder table
        self.leg_builder_table = QTableWidget()
        self.leg_builder_table.setColumnCount(7)
        self.leg_builder_table.setHorizontalHeaderLabels([
            "Strike", "Expiry", "CE/PE", "BUY/SELL", "Lots", "Premium ₹", "Remove"
        ])
        self.leg_builder_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.leg_builder_table.setMaximumHeight(140)
        build_layout.addWidget(self.leg_builder_table)

        # Add leg button
        leg_btn_row = QHBoxLayout()
        add_leg_btn = QPushButton("+ Add Leg")
        add_leg_btn.clicked.connect(self._add_builder_leg)
        leg_btn_row.addWidget(add_leg_btn)

        # Exit settings inline
        leg_btn_row.addWidget(QLabel("Exit:"))
        self.opt_exit_type = QComboBox()
        self.opt_exit_type.addItems([e.value for e in ExitType])
        self.opt_exit_type.currentTextChanged.connect(self._on_opt_exit_type_changed)
        leg_btn_row.addWidget(self.opt_exit_type)

        leg_btn_row.addWidget(QLabel("SL:"))
        self.opt_sl_value = QDoubleSpinBox()
        self.opt_sl_value.setRange(0, 1000000)
        self.opt_sl_value.setDecimals(2)
        self.opt_sl_value.setPrefix("₹")
        leg_btn_row.addWidget(self.opt_sl_value)

        leg_btn_row.addWidget(QLabel("Target:"))
        self.opt_target_value = QDoubleSpinBox()
        self.opt_target_value.setRange(0, 1000000)
        self.opt_target_value.setDecimals(2)
        self.opt_target_value.setPrefix("₹")
        leg_btn_row.addWidget(self.opt_target_value)

        leg_btn_row.addWidget(QLabel("TSL:"))
        self.opt_tsl_value = QDoubleSpinBox()
        self.opt_tsl_value.setRange(0, 1000000)
        self.opt_tsl_value.setDecimals(2)
        leg_btn_row.addWidget(self.opt_tsl_value)

        build_layout.addLayout(leg_btn_row)

        # Create position button
        create_pos_btn = QPushButton(">>> Create Multi-Leg Position <<<")
        create_pos_btn.setMinimumHeight(35)
        create_pos_btn.clicked.connect(self._add_option_position)
        build_layout.addWidget(create_pos_btn)

        layout.addWidget(build_group)

        # --- Active Option Positions Table ---
        positions_group = QGroupBox("Active Option Positions")
        positions_layout = QVBoxLayout(positions_group)

        self.opt_positions_table = QTableWidget()
        self.opt_positions_table.setColumnCount(10)
        self.opt_positions_table.setHorizontalHeaderLabels([
            "ID", "Symbol", "Strategy", "Legs", "Expiry",
            "Total P&L", "P&L %", "Max P&L", "Exit Type", "Actions"
        ])
        self.opt_positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.opt_positions_table.setMaximumHeight(180)
        positions_layout.addWidget(self.opt_positions_table)

        # Legs detail table
        positions_layout.addWidget(QLabel("Leg Details (select position above):"))
        self.opt_legs_table = QTableWidget()
        self.opt_legs_table.setColumnCount(10)
        self.opt_legs_table.setHorizontalHeaderLabels([
            "Leg", "Strike", "Expiry", "Type", "Action", "Qty", "Entry", "LTP", "P&L", "P&L %"
        ])
        self.opt_legs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.opt_legs_table.setMaximumHeight(150)
        positions_layout.addWidget(self.opt_legs_table)

        self.opt_positions_table.cellClicked.connect(self._on_opt_position_selected)

        opt_refresh_btn = QPushButton("Refresh Positions")
        opt_refresh_btn.clicked.connect(self._refresh_option_positions)
        positions_layout.addWidget(opt_refresh_btn)

        layout.addWidget(positions_group)

        scroll.setWidget(options)
        self.tabs.addTab(scroll, "Options")

    def _create_backtest_tab(self):
        """Create backtesting tab"""
        backtest = QWidget()
        layout = QVBoxLayout(backtest)

        # Backtest config
        config_group = QGroupBox("Backtest Configuration")
        config_layout = QFormLayout(config_group)

        self.bt_strategy_combo = QComboBox()
        config_layout.addRow("Strategy:", self.bt_strategy_combo)

        self.bt_symbol = QLineEdit()
        self.bt_symbol.setPlaceholderText("e.g., NIFTY, RELIANCE")
        config_layout.addRow("Symbol:", self.bt_symbol)

        self.bt_capital = QDoubleSpinBox()
        self.bt_capital.setRange(10000, 10000000)
        self.bt_capital.setValue(100000)
        self.bt_capital.setPrefix("₹")
        config_layout.addRow("Initial Capital:", self.bt_capital)

        self.run_backtest_btn = QPushButton("Run Backtest")
        self.run_backtest_btn.clicked.connect(self._run_backtest)
        config_layout.addRow(self.run_backtest_btn)

        layout.addWidget(config_group)

        # Results
        results_group = QGroupBox("Backtest Results")
        results_layout = QVBoxLayout(results_group)

        self.backtest_results = QTextEdit()
        self.backtest_results.setReadOnly(True)
        results_layout.addWidget(self.backtest_results)

        layout.addWidget(results_group)

        self.tabs.addTab(backtest, "Backtest")

    def _create_settings_tab(self):
        """Create settings tab"""
        settings = QWidget()
        layout = QVBoxLayout(settings)

        # Broker settings
        broker_group = QGroupBox("Broker Connections")
        broker_layout = QVBoxLayout(broker_group)

        self.broker_settings_table = QTableWidget()
        self.broker_settings_table.setColumnCount(4)
        self.broker_settings_table.setHorizontalHeaderLabels([
            "Broker", "Status", "User ID", "Actions"
        ])
        self.broker_settings_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        broker_layout.addWidget(self.broker_settings_table)

        broker_btn_layout = QHBoxLayout()
        add_broker_btn = QPushButton("Add Broker")
        add_broker_btn.clicked.connect(self._show_broker_dialog)
        broker_btn_layout.addWidget(add_broker_btn)
        broker_layout.addLayout(broker_btn_layout)

        layout.addWidget(broker_group)

        # Trading settings
        trading_group = QGroupBox("Trading Settings")
        trading_layout = QFormLayout(trading_group)

        self.default_qty = QSpinBox()
        self.default_qty.setRange(1, 1000)
        self.default_qty.setValue(self.config.get('trading.default_quantity', 1))
        trading_layout.addRow("Default Quantity:", self.default_qty)

        self.max_positions = QSpinBox()
        self.max_positions.setRange(1, 100)
        self.max_positions.setValue(self.config.get('trading.max_positions', 10))
        trading_layout.addRow("Max Positions:", self.max_positions)

        self.risk_percent = QDoubleSpinBox()
        self.risk_percent.setRange(0.1, 10)
        self.risk_percent.setValue(self.config.get('trading.risk_percent', 2.0))
        self.risk_percent.setSuffix("%")
        trading_layout.addRow("Risk per Trade:", self.risk_percent)

        save_settings_btn = QPushButton("Save Settings")
        save_settings_btn.clicked.connect(self._save_settings)
        trading_layout.addRow(save_settings_btn)

        layout.addWidget(trading_group)
        layout.addStretch()

        self.tabs.addTab(settings, "Settings")

    def _load_configured_brokers(self):
        """Load previously configured brokers"""
        brokers = self.config.list_configured_brokers()
        for broker in brokers:
            self.broker_combo.addItem(broker.title())

        self._update_broker_settings_table()

    def _update_broker_settings_table(self):
        """Update broker settings table"""
        brokers = self.config.list_configured_brokers()
        self.broker_settings_table.setRowCount(len(brokers))

        for i, broker in enumerate(brokers):
            self.broker_settings_table.setItem(i, 0, QTableWidgetItem(broker.title()))
            status = "Connected" if broker in self.brokers else "Disconnected"
            self.broker_settings_table.setItem(i, 1, QTableWidgetItem(status))
            creds = self.config.get_broker_credentials(broker)
            self.broker_settings_table.setItem(i, 2, QTableWidgetItem(creds.get('user_id', 'N/A')))

    def _setup_timers(self):
        """Setup refresh timers"""
        # Refresh every 30 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_data)
        self.refresh_timer.start(30000)

    def _refresh_data(self):
        """Refresh all data"""
        self._load_orders()
        self._load_positions()
        self.status_bar.showMessage("Data refreshed", 3000)

    def _load_strategies(self):
        """Load strategies from database"""
        strategies = self.db.get_all_strategies()
        self.strategy_list.setRowCount(len(strategies))
        self.bt_strategy_combo.clear()

        for i, strategy in enumerate(strategies):
            self.strategy_list.setItem(i, 0, QTableWidgetItem(strategy['name']))
            self.strategy_list.setItem(i, 1, QTableWidgetItem(strategy.get('source_type', 'pine')))
            self.strategy_list.setItem(i, 2, QTableWidgetItem("Yes" if strategy['is_active'] else "No"))
            self.bt_strategy_combo.addItem(strategy['name'])

    def _load_orders(self):
        """Load orders from database"""
        orders = self.db.get_orders()
        self.orders_table.setRowCount(len(orders))

        for i, order in enumerate(orders):
            self.orders_table.setItem(i, 0, QTableWidgetItem(str(order.get('created_at', ''))))
            self.orders_table.setItem(i, 1, QTableWidgetItem(order.get('symbol', '')))
            self.orders_table.setItem(i, 2, QTableWidgetItem(order.get('transaction_type', '')))
            self.orders_table.setItem(i, 3, QTableWidgetItem(str(order.get('quantity', ''))))
            self.orders_table.setItem(i, 4, QTableWidgetItem(str(order.get('price', ''))))
            self.orders_table.setItem(i, 5, QTableWidgetItem(order.get('status', '')))
            self.orders_table.setItem(i, 6, QTableWidgetItem(order.get('broker_order_id', '')))

    def _load_positions(self):
        """Load positions from active broker"""
        current_broker = self.broker_combo.currentText().lower()
        if current_broker and current_broker in self.brokers:
            positions = self.brokers[current_broker].get_positions()
            self.positions_table.setRowCount(len(positions))

            for i, pos in enumerate(positions):
                self.positions_table.setItem(i, 0, QTableWidgetItem(pos.get('symbol', '')))
                self.positions_table.setItem(i, 1, QTableWidgetItem(pos.get('exchange', '')))
                self.positions_table.setItem(i, 2, QTableWidgetItem(str(pos.get('quantity', ''))))
                self.positions_table.setItem(i, 3, QTableWidgetItem(str(pos.get('average_price', ''))))
                self.positions_table.setItem(i, 4, QTableWidgetItem(str(pos.get('ltp', ''))))
                self.positions_table.setItem(i, 5, QTableWidgetItem(str(pos.get('pnl', ''))))

    def _show_broker_dialog(self):
        """Show broker configuration dialog"""
        from algo_trader.ui.broker_dialog import BrokerConfigDialog
        dialog = BrokerConfigDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_configured_brokers()
            self._update_broker_settings_table()

    def _on_strategy_selected(self, row, col):
        """Handle strategy selection"""
        name_item = self.strategy_list.item(row, 0)
        if name_item:
            strategy = self.db.get_strategy(name_item.text())
            if strategy:
                self.strategy_name_edit.setText(strategy['name'])
                self.pine_script_editor.setText(strategy['pine_script'])

    def _new_strategy(self):
        """Create new strategy"""
        self.strategy_name_edit.clear()
        self.pine_script_editor.clear()

    def _save_strategy(self):
        """Save current strategy"""
        name = self.strategy_name_edit.text().strip()
        script = self.pine_script_editor.toPlainText().strip()

        if not name:
            QMessageBox.warning(self, "Error", "Please enter a strategy name")
            return

        if not script:
            QMessageBox.warning(self, "Error", "Please enter Pine Script code")
            return

        self.db.save_strategy(name, script)
        self._load_strategies()
        QMessageBox.information(self, "Success", f"Strategy '{name}' saved successfully")

    def _validate_strategy(self):
        """Validate Pine Script"""
        from algo_trader.strategies.pine_parser import PineScriptParser

        script = self.pine_script_editor.toPlainText().strip()
        if not script:
            QMessageBox.warning(self, "Error", "Please enter Pine Script code")
            return

        parser = PineScriptParser()
        result = parser.parse(script)

        if result:
            QMessageBox.information(
                self, "Validation Success",
                f"Strategy parsed successfully!\n\n"
                f"Name: {result.name}\n"
                f"Version: {result.version}\n"
                f"Variables: {len(result.variables)}\n"
                f"Inputs: {len(result.inputs)}\n"
                f"Indicators: {len(result.indicators)}\n"
                f"Entry conditions: {len(result.entry_conditions)}\n"
                f"Exit conditions: {len(result.exit_conditions)}"
            )
        else:
            QMessageBox.warning(self, "Validation Failed", "Failed to parse Pine Script. Check syntax.")

    def _delete_strategy(self):
        """Delete selected strategy"""
        current_row = self.strategy_list.currentRow()
        if current_row < 0:
            return

        name_item = self.strategy_list.item(current_row, 0)
        if name_item:
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Are you sure you want to delete strategy '{name_item.text()}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.db.delete_strategy(name_item.text())
                self._load_strategies()

    def _activate_strategy(self):
        """Activate selected strategy for live trading"""
        name = self.strategy_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Please select a strategy")
            return

        script = self.pine_script_editor.toPlainText().strip()
        if self.strategy_engine.load_strategy(name, script):
            self.strategy_engine.enable_strategy(name)
            QMessageBox.information(self, "Success", f"Strategy '{name}' activated for live trading")
            self._load_strategies()
        else:
            QMessageBox.warning(self, "Error", "Failed to activate strategy")

    def _place_manual_order(self):
        """Place a manual order"""
        from algo_trader.core.order_manager import Order, OrderType, TransactionType, Exchange

        current_broker = self.broker_combo.currentText().lower()
        if not current_broker or current_broker not in self.brokers:
            QMessageBox.warning(self, "Error", "Please connect to a broker first")
            return

        symbol = self.order_symbol.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Error", "Please enter a symbol")
            return

        order = Order(
            symbol=symbol,
            transaction_type=TransactionType.BUY if self.order_type.currentText() == "BUY" else TransactionType.SELL,
            quantity=self.order_quantity.value(),
            order_type=OrderType[self.order_price_type.currentText().replace("-", "_")],
            price=self.order_price.value() if self.order_price.value() > 0 else None,
            exchange=Exchange[self.order_exchange.currentText()]
        )

        result = self.order_manager.place_order(order, current_broker)

        if result.status.value in ('OPEN', 'COMPLETE'):
            QMessageBox.information(self, "Success", f"Order placed: {result.broker_order_id}")
            self._load_orders()
        else:
            QMessageBox.warning(self, "Error", f"Order failed: {result.message}")

    def _run_backtest(self):
        """Run backtest on selected strategy"""
        strategy_name = self.bt_strategy_combo.currentText()
        if not strategy_name:
            QMessageBox.warning(self, "Error", "Please select a strategy")
            return

        symbol = self.bt_symbol.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Error", "Please enter a symbol")
            return

        capital = self.bt_capital.value()

        # Load strategy
        strategy = self.db.get_strategy(strategy_name)
        if not strategy:
            QMessageBox.warning(self, "Error", "Strategy not found")
            return

        from algo_trader.strategies.pine_parser import PineScriptParser
        from algo_trader.strategies.pine_interpreter import PineScriptInterpreter

        parser = PineScriptParser()
        parsed = parser.parse(strategy['pine_script'])

        if not parsed:
            QMessageBox.warning(self, "Error", "Failed to parse strategy")
            return

        interpreter = PineScriptInterpreter(parsed)

        # For demo, create sample data
        # In production, fetch historical data from broker
        import pandas as pd
        import numpy as np

        dates = pd.date_range(end=pd.Timestamp.now(), periods=500, freq='D')
        np.random.seed(42)
        price = 100
        prices = []
        for _ in range(500):
            price = price * (1 + np.random.randn() * 0.02)
            prices.append(price)

        sample_data = pd.DataFrame({
            'open': prices,
            'high': [p * 1.01 for p in prices],
            'low': [p * 0.99 for p in prices],
            'close': [p * (1 + np.random.randn() * 0.005) for p in prices],
            'volume': [np.random.randint(100000, 1000000) for _ in prices]
        }, index=dates)

        interpreter.load_data(sample_data)
        results = interpreter.run_backtest(capital)

        # Display results
        self.backtest_results.setText(
            f"Backtest Results for {strategy_name}\n"
            f"{'=' * 50}\n\n"
            f"Symbol: {symbol}\n"
            f"Initial Capital: ₹{results['initial_capital']:,.2f}\n"
            f"Final Capital: ₹{results['final_capital']:,.2f}\n"
            f"Total Return: {results['total_return']:.2f}%\n\n"
            f"Total Trades: {results['total_trades']}\n"
            f"Winning Trades: {results['winning_trades']}\n"
            f"Losing Trades: {results['losing_trades']}\n"
            f"Win Rate: {results['win_rate']:.2f}%\n\n"
            f"Max Drawdown: {results['max_drawdown']:.2f}%\n"
            f"Sharpe Ratio: {results['sharpe_ratio']:.2f}\n"
            f"Profit Factor: {results['profit_factor']:.2f}"
        )

    def _save_settings(self):
        """Save trading settings"""
        self.config.set('trading.default_quantity', self.default_qty.value())
        self.config.set('trading.max_positions', self.max_positions.value())
        self.config.set('trading.risk_percent', self.risk_percent.value())
        QMessageBox.information(self, "Success", "Settings saved")

    # Chartink methods
    def _init_chartink(self):
        """Initialize Chartink scanner"""
        from algo_trader.integrations.chartink import ChartinkScanner
        self.chartink_scanner = ChartinkScanner()
        self.chartink_scanner.register_alert_callback(self._on_chartink_alert)

    def _load_chartink_scans(self):
        """Load saved Chartink scans from config"""
        try:
            self._init_chartink()
            scans = self.config.get('chartink.scans', [])
            for scan in scans:
                self.chartink_scanner.add_scan(
                    scan_name=scan.get('name'),
                    scan_url=scan.get('url'),
                    interval=scan.get('interval', 60),
                    action=scan.get('action', 'BUY'),
                    quantity=scan.get('quantity', 1),
                    start_time=scan.get('start_time', '09:15'),
                    exit_time=scan.get('exit_time', '15:15'),
                    no_new_trade_time=scan.get('no_new_trade_time', '14:30'),
                    total_capital=scan.get('total_capital', scan.get('total_amount', 0)),
                    alloc_type=scan.get('alloc_type', 'auto'),
                    alloc_value=scan.get('alloc_value', scan.get('stock_quantity', 0)),
                    max_trades=scan.get('max_trades', 0)
                )
            self._refresh_chartink_scans_table()
        except Exception as e:
            logger.error(f"Error loading Chartink scans: {e}")

    def _on_chartink_alloc_type_changed(self, index):
        """Handle allocation type change"""
        if index == 0:  # Auto
            self.chartink_alloc_value.setEnabled(False)
            self.chartink_alloc_value.setValue(0)
            self.chartink_alloc_value_label.setText("(Auto)")
        elif index == 1:  # Fixed Qty
            self.chartink_alloc_value.setEnabled(True)
            self.chartink_alloc_value.setPrefix("")
            self.chartink_alloc_value.setSuffix(" shares")
            self.chartink_alloc_value_label.setText("")
        elif index == 2:  # Fixed Amount
            self.chartink_alloc_value.setEnabled(True)
            self.chartink_alloc_value.setPrefix("₹ ")
            self.chartink_alloc_value.setSuffix("")
            self.chartink_alloc_value_label.setText("per stock")

    def _add_chartink_scan(self):
        """Add a new Chartink scan with time controls and allocation"""
        name = self.chartink_scan_name.text().strip()
        url = self.chartink_scan_url.text().strip()

        if not name:
            QMessageBox.warning(self, "Error", "Please enter a scan name")
            return

        if not url:
            QMessageBox.warning(self, "Error", "Please enter a scanner URL")
            return

        if not url.startswith("https://chartink.com/screener/"):
            QMessageBox.warning(self, "Error", "Invalid Chartink URL. Should start with https://chartink.com/screener/")
            return

        action = self.chartink_action.currentText()
        quantity = self.chartink_quantity.value()
        interval = self.chartink_interval.value()
        start_time = self.chartink_start_time.currentText().strip()
        exit_time = self.chartink_exit_time.currentText().strip()
        no_new_trade_time = self.chartink_no_new_trade_time.currentText().strip()
        total_capital = self.chartink_total_capital.value()
        max_trades = self.chartink_max_trades.value()

        # Get allocation type and value
        alloc_type_index = self.chartink_alloc_type.currentIndex()
        alloc_type = ["auto", "fixed_qty", "fixed_amount"][alloc_type_index]
        alloc_value = self.chartink_alloc_value.value()

        # Add to scanner
        self.chartink_scanner.add_scan(
            scan_name=name,
            scan_url=url,
            interval=interval,
            action=action,
            quantity=quantity,
            start_time=start_time,
            exit_time=exit_time,
            no_new_trade_time=no_new_trade_time,
            total_capital=total_capital,
            alloc_type=alloc_type,
            alloc_value=alloc_value,
            max_trades=max_trades
        )

        # Save to config
        scans = self.config.get('chartink.scans', [])
        scans.append({
            'name': name,
            'url': url,
            'action': action,
            'quantity': quantity,
            'interval': interval,
            'start_time': start_time,
            'exit_time': exit_time,
            'no_new_trade_time': no_new_trade_time,
            'total_capital': total_capital,
            'alloc_type': alloc_type,
            'alloc_value': alloc_value,
            'max_trades': max_trades
        })
        self.config.set('chartink.scans', scans)

        # Clear inputs
        self.chartink_scan_name.clear()
        self.chartink_scan_url.clear()

        # Refresh table
        self._refresh_chartink_scans_table()

        QMessageBox.information(self, "Success", f"Scanner '{name}' added successfully")

    def _test_chartink_scan(self):
        """Test a Chartink scanner URL"""
        url = self.chartink_scan_url.text().strip()

        if not url:
            QMessageBox.warning(self, "Error", "Please enter a scanner URL")
            return

        if not url.startswith("https://chartink.com/screener/"):
            QMessageBox.warning(self, "Error", "Invalid Chartink URL")
            return

        try:
            self.status_bar.showMessage("Testing scanner...")
            results = self.chartink_scanner.test_scan(url)

            if results:
                result_text = f"Found {len(results)} stocks:\n\n"
                for i, stock in enumerate(results[:10]):  # Show max 10
                    result_text += f"{i+1}. {stock['symbol']} - ₹{stock['price']:.2f}\n"
                if len(results) > 10:
                    result_text += f"\n... and {len(results) - 10} more"

                QMessageBox.information(self, "Scanner Test Results", result_text)
            else:
                QMessageBox.information(self, "Scanner Test Results", "No stocks found in this scanner")

            self.status_bar.showMessage("Ready")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to test scanner: {e}")
            self.status_bar.showMessage("Ready")

    def _refresh_chartink_scans_table(self):
        """Refresh the Chartink scans table with all fields"""
        scans = self.chartink_scanner.get_active_scans()
        self.chartink_scans_table.setRowCount(len(scans))

        for i, scan in enumerate(scans):
            self.chartink_scans_table.setItem(i, 0, QTableWidgetItem(scan['name']))
            self.chartink_scans_table.setItem(i, 1, QTableWidgetItem(scan['action']))

            # Show allocation type and value
            alloc_type = scan.get('alloc_type', 'auto')
            alloc_value = scan.get('alloc_value', 0)
            if alloc_type == 'fixed_qty':
                alloc_text = f"{int(alloc_value)} shares"
            elif alloc_type == 'fixed_amount':
                alloc_text = f"₹{alloc_value:,.0f}/stock"
            else:
                alloc_text = "Auto"
            self.chartink_scans_table.setItem(i, 2, QTableWidgetItem(alloc_text))

            self.chartink_scans_table.setItem(i, 3, QTableWidgetItem(scan.get('start_time', '09:15')))
            self.chartink_scans_table.setItem(i, 4, QTableWidgetItem(scan.get('exit_time', '15:15')))
            self.chartink_scans_table.setItem(i, 5, QTableWidgetItem(scan.get('no_new_trade_time', '14:30')))
            amt = scan.get('total_capital', 0)
            self.chartink_scans_table.setItem(i, 6, QTableWidgetItem(f"₹{amt:,.0f}" if amt > 0 else "Unlimited"))
            max_t = scan.get('max_trades', 0)
            self.chartink_scans_table.setItem(i, 7, QTableWidgetItem(str(max_t) if max_t > 0 else "Unlimited"))
            self.chartink_scans_table.setItem(i, 8, QTableWidgetItem(str(scan.get('trade_count', 0))))

            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(lambda checked, name=scan['name']: self._remove_chartink_scan(name))
            self.chartink_scans_table.setCellWidget(i, 9, remove_btn)

        # Also refresh positions table
        self._refresh_chartink_positions_table()

    def _refresh_chartink_positions_table(self):
        """Refresh the scanner open positions table"""
        all_positions = []
        for scan_name in self.chartink_scanner.active_scans:
            positions = self.chartink_scanner.get_open_positions(scan_name)
            for symbol, pos in positions.items():
                all_positions.append({
                    'scanner': scan_name,
                    'symbol': symbol,
                    **pos
                })

        self.chartink_positions_table.setRowCount(len(all_positions))
        for i, pos in enumerate(all_positions):
            self.chartink_positions_table.setItem(i, 0, QTableWidgetItem(pos['scanner']))
            self.chartink_positions_table.setItem(i, 1, QTableWidgetItem(pos['symbol']))
            self.chartink_positions_table.setItem(i, 2, QTableWidgetItem(pos['action']))
            self.chartink_positions_table.setItem(i, 3, QTableWidgetItem(str(pos['quantity'])))
            self.chartink_positions_table.setItem(i, 4, QTableWidgetItem(f"₹{pos['price']:.2f}" if pos.get('price') else "N/A"))
            self.chartink_positions_table.setItem(i, 5, QTableWidgetItem(pos.get('time', '')))

    def _remove_chartink_scan(self, scan_name: str):
        """Remove a Chartink scan"""
        self.chartink_scanner.remove_scan(scan_name)

        # Remove from config
        scans = self.config.get('chartink.scans', [])
        scans = [s for s in scans if s.get('name') != scan_name]
        self.config.set('chartink.scans', scans)

        self._refresh_chartink_scans_table()

    def _start_chartink_monitoring(self):
        """Start Chartink monitoring"""
        self.chartink_scanner.start_monitoring()
        self.start_chartink_btn.setEnabled(False)
        self.stop_chartink_btn.setEnabled(True)
        self.status_bar.showMessage("Chartink monitoring started")

    def _stop_chartink_monitoring(self):
        """Stop Chartink monitoring"""
        self.chartink_scanner.stop_monitoring()
        self.start_chartink_btn.setEnabled(True)
        self.stop_chartink_btn.setEnabled(False)
        self.status_bar.showMessage("Chartink monitoring stopped")

    def _reset_chartink_counters(self):
        """Reset daily trade counters for all scanners"""
        self.chartink_scanner.reset_daily_counters()
        self._refresh_chartink_scans_table()
        self.status_bar.showMessage("Daily counters reset")

    def _on_chartink_alert(self, alert):
        """Handle Chartink alert - execute trade with position tracking"""
        from algo_trader.core.order_manager import Order, OrderType, TransactionType, Exchange

        extra = alert.extra_data or {}
        is_squareoff = extra.get('is_squareoff', False)

        # Determine action and quantity
        if is_squareoff:
            action = extra.get('exit_action', 'SELL')
            quantity = extra.get('quantity', 1)
        else:
            scan_config = self.chartink_scanner.active_scans.get(alert.scan_name, {})
            action = scan_config.get('action', 'BUY')
            # Use calculated quantity from allocation logic
            quantity = extra.get('calculated_quantity', scan_config.get('quantity', 1))

        # Log alert to table
        row = self.chartink_alerts_table.rowCount()
        self.chartink_alerts_table.insertRow(row)
        self.chartink_alerts_table.setItem(row, 0, QTableWidgetItem(alert.triggered_at.strftime("%H:%M:%S")))
        self.chartink_alerts_table.setItem(row, 1, QTableWidgetItem(alert.scan_name))
        self.chartink_alerts_table.setItem(row, 2, QTableWidgetItem(alert.symbol))
        self.chartink_alerts_table.setItem(row, 3, QTableWidgetItem(f"₹{alert.price:.2f}" if alert.price else "N/A"))
        self.chartink_alerts_table.setItem(row, 4, QTableWidgetItem(str(quantity)))

        # Execute trade if broker is connected
        current_broker = self.broker_combo.currentText().lower()
        if current_broker and current_broker in self.brokers:
            try:
                order = Order(
                    symbol=alert.symbol,
                    transaction_type=TransactionType.BUY if action == "BUY" else TransactionType.SELL,
                    quantity=quantity,
                    order_type=OrderType.MARKET,
                    exchange=Exchange.NSE
                )
                result = self.order_manager.place_order(order, current_broker)

                if is_squareoff:
                    action_text = f"SQUARE-OFF {action}: {result.broker_order_id}"
                    self.chartink_scanner.record_squareoff(alert.scan_name, alert.symbol)
                else:
                    action_text = f"{action} order placed: {result.broker_order_id}"
                    # Record this trade for position tracking
                    self.chartink_scanner.record_trade(
                        alert.scan_name, alert.symbol, action, quantity,
                        alert.price or 0
                    )

                logger.info(f"Chartink auto-trade: {action_text}")
            except Exception as e:
                action_text = f"Order failed: {e}"
                logger.error(f"Chartink auto-trade error: {e}")
        else:
            action_text = "No broker connected"

        self.chartink_alerts_table.setItem(row, 5, QTableWidgetItem(action_text))

        # Refresh positions and scans tables
        self._refresh_chartink_scans_table()

    # Risk Management / TSL Methods
    def _init_risk_manager(self):
        """Initialize the risk manager"""
        self.risk_manager = RiskManager()
        self.risk_manager.register_mtm_callback(self._on_mtm_update)
        self.risk_manager.register_sl_hit_callback(self._on_sl_hit)
        self.risk_manager.register_target_hit_callback(self._on_target_hit)
        logger.info("Risk manager initialized")

    def _on_sl_type_changed(self, sl_type: str):
        """Handle stop loss type change"""
        if sl_type == "Fixed Price":
            self.risk_sl_value.setPrefix("₹")
            self.risk_sl_value.setSuffix("")
            self.risk_sl_value.setDecimals(2)
        elif sl_type == "Trailing %":
            self.risk_sl_value.setPrefix("")
            self.risk_sl_value.setSuffix("%")
            self.risk_sl_value.setDecimals(1)
            self.risk_sl_value.setRange(0.1, 50)
        elif sl_type == "Trailing Points":
            self.risk_sl_value.setPrefix("₹")
            self.risk_sl_value.setSuffix(" pts")
            self.risk_sl_value.setDecimals(2)

    def _add_risk_position(self):
        """Add a new position to risk manager"""
        symbol = self.risk_symbol.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Error", "Please enter a symbol")
            return

        exchange = self.risk_exchange.currentText()
        quantity = self.risk_quantity.value()
        entry_price = self.risk_entry_price.value()
        sl_type = self.risk_sl_type.currentText()
        sl_value = self.risk_sl_value.value()
        target = self.risk_target.value() if self.risk_target.value() > 0 else None

        if quantity == 0:
            QMessageBox.warning(self, "Error", "Quantity cannot be zero")
            return

        if entry_price <= 0:
            QMessageBox.warning(self, "Error", "Please enter a valid entry price")
            return

        # Determine SL parameters based on type
        stop_loss = None
        trailing_sl_percent = None
        trailing_sl_points = None

        if sl_value > 0:
            if sl_type == "Fixed Price":
                stop_loss = sl_value
            elif sl_type == "Trailing %":
                trailing_sl_percent = sl_value
                # Calculate initial SL
                if quantity > 0:
                    stop_loss = entry_price * (1 - sl_value / 100)
                else:
                    stop_loss = entry_price * (1 + sl_value / 100)
            elif sl_type == "Trailing Points":
                trailing_sl_points = sl_value
                # Calculate initial SL
                if quantity > 0:
                    stop_loss = entry_price - sl_value
                else:
                    stop_loss = entry_price + sl_value

        # Add position to risk manager
        self.risk_manager.add_position(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            exchange=exchange,
            stop_loss=stop_loss,
            target=target,
            trailing_sl_percent=trailing_sl_percent,
            trailing_sl_points=trailing_sl_points
        )

        # Clear inputs
        self.risk_symbol.clear()
        self.risk_entry_price.setValue(0)
        self.risk_sl_value.setValue(0)
        self.risk_target.setValue(0)

        # Refresh table
        self._refresh_risk_positions()

        QMessageBox.information(self, "Success", f"Position {symbol} added for tracking")

    def _start_risk_monitoring(self):
        """Start risk monitoring with price updates"""
        # Get active broker for price feed
        current_broker = self.broker_combo.currentText().lower()
        price_feed = self.brokers.get(current_broker) if current_broker else None

        self.risk_manager.start_monitoring(price_feed=price_feed, interval=2.0)

        self.start_risk_monitor_btn.setEnabled(False)
        self.stop_risk_monitor_btn.setEnabled(True)
        self.status_bar.showMessage("Risk monitoring started")

    def _stop_risk_monitoring(self):
        """Stop risk monitoring"""
        self.risk_manager.stop_monitoring()

        self.start_risk_monitor_btn.setEnabled(True)
        self.stop_risk_monitor_btn.setEnabled(False)
        self.status_bar.showMessage("Risk monitoring stopped")

    def _refresh_risk_positions(self):
        """Refresh the risk positions table"""
        positions = self.risk_manager.get_all_positions()
        self.risk_positions_table.setRowCount(len(positions))

        for i, pos in enumerate(positions):
            self.risk_positions_table.setItem(i, 0, QTableWidgetItem(pos.symbol))
            self.risk_positions_table.setItem(i, 1, QTableWidgetItem(str(pos.quantity)))
            self.risk_positions_table.setItem(i, 2, QTableWidgetItem(f"₹{pos.entry_price:.2f}"))
            self.risk_positions_table.setItem(i, 3, QTableWidgetItem(f"₹{pos.current_price:.2f}"))
            self.risk_positions_table.setItem(i, 4, QTableWidgetItem(f"₹{pos.stop_loss:.2f}" if pos.stop_loss else "-"))
            self.risk_positions_table.setItem(i, 5, QTableWidgetItem(f"₹{pos.target:.2f}" if pos.target else "-"))

            # High/Low for trailing SL
            if pos.quantity > 0:
                self.risk_positions_table.setItem(i, 6, QTableWidgetItem(f"H: ₹{pos.highest_price:.2f}"))
            else:
                self.risk_positions_table.setItem(i, 6, QTableWidgetItem(f"L: ₹{pos.lowest_price:.2f}"))

            # P&L with color
            pnl_item = QTableWidgetItem(f"₹{pos.pnl:.2f}")
            if pos.pnl > 0:
                pnl_item.setForeground(Qt.GlobalColor.darkGreen)
            elif pos.pnl < 0:
                pnl_item.setForeground(Qt.GlobalColor.red)
            self.risk_positions_table.setItem(i, 7, pnl_item)

            # P&L %
            pnl_pct_item = QTableWidgetItem(f"{pos.pnl_percent:.2f}%")
            if pos.pnl_percent > 0:
                pnl_pct_item.setForeground(Qt.GlobalColor.darkGreen)
            elif pos.pnl_percent < 0:
                pnl_pct_item.setForeground(Qt.GlobalColor.red)
            self.risk_positions_table.setItem(i, 8, pnl_pct_item)

            # Close button
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(lambda checked, s=pos.symbol, e=pos.exchange: self._close_risk_position(s, e))
            self.risk_positions_table.setCellWidget(i, 9, close_btn)

        # Update MTM summary
        mtm = self.risk_manager.get_mtm_summary()
        self._update_mtm_display(mtm)

    def _close_risk_position(self, symbol: str, exchange: str):
        """Close a tracked position"""
        position = self.risk_manager.get_position(symbol, exchange)
        if position:
            # Use current price as exit price
            self.risk_manager.close_position(symbol, position.current_price, exchange)
            self._refresh_risk_positions()
            QMessageBox.information(self, "Position Closed", f"Closed {symbol} @ ₹{position.current_price:.2f}")

    def _update_mtm_display(self, mtm):
        """Update MTM display labels"""
        # Total P&L
        total_color = "green" if mtm.total_pnl >= 0 else "red"
        self.mtm_total_pnl.setText(f"Total P&L: <span style='color:{total_color}'>₹{mtm.total_pnl:.2f}</span>")
        self.mtm_total_pnl.setTextFormat(Qt.TextFormat.RichText)

        # Realized
        realized_color = "green" if mtm.realized_pnl >= 0 else "red"
        self.mtm_realized.setText(f"Realized: <span style='color:{realized_color}'>₹{mtm.realized_pnl:.2f}</span>")
        self.mtm_realized.setTextFormat(Qt.TextFormat.RichText)

        # Unrealized
        unrealized_color = "green" if mtm.unrealized_pnl >= 0 else "red"
        self.mtm_unrealized.setText(f"Unrealized: <span style='color:{unrealized_color}'>₹{mtm.unrealized_pnl:.2f}</span>")
        self.mtm_unrealized.setTextFormat(Qt.TextFormat.RichText)

        # Trade stats
        self.mtm_trades.setText(f"Trades: {mtm.total_trades} (W: {mtm.winning_trades} / L: {mtm.losing_trades})")

    def _on_mtm_update(self, mtm):
        """Handle MTM update from risk manager"""
        self._update_mtm_display(mtm)
        self._refresh_risk_positions()

    def _on_sl_hit(self, position):
        """Handle stop loss hit"""
        QMessageBox.warning(
            self, "Stop Loss Hit",
            f"Stop Loss triggered for {position.symbol}!\n"
            f"Entry: ₹{position.entry_price:.2f}\n"
            f"Exit: ₹{position.current_price:.2f}\n"
            f"P&L: ₹{position.pnl:.2f}"
        )

        # Auto-close position from tracking
        self.risk_manager.close_position(position.symbol, position.current_price, position.exchange)
        self._refresh_risk_positions()

        # Place exit order if broker connected
        self._place_exit_order(position)

    def _on_target_hit(self, position):
        """Handle target hit"""
        QMessageBox.information(
            self, "Target Hit",
            f"Target reached for {position.symbol}!\n"
            f"Entry: ₹{position.entry_price:.2f}\n"
            f"Exit: ₹{position.current_price:.2f}\n"
            f"P&L: ₹{position.pnl:.2f}"
        )

        # Auto-close position from tracking
        self.risk_manager.close_position(position.symbol, position.current_price, position.exchange)
        self._refresh_risk_positions()

        # Place exit order if broker connected
        self._place_exit_order(position)

    def _place_exit_order(self, position):
        """Place exit order for a position"""
        from algo_trader.core.order_manager import Order, OrderType, TransactionType, Exchange

        current_broker = self.broker_combo.currentText().lower()
        if not current_broker or current_broker not in self.brokers:
            logger.warning("No broker connected for exit order")
            return

        try:
            # Exit is opposite of entry
            if position.quantity > 0:
                transaction_type = TransactionType.SELL
            else:
                transaction_type = TransactionType.BUY

            order = Order(
                symbol=position.symbol,
                transaction_type=transaction_type,
                quantity=abs(position.quantity),
                order_type=OrderType.MARKET,
                exchange=Exchange[position.exchange]
            )

            result = self.order_manager.place_order(order, current_broker)
            logger.info(f"Exit order placed: {result.broker_order_id}")
            self._load_orders()

        except Exception as e:
            logger.error(f"Failed to place exit order: {e}")

    # Options Trading Methods
    def _init_options_manager(self):
        """Initialize the options manager"""
        self.options_manager = OptionsManager()
        self.options_manager.register_exit_callback(self._on_option_exit)
        self.options_manager.register_pnl_callback(self._on_option_pnl_update)
        self._on_opt_symbol_changed(self.opt_symbol.currentText())

        # Initialize auto-options executor
        self.auto_options = AutoOptionsExecutor(self.options_manager, self.strategy_engine)
        self.auto_options.register_trade_callback(self._on_auto_option_trade)
        logger.info("Options manager initialized")

    def _save_auto_options_config(self):
        """Save auto-options configuration with per-leg settings"""
        from algo_trader.core.auto_options import LegConfig

        # Update Leg 1 config
        self.auto_options.config.leg1 = LegConfig(
            enabled=True,
            option_type=self.auto_leg1_type.currentText(),
            action=self.auto_leg1_action.currentText(),
            strike_selection=self.auto_leg1_strike.currentText(),
            expiry_selection=self.auto_leg1_expiry.currentText(),
            quantity=self.auto_leg1_qty.value()
        )

        # Update Leg 2 config (hedge)
        hedge_on = self.auto_opt_hedge_enabled.isChecked()
        self.auto_options.config.leg2 = LegConfig(
            enabled=hedge_on,
            option_type=self.auto_leg2_type.currentText(),
            action=self.auto_leg2_action.currentText(),
            strike_selection=self.auto_leg2_strike.currentText(),
            expiry_selection=self.auto_leg2_expiry.currentText(),
            quantity=self.auto_leg2_qty.value()
        )

        self.auto_options.update_config(
            symbol=self.auto_opt_symbol.currentText().strip().upper(),
            hedge_enabled=hedge_on,
            close_on_opposite=self.auto_opt_close_opposite.isChecked(),
            exit_type=self.auto_opt_exit_type.currentText(),
            sl_value=self.auto_opt_sl.value(),
            target_value=self.auto_opt_target.value(),
            tsl_value=self.auto_opt_tsl.value(),
        )

        if self.auto_opt_enabled.isChecked():
            current_broker = self.broker_combo.currentText().lower()
            if current_broker and current_broker in self.brokers:
                self.auto_options.set_broker(self.brokers[current_broker])
            self.auto_options.enable()
        else:
            self.auto_options.disable()

        # Build info message
        leg1_info = (f"Leg 1: {self.auto_leg1_action.currentText()} "
                     f"{self.auto_leg1_type.currentText()} "
                     f"Strike:{self.auto_leg1_strike.currentText()} "
                     f"Expiry:{self.auto_leg1_expiry.currentText()}")

        leg2_info = ""
        if hedge_on:
            leg2_info = (f"\nLeg 2: {self.auto_leg2_action.currentText()} "
                         f"{self.auto_leg2_type.currentText()} "
                         f"Strike:{self.auto_leg2_strike.currentText()} "
                         f"Expiry:{self.auto_leg2_expiry.currentText()}")

        QMessageBox.information(
            self, "Saved",
            f"Auto-Options config saved!\n"
            f"Status: {'ENABLED' if self.auto_opt_enabled.isChecked() else 'DISABLED'}\n"
            f"{leg1_info}{leg2_info}"
        )

    def _on_auto_option_trade(self, trade_info):
        """Handle auto-option trade execution"""
        row = self.auto_trade_log_table.rowCount()
        self.auto_trade_log_table.insertRow(row)
        self.auto_trade_log_table.setItem(row, 0, QTableWidgetItem(trade_info.get("time", "")))
        self.auto_trade_log_table.setItem(row, 1, QTableWidgetItem(trade_info.get("signal", "")))
        self.auto_trade_log_table.setItem(row, 2, QTableWidgetItem(trade_info.get("strategy", "")))
        self.auto_trade_log_table.setItem(row, 3, QTableWidgetItem(trade_info.get("action", "")))
        self.auto_trade_log_table.setItem(row, 4, QTableWidgetItem(trade_info.get("expiry", "")))
        self.auto_trade_log_table.setItem(row, 5, QTableWidgetItem(str(trade_info.get("qty", ""))))
        self._refresh_option_positions()

    def _on_opt_symbol_changed(self, symbol: str):
        """Handle symbol change in options tab"""
        if not symbol:
            return
        from algo_trader.core.options_manager import INDEX_LOT_SIZES
        lot_size = INDEX_LOT_SIZES.get(symbol.upper(), 1)
        self.opt_lot_size.setText(f"Lot Size: {lot_size}")

    def _fetch_spot_price(self):
        """Fetch spot price from broker"""
        symbol = self.opt_symbol.currentText().strip()
        current_broker = self.broker_combo.currentText().lower()

        if current_broker and current_broker in self.brokers:
            try:
                quote = self.brokers[current_broker].get_quote(symbol, "NSE")
                if quote:
                    ltp = quote.get('last_price') or quote.get('ltp') or 0
                    if isinstance(ltp, dict):
                        ltp = ltp.get('last_price', 0)
                    self.opt_spot_price.setValue(float(ltp))
                    self.status_bar.showMessage(f"Spot price fetched: ₹{ltp}")
                    return
            except Exception as e:
                logger.error(f"Error fetching spot: {e}")

        QMessageBox.warning(self, "Error", "Could not fetch spot price. Please enter manually or connect broker.")

    def _load_expiry_dates(self):
        """Load expiry dates for selected symbol"""
        symbol = self.opt_symbol.currentText().strip()
        if not symbol:
            return

        current_broker = self.broker_combo.currentText().lower()
        broker = self.brokers.get(current_broker) if current_broker else None

        expiries = self.options_manager.get_expiry_dates(symbol, broker)
        self.opt_expiry.clear()
        for exp in expiries:
            self.opt_expiry.addItem(exp)

        self.status_bar.showMessage(f"Loaded {len(expiries)} expiry dates for {symbol}")

    def _load_strike_prices(self):
        """Load strike prices based on spot price"""
        symbol = self.opt_symbol.currentText().strip()
        spot = self.opt_spot_price.value()

        if spot <= 0:
            QMessageBox.warning(self, "Error", "Please enter or fetch spot price first")
            return

        strikes = self.options_manager.get_strike_prices(symbol, spot)
        self.opt_strike.clear()
        for strike in strikes:
            self.opt_strike.addItem(str(int(strike)) if strike == int(strike) else str(strike))

        # Select ATM
        from algo_trader.core.options_manager import INDEX_STRIKE_GAPS
        gap = INDEX_STRIKE_GAPS.get(symbol.upper(), 50)
        atm = round(spot / gap) * gap
        atm_str = str(int(atm)) if atm == int(atm) else str(atm)
        idx = self.opt_strike.findText(atm_str)
        if idx >= 0:
            self.opt_strike.setCurrentIndex(idx)

        self.status_bar.showMessage(f"Loaded {len(strikes)} strikes. ATM: {atm_str}")

    def _add_builder_leg(self):
        """Add a new leg row to the multi-leg builder table"""
        row = self.leg_builder_table.rowCount()
        self.leg_builder_table.insertRow(row)

        # Strike combo - populate from loaded strikes
        strike_combo = QComboBox()
        strike_combo.setEditable(True)
        for i in range(self.opt_strike.count()):
            strike_combo.addItem(self.opt_strike.itemText(i))
        # Auto-select ATM if available
        if self.opt_strike.currentText():
            strike_combo.setCurrentText(self.opt_strike.currentText())
        self.leg_builder_table.setCellWidget(row, 0, strike_combo)

        # Expiry combo - populate from loaded expiries
        expiry_combo = QComboBox()
        for i in range(self.opt_expiry.count()):
            expiry_combo.addItem(self.opt_expiry.itemText(i))
        if self.opt_expiry.currentText():
            expiry_combo.setCurrentText(self.opt_expiry.currentText())
        self.leg_builder_table.setCellWidget(row, 1, expiry_combo)

        # CE/PE
        type_combo = QComboBox()
        type_combo.addItems(["CE", "PE"])
        self.leg_builder_table.setCellWidget(row, 2, type_combo)

        # BUY/SELL
        action_combo = QComboBox()
        action_combo.addItems(["BUY", "SELL"])
        self.leg_builder_table.setCellWidget(row, 3, action_combo)

        # Lots
        qty_spin = QSpinBox()
        qty_spin.setRange(1, 500)
        qty_spin.setValue(1)
        self.leg_builder_table.setCellWidget(row, 4, qty_spin)

        # Premium
        premium_spin = QDoubleSpinBox()
        premium_spin.setRange(0, 100000)
        premium_spin.setDecimals(2)
        self.leg_builder_table.setCellWidget(row, 5, premium_spin)

        # Remove button
        remove_btn = QPushButton("X")
        remove_btn.setMaximumWidth(30)
        remove_btn.clicked.connect(lambda checked, r=row: self._remove_builder_leg(r))
        self.leg_builder_table.setCellWidget(row, 6, remove_btn)

    def _remove_builder_leg(self, row):
        """Remove a leg from builder"""
        if row < self.leg_builder_table.rowCount():
            self.leg_builder_table.removeRow(row)

    def _on_opt_strategy_changed(self, strategy_name: str):
        """Handle strategy type change - kept for compatibility"""
        pass

    def _on_opt_exit_type_changed(self, exit_type: str):
        """Handle exit type change"""
        is_pnl = exit_type == "P&L Based"
        is_sl_pct = exit_type == "SL %"
        is_tsl = exit_type in ("TSL %", "TSL Points")

        if is_pnl:
            self.opt_sl_value.setPrefix("₹")
            self.opt_sl_value.setSuffix("")
            self.opt_target_value.setPrefix("₹")
            self.opt_target_value.setSuffix("")
            self.opt_tsl_value.setPrefix("₹")
            self.opt_tsl_value.setSuffix("")
        elif is_sl_pct:
            self.opt_sl_value.setPrefix("")
            self.opt_sl_value.setSuffix("%")
            self.opt_target_value.setPrefix("")
            self.opt_target_value.setSuffix("%")
        elif is_tsl:
            self.opt_tsl_value.setPrefix("")
            self.opt_tsl_value.setSuffix("%" if exit_type == "TSL %" else " pts")

    def _add_option_position(self):
        """Add a new multi-leg option position from builder table"""
        symbol = self.opt_symbol.currentText().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Error", "Please select a symbol")
            return

        num_legs = self.leg_builder_table.rowCount()
        if num_legs == 0:
            QMessageBox.warning(self, "Error", "Please add at least one leg using '+ Add Leg' button")
            return

        # Read all legs from builder table
        legs_data = []
        for row in range(num_legs):
            strike_widget = self.leg_builder_table.cellWidget(row, 0)
            expiry_widget = self.leg_builder_table.cellWidget(row, 1)
            type_widget = self.leg_builder_table.cellWidget(row, 2)
            action_widget = self.leg_builder_table.cellWidget(row, 3)
            qty_widget = self.leg_builder_table.cellWidget(row, 4)
            premium_widget = self.leg_builder_table.cellWidget(row, 5)

            if not all([strike_widget, expiry_widget, type_widget, action_widget, qty_widget, premium_widget]):
                QMessageBox.warning(self, "Error", f"Leg {row + 1} has missing fields")
                return

            try:
                strike = float(strike_widget.currentText())
            except (ValueError, AttributeError):
                QMessageBox.warning(self, "Error", f"Leg {row + 1}: Invalid strike price")
                return

            expiry = expiry_widget.currentText()
            if not expiry:
                QMessageBox.warning(self, "Error", f"Leg {row + 1}: Please select expiry")
                return

            legs_data.append({
                "strike": strike,
                "expiry": expiry,
                "option_type": type_widget.currentText(),
                "action": action_widget.currentText(),
                "quantity": qty_widget.value(),
                "entry_price": premium_widget.value()
            })

        exit_type = self.opt_exit_type.currentText()
        sl_value = self.opt_sl_value.value()
        target_value = self.opt_target_value.value()
        tsl_value = self.opt_tsl_value.value()

        if num_legs == 1:
            # Single leg - use create_single_option
            leg = legs_data[0]
            position = self.options_manager.create_single_option(
                symbol=symbol, expiry=leg["expiry"], strike=leg["strike"],
                option_type=leg["option_type"], action=leg["action"],
                quantity=leg["quantity"], entry_price=leg["entry_price"],
                exit_type=exit_type, sl_value=sl_value,
                target_value=target_value, tsl_value=tsl_value
            )
        else:
            # Multi-leg - use create_custom_multileg
            position = self.options_manager.create_custom_multileg(
                symbol=symbol, legs_data=legs_data,
                exit_type=exit_type, sl_value=sl_value,
                target_value=target_value, tsl_value=tsl_value
            )

        # Show confirmation
        legs_info = "\n".join(
            f"  Leg {i+1}: {l['strike']}{l['option_type']} {l['action']} "
            f"Exp:{l['expiry']} Qty:{l['quantity']} @₹{l['entry_price']}"
            for i, l in enumerate(legs_data)
        )
        QMessageBox.information(
            self, "Position Created",
            f"{position.position_id}: {symbol}\n"
            f"Legs ({num_legs}):\n{legs_info}"
        )

        # Clear builder table
        self.leg_builder_table.setRowCount(0)

        self._refresh_option_positions()

    def _refresh_option_positions(self):
        """Refresh the options positions table"""
        positions = self.options_manager.get_all_positions()
        self.opt_positions_table.setRowCount(len(positions))

        for i, pos in enumerate(positions):
            self.opt_positions_table.setItem(i, 0, QTableWidgetItem(pos.position_id))
            self.opt_positions_table.setItem(i, 1, QTableWidgetItem(pos.symbol))
            self.opt_positions_table.setItem(i, 2, QTableWidgetItem(pos.strategy_type.value))
            self.opt_positions_table.setItem(i, 3, QTableWidgetItem(str(len(pos.legs))))

            # Expiry from first leg
            expiry = pos.legs[0].expiry if pos.legs else "-"
            self.opt_positions_table.setItem(i, 4, QTableWidgetItem(expiry))

            # P&L with color
            pnl_item = QTableWidgetItem(f"₹{pos.total_pnl:.2f}")
            if pos.total_pnl > 0:
                pnl_item.setForeground(Qt.GlobalColor.darkGreen)
            elif pos.total_pnl < 0:
                pnl_item.setForeground(Qt.GlobalColor.red)
            self.opt_positions_table.setItem(i, 5, pnl_item)

            # P&L %
            pct_item = QTableWidgetItem(f"{pos.total_pnl_percent:.2f}%")
            if pos.total_pnl_percent > 0:
                pct_item.setForeground(Qt.GlobalColor.darkGreen)
            elif pos.total_pnl_percent < 0:
                pct_item.setForeground(Qt.GlobalColor.red)
            self.opt_positions_table.setItem(i, 6, pct_item)

            self.opt_positions_table.setItem(i, 7, QTableWidgetItem(f"₹{pos.max_pnl:.2f}"))
            self.opt_positions_table.setItem(i, 8, QTableWidgetItem(pos.exit_type.value))

            # Close button
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(lambda checked, pid=pos.position_id: self._close_option_position(pid))
            self.opt_positions_table.setCellWidget(i, 9, close_btn)

        # Update summary
        summary = self.options_manager.get_options_summary()
        color = "green" if summary["total_pnl"] >= 0 else "red"
        self.opt_total_pnl.setText(f"Total P&L: <span style='color:{color}'>₹{summary['total_pnl']:.2f}</span>")
        self.opt_total_pnl.setTextFormat(Qt.TextFormat.RichText)
        self.opt_active_count.setText(f"Active: {summary['active_positions']}")
        self.opt_closed_count.setText(f"Closed: {summary['closed_positions']}")

    def _on_opt_position_selected(self, row, col):
        """Show leg details when position is selected"""
        pos_id_item = self.opt_positions_table.item(row, 0)
        if not pos_id_item:
            return

        pos = self.options_manager.get_position(pos_id_item.text())
        if not pos:
            return

        self.opt_legs_table.setRowCount(len(pos.legs))
        for i, leg in enumerate(pos.legs):
            self.opt_legs_table.setItem(i, 0, QTableWidgetItem(f"Leg {leg.leg_id}"))
            self.opt_legs_table.setItem(i, 1, QTableWidgetItem(str(int(leg.strike))))
            self.opt_legs_table.setItem(i, 2, QTableWidgetItem(leg.expiry))
            self.opt_legs_table.setItem(i, 3, QTableWidgetItem(leg.option_type.value))
            self.opt_legs_table.setItem(i, 4, QTableWidgetItem(leg.action))
            self.opt_legs_table.setItem(i, 5, QTableWidgetItem(f"{leg.quantity} x {leg.lot_size}"))
            self.opt_legs_table.setItem(i, 6, QTableWidgetItem(f"₹{leg.entry_price:.2f}"))
            self.opt_legs_table.setItem(i, 7, QTableWidgetItem(f"₹{leg.current_price:.2f}"))

            pnl_item = QTableWidgetItem(f"₹{leg.pnl:.2f}")
            if leg.pnl > 0:
                pnl_item.setForeground(Qt.GlobalColor.darkGreen)
            elif leg.pnl < 0:
                pnl_item.setForeground(Qt.GlobalColor.red)
            self.opt_legs_table.setItem(i, 8, pnl_item)

            pct_item = QTableWidgetItem(f"{leg.pnl_percent:.2f}%")
            if leg.pnl_percent > 0:
                pct_item.setForeground(Qt.GlobalColor.darkGreen)
            elif leg.pnl_percent < 0:
                pct_item.setForeground(Qt.GlobalColor.red)
            self.opt_legs_table.setItem(i, 9, pct_item)

    def _close_option_position(self, pos_id: str):
        """Close an option position"""
        pos = self.options_manager.get_position(pos_id)
        if not pos:
            return

        reply = QMessageBox.question(
            self, "Close Position",
            f"Close {pos.symbol} {pos.strategy_type.value} position?\n"
            f"Current P&L: ₹{pos.total_pnl:.2f}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Place exit orders for each leg
            self._place_option_exit_orders(pos)
            self.options_manager.close_position(pos_id)
            self._refresh_option_positions()
            QMessageBox.information(self, "Closed", f"Position {pos_id} closed. P&L: ₹{pos.total_pnl:.2f}")

    def _place_option_exit_orders(self, position):
        """Place exit orders for all legs of an option position"""
        from algo_trader.core.order_manager import Order, OrderType, TransactionType, Exchange

        current_broker = self.broker_combo.currentText().lower()
        if not current_broker or current_broker not in self.brokers:
            logger.warning("No broker connected for option exit orders")
            return

        for leg in position.legs:
            try:
                # Exit is opposite of entry action
                exit_action = TransactionType.SELL if leg.action == "BUY" else TransactionType.BUY

                order = Order(
                    symbol=leg.trading_symbol,
                    transaction_type=exit_action,
                    quantity=leg.quantity * leg.lot_size,
                    order_type=OrderType.MARKET,
                    exchange=Exchange.NFO,
                    product="NRML"
                )

                result = self.order_manager.place_order(order, current_broker)
                logger.info(f"Option exit order: {leg.trading_symbol} -> {result.broker_order_id}")

            except Exception as e:
                logger.error(f"Failed to place option exit order for {leg.trading_symbol}: {e}")

    def _on_option_exit(self, position, reason):
        """Handle auto-exit trigger for options"""
        QMessageBox.warning(
            self, "Option Exit Triggered",
            f"Exit triggered for {position.symbol} {position.strategy_type.value}!\n"
            f"Reason: {reason}\n"
            f"P&L: ₹{position.total_pnl:.2f}"
        )

        self._place_option_exit_orders(position)
        self.options_manager.close_position(position.position_id)
        self._refresh_option_positions()

    def _on_option_pnl_update(self, position):
        """Handle P&L update for options"""
        self._refresh_option_positions()

    def _load_window_geometry(self):
        """Load saved window size and position"""
        try:
            import json
            import os
            settings_file = os.path.join(os.path.dirname(__file__), '..', 'window_settings.json')
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    if 'width' in settings and 'height' in settings:
                        self.resize(settings['width'], settings['height'])
                    if 'x' in settings and 'y' in settings:
                        self.move(settings['x'], settings['y'])
                    if settings.get('maximized', False):
                        self.showMaximized()
        except Exception as e:
            logger.debug(f"Could not load window geometry: {e}")

    def _save_window_geometry(self):
        """Save window size and position"""
        try:
            import json
            import os
            settings_file = os.path.join(os.path.dirname(__file__), '..', 'window_settings.json')
            settings = {
                'width': self.width(),
                'height': self.height(),
                'x': self.x(),
                'y': self.y(),
                'maximized': self.isMaximized()
            }
            with open(settings_file, 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            logger.debug(f"Could not save window geometry: {e}")

    def closeEvent(self, event):
        """Handle window close"""
        reply = QMessageBox.question(
            self, "Exit",
            "Are you sure you want to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._save_window_geometry()  # Save window size before closing
            event.accept()
        else:
            event.ignore()
