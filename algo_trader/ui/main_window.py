"""
Main Application Window
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QPushButton,
    QLabel, QComboBox, QLineEdit, QTextEdit, QSplitter,
    QMessageBox, QStatusBar, QToolBar, QGroupBox, QFormLayout,
    QHeaderView, QDialog, QSpinBox, QDoubleSpinBox, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont

from algo_trader.core.config import Config
from algo_trader.core.database import Database
from algo_trader.core.order_manager import OrderManager
from algo_trader.core.strategy_engine import StrategyEngine
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
        self.setMinimumSize(1200, 800)

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
        self._create_backtest_tab()
        self._create_settings_tab()

        # Load strategies after all tabs are created
        self._load_strategies()
        self._load_chartink_scans()

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
        """Create Chartink scanner integration tab"""
        chartink = QWidget()
        layout = QVBoxLayout(chartink)

        # Add scan section
        add_scan_group = QGroupBox("Add Chartink Scanner")
        add_scan_layout = QFormLayout(add_scan_group)

        self.chartink_scan_name = QLineEdit()
        self.chartink_scan_name.setPlaceholderText("e.g., My Breakout Scanner")
        add_scan_layout.addRow("Scan Name:", self.chartink_scan_name)

        self.chartink_scan_url = QLineEdit()
        self.chartink_scan_url.setPlaceholderText("https://chartink.com/screener/your-scanner-name")
        add_scan_layout.addRow("Scanner URL:", self.chartink_scan_url)

        self.chartink_action = QComboBox()
        self.chartink_action.addItems(["BUY", "SELL"])
        add_scan_layout.addRow("Action:", self.chartink_action)

        self.chartink_quantity = QSpinBox()
        self.chartink_quantity.setRange(1, 10000)
        self.chartink_quantity.setValue(1)
        add_scan_layout.addRow("Quantity:", self.chartink_quantity)

        self.chartink_interval = QSpinBox()
        self.chartink_interval.setRange(30, 3600)
        self.chartink_interval.setValue(60)
        self.chartink_interval.setSuffix(" seconds")
        add_scan_layout.addRow("Scan Interval:", self.chartink_interval)

        btn_layout = QHBoxLayout()
        self.add_chartink_scan_btn = QPushButton("Add Scanner")
        self.add_chartink_scan_btn.clicked.connect(self._add_chartink_scan)
        self.test_chartink_scan_btn = QPushButton("Test Scanner")
        self.test_chartink_scan_btn.clicked.connect(self._test_chartink_scan)
        btn_layout.addWidget(self.add_chartink_scan_btn)
        btn_layout.addWidget(self.test_chartink_scan_btn)
        add_scan_layout.addRow(btn_layout)

        layout.addWidget(add_scan_group)

        # Active scans section
        scans_group = QGroupBox("Active Scanners")
        scans_layout = QVBoxLayout(scans_group)

        self.chartink_scans_table = QTableWidget()
        self.chartink_scans_table.setColumnCount(6)
        self.chartink_scans_table.setHorizontalHeaderLabels([
            "Name", "Action", "Qty", "Interval", "Stocks Found", "Actions"
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
        monitor_btn_layout.addWidget(self.start_chartink_btn)
        monitor_btn_layout.addWidget(self.stop_chartink_btn)
        scans_layout.addLayout(monitor_btn_layout)

        layout.addWidget(scans_group)

        # Alerts log section
        alerts_group = QGroupBox("Recent Alerts")
        alerts_layout = QVBoxLayout(alerts_group)

        self.chartink_alerts_table = QTableWidget()
        self.chartink_alerts_table.setColumnCount(5)
        self.chartink_alerts_table.setHorizontalHeaderLabels([
            "Time", "Scanner", "Symbol", "Price", "Action Taken"
        ])
        self.chartink_alerts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        alerts_layout.addWidget(self.chartink_alerts_table)

        layout.addWidget(alerts_group)

        self.tabs.addTab(chartink, "Chartink")

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
                    quantity=scan.get('quantity', 1)
                )
            self._refresh_chartink_scans_table()
        except Exception as e:
            logger.error(f"Error loading Chartink scans: {e}")

    def _add_chartink_scan(self):
        """Add a new Chartink scan"""
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

        # Add to scanner
        self.chartink_scanner.add_scan(
            scan_name=name,
            scan_url=url,
            interval=interval,
            action=action,
            quantity=quantity
        )

        # Save to config
        scans = self.config.get('chartink.scans', [])
        scans.append({
            'name': name,
            'url': url,
            'action': action,
            'quantity': quantity,
            'interval': interval
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
        """Refresh the Chartink scans table"""
        scans = self.chartink_scanner.get_active_scans()
        self.chartink_scans_table.setRowCount(len(scans))

        for i, scan in enumerate(scans):
            self.chartink_scans_table.setItem(i, 0, QTableWidgetItem(scan['name']))
            self.chartink_scans_table.setItem(i, 1, QTableWidgetItem(scan['action']))
            self.chartink_scans_table.setItem(i, 2, QTableWidgetItem(str(scan['quantity'])))
            self.chartink_scans_table.setItem(i, 3, QTableWidgetItem(f"{scan['interval']}s"))
            self.chartink_scans_table.setItem(i, 4, QTableWidgetItem(str(scan['stocks_count'])))

            # Add remove button
            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(lambda checked, name=scan['name']: self._remove_chartink_scan(name))
            self.chartink_scans_table.setCellWidget(i, 5, remove_btn)

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

    def _on_chartink_alert(self, alert):
        """Handle Chartink alert - execute trade"""
        from algo_trader.core.order_manager import Order, OrderType, TransactionType, Exchange

        # Log alert to table
        row = self.chartink_alerts_table.rowCount()
        self.chartink_alerts_table.insertRow(row)
        self.chartink_alerts_table.setItem(row, 0, QTableWidgetItem(alert.triggered_at.strftime("%H:%M:%S")))
        self.chartink_alerts_table.setItem(row, 1, QTableWidgetItem(alert.scan_name))
        self.chartink_alerts_table.setItem(row, 2, QTableWidgetItem(alert.symbol))
        self.chartink_alerts_table.setItem(row, 3, QTableWidgetItem(f"₹{alert.price:.2f}" if alert.price else "N/A"))

        # Get scan config for action and quantity
        scan_config = self.chartink_scanner.active_scans.get(alert.scan_name, {})
        action = scan_config.get('action', 'BUY')
        quantity = scan_config.get('quantity', 1)

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
                action_text = f"{action} order placed: {result.broker_order_id}"
                logger.info(f"Chartink auto-trade: {action_text}")
            except Exception as e:
                action_text = f"Order failed: {e}"
                logger.error(f"Chartink auto-trade error: {e}")
        else:
            action_text = "No broker connected"

        self.chartink_alerts_table.setItem(row, 4, QTableWidgetItem(action_text))

    def closeEvent(self, event):
        """Handle window close"""
        reply = QMessageBox.question(
            self, "Exit",
            "Are you sure you want to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()
