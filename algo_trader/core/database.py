"""
Database management for Algo Trader
Stores orders, trades, strategies, and backtest results
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger


class Database:
    """SQLite database for storing trading data"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(Path.home() / ".algo_trader" / "algo_trader.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Strategies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                pine_script TEXT,
                source_type TEXT DEFAULT 'pine',
                is_active INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                broker TEXT NOT NULL,
                broker_order_id TEXT,
                strategy_id INTEGER,
                symbol TEXT NOT NULL,
                exchange TEXT,
                order_type TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL,
                trigger_price REAL,
                status TEXT DEFAULT 'PENDING',
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        ''')

        # Trades table (executed orders)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                broker TEXT NOT NULL,
                symbol TEXT NOT NULL,
                exchange TEXT,
                transaction_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        ''')

        # Positions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                broker TEXT NOT NULL,
                symbol TEXT NOT NULL,
                exchange TEXT,
                quantity INTEGER NOT NULL,
                average_price REAL NOT NULL,
                current_price REAL,
                pnl REAL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(broker, symbol, exchange)
            )
        ''')

        # Backtest results table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER,
                symbol TEXT NOT NULL,
                start_date DATE,
                end_date DATE,
                initial_capital REAL,
                final_capital REAL,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                max_drawdown REAL,
                sharpe_ratio REAL,
                profit_factor REAL,
                results_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        ''')

        # Chartink alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chartink_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action_taken TEXT,
                order_id INTEGER,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

    # Strategy methods
    def save_strategy(self, name: str, pine_script: str, description: str = "", source_type: str = "pine") -> int:
        """Save a new strategy or update existing"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO strategies (name, pine_script, description, source_type, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    pine_script = excluded.pine_script,
                    description = excluded.description,
                    source_type = excluded.source_type,
                    updated_at = excluded.updated_at
            ''', (name, pine_script, description, source_type, datetime.now()))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_strategy(self, name: str) -> Optional[Dict]:
        """Get strategy by name"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM strategies WHERE name = ?', (name,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_strategies(self) -> List[Dict]:
        """Get all strategies"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM strategies ORDER BY updated_at DESC')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def delete_strategy(self, name: str):
        """Delete a strategy"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM strategies WHERE name = ?', (name,))
        conn.commit()
        conn.close()

    def set_strategy_active(self, name: str, is_active: bool):
        """Activate or deactivate a strategy"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE strategies SET is_active = ? WHERE name = ?', (int(is_active), name))
        conn.commit()
        conn.close()

    # Order methods
    def save_order(self, broker: str, symbol: str, order_type: str, transaction_type: str,
                   quantity: int, price: float = None, trigger_price: float = None,
                   exchange: str = None, strategy_id: int = None, broker_order_id: str = None) -> int:
        """Save a new order"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (broker, broker_order_id, strategy_id, symbol, exchange,
                              order_type, transaction_type, quantity, price, trigger_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (broker, broker_order_id, strategy_id, symbol, exchange,
              order_type, transaction_type, quantity, price, trigger_price))
        conn.commit()
        order_id = cursor.lastrowid
        conn.close()
        return order_id

    def update_order_status(self, order_id: int, status: str, broker_order_id: str = None, message: str = None):
        """Update order status"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE orders SET status = ?, broker_order_id = COALESCE(?, broker_order_id),
                           message = ?, updated_at = ?
            WHERE id = ?
        ''', (status, broker_order_id, message, datetime.now(), order_id))
        conn.commit()
        conn.close()

    def get_orders(self, broker: str = None, status: str = None, limit: int = 100) -> List[Dict]:
        """Get orders with optional filters"""
        conn = self._get_connection()
        cursor = conn.cursor()
        query = 'SELECT * FROM orders WHERE 1=1'
        params = []
        if broker:
            query += ' AND broker = ?'
            params.append(broker)
        if status:
            query += ' AND status = ?'
            params.append(status)
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Trade methods
    def save_trade(self, order_id: int, broker: str, symbol: str, transaction_type: str,
                   quantity: int, price: float, exchange: str = None) -> int:
        """Save an executed trade"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (order_id, broker, symbol, exchange, transaction_type, quantity, price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (order_id, broker, symbol, exchange, transaction_type, quantity, price))
        conn.commit()
        trade_id = cursor.lastrowid
        conn.close()
        return trade_id

    def get_trades(self, broker: str = None, symbol: str = None, limit: int = 100) -> List[Dict]:
        """Get trades with optional filters"""
        conn = self._get_connection()
        cursor = conn.cursor()
        query = 'SELECT * FROM trades WHERE 1=1'
        params = []
        if broker:
            query += ' AND broker = ?'
            params.append(broker)
        if symbol:
            query += ' AND symbol = ?'
            params.append(symbol)
        query += ' ORDER BY executed_at DESC LIMIT ?'
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # Backtest methods
    def save_backtest_result(self, strategy_id: int, symbol: str, start_date: str, end_date: str,
                             initial_capital: float, final_capital: float, total_trades: int,
                             winning_trades: int, losing_trades: int, max_drawdown: float,
                             sharpe_ratio: float, profit_factor: float, results_json: str) -> int:
        """Save backtest results"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO backtest_results (strategy_id, symbol, start_date, end_date,
                                         initial_capital, final_capital, total_trades,
                                         winning_trades, losing_trades, max_drawdown,
                                         sharpe_ratio, profit_factor, results_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (strategy_id, symbol, start_date, end_date, initial_capital, final_capital,
              total_trades, winning_trades, losing_trades, max_drawdown, sharpe_ratio,
              profit_factor, results_json))
        conn.commit()
        result_id = cursor.lastrowid
        conn.close()
        return result_id

    def get_backtest_results(self, strategy_id: int = None) -> List[Dict]:
        """Get backtest results"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if strategy_id:
            cursor.execute('SELECT * FROM backtest_results WHERE strategy_id = ? ORDER BY created_at DESC', (strategy_id,))
        else:
            cursor.execute('SELECT * FROM backtest_results ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
