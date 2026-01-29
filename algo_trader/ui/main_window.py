"""
Main Application Window
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton,
    QLabel, QComboBox, QLineEdit, QTextEdit, QSplitter,
    QMessageBox, QStatusBar, QToolBar, QGroupBox, QFormLayout,
    QHeaderView, QDialog, QSpinBox, QDoubleSpinBox, QCheckBox,
    QScrollArea, QApplication
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

        # Paper trading simulator
        self.paper_simulator = None

        # Telegram alerts
        self.telegram = None

        self._init_ui()
        self._load_configured_brokers()
        self._setup_timers()
        self._init_telegram()

        # Initialize paper trading if enabled
        if self.config.get('trading.paper_mode', False):
            self._init_paper_trading()

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
        self._create_journal_tab()
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
        """Create enhanced dashboard tab with live P&L"""
        dashboard = QWidget()
        layout = QVBoxLayout(dashboard)

        # === Top Row - P&L Summary Cards ===
        pnl_group = QGroupBox("Today's Performance")
        pnl_layout = QHBoxLayout(pnl_group)

        # Realized P&L Card
        realized_card = QGroupBox("Realized P&L")
        realized_layout = QVBoxLayout(realized_card)
        self.dash_realized_pnl = QLabel("₹0.00")
        self.dash_realized_pnl.setStyleSheet("font-size: 24px; font-weight: bold; color: #4CAF50;")
        self.dash_realized_pnl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        realized_layout.addWidget(self.dash_realized_pnl)
        pnl_layout.addWidget(realized_card)

        # Unrealized P&L Card
        unrealized_card = QGroupBox("Unrealized P&L")
        unrealized_layout = QVBoxLayout(unrealized_card)
        self.dash_unrealized_pnl = QLabel("₹0.00")
        self.dash_unrealized_pnl.setStyleSheet("font-size: 24px; font-weight: bold; color: #2196F3;")
        self.dash_unrealized_pnl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unrealized_layout.addWidget(self.dash_unrealized_pnl)
        pnl_layout.addWidget(unrealized_card)

        # Total P&L Card
        total_card = QGroupBox("Total P&L")
        total_layout = QVBoxLayout(total_card)
        self.dash_total_pnl = QLabel("₹0.00")
        self.dash_total_pnl.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.dash_total_pnl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_layout.addWidget(self.dash_total_pnl)
        pnl_layout.addWidget(total_card)

        # Trades Today Card
        trades_card = QGroupBox("Trades Today")
        trades_layout = QVBoxLayout(trades_card)
        self.dash_trades_count = QLabel("0")
        self.dash_trades_count.setStyleSheet("font-size: 24px; font-weight: bold; color: #FF9800;")
        self.dash_trades_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        trades_layout.addWidget(self.dash_trades_count)
        pnl_layout.addWidget(trades_card)

        # Win Rate Card
        winrate_card = QGroupBox("Win Rate")
        winrate_layout = QVBoxLayout(winrate_card)
        self.dash_win_rate = QLabel("0%")
        self.dash_win_rate.setStyleSheet("font-size: 24px; font-weight: bold; color: #9C27B0;")
        self.dash_win_rate.setAlignment(Qt.AlignmentFlag.AlignCenter)
        winrate_layout.addWidget(self.dash_win_rate)
        pnl_layout.addWidget(winrate_card)

        layout.addWidget(pnl_group)

        # === Second Row - Account & Market Info ===
        info_layout = QHBoxLayout()

        # Account Summary
        account_group = QGroupBox("Account Summary")
        account_layout = QFormLayout(account_group)
        self.dash_available_margin = QLabel("₹0")
        self.dash_used_margin = QLabel("₹0")
        self.dash_total_balance = QLabel("₹0")
        self.dash_broker_status = QLabel("Not Connected")
        self.dash_broker_status.setStyleSheet("color: red;")
        account_layout.addRow("Available Margin:", self.dash_available_margin)
        account_layout.addRow("Used Margin:", self.dash_used_margin)
        account_layout.addRow("Total Balance:", self.dash_total_balance)
        account_layout.addRow("Broker Status:", self.dash_broker_status)
        info_layout.addWidget(account_group)

        # Market Status
        market_group = QGroupBox("Market Status")
        market_layout = QFormLayout(market_group)
        self.dash_market_status = QLabel("Closed")
        self.dash_market_status.setStyleSheet("color: red; font-weight: bold;")
        self.dash_nifty_price = QLabel("--")
        self.dash_banknifty_price = QLabel("--")
        self.dash_last_update = QLabel("--")
        market_layout.addRow("Market:", self.dash_market_status)
        market_layout.addRow("NIFTY:", self.dash_nifty_price)
        market_layout.addRow("BANKNIFTY:", self.dash_banknifty_price)
        market_layout.addRow("Last Update:", self.dash_last_update)
        info_layout.addWidget(market_group)

        # Quick Stats
        stats_group = QGroupBox("Quick Stats")
        stats_layout = QFormLayout(stats_group)
        self.dash_open_positions = QLabel("0")
        self.dash_active_scanners = QLabel("0")
        self.dash_active_strategies = QLabel("0")
        self.dash_pending_orders = QLabel("0")
        stats_layout.addRow("Open Positions:", self.dash_open_positions)
        stats_layout.addRow("Active Scanners:", self.dash_active_scanners)
        stats_layout.addRow("Active Strategies:", self.dash_active_strategies)
        stats_layout.addRow("Pending Orders:", self.dash_pending_orders)
        info_layout.addWidget(stats_group)

        layout.addLayout(info_layout)

        # === Open Positions Table ===
        positions_group = QGroupBox("Open Positions (Live P&L)")
        positions_layout = QVBoxLayout(positions_group)

        self.dash_positions_table = QTableWidget()
        self.dash_positions_table.setColumnCount(9)
        self.dash_positions_table.setHorizontalHeaderLabels([
            "Symbol", "Type", "Qty", "Avg Price", "LTP", "P&L", "P&L %", "Source", "Action"
        ])
        self.dash_positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        positions_layout.addWidget(self.dash_positions_table)

        layout.addWidget(positions_group)

        # === Recent Activity / Signals ===
        activity_group = QGroupBox("Recent Activity")
        activity_layout = QVBoxLayout(activity_group)

        self.dash_activity_table = QTableWidget()
        self.dash_activity_table.setColumnCount(6)
        self.dash_activity_table.setHorizontalHeaderLabels([
            "Time", "Type", "Symbol", "Action", "Price", "Status"
        ])
        self.dash_activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.dash_activity_table.setMaximumHeight(150)
        activity_layout.addWidget(self.dash_activity_table)

        layout.addWidget(activity_group)

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Dashboard")
        refresh_btn.clicked.connect(self._refresh_dashboard)
        layout.addWidget(refresh_btn)

        self.tabs.addTab(dashboard, "Dashboard")

        # Set up auto-refresh timer for dashboard
        self.dashboard_timer = QTimer(self)
        self.dashboard_timer.timeout.connect(self._refresh_dashboard)
        self.dashboard_timer.start(10000)  # Refresh every 10 seconds

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

        # === Risk Management Section ===
        risk_group = QGroupBox("Risk Management (Per Stock & Scanner MTM)")
        risk_main = QHBoxLayout(risk_group)

        # Left - Per Stock SL/Target
        stock_risk_form = QFormLayout()
        stock_risk_form.addRow(QLabel("<b>Per Stock Exit:</b>"))

        # Stop Loss Type
        self.chartink_sl_type = QComboBox()
        self.chartink_sl_type.addItems(["None", "Fixed Points", "Fixed %", "Fixed Amount"])
        self.chartink_sl_type.currentIndexChanged.connect(self._on_chartink_sl_type_changed)
        stock_risk_form.addRow("Stop Loss:", self.chartink_sl_type)

        self.chartink_sl_value = QDoubleSpinBox()
        self.chartink_sl_value.setRange(0, 99999)
        self.chartink_sl_value.setValue(0)
        self.chartink_sl_value.setEnabled(False)
        stock_risk_form.addRow("SL Value:", self.chartink_sl_value)

        # Target
        self.chartink_target_type = QComboBox()
        self.chartink_target_type.addItems(["None", "Fixed Points", "Fixed %", "Fixed Amount"])
        self.chartink_target_type.currentIndexChanged.connect(self._on_chartink_target_type_changed)
        stock_risk_form.addRow("Target:", self.chartink_target_type)

        self.chartink_target_value = QDoubleSpinBox()
        self.chartink_target_value.setRange(0, 99999)
        self.chartink_target_value.setValue(0)
        self.chartink_target_value.setEnabled(False)
        stock_risk_form.addRow("Target Value:", self.chartink_target_value)

        risk_main.addLayout(stock_risk_form)

        # Middle - Trailing SL
        tsl_form = QFormLayout()
        tsl_form.addRow(QLabel("<b>Trailing Stop Loss:</b>"))

        self.chartink_tsl_enabled = QCheckBox("Enable TSL")
        self.chartink_tsl_enabled.stateChanged.connect(self._on_chartink_tsl_toggle)
        tsl_form.addRow(self.chartink_tsl_enabled)

        self.chartink_tsl_type = QComboBox()
        self.chartink_tsl_type.addItems(["Points", "Percentage"])
        self.chartink_tsl_type.setEnabled(False)
        tsl_form.addRow("TSL Type:", self.chartink_tsl_type)

        self.chartink_tsl_value = QDoubleSpinBox()
        self.chartink_tsl_value.setRange(0, 9999)
        self.chartink_tsl_value.setValue(0)
        self.chartink_tsl_value.setEnabled(False)
        tsl_form.addRow("TSL Value:", self.chartink_tsl_value)

        # Profit Lock (move SL to breakeven after X profit)
        tsl_form.addRow(QLabel("<b>Profit Lock:</b>"))
        self.chartink_profit_lock_enabled = QCheckBox("Enable Profit Lock")
        tsl_form.addRow(self.chartink_profit_lock_enabled)

        self.chartink_profit_lock_type = QComboBox()
        self.chartink_profit_lock_type.addItems(["Points", "Amount"])
        tsl_form.addRow("Lock After:", self.chartink_profit_lock_type)

        self.chartink_profit_lock_value = QDoubleSpinBox()
        self.chartink_profit_lock_value.setRange(0, 99999)
        self.chartink_profit_lock_value.setValue(0)
        tsl_form.addRow("Lock Value:", self.chartink_profit_lock_value)

        risk_main.addLayout(tsl_form)

        # Right - Scanner MTM
        mtm_form = QFormLayout()
        mtm_form.addRow(QLabel("<b>Scanner MTM Limits:</b>"))

        self.chartink_mtm_profit = QDoubleSpinBox()
        self.chartink_mtm_profit.setRange(0, 9999999)
        self.chartink_mtm_profit.setDecimals(0)
        self.chartink_mtm_profit.setPrefix("₹ ")
        self.chartink_mtm_profit.setSpecialValueText("No Limit")
        mtm_form.addRow("MTM Profit Target:", self.chartink_mtm_profit)

        self.chartink_mtm_loss = QDoubleSpinBox()
        self.chartink_mtm_loss.setRange(0, 9999999)
        self.chartink_mtm_loss.setDecimals(0)
        self.chartink_mtm_loss.setPrefix("₹ ")
        self.chartink_mtm_loss.setSpecialValueText("No Limit")
        mtm_form.addRow("MTM Loss Limit:", self.chartink_mtm_loss)

        mtm_form.addRow(QLabel("(Scanner stops when MTM limit hit)"))

        risk_main.addLayout(mtm_form)

        layout.addWidget(risk_group)

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
        """Create advanced backtesting simulator tab"""
        backtest = QWidget()
        layout = QVBoxLayout(backtest)

        # Top section - Config and Controls in horizontal layout
        top_layout = QHBoxLayout()

        # Left - Configuration
        config_group = QGroupBox("Backtest Configuration")
        config_layout = QFormLayout(config_group)

        self.bt_strategy_combo = QComboBox()
        config_layout.addRow("Strategy:", self.bt_strategy_combo)

        # Symbol with preset options
        symbol_layout = QHBoxLayout()
        self.bt_symbol = QComboBox()
        self.bt_symbol.setEditable(True)
        self.bt_symbol.addItems(["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "HDFCBANK",
                                  "INFY", "ICICIBANK", "SBIN", "TATASTEEL", "WIPRO"])
        symbol_layout.addWidget(self.bt_symbol)
        config_layout.addRow("Symbol:", symbol_layout)

        # Date range
        self.bt_days = QSpinBox()
        self.bt_days.setRange(30, 1000)
        self.bt_days.setValue(365)
        self.bt_days.setSuffix(" days")
        config_layout.addRow("History:", self.bt_days)

        # Interval
        self.bt_interval = QComboBox()
        self.bt_interval.addItems(["1d (Daily)", "1h (Hourly)", "15m (15 min)", "5m (5 min)"])
        config_layout.addRow("Interval:", self.bt_interval)

        self.bt_capital = QDoubleSpinBox()
        self.bt_capital.setRange(10000, 10000000)
        self.bt_capital.setValue(100000)
        self.bt_capital.setPrefix("₹ ")
        self.bt_capital.setDecimals(0)
        config_layout.addRow("Initial Capital:", self.bt_capital)

        top_layout.addWidget(config_group)

        # Middle - Risk Settings
        risk_group = QGroupBox("Risk Settings")
        risk_layout = QFormLayout(risk_group)

        self.bt_sl = QDoubleSpinBox()
        self.bt_sl.setRange(0, 50)
        self.bt_sl.setValue(2)
        self.bt_sl.setSuffix(" %")
        self.bt_sl.setSpecialValueText("No SL")
        risk_layout.addRow("Stop Loss:", self.bt_sl)

        self.bt_target = QDoubleSpinBox()
        self.bt_target.setRange(0, 100)
        self.bt_target.setValue(4)
        self.bt_target.setSuffix(" %")
        self.bt_target.setSpecialValueText("No Target")
        risk_layout.addRow("Target:", self.bt_target)

        self.bt_tsl = QDoubleSpinBox()
        self.bt_tsl.setRange(0, 50)
        self.bt_tsl.setValue(0)
        self.bt_tsl.setSuffix(" %")
        self.bt_tsl.setSpecialValueText("No TSL")
        risk_layout.addRow("Trailing SL:", self.bt_tsl)

        top_layout.addWidget(risk_group)

        # Right - Controls
        control_group = QGroupBox("Simulation Controls")
        control_layout = QVBoxLayout(control_group)

        self.run_backtest_btn = QPushButton("▶ Start Backtest")
        self.run_backtest_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.run_backtest_btn.clicked.connect(self._run_advanced_backtest)
        control_layout.addWidget(self.run_backtest_btn)

        self.bt_realtime_mode = QCheckBox("Real-time Mode (Slow)")
        control_layout.addWidget(self.bt_realtime_mode)

        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self.bt_speed = QComboBox()
        self.bt_speed.addItems(["1x", "2x", "5x", "10x"])
        self.bt_speed.setCurrentIndex(1)
        speed_layout.addWidget(self.bt_speed)
        control_layout.addLayout(speed_layout)

        self.bt_progress = QLabel("Ready")
        self.bt_progress.setStyleSheet("font-weight: bold;")
        control_layout.addWidget(self.bt_progress)

        self.export_trades_btn = QPushButton("Export Trades CSV")
        self.export_trades_btn.clicked.connect(self._export_backtest_trades)
        self.export_trades_btn.setEnabled(False)
        control_layout.addWidget(self.export_trades_btn)

        control_layout.addStretch()
        top_layout.addWidget(control_group)

        layout.addLayout(top_layout)

        # Middle - Results Summary
        summary_group = QGroupBox("Results Summary")
        summary_layout = QHBoxLayout(summary_group)

        # Stats in a horizontal row
        self.bt_stat_pnl = QLabel("P&L: --")
        self.bt_stat_pnl.setStyleSheet("font-size: 14px; font-weight: bold;")
        summary_layout.addWidget(self.bt_stat_pnl)

        self.bt_stat_trades = QLabel("Trades: --")
        summary_layout.addWidget(self.bt_stat_trades)

        self.bt_stat_winrate = QLabel("Win Rate: --")
        summary_layout.addWidget(self.bt_stat_winrate)

        self.bt_stat_pf = QLabel("Profit Factor: --")
        summary_layout.addWidget(self.bt_stat_pf)

        self.bt_stat_dd = QLabel("Max Drawdown: --")
        summary_layout.addWidget(self.bt_stat_dd)

        layout.addWidget(summary_group)

        # Bottom - Trade Log Table
        trades_group = QGroupBox("Trade Log (Step-by-Step)")
        trades_layout = QVBoxLayout(trades_group)

        self.bt_trades_table = QTableWidget()
        self.bt_trades_table.setColumnCount(10)
        self.bt_trades_table.setHorizontalHeaderLabels([
            "ID", "Type", "Entry Time", "Entry Price", "Exit Time",
            "Exit Price", "Qty", "P&L", "P&L %", "Exit Reason"
        ])
        self.bt_trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        trades_layout.addWidget(self.bt_trades_table)

        layout.addWidget(trades_group)

        self.tabs.addTab(backtest, "Backtest")

    def _create_journal_tab(self):
        """Create Trade Journal / Performance Analytics tab"""
        journal = QWidget()
        layout = QVBoxLayout(journal)

        # === Filter Controls ===
        filter_group = QGroupBox("Filter & Export")
        filter_layout = QHBoxLayout(filter_group)

        filter_layout.addWidget(QLabel("Date Range:"))
        self.journal_date_from = QComboBox()
        self.journal_date_from.addItems(["Today", "This Week", "This Month", "Last 30 Days", "Last 90 Days", "This Year", "All Time"])
        self.journal_date_from.setCurrentIndex(3)  # Last 30 Days
        self.journal_date_from.currentIndexChanged.connect(self._refresh_journal)
        filter_layout.addWidget(self.journal_date_from)

        filter_layout.addWidget(QLabel("Symbol:"))
        self.journal_symbol_filter = QComboBox()
        self.journal_symbol_filter.addItem("All Symbols")
        self.journal_symbol_filter.currentIndexChanged.connect(self._refresh_journal)
        filter_layout.addWidget(self.journal_symbol_filter)

        filter_layout.addWidget(QLabel("Side:"))
        self.journal_side_filter = QComboBox()
        self.journal_side_filter.addItems(["All", "BUY Only", "SELL Only"])
        self.journal_side_filter.currentIndexChanged.connect(self._refresh_journal)
        filter_layout.addWidget(self.journal_side_filter)

        filter_layout.addStretch()

        # Export buttons
        self.export_excel_btn = QPushButton("📊 Export to Excel")
        self.export_excel_btn.setStyleSheet("background-color: #217346; color: white; font-weight: bold; padding: 8px;")
        self.export_excel_btn.clicked.connect(self._export_trades_excel)
        filter_layout.addWidget(self.export_excel_btn)

        self.export_csv_btn = QPushButton("📄 Export CSV")
        self.export_csv_btn.clicked.connect(self._export_trades_csv)
        filter_layout.addWidget(self.export_csv_btn)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._refresh_journal)
        filter_layout.addWidget(refresh_btn)

        layout.addWidget(filter_group)

        # === Performance Summary Cards ===
        perf_group = QGroupBox("Performance Summary")
        perf_layout = QHBoxLayout(perf_group)

        # Total P&L Card
        pnl_card = QGroupBox("Total P&L")
        pnl_layout = QVBoxLayout(pnl_card)
        self.journal_total_pnl = QLabel("₹0")
        self.journal_total_pnl.setStyleSheet("font-size: 20px; font-weight: bold; color: #4CAF50;")
        self.journal_total_pnl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pnl_layout.addWidget(self.journal_total_pnl)
        perf_layout.addWidget(pnl_card)

        # Total Trades Card
        trades_card = QGroupBox("Total Trades")
        trades_layout = QVBoxLayout(trades_card)
        self.journal_total_trades = QLabel("0")
        self.journal_total_trades.setStyleSheet("font-size: 20px; font-weight: bold; color: #2196F3;")
        self.journal_total_trades.setAlignment(Qt.AlignmentFlag.AlignCenter)
        trades_layout.addWidget(self.journal_total_trades)
        perf_layout.addWidget(trades_card)

        # Win Rate Card
        win_card = QGroupBox("Win Rate")
        win_layout = QVBoxLayout(win_card)
        self.journal_win_rate = QLabel("0%")
        self.journal_win_rate.setStyleSheet("font-size: 20px; font-weight: bold; color: #9C27B0;")
        self.journal_win_rate.setAlignment(Qt.AlignmentFlag.AlignCenter)
        win_layout.addWidget(self.journal_win_rate)
        perf_layout.addWidget(win_card)

        # Profit Factor Card
        pf_card = QGroupBox("Profit Factor")
        pf_layout = QVBoxLayout(pf_card)
        self.journal_profit_factor = QLabel("0")
        self.journal_profit_factor.setStyleSheet("font-size: 20px; font-weight: bold; color: #FF9800;")
        self.journal_profit_factor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pf_layout.addWidget(self.journal_profit_factor)
        perf_layout.addWidget(pf_card)

        # Avg Win/Loss Card
        avg_card = QGroupBox("Avg Win / Avg Loss")
        avg_layout = QVBoxLayout(avg_card)
        self.journal_avg_win_loss = QLabel("₹0 / ₹0")
        self.journal_avg_win_loss.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.journal_avg_win_loss.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avg_layout.addWidget(self.journal_avg_win_loss)
        perf_layout.addWidget(avg_card)

        # Max Drawdown Card
        dd_card = QGroupBox("Max Drawdown")
        dd_layout = QVBoxLayout(dd_card)
        self.journal_max_dd = QLabel("₹0")
        self.journal_max_dd.setStyleSheet("font-size: 20px; font-weight: bold; color: #F44336;")
        self.journal_max_dd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dd_layout.addWidget(self.journal_max_dd)
        perf_layout.addWidget(dd_card)

        layout.addWidget(perf_group)

        # === Detailed Statistics ===
        stats_group = QGroupBox("Detailed Statistics")
        stats_layout = QHBoxLayout(stats_group)

        # Left stats
        left_stats = QFormLayout()
        self.journal_winning_trades = QLabel("0")
        self.journal_losing_trades = QLabel("0")
        self.journal_largest_win = QLabel("₹0")
        self.journal_largest_loss = QLabel("₹0")
        left_stats.addRow("Winning Trades:", self.journal_winning_trades)
        left_stats.addRow("Losing Trades:", self.journal_losing_trades)
        left_stats.addRow("Largest Win:", self.journal_largest_win)
        left_stats.addRow("Largest Loss:", self.journal_largest_loss)
        stats_layout.addLayout(left_stats)

        # Middle stats
        mid_stats = QFormLayout()
        self.journal_avg_trade = QLabel("₹0")
        self.journal_avg_hold_time = QLabel("0 min")
        self.journal_total_volume = QLabel("0")
        self.journal_total_brokerage = QLabel("₹0")
        mid_stats.addRow("Average Trade:", self.journal_avg_trade)
        mid_stats.addRow("Avg Hold Time:", self.journal_avg_hold_time)
        mid_stats.addRow("Total Volume:", self.journal_total_volume)
        mid_stats.addRow("Est. Brokerage:", self.journal_total_brokerage)
        stats_layout.addLayout(mid_stats)

        # Right stats - Per symbol breakdown
        right_stats = QFormLayout()
        self.journal_best_symbol = QLabel("--")
        self.journal_worst_symbol = QLabel("--")
        self.journal_most_traded = QLabel("--")
        self.journal_consecutive_wins = QLabel("0")
        right_stats.addRow("Best Symbol:", self.journal_best_symbol)
        right_stats.addRow("Worst Symbol:", self.journal_worst_symbol)
        right_stats.addRow("Most Traded:", self.journal_most_traded)
        right_stats.addRow("Max Consecutive Wins:", self.journal_consecutive_wins)
        stats_layout.addLayout(right_stats)

        layout.addWidget(stats_group)

        # === Trade History Table ===
        history_group = QGroupBox("Trade History")
        history_layout = QVBoxLayout(history_group)

        self.journal_trades_table = QTableWidget()
        self.journal_trades_table.setColumnCount(12)
        self.journal_trades_table.setHorizontalHeaderLabels([
            "Date", "Time", "Symbol", "Side", "Qty", "Entry Price",
            "Exit Price", "P&L", "P&L %", "Source", "Strategy", "Notes"
        ])
        self.journal_trades_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.journal_trades_table.setAlternatingRowColors(True)
        self.journal_trades_table.setSortingEnabled(True)
        history_layout.addWidget(self.journal_trades_table)

        layout.addWidget(history_group)

        self.tabs.addTab(journal, "Journal")

        # Initial load
        QTimer.singleShot(100, self._refresh_journal)

    def _refresh_journal(self):
        """Refresh trade journal with filtered data"""
        try:
            from datetime import datetime, timedelta
            from collections import defaultdict

            # Get date range
            date_filter = self.journal_date_from.currentText()
            now = datetime.now()

            if date_filter == "Today":
                start_date = now.replace(hour=0, minute=0, second=0)
            elif date_filter == "This Week":
                start_date = now - timedelta(days=now.weekday())
                start_date = start_date.replace(hour=0, minute=0, second=0)
            elif date_filter == "This Month":
                start_date = now.replace(day=1, hour=0, minute=0, second=0)
            elif date_filter == "Last 30 Days":
                start_date = now - timedelta(days=30)
            elif date_filter == "Last 90 Days":
                start_date = now - timedelta(days=90)
            elif date_filter == "This Year":
                start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0)
            else:  # All Time
                start_date = datetime(2000, 1, 1)

            # Get all orders from database
            all_orders = self.db.get_orders()

            # Filter orders
            filtered_orders = []
            symbols_set = set()

            for order in all_orders:
                # Parse order date
                order_date_str = order.get('created_at', '')
                try:
                    if isinstance(order_date_str, str):
                        order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00').replace('+00:00', ''))
                    else:
                        order_date = order_date_str
                except:
                    continue

                if order_date < start_date:
                    continue

                symbol = order.get('symbol', '')
                symbols_set.add(symbol)

                # Symbol filter
                symbol_filter = self.journal_symbol_filter.currentText()
                if symbol_filter != "All Symbols" and symbol != symbol_filter:
                    continue

                # Side filter
                side_filter = self.journal_side_filter.currentText()
                side = order.get('transaction_type', order.get('side', ''))
                if side_filter == "BUY Only" and side != "BUY":
                    continue
                if side_filter == "SELL Only" and side != "SELL":
                    continue

                filtered_orders.append(order)

            # Update symbol filter dropdown
            current_symbol = self.journal_symbol_filter.currentText()
            self.journal_symbol_filter.blockSignals(True)
            self.journal_symbol_filter.clear()
            self.journal_symbol_filter.addItem("All Symbols")
            for sym in sorted(symbols_set):
                if sym:
                    self.journal_symbol_filter.addItem(sym)
            idx = self.journal_symbol_filter.findText(current_symbol)
            if idx >= 0:
                self.journal_symbol_filter.setCurrentIndex(idx)
            self.journal_symbol_filter.blockSignals(False)

            # Calculate statistics
            self._calculate_journal_stats(filtered_orders)

            # Populate table
            self._populate_journal_table(filtered_orders)

        except Exception as e:
            logger.error(f"Error refreshing journal: {e}")

    def _calculate_journal_stats(self, orders: list):
        """Calculate performance statistics from orders"""
        from collections import defaultdict

        if not orders:
            self.journal_total_pnl.setText("₹0")
            self.journal_total_trades.setText("0")
            self.journal_win_rate.setText("0%")
            self.journal_profit_factor.setText("0")
            self.journal_avg_win_loss.setText("₹0 / ₹0")
            self.journal_max_dd.setText("₹0")
            return

        # Extract P&L from orders
        pnls = []
        symbol_pnl = defaultdict(float)
        symbol_count = defaultdict(int)
        total_volume = 0

        for order in orders:
            pnl = float(order.get('pnl', 0))
            qty = int(order.get('quantity', 0))
            symbol = order.get('symbol', '')

            if order.get('status') == 'COMPLETE':
                pnls.append(pnl)
                symbol_pnl[symbol] += pnl
                symbol_count[symbol] += 1
                total_volume += qty

        if not pnls:
            return

        total_pnl = sum(pnls)
        total_trades = len(pnls)
        winning_trades = [p for p in pnls if p > 0]
        losing_trades = [p for p in pnls if p < 0]

        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

        total_wins = sum(winning_trades) if winning_trades else 0
        total_losses = abs(sum(losing_trades)) if losing_trades else 0
        profit_factor = (total_wins / total_losses) if total_losses > 0 else total_wins

        avg_win = (total_wins / win_count) if win_count > 0 else 0
        avg_loss = (total_losses / loss_count) if loss_count > 0 else 0

        # Calculate max drawdown
        cumulative = 0
        peak = 0
        max_dd = 0
        for pnl in pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        # Consecutive wins
        max_consecutive = 0
        current_consecutive = 0
        for pnl in pnls:
            if pnl > 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        # Best/worst symbols
        best_symbol = max(symbol_pnl.items(), key=lambda x: x[1]) if symbol_pnl else ("--", 0)
        worst_symbol = min(symbol_pnl.items(), key=lambda x: x[1]) if symbol_pnl else ("--", 0)
        most_traded = max(symbol_count.items(), key=lambda x: x[1]) if symbol_count else ("--", 0)

        # Update UI
        self.journal_total_pnl.setText(f"₹{total_pnl:+,.2f}")
        color = "#4CAF50" if total_pnl >= 0 else "#F44336"
        self.journal_total_pnl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color};")

        self.journal_total_trades.setText(str(total_trades))
        self.journal_win_rate.setText(f"{win_rate:.1f}%")
        self.journal_profit_factor.setText(f"{profit_factor:.2f}")
        self.journal_avg_win_loss.setText(f"₹{avg_win:,.0f} / ₹{avg_loss:,.0f}")
        self.journal_max_dd.setText(f"₹{max_dd:,.2f}")

        self.journal_winning_trades.setText(str(win_count))
        self.journal_losing_trades.setText(str(loss_count))
        self.journal_largest_win.setText(f"₹{max(winning_trades):,.2f}" if winning_trades else "₹0")
        self.journal_largest_loss.setText(f"₹{min(losing_trades):,.2f}" if losing_trades else "₹0")

        avg_trade = total_pnl / total_trades if total_trades > 0 else 0
        self.journal_avg_trade.setText(f"₹{avg_trade:,.2f}")
        self.journal_avg_hold_time.setText("--")  # Would need entry/exit times
        self.journal_total_volume.setText(f"{total_volume:,}")
        self.journal_total_brokerage.setText(f"₹{total_volume * 20 / 100000:,.2f}")  # Rough estimate

        self.journal_best_symbol.setText(f"{best_symbol[0]} (₹{best_symbol[1]:+,.0f})")
        self.journal_worst_symbol.setText(f"{worst_symbol[0]} (₹{worst_symbol[1]:+,.0f})")
        self.journal_most_traded.setText(f"{most_traded[0]} ({most_traded[1]} trades)")
        self.journal_consecutive_wins.setText(str(max_consecutive))

    def _populate_journal_table(self, orders: list):
        """Populate the journal trades table"""
        self.journal_trades_table.setRowCount(len(orders))

        for i, order in enumerate(orders):
            date_str = order.get('created_at', '')[:10]
            time_str = order.get('created_at', '')[11:19] if len(order.get('created_at', '')) > 11 else ''
            symbol = order.get('symbol', '')
            side = order.get('transaction_type', order.get('side', ''))
            qty = order.get('quantity', 0)
            entry_price = float(order.get('price', 0))
            exit_price = float(order.get('exit_price', entry_price))
            pnl = float(order.get('pnl', 0))
            pnl_pct = (pnl / (entry_price * qty) * 100) if entry_price and qty else 0
            source = order.get('source', 'Manual')
            strategy = order.get('strategy', '')
            notes = order.get('notes', '')

            self.journal_trades_table.setItem(i, 0, QTableWidgetItem(date_str))
            self.journal_trades_table.setItem(i, 1, QTableWidgetItem(time_str))
            self.journal_trades_table.setItem(i, 2, QTableWidgetItem(symbol))

            side_item = QTableWidgetItem(side)
            side_item.setForeground(Qt.GlobalColor.green if side == "BUY" else Qt.GlobalColor.red)
            self.journal_trades_table.setItem(i, 3, side_item)

            self.journal_trades_table.setItem(i, 4, QTableWidgetItem(str(qty)))
            self.journal_trades_table.setItem(i, 5, QTableWidgetItem(f"₹{entry_price:.2f}"))
            self.journal_trades_table.setItem(i, 6, QTableWidgetItem(f"₹{exit_price:.2f}"))

            pnl_item = QTableWidgetItem(f"₹{pnl:+,.2f}")
            pnl_item.setForeground(Qt.GlobalColor.green if pnl >= 0 else Qt.GlobalColor.red)
            self.journal_trades_table.setItem(i, 7, pnl_item)

            self.journal_trades_table.setItem(i, 8, QTableWidgetItem(f"{pnl_pct:+.2f}%"))
            self.journal_trades_table.setItem(i, 9, QTableWidgetItem(source))
            self.journal_trades_table.setItem(i, 10, QTableWidgetItem(strategy))
            self.journal_trades_table.setItem(i, 11, QTableWidgetItem(notes))

    def _export_trades_excel(self):
        """Export trade history to Excel with formatting"""
        try:
            from datetime import datetime
            import os

            # Check if openpyxl is available
            try:
                from openpyxl import Workbook
                from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
                from openpyxl.utils import get_column_letter
            except ImportError:
                QMessageBox.warning(
                    self, "Missing Package",
                    "Excel export requires 'openpyxl' package.\n\nInstall with: pip install openpyxl"
                )
                return

            # Get data from table
            rows = self.journal_trades_table.rowCount()
            if rows == 0:
                QMessageBox.information(self, "No Data", "No trades to export")
                return

            # Create workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Trade History"

            # Header style
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center")

            # Headers
            headers = ["Date", "Time", "Symbol", "Side", "Qty", "Entry Price",
                       "Exit Price", "P&L", "P&L %", "Source", "Strategy", "Notes"]

            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment

            # Data
            green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
            red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

            for row in range(rows):
                for col in range(12):
                    item = self.journal_trades_table.item(row, col)
                    value = item.text() if item else ""

                    # Clean currency symbols for numeric columns
                    if col in [5, 6, 7]:  # Price and P&L columns
                        value = value.replace("₹", "").replace(",", "").replace("+", "")
                        try:
                            value = float(value)
                        except:
                            pass
                    elif col == 8:  # P&L % column
                        value = value.replace("%", "").replace("+", "")
                        try:
                            value = float(value)
                        except:
                            pass

                    cell = ws.cell(row=row + 2, column=col + 1, value=value)

                    # Color P&L cells
                    if col == 7:  # P&L column
                        try:
                            if float(value) >= 0:
                                cell.fill = green_fill
                            else:
                                cell.fill = red_fill
                        except:
                            pass

            # Adjust column widths
            for col in range(1, 13):
                ws.column_dimensions[get_column_letter(col)].width = 15

            # Add summary sheet
            ws_summary = wb.create_sheet("Summary")
            ws_summary.cell(row=1, column=1, value="Performance Summary").font = Font(bold=True, size=14)

            summary_data = [
                ("Total P&L", self.journal_total_pnl.text()),
                ("Total Trades", self.journal_total_trades.text()),
                ("Win Rate", self.journal_win_rate.text()),
                ("Profit Factor", self.journal_profit_factor.text()),
                ("Winning Trades", self.journal_winning_trades.text()),
                ("Losing Trades", self.journal_losing_trades.text()),
                ("Largest Win", self.journal_largest_win.text()),
                ("Largest Loss", self.journal_largest_loss.text()),
                ("Max Drawdown", self.journal_max_dd.text()),
                ("Best Symbol", self.journal_best_symbol.text()),
                ("Worst Symbol", self.journal_worst_symbol.text()),
            ]

            for row, (label, value) in enumerate(summary_data, 3):
                ws_summary.cell(row=row, column=1, value=label).font = Font(bold=True)
                ws_summary.cell(row=row, column=2, value=value)

            ws_summary.column_dimensions['A'].width = 20
            ws_summary.column_dimensions['B'].width = 25

            # Save file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"trade_history_{timestamp}.xlsx"
            filepath = os.path.join(os.path.expanduser("~"), "Documents", filename)

            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            wb.save(filepath)

            QMessageBox.information(
                self, "Export Complete",
                f"Trade history exported to:\n{filepath}"
            )

        except Exception as e:
            logger.error(f"Excel export error: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")

    def _export_trades_csv(self):
        """Export trade history to CSV"""
        try:
            from datetime import datetime
            import csv
            import os

            rows = self.journal_trades_table.rowCount()
            if rows == 0:
                QMessageBox.information(self, "No Data", "No trades to export")
                return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"trade_history_{timestamp}.csv"
            filepath = os.path.join(os.path.expanduser("~"), "Documents", filename)

            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Headers
                headers = ["Date", "Time", "Symbol", "Side", "Qty", "Entry Price",
                           "Exit Price", "P&L", "P&L %", "Source", "Strategy", "Notes"]
                writer.writerow(headers)

                # Data
                for row in range(rows):
                    row_data = []
                    for col in range(12):
                        item = self.journal_trades_table.item(row, col)
                        value = item.text() if item else ""
                        # Clean currency symbols
                        value = value.replace("₹", "").replace(",", "")
                        row_data.append(value)
                    writer.writerow(row_data)

            QMessageBox.information(
                self, "Export Complete",
                f"Trade history exported to:\n{filepath}"
            )

        except Exception as e:
            logger.error(f"CSV export error: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")

    def _create_settings_tab(self):
        """Create settings tab"""
        settings = QWidget()
        layout = QVBoxLayout(settings)

        # Use scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # === Paper Trading Mode ===
        paper_group = QGroupBox("Trading Mode")
        paper_layout = QVBoxLayout(paper_group)

        mode_layout = QHBoxLayout()
        self.paper_trading_toggle = QCheckBox("Paper Trading Mode (Simulator)")
        self.paper_trading_toggle.setChecked(self.config.get('trading.paper_mode', False))
        self.paper_trading_toggle.stateChanged.connect(self._on_paper_mode_changed)
        mode_layout.addWidget(self.paper_trading_toggle)

        self.paper_mode_label = QLabel("🟢 LIVE TRADING" if not self.paper_trading_toggle.isChecked() else "📝 PAPER TRADING")
        self.paper_mode_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        mode_layout.addWidget(self.paper_mode_label)
        mode_layout.addStretch()
        paper_layout.addLayout(mode_layout)

        # Paper trading capital
        paper_capital_layout = QHBoxLayout()
        paper_capital_layout.addWidget(QLabel("Simulator Capital:"))
        self.paper_capital = QDoubleSpinBox()
        self.paper_capital.setRange(1000, 99999999)
        self.paper_capital.setDecimals(0)
        self.paper_capital.setPrefix("₹ ")
        self.paper_capital.setValue(self.config.get('trading.paper_capital', 100000))
        paper_capital_layout.addWidget(self.paper_capital)

        self.reset_paper_btn = QPushButton("Reset Simulator")
        self.reset_paper_btn.clicked.connect(self._reset_paper_trading)
        paper_capital_layout.addWidget(self.reset_paper_btn)
        paper_capital_layout.addStretch()
        paper_layout.addLayout(paper_capital_layout)

        scroll_layout.addWidget(paper_group)

        # === Telegram Alerts ===
        telegram_group = QGroupBox("Telegram Alerts")
        telegram_layout = QFormLayout(telegram_group)

        self.telegram_enabled = QCheckBox("Enable Telegram Alerts")
        self.telegram_enabled.setChecked(self.config.get('telegram.enabled', False))
        self.telegram_enabled.stateChanged.connect(self._on_telegram_toggle)
        telegram_layout.addRow(self.telegram_enabled)

        self.telegram_bot_token = QLineEdit()
        self.telegram_bot_token.setPlaceholderText("Enter Bot Token from @BotFather")
        self.telegram_bot_token.setText(self.config.get('telegram.bot_token', ''))
        self.telegram_bot_token.setEchoMode(QLineEdit.EchoMode.Password)
        telegram_layout.addRow("Bot Token:", self.telegram_bot_token)

        self.telegram_chat_id = QLineEdit()
        self.telegram_chat_id.setPlaceholderText("Enter Chat ID")
        self.telegram_chat_id.setText(self.config.get('telegram.chat_id', ''))
        telegram_layout.addRow("Chat ID:", self.telegram_chat_id)

        telegram_btn_layout = QHBoxLayout()
        self.save_telegram_btn = QPushButton("Save Telegram")
        self.save_telegram_btn.clicked.connect(self._save_telegram_settings)
        self.test_telegram_btn = QPushButton("Test Connection")
        self.test_telegram_btn.clicked.connect(self._test_telegram)
        telegram_btn_layout.addWidget(self.save_telegram_btn)
        telegram_btn_layout.addWidget(self.test_telegram_btn)
        telegram_layout.addRow(telegram_btn_layout)

        # Help text
        help_label = QLabel("How to setup:\n1. Open Telegram, search @BotFather\n2. Send /newbot, follow steps\n3. Copy Bot Token\n4. Send message to your bot, then visit:\n   https://api.telegram.org/bot<TOKEN>/getUpdates\n5. Copy chat_id from response")
        help_label.setStyleSheet("color: gray; font-size: 11px;")
        telegram_layout.addRow(help_label)

        scroll_layout.addWidget(telegram_group)

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

        scroll_layout.addWidget(broker_group)

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

        scroll_layout.addWidget(trading_group)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

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
            is_connected = broker in self.brokers
            status = "Connected" if is_connected else "Disconnected"
            status_item = QTableWidgetItem(status)
            status_item.setForeground(Qt.GlobalColor.green if is_connected else Qt.GlobalColor.red)
            self.broker_settings_table.setItem(i, 1, status_item)
            creds = self.config.get_broker_credentials(broker)
            self.broker_settings_table.setItem(i, 2, QTableWidgetItem(creds.get('user_id', 'N/A')))

            # Add Connect/Reconnect button
            if not is_connected:
                connect_btn = QPushButton("Connect")
                connect_btn.clicked.connect(lambda checked, b=broker: self._reconnect_broker(b))
                self.broker_settings_table.setCellWidget(i, 3, connect_btn)
            else:
                disconnect_btn = QPushButton("Disconnect")
                disconnect_btn.clicked.connect(lambda checked, b=broker: self._disconnect_broker(b))
                self.broker_settings_table.setCellWidget(i, 3, disconnect_btn)

    def _reconnect_broker(self, broker_name: str):
        """Reconnect to a broker using saved credentials"""
        try:
            creds = self.config.get_broker_credentials(broker_name)
            if not creds:
                QMessageBox.warning(self, "Error", f"No credentials found for {broker_name}")
                return

            api_key = creds.get('api_key', '')
            api_secret = creds.get('api_secret', '')
            user_id = creds.get('user_id', '')

            # Need to re-authenticate - show broker dialog
            QMessageBox.information(
                self, "Re-authentication Required",
                f"Broker sessions expire daily. Please re-authenticate {broker_name.title()}.\n\n"
                "Click 'Connect Broker' and follow the authentication steps."
            )
            self._show_broker_dialog()

        except Exception as e:
            logger.error(f"Error reconnecting broker: {e}")
            QMessageBox.warning(self, "Error", f"Failed to reconnect: {str(e)}")

    def _disconnect_broker(self, broker_name: str):
        """Disconnect a broker"""
        if broker_name in self.brokers:
            del self.brokers[broker_name]
            self._update_broker_settings_table()
            self._refresh_dashboard()
            logger.info(f"Broker {broker_name} disconnected")

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
        self._refresh_dashboard()
        self.status_bar.showMessage("Data refreshed", 3000)

    def _refresh_dashboard(self):
        """Refresh dashboard with live data"""
        try:
            from datetime import datetime

            # Update market status
            if hasattr(self, 'brokers') and self.brokers:
                broker = list(self.brokers.values())[0]
                is_open = broker.is_market_open() if hasattr(broker, 'is_market_open') else False
                self.dash_market_status.setText("Open" if is_open else "Closed")
                self.dash_market_status.setStyleSheet(f"color: {'green' if is_open else 'red'}; font-weight: bold;")
                self.dash_broker_status.setText("Connected")
                self.dash_broker_status.setStyleSheet("color: green;")

                # Get funds
                try:
                    funds = broker.get_funds()
                    if funds:
                        self.dash_available_margin.setText(f"₹{funds.get('available_margin', 0):,.2f}")
                        self.dash_used_margin.setText(f"₹{funds.get('used_margin', 0):,.2f}")
                        self.dash_total_balance.setText(f"₹{funds.get('total_balance', 0):,.2f}")
                except:
                    pass

                # Get positions for P&L
                try:
                    positions = broker.get_positions()
                    self._update_dashboard_positions(positions)
                except:
                    pass
            else:
                self.dash_broker_status.setText("Not Connected")
                self.dash_broker_status.setStyleSheet("color: red;")

            # Update quick stats
            if hasattr(self, 'chartink_scanner'):
                active_scans = len(self.chartink_scanner.active_scans)
                self.dash_active_scanners.setText(str(active_scans))

            # Count active strategies
            strategies = self.db.get_all_strategies()
            active_strategies = len([s for s in strategies if s.get('is_active')])
            self.dash_active_strategies.setText(str(active_strategies))

            # Update timestamp
            self.dash_last_update.setText(datetime.now().strftime("%H:%M:%S"))

            # Calculate P&L from orders
            self._update_dashboard_pnl()

        except Exception as e:
            logger.debug(f"Dashboard refresh error: {e}")

    def _update_dashboard_positions(self, positions: list):
        """Update dashboard positions table"""
        self.dash_positions_table.setRowCount(len(positions))
        self.dash_open_positions.setText(str(len(positions)))

        total_unrealized = 0
        for i, pos in enumerate(positions):
            symbol = pos.get('tradingsymbol', pos.get('symbol', ''))
            qty = pos.get('quantity', pos.get('netqty', 0))
            avg_price = float(pos.get('averageprice', pos.get('buyavgprice', 0)))
            ltp = float(pos.get('ltp', pos.get('lastprice', avg_price)))
            pnl = float(pos.get('pnl', pos.get('unrealizedpnl', 0)))
            pnl_pct = (pnl / (avg_price * abs(qty)) * 100) if avg_price and qty else 0

            total_unrealized += pnl

            self.dash_positions_table.setItem(i, 0, QTableWidgetItem(symbol))
            self.dash_positions_table.setItem(i, 1, QTableWidgetItem("LONG" if qty > 0 else "SHORT"))
            self.dash_positions_table.setItem(i, 2, QTableWidgetItem(str(abs(qty))))
            self.dash_positions_table.setItem(i, 3, QTableWidgetItem(f"₹{avg_price:.2f}"))
            self.dash_positions_table.setItem(i, 4, QTableWidgetItem(f"₹{ltp:.2f}"))

            pnl_item = QTableWidgetItem(f"₹{pnl:+,.2f}")
            pnl_item.setForeground(Qt.GlobalColor.green if pnl >= 0 else Qt.GlobalColor.red)
            self.dash_positions_table.setItem(i, 5, pnl_item)

            self.dash_positions_table.setItem(i, 6, QTableWidgetItem(f"{pnl_pct:+.2f}%"))
            self.dash_positions_table.setItem(i, 7, QTableWidgetItem(pos.get('product', '')))

            # Add close button
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(lambda checked, s=symbol, q=qty: self._close_position(s, q))
            self.dash_positions_table.setCellWidget(i, 8, close_btn)

        # Update unrealized P&L
        self.dash_unrealized_pnl.setText(f"₹{total_unrealized:+,.2f}")
        color = "#4CAF50" if total_unrealized >= 0 else "#F44336"
        self.dash_unrealized_pnl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")

    def _update_dashboard_pnl(self):
        """Update P&L summary from trade history"""
        try:
            orders = self.db.get_orders()
            today = datetime.now().date()

            today_orders = [o for o in orders if str(o.get('created_at', ''))[:10] == str(today)]

            # Calculate realized P&L (from completed trades)
            realized_pnl = sum(float(o.get('pnl', 0)) for o in today_orders if o.get('status') == 'COMPLETE')

            # Count trades
            completed_trades = [o for o in today_orders if o.get('status') == 'COMPLETE']
            winning = len([t for t in completed_trades if float(t.get('pnl', 0)) > 0])
            total = len(completed_trades)

            self.dash_realized_pnl.setText(f"₹{realized_pnl:+,.2f}")
            color = "#4CAF50" if realized_pnl >= 0 else "#F44336"
            self.dash_realized_pnl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")

            self.dash_trades_count.setText(str(total))
            win_rate = (winning / total * 100) if total > 0 else 0
            self.dash_win_rate.setText(f"{win_rate:.1f}%")

            # Total P&L
            unrealized_text = self.dash_unrealized_pnl.text().replace('₹', '').replace(',', '').replace('+', '')
            try:
                unrealized = float(unrealized_text)
            except:
                unrealized = 0

            total_pnl = realized_pnl + unrealized
            self.dash_total_pnl.setText(f"₹{total_pnl:+,.2f}")
            color = "#4CAF50" if total_pnl >= 0 else "#F44336"
            self.dash_total_pnl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")

        except Exception as e:
            logger.debug(f"P&L update error: {e}")

    def _close_position(self, symbol: str, quantity: int):
        """Close a position from dashboard"""
        reply = QMessageBox.question(
            self, "Close Position",
            f"Close position for {symbol} ({quantity} qty)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Place opposite order to close
            action = "SELL" if quantity > 0 else "BUY"
            self._quick_order(symbol, action, abs(quantity))

    def _quick_order(self, symbol: str, action: str, quantity: int):
        """Place a quick market order"""
        if not self.brokers:
            QMessageBox.warning(self, "Error", "No broker connected")
            return

        broker = list(self.brokers.values())[0]
        from algo_trader.brokers.base import BrokerOrder

        order = BrokerOrder(
            symbol=symbol,
            exchange="NSE",
            transaction_type=action,
            order_type="MARKET",
            quantity=quantity,
            product="MIS"
        )

        result = broker.place_order(order)
        if result.get('success'):
            QMessageBox.information(self, "Success", f"Order placed: {result.get('order_id')}")
            self._refresh_dashboard()
        else:
            QMessageBox.warning(self, "Error", f"Order failed: {result.get('message')}")

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
        result = dialog.exec()

        logger.info(f"Dialog result: {result}, Accepted: {QDialog.DialogCode.Accepted}")

        if result == QDialog.DialogCode.Accepted:
            broker_name = dialog.broker_combo.currentText().lower().replace(" ", "_")
            logger.info(f"Dialog accepted for broker: {broker_name}")
            logger.info(f"broker_instance exists: {dialog.broker_instance is not None}")

            # If broker was authenticated, add it to active brokers
            if dialog.broker_instance:
                logger.info(f"is_authenticated: {dialog.broker_instance.is_authenticated}")
                if dialog.broker_instance.is_authenticated:
                    self.brokers[broker_name] = dialog.broker_instance
                    logger.info(f"Broker {broker_name} added to self.brokers")
                    QMessageBox.information(self, "Connected", f"{broker_name.title()} broker connected successfully!")
                else:
                    logger.warning(f"Broker {broker_name} instance exists but not authenticated")
                    QMessageBox.warning(self, "Not Connected",
                        f"Broker was not fully authenticated.\n\nPlease try again and make sure to:\n"
                        "1. Click 'Get Login URL'\n"
                        "2. Login in browser\n"
                        "3. Copy the code from URL\n"
                        "4. Paste and click 'Authenticate'")
            else:
                logger.warning("No broker_instance after dialog closed")

            self._load_configured_brokers()
            self._update_broker_settings_table()
            self._refresh_dashboard()

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

        # Display results (old format for backward compat)
        self.bt_stat_pnl.setText(f"P&L: ₹{results['final_capital'] - results['initial_capital']:,.2f}")
        self.bt_stat_trades.setText(f"Trades: {results['total_trades']}")
        self.bt_stat_winrate.setText(f"Win Rate: {results['win_rate']:.1f}%")
        self.bt_stat_pf.setText(f"Profit Factor: {results['profit_factor']:.2f}")
        self.bt_stat_dd.setText(f"Max DD: {results['max_drawdown']:.1f}%")

    def _run_advanced_backtest(self):
        """Run advanced backtest with step-by-step simulation"""
        strategy_name = self.bt_strategy_combo.currentText()
        if not strategy_name:
            QMessageBox.warning(self, "Error", "Please select a strategy")
            return

        symbol = self.bt_symbol.currentText().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Error", "Please enter a symbol")
            return

        capital = self.bt_capital.value()
        days = self.bt_days.value()

        # Get interval
        interval_text = self.bt_interval.currentText()
        interval_map = {"1d": "1d", "1h": "1h", "15m": "15m", "5m": "5m"}
        interval = "1d"
        for key in interval_map:
            if key in interval_text:
                interval = interval_map[key]
                break

        # Risk settings
        sl_pct = self.bt_sl.value()
        target_pct = self.bt_target.value()
        tsl_pct = self.bt_tsl.value()

        self.bt_progress.setText("Fetching data...")
        self.run_backtest_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            # Load strategy
            strategy = self.db.get_strategy(strategy_name)
            if not strategy:
                QMessageBox.warning(self, "Error", "Strategy not found")
                return

            from algo_trader.strategies.pine_parser import PineScriptParser
            from algo_trader.strategies.pine_interpreter import PineScriptInterpreter
            from algo_trader.backtest.simulator import BacktestSimulator
            from algo_trader.data.historical import HistoricalDataManager

            # Parse strategy
            parser = PineScriptParser()
            parsed = parser.parse(strategy['pine_script'])
            if not parsed:
                QMessageBox.warning(self, "Error", "Failed to parse strategy")
                return

            interpreter = PineScriptInterpreter(parsed)

            # Fetch historical data
            self.bt_progress.setText("Downloading historical data...")
            QApplication.processEvents()

            data_manager = HistoricalDataManager()
            data = data_manager.get_data_for_backtest(symbol, days, interval)

            if data is None or len(data) == 0:
                QMessageBox.warning(self, "Error", "Could not fetch historical data")
                return

            self.bt_progress.setText(f"Running backtest on {len(data)} candles...")
            QApplication.processEvents()

            # Create strategy function for simulator
            interpreter.load_data(data.set_index('datetime') if 'datetime' in data.columns else data)

            def strategy_signal(row, idx, full_data):
                """Generate strategy signal for each candle"""
                try:
                    # Update interpreter with current candle
                    result = interpreter.process_candle({
                        'open': row['open'],
                        'high': row['high'],
                        'low': row['low'],
                        'close': row['close'],
                        'volume': row.get('volume', 0)
                    })
                    if result and 'signal' in result:
                        return result['signal']  # 'BUY' or 'SELL'
                except Exception:
                    pass
                return None

            # Create and configure simulator
            simulator = BacktestSimulator(initial_capital=capital)
            simulator.set_risk_params(
                stop_loss=sl_pct,
                target=target_pct,
                trailing_sl=tsl_pct
            )

            # Register progress callback
            def on_progress(idx, total, time, price, equity, open_trades):
                if idx % 50 == 0:
                    self.bt_progress.setText(f"Processing: {idx}/{total} ({time.strftime('%Y-%m-%d') if hasattr(time, 'strftime') else time})")
                    QApplication.processEvents()

            simulator.register_progress_callback(on_progress)

            # Get speed setting
            speed_text = self.bt_speed.currentText()
            speed = float(speed_text.replace('x', ''))

            # Run backtest
            realtime = self.bt_realtime_mode.isChecked()
            simulator.set_speed(speed)

            self.bt_simulator = simulator  # Store for export
            result = simulator.run_backtest(
                data=data,
                strategy_func=strategy_signal,
                symbol=symbol,
                strategy_name=strategy_name,
                realtime_mode=realtime
            )

            # Update UI with results
            self._display_backtest_results(result)

        except Exception as e:
            logger.error(f"Backtest error: {e}")
            QMessageBox.warning(self, "Error", f"Backtest failed: {str(e)}")
        finally:
            self.run_backtest_btn.setEnabled(True)
            self.bt_progress.setText("Complete")

    def _display_backtest_results(self, result):
        """Display backtest results in UI"""
        # Update summary stats
        pnl_color = "green" if result.total_pnl >= 0 else "red"
        self.bt_stat_pnl.setText(f"P&L: ₹{result.total_pnl:,.2f}")
        self.bt_stat_pnl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {pnl_color};")

        self.bt_stat_trades.setText(f"Trades: {result.total_trades}")
        self.bt_stat_winrate.setText(f"Win Rate: {result.win_rate:.1f}%")
        self.bt_stat_pf.setText(f"PF: {result.profit_factor:.2f}")
        self.bt_stat_dd.setText(f"Max DD: ₹{result.max_drawdown:,.0f} ({result.max_drawdown_percent:.1f}%)")

        # Populate trade log table
        self.bt_trades_table.setRowCount(len(result.trades))
        for i, trade in enumerate(result.trades):
            self.bt_trades_table.setItem(i, 0, QTableWidgetItem(str(trade.trade_id)))
            self.bt_trades_table.setItem(i, 1, QTableWidgetItem(trade.trade_type.value))
            self.bt_trades_table.setItem(i, 2, QTableWidgetItem(
                trade.entry_time.strftime('%Y-%m-%d %H:%M') if trade.entry_time else ''))
            self.bt_trades_table.setItem(i, 3, QTableWidgetItem(f"₹{trade.entry_price:.2f}"))
            self.bt_trades_table.setItem(i, 4, QTableWidgetItem(
                trade.exit_time.strftime('%Y-%m-%d %H:%M') if trade.exit_time else ''))
            self.bt_trades_table.setItem(i, 5, QTableWidgetItem(f"₹{trade.exit_price:.2f}"))
            self.bt_trades_table.setItem(i, 6, QTableWidgetItem(str(trade.quantity)))

            pnl_item = QTableWidgetItem(f"₹{trade.pnl:,.2f}")
            pnl_item.setForeground(Qt.GlobalColor.green if trade.pnl >= 0 else Qt.GlobalColor.red)
            self.bt_trades_table.setItem(i, 7, pnl_item)

            self.bt_trades_table.setItem(i, 8, QTableWidgetItem(f"{trade.pnl_percent:.2f}%"))
            self.bt_trades_table.setItem(i, 9, QTableWidgetItem(trade.exit_reason))

        self.export_trades_btn.setEnabled(True)
        logger.info(f"Backtest complete: {result.total_trades} trades, P&L: ₹{result.total_pnl:.2f}")

    def _export_backtest_trades(self):
        """Export backtest trades to CSV"""
        if not hasattr(self, 'bt_simulator') or not self.bt_simulator:
            QMessageBox.warning(self, "Error", "No backtest results to export")
            return

        from datetime import datetime
        filename = f"backtest_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        try:
            self.bt_simulator.export_trades_csv(filename)
            QMessageBox.information(self, "Exported", f"Trades exported to: {filename}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Export failed: {e}")

    def _save_settings(self):
        """Save trading settings"""
        self.config.set('trading.default_quantity', self.default_qty.value())
        self.config.set('trading.max_positions', self.max_positions.value())
        self.config.set('trading.risk_percent', self.risk_percent.value())
        self.config.set('trading.paper_capital', self.paper_capital.value())
        QMessageBox.information(self, "Success", "Settings saved")

    # Paper Trading methods
    def _init_paper_trading(self):
        """Initialize paper trading simulator"""
        from algo_trader.core.paper_trading import PaperTradingSimulator
        capital = self.config.get('trading.paper_capital', 100000)
        self.paper_simulator = PaperTradingSimulator(initial_capital=capital)
        logger.info(f"Paper Trading Simulator initialized with ₹{capital:,.2f}")

    def _on_paper_mode_changed(self, state):
        """Handle paper trading mode toggle"""
        is_paper = state == Qt.CheckState.Checked.value
        self.config.set('trading.paper_mode', is_paper)

        if is_paper:
            self.paper_mode_label.setText("📝 PAPER TRADING")
            self.paper_mode_label.setStyleSheet("font-weight: bold; font-size: 14px; color: orange;")
            self._init_paper_trading()
            QMessageBox.information(self, "Paper Trading",
                "Paper Trading Mode enabled!\n\nAll trades will be simulated - no real money will be used.")
        else:
            self.paper_mode_label.setText("🟢 LIVE TRADING")
            self.paper_mode_label.setStyleSheet("font-weight: bold; font-size: 14px; color: green;")
            QMessageBox.warning(self, "Live Trading",
                "Live Trading Mode enabled!\n\nReal orders will be placed with your broker.")

    def _reset_paper_trading(self):
        """Reset paper trading simulator"""
        if hasattr(self, 'paper_simulator'):
            capital = self.paper_capital.value()
            self.paper_simulator.reset(capital)
            QMessageBox.information(self, "Reset", f"Simulator reset with ₹{capital:,.0f}")
        else:
            self._init_paper_trading()
            QMessageBox.information(self, "Initialized", "Paper Trading Simulator initialized")

    def is_paper_mode(self) -> bool:
        """Check if paper trading mode is enabled"""
        return self.paper_trading_toggle.isChecked()

    # Telegram Alert methods
    def _init_telegram(self):
        """Initialize Telegram alerts"""
        from algo_trader.integrations.telegram_alerts import TelegramAlerts
        self.telegram = TelegramAlerts()
        bot_token = self.config.get('telegram.bot_token', '')
        chat_id = self.config.get('telegram.chat_id', '')
        if bot_token and chat_id:
            self.telegram.configure(bot_token, chat_id)
            if self.config.get('telegram.enabled', False):
                self.telegram.enable()

    def _on_telegram_toggle(self, state):
        """Handle Telegram enable/disable"""
        enabled = state == Qt.CheckState.Checked.value
        if enabled:
            if not hasattr(self, 'telegram'):
                self._init_telegram()
            if self.telegram.is_configured():
                self.telegram.enable()
                self.config.set('telegram.enabled', True)
            else:
                QMessageBox.warning(self, "Error", "Please enter Bot Token and Chat ID first")
                self.telegram_enabled.setChecked(False)
        else:
            if hasattr(self, 'telegram'):
                self.telegram.disable()
            self.config.set('telegram.enabled', False)

    def _save_telegram_settings(self):
        """Save Telegram configuration"""
        bot_token = self.telegram_bot_token.text().strip()
        chat_id = self.telegram_chat_id.text().strip()

        self.config.set('telegram.bot_token', bot_token)
        self.config.set('telegram.chat_id', chat_id)

        if not hasattr(self, 'telegram'):
            self._init_telegram()

        if bot_token and chat_id:
            self.telegram.configure(bot_token, chat_id)
            QMessageBox.information(self, "Saved", "Telegram settings saved!")
        else:
            QMessageBox.warning(self, "Warning", "Please enter both Bot Token and Chat ID")

    def _test_telegram(self):
        """Test Telegram connection"""
        if not hasattr(self, 'telegram'):
            self._init_telegram()

        bot_token = self.telegram_bot_token.text().strip()
        chat_id = self.telegram_chat_id.text().strip()

        if not bot_token or not chat_id:
            QMessageBox.warning(self, "Error", "Please enter Bot Token and Chat ID")
            return

        self.telegram.configure(bot_token, chat_id)
        if self.telegram.test_connection():
            QMessageBox.information(self, "Success", "Telegram connection successful! Check your Telegram.")
        else:
            QMessageBox.warning(self, "Failed", "Could not connect to Telegram. Check your credentials.")

    def _send_telegram_alert(self, message_type: str, **kwargs):
        """Send alert to Telegram if enabled"""
        if not hasattr(self, 'telegram') or not self.telegram.enabled:
            return

        try:
            if message_type == 'trade':
                self.telegram.send_trade_alert(**kwargs)
            elif message_type == 'signal':
                self.telegram.send_signal_alert(**kwargs)
            elif message_type == 'chartink':
                self.telegram.send_chartink_alert(**kwargs)
            elif message_type == 'option':
                self.telegram.send_option_alert(**kwargs)
            elif message_type == 'sl_hit':
                self.telegram.send_sl_hit_alert(**kwargs)
            elif message_type == 'target_hit':
                self.telegram.send_target_hit_alert(**kwargs)
        except Exception as e:
            logger.error(f"Telegram alert error: {e}")

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
                    max_trades=scan.get('max_trades', 0),
                    risk_config=scan.get('risk_config', None)
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

    def _on_chartink_sl_type_changed(self, index):
        """Handle SL type change"""
        self.chartink_sl_value.setEnabled(index > 0)
        if index == 1:  # Points
            self.chartink_sl_value.setSuffix(" pts")
            self.chartink_sl_value.setPrefix("")
        elif index == 2:  # Percentage
            self.chartink_sl_value.setSuffix(" %")
            self.chartink_sl_value.setPrefix("")
        elif index == 3:  # Amount
            self.chartink_sl_value.setSuffix("")
            self.chartink_sl_value.setPrefix("₹ ")

    def _on_chartink_target_type_changed(self, index):
        """Handle Target type change"""
        self.chartink_target_value.setEnabled(index > 0)
        if index == 1:  # Points
            self.chartink_target_value.setSuffix(" pts")
            self.chartink_target_value.setPrefix("")
        elif index == 2:  # Percentage
            self.chartink_target_value.setSuffix(" %")
            self.chartink_target_value.setPrefix("")
        elif index == 3:  # Amount
            self.chartink_target_value.setSuffix("")
            self.chartink_target_value.setPrefix("₹ ")

    def _on_chartink_tsl_toggle(self, state):
        """Handle TSL enable/disable"""
        enabled = state == Qt.CheckState.Checked.value
        self.chartink_tsl_type.setEnabled(enabled)
        self.chartink_tsl_value.setEnabled(enabled)

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

        # Get risk settings
        sl_type_index = self.chartink_sl_type.currentIndex()
        sl_type = ["none", "points", "percent", "amount"][sl_type_index]
        sl_value = self.chartink_sl_value.value()

        target_type_index = self.chartink_target_type.currentIndex()
        target_type = ["none", "points", "percent", "amount"][target_type_index]
        target_value = self.chartink_target_value.value()

        tsl_enabled = self.chartink_tsl_enabled.isChecked()
        tsl_type = "points" if self.chartink_tsl_type.currentIndex() == 0 else "percent"
        tsl_value = self.chartink_tsl_value.value()

        profit_lock_enabled = self.chartink_profit_lock_enabled.isChecked()
        profit_lock_type = "points" if self.chartink_profit_lock_type.currentIndex() == 0 else "amount"
        profit_lock_value = self.chartink_profit_lock_value.value()

        mtm_profit = self.chartink_mtm_profit.value()
        mtm_loss = self.chartink_mtm_loss.value()

        # Risk config dict
        risk_config = {
            'sl_type': sl_type,
            'sl_value': sl_value,
            'target_type': target_type,
            'target_value': target_value,
            'tsl_enabled': tsl_enabled,
            'tsl_type': tsl_type,
            'tsl_value': tsl_value,
            'profit_lock_enabled': profit_lock_enabled,
            'profit_lock_type': profit_lock_type,
            'profit_lock_value': profit_lock_value,
            'mtm_profit': mtm_profit,
            'mtm_loss': mtm_loss
        }

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
            max_trades=max_trades,
            risk_config=risk_config
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
            'max_trades': max_trades,
            'risk_config': risk_config
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
